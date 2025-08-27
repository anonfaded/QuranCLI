# core/audio_download_manager.py
import asyncio
import concurrent.futures
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import tqdm
from colorama import Fore, Style

# Cross-platform notifications
try:
    if sys.platform == "win32":
        from win10toast import ToastNotifier
        HAS_NOTIFICATIONS = True
    else:
        import notify2
        HAS_NOTIFICATIONS = True
except ImportError:
    HAS_NOTIFICATIONS = False

# utils and data handler are accessed via instance references or local imports when needed

@dataclass
class DownloadTask:
    """Represents a single audio download task"""
    surah_num: int
    reciter: str
    url: str
    filename: str
    estimated_size_mb: Optional[float]
    status: str = "pending"  # pending, downloading, completed, failed

@dataclass
class DownloadStats:
    """Tracks download statistics"""
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    total_size_mb: float = 0
    downloaded_size_mb: float = 0
    elapsed_time: float = 0

class AudioDownloadManager:
    """Manages bulk audio downloads with progress tracking and notifications"""

    def __init__(self, audio_manager, data_handler, app=None):
        self.audio_manager = audio_manager
        self.data_handler = data_handler
        self.app = app  # Reference to main app for surah names
        self.max_concurrent_downloads = 3
        self.download_stats = DownloadStats()
        self.is_downloading = False
        self.download_queue: List[DownloadTask] = []
        self.completed_tasks: List[DownloadTask] = []
        self.failed_tasks: List[DownloadTask] = []

        # Notification setup
        self._setup_notifications()

    def cancel_download(self):
        """Cancel the current download operation"""
        if self.is_downloading:
            print(f"{Fore.YELLOW}Cancelling download...{Style.RESET_ALL}")
            self.is_downloading = False

    def _setup_notifications(self):
        """Setup cross-platform notifications"""
        if not HAS_NOTIFICATIONS:
            return

        try:
            if sys.platform == "win32":
                self.notifier = ToastNotifier()
            else:
                notify2.init("QuranCLI")
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not setup notifications: {e}{Style.RESET_ALL}")

    def send_notification(self, title: str, message: str):
        """Send system notification"""
        if not HAS_NOTIFICATIONS:
            return
        # Best-effort notification. Do not print debug messages; swallow errors to avoid UI tracebacks.
        try:
            if sys.platform == "win32":
                icon_path = None
                try:
                    from utils import get_app_path
                    app_dir = Path(get_app_path())
                    potential_icons = [
                        app_dir / 'icon.ico',
                        app_dir / 'qurancli.ico',
                        app_dir / 'QuranCLI.ico',
                        app_dir / 'core' / 'img' / 'icon.ico',
                        app_dir / 'core' / 'img' / 'icon.png',
                        app_dir / 'core' / 'img' / 'qurancli.png',
                        app_dir / 'img' / 'icon.ico',
                        app_dir / 'img' / 'icon.png',
                    ]
                    for icon_file in potential_icons:
                        if icon_file.exists():
                            icon_path = str(icon_file)
                            break
                except Exception:
                    icon_path = None

                try:
                    # Avoid using threaded=True here. win10toast uses a background thread
                    # which can emit exceptions in the process event loop (seen as WPARAM/LRESULT
                    # TypeError messages). Use a blocking call to avoid that noisy output.
                    if icon_path:
                        self.notifier.show_toast(title, message, icon_path=icon_path, duration=5, threaded=False)
                    else:
                        self.notifier.show_toast(title, message, duration=5, threaded=False)
                except Exception:
                    # Silence notification errors to prevent UI tracebacks or unexpected text
                    pass
            else:
                try:
                    n = notify2.Notification(title, message)
                    n.show()
                except Exception:
                    pass
        except Exception:
            pass

    def get_available_reciters(self) -> Dict[str, str]:
        """Get available reciters from cache"""
        reciters = {}

        # Check cache for available reciters
        for surah_num in range(1, 3):  # Check first few surahs for reciter data
            cached_data = self.data_handler.cache.get_surah(surah_num)
            if cached_data and "audio" in cached_data:
                for reciter_key, reciter_data in cached_data["audio"].items():
                    if reciter_key not in reciters:
                        reciters[reciter_key] = reciter_data.get("reciter", reciter_key)

        # Always include Muhammad Al Luhaidan as fallback
        if "luhaidan" not in reciters:
            reciters["luhaidan"] = "Muhammad Al Luhaidan"

        return reciters

    def estimate_download_size(self, surah_numbers: List[int], reciter: str) -> Optional[float]:
        """Estimate total download size in MB using real file size requests.

        Returns None if any file's size cannot be reliably determined (UI should show N/A).
        Mirrors the player's URL resolution rules by reading per-surah audio entries from
        the data handler and performing HEAD (then GET) requests to determine Content-Length.
        """
        async def get_size_for_url(session: aiohttp.ClientSession, url: str) -> Optional[float]:
            try:
                # Prefer HEAD to avoid downloading full file
                async with session.head(url, timeout=15) as resp:
                    if resp.status == 200:
                        cl = resp.headers.get('Content-Length') or resp.headers.get('content-length')
                        if cl:
                            return int(cl) / (1024 * 1024)
                # HEAD didn't give us length; try GET (may be heavy but required for accuracy)
                async with session.get(url, timeout=30) as resp2:
                    if resp2.status == 200:
                        data = await resp2.read()
                        return len(data) / (1024 * 1024)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                # Network-related issues -> unknown size
                return None
            except Exception:
                # Other unexpected issues -> unknown size
                return None
            return None

        async def estimate_all():
            """Asynchronously probe each surah's candidate URLs and report a running progress bar.

            Uses a single-line tqdm progress bar so the TUI doesn't flood with new lines and the
            user sees live feedback while the network probes are happening.
            """
            sizes = []
            pbar = None
            try:
                async with aiohttp.ClientSession() as session:
                    # Create a single-line progress bar for the whole operation
                    try:
                        pbar = tqdm.tqdm(total=len(surah_numbers), desc=f"Probing sizes", ncols=80, unit="surah", leave=False)
                    except Exception:
                        pbar = None

                    for surah_num in surah_numbers:
                        surah_info = self.data_handler.get_surah_info(surah_num)
                        url_candidates = []

                        # Prefer URL from cached surah audio info if available
                        if surah_info and getattr(surah_info, 'audio', None):
                            # surah_info.audio is expected to be a dict of reciter_id -> data
                            if reciter in surah_info.audio and 'url' in surah_info.audio[reciter]:
                                url_candidates.append(surah_info.audio[reciter]['url'])

                        # Special-case: attempt known Luhaidan pattern if no cached URL
                        if not url_candidates and (reciter.lower().startswith('luhaid') or reciter == 'luhaidan'):
                            padded = str(surah_num).zfill(3)
                            url_candidates.append(f"https://download.quranicaudio.com/quran/muhammad_alhaidan/{padded}.mp3")
                            # GitHub fallback for specific surahs (player logic)
                            if surah_num in {2, 6, 25, 112}:
                                url_candidates.append(
                                    f"https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/muhammad_al_luhaidan/muhammad-al-luhaidan-{padded}.mp3"
                                )

                        # If still no candidates, try to find any reciter entry and map by display name
                        if not url_candidates and surah_info and getattr(surah_info, 'audio', None):
                            # pick first available url as best-effort source
                            for v in surah_info.audio.values():
                                if isinstance(v, dict) and 'url' in v:
                                    url_candidates.append(v['url'])
                                    break

                        # Mirror AudioManager special-case: for Muhammad Al Luhaidan certain surahs
                        # (2,6,25,112) should use the GitHub raw URL. Ensure the estimator picks the
                        # same URL the player will actually use so the wizard doesn't 404.
                        try:
                            luhaidan_names = {'muhammad al luhaidan', 'luhaidan'}
                            if (reciter.lower() in luhaidan_names or reciter.lower().startswith('luhaid')) and surah_num in {2, 6, 25, 112}:
                                padded = str(surah_num).zfill(3)
                                url_candidates = [f"https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/muhammad_al_luhaidan/muhammad-al-luhaidan-{padded}.mp3"]
                        except Exception:
                            # Best-effort: ignore errors and keep original url_candidates
                            pass

                        # No URL candidates -> mark unknown and continue
                        if not url_candidates:
                            if pbar:
                                pbar.update(1)
                            # Mark as unknown by appending None placeholder
                            sizes.append(None)
                            continue

                        # Try candidates in order
                        found_size = None
                        for u in url_candidates:
                            size_mb = await get_size_for_url(session, u)
                            if size_mb is not None:
                                found_size = size_mb
                                break

                        if found_size is None:
                            # mark unknown and continue probing remaining surahs
                            sizes.append(None)
                            if pbar:
                                pbar.update(1)
                            continue

                        sizes.append(found_size)
                        if pbar:
                            pbar.update(1)

            finally:
                if pbar:
                    try:
                        pbar.close()
                    except Exception:
                        pass

            # After probing all surahs: return sum of known sizes, or None if ALL are unknown
            known_sizes = [s for s in sizes if s is not None]
            if not known_sizes:
                return None
            return sum(known_sizes)

        try:
            # Use a fresh event loop to avoid RuntimeError when an event loop
            # may already be running in the caller's environment.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(estimate_all())
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
        except KeyboardInterrupt:
            return None
        except Exception:
            # Any unexpected errors during the async probing should result in unknown size
            return None

    def _estimate_fallback_size(self, surah_numbers: List[int]) -> float:
        """Fallback estimation when real size requests fail"""
        # Average file sizes based on surah length (rough estimation)
        size_estimates = {
            "short": 2.5,    # Surahs 1-10 (avg ~2.5MB)
            "medium": 5.0,   # Surahs 11-50 (avg ~5MB)
            "long": 8.0      # Surahs 51-114 (avg ~8MB)
        }

        total_size = 0
        for surah_num in surah_numbers:
            if surah_num <= 10:
                total_size += size_estimates["short"]
            elif surah_num <= 50:
                total_size += size_estimates["medium"]
            else:
                total_size += size_estimates["long"]

        return total_size

    def prepare_download_queue(self, surah_numbers: List[int], reciter: str) -> List[DownloadTask]:
        """Prepare download queue with all necessary information"""
        tasks = []
        reciters = self.get_available_reciters()

        if reciter not in reciters:
            print(f"{Fore.RED}Error: Reciter '{reciter}' not found{Style.RESET_ALL}")
            return []

    # asyncio already imported at module level

        async def resolve_task(surah_num: int) -> Optional[DownloadTask]:
            surah_info = self.data_handler.get_surah_info(surah_num)
            url_candidates = []

            if surah_info and getattr(surah_info, 'audio', None):
                if reciter in surah_info.audio and 'url' in surah_info.audio[reciter]:
                    audio_data = surah_info.audio[reciter]
                    url_candidates.append((audio_data['url'], audio_data.get('reciter', reciter)))

            # Luhaidan pattern fallback
            if not url_candidates and (reciter.lower().startswith('luhaid') or reciter == 'luhaidan'):
                padded = str(surah_num).zfill(3)
                url_candidates.append((f"https://download.quranicaudio.com/quran/muhammad_alhaidan/{padded}.mp3", 'Muhammad Al Luhaidan'))
                if surah_num in {2, 6, 25, 112}:
                    url_candidates.append((
                        f"https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/muhammad_al_luhaidan/muhammad-al-luhaidan-{padded}.mp3",
                        'Muhammad Al Luhaidan'
                    ))

            # If still none, try first available audio entry
            if not url_candidates and surah_info and getattr(surah_info, 'audio', None):
                for k, v in surah_info.audio.items():
                    if isinstance(v, dict) and 'url' in v:
                        url_candidates.append((v['url'], v.get('reciter', k)))
                        break
                if not url_candidates and surah_info and getattr(surah_info, 'audio', None):
                    for v in surah_info.audio.values():
                        if isinstance(v, dict) and 'url' in v:
                            url_candidates.append((v['url'], v.get('reciter', None)))
                            break

            if not url_candidates:
                print(f"{Fore.YELLOW}Warning: No audio data for Surah {surah_num}, reciter {reciter}{Style.RESET_ALL}")
                return None

            # Choose the first candidate URL as the intended download source (player uses the
            # first available audio entry). Probe for Content-Length as a best-effort but
            # do not reject the URL if probing fails — the downstream downloader has its
            # own fallback and retry logic.
            chosen_url, chosen_reciter_name = url_candidates[0]
            # Mirror AudioManager special-case: for Muhammad Al Luhaidan certain surahs
            # (2,6,25,112) should use the GitHub raw URL. Ensure the resolver picks the
            # same URL the player will actually use so the wizard doesn't 404.
            try:
                luhaidan_names = {'muhammad al luhaidan', 'luhaidan'}
                if (chosen_reciter_name and chosen_reciter_name.lower() in luhaidan_names) or reciter.lower().startswith('luhaid'):
                    special = {2, 6, 25, 112}
                    if surah_num in special:
                        padded = str(surah_num).zfill(3)
                        chosen_url = f"https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/muhammad_al_luhaidan/muhammad-al-luhaidan-{padded}.mp3"
            except Exception:
                # Best-effort: ignore errors and keep original chosen_url
                pass
            size_mb = None
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': '*/*',
                        'Accept-Encoding': 'identity',
                        'Connection': 'keep-alive',
                        'Referer': chosen_url
                    }
                    if 'download.quranicaudio.com' in chosen_url:
                        headers['Host'] = 'download.quranicaudio.com'
                    if 'raw.githubusercontent.com' in chosen_url:
                        headers['Host'] = 'raw.githubusercontent.com'

                    # Try HEAD then GET for size; ignore network failures and proceed with unknown size
                    try:
                        async with session.head(chosen_url, timeout=12, headers=headers) as resp_head:
                            if resp_head.status in (200, 206):
                                cl = resp_head.headers.get('Content-Length') or resp_head.headers.get('content-length')
                                if cl:
                                    size_mb = int(cl) / (1024 * 1024)
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        try:
                            async with session.get(chosen_url, timeout=20, headers=headers) as resp_get:
                                if resp_get.status in (200, 206):
                                    cl2 = resp_get.headers.get('Content-Length') or resp_get.headers.get('content-length')
                                    if cl2:
                                        size_mb = int(cl2) / (1024 * 1024)
                        except (aiohttp.ClientError, asyncio.TimeoutError):
                            # give up on probing size for this URL
                            pass
            except (aiohttp.ClientError, asyncio.TimeoutError):
                size_mb = None
            except Exception:
                size_mb = None
            filename_path = self.audio_manager.get_audio_path(surah_num, chosen_reciter_name or reciter)
            if not filename_path:
                return None

            return DownloadTask(
                surah_num=surah_num,
                reciter=chosen_reciter_name or reciter,
                url=chosen_url,
                filename=str(filename_path),
                estimated_size_mb=size_mb
            )

        async def build_all():
            coros = [resolve_task(n) for n in surah_numbers]
            results = await asyncio.gather(*coros)
            return [r for r in results if r]

        try:
            tasks = asyncio.run(build_all())
        except Exception:
            tasks = []

        return tasks

    async def download_single_file(self, task: DownloadTask, progress_callback=None) -> bool:
        """Download a single audio file"""
        try:
            # Check if download was cancelled before starting
            if not self.is_downloading:
                task.status = "cancelled"
                return False

            task.status = "downloading"

            # Try primary URL first (if present)
            attempts = []
            if task.url:
                attempts.append((task.url, task.reciter))

            # If reciter looks like Luhaidan key, add canonical quranicaudio + github fallback
            if task.reciter and ('luhaid' in task.reciter.lower() or task.reciter.lower() == 'luhaidan'):
                padded = str(task.surah_num).zfill(3)
                qurl = f"https://download.quranicaudio.com/quran/muhammad_alhaidan/{padded}.mp3"
                gh_url = f"https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/muhammad_al_luhaidan/muhammad-al-luhaidan-{padded}.mp3"
                attempts.append((qurl, 'Muhammad Al Luhaidan'))
                attempts.append((gh_url, 'Muhammad Al Luhaidan'))

            # As a last resort, try to use any cached audio entry for this surah
            if not attempts:
                surah_info = self.data_handler.get_surah_info(task.surah_num)
                if surah_info and getattr(surah_info, 'audio', None):
                    for k, v in surah_info.audio.items():
                        if isinstance(v, dict) and 'url' in v:
                            attempts.append((v['url'], v.get('reciter', k)))
                            break

            file_path = None
            for url, reciter_name in attempts:
                # Quick reachability check before invoking the heavier downloader
                try:
                    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*', 'Accept-Encoding': 'identity', 'Connection': 'keep-alive', 'Referer': url}
                    if 'download.quranicaudio.com' in url:
                        headers['Host'] = 'download.quranicaudio.com'
                    if 'raw.githubusercontent.com' in url:
                        headers['Host'] = 'raw.githubusercontent.com'
                    async with aiohttp.ClientSession() as session:
                        try:
                            async with session.head(url, timeout=10, headers=headers) as resp:
                                status = resp.status
                                if status not in (200, 206):
                                    # try GET as a fallback
                                    async with session.get(url, timeout=20, headers=headers) as resp2:
                                        if resp2.status not in (200, 206):
                                            print(f"{Fore.YELLOW}Skipping unreachable URL {url} (status {resp2.status}){Style.RESET_ALL}")
                                            continue
                        except Exception:
                            # HEAD failed, try GET
                            async with session.get(url, timeout=20, headers=headers) as resp3:
                                if resp3.status not in (200, 206):
                                    print(f"{Fore.YELLOW}Skipping unreachable URL {url} (status {resp3.status}){Style.RESET_ALL}")
                                    continue
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    print(f"{Fore.YELLOW}URL check failed for {url}: {e}{Style.RESET_ALL}")
                    continue

                try:
                    file_path = await self.audio_manager.download_audio(
                        url=url,
                        surah_num=task.surah_num,
                        reciter=reciter_name,
                        max_retries=3
                    )
                except Exception as e:
                    print(f"{Fore.YELLOW}Download attempt error for {url}: {e}{Style.RESET_ALL}")
                    file_path = None

                if file_path and file_path.exists():
                    task.status = 'completed'
                    task.url = url
                    task.reciter = reciter_name
                    if progress_callback:
                        progress_callback(task)
                    return True

            task.status = 'failed'
            return False

        except Exception as e:
            print(f"{Fore.RED}Error downloading Surah {task.surah_num}: {e}{Style.RESET_ALL}")
            task.status = "failed"
            return False

    def download_progress_callback(self, task: DownloadTask):
        """Handle progress updates"""
        self.download_stats.completed_files += 1
        # Some tasks may have unknown estimated sizes (None). Only add if available.
        if task.estimated_size_mb is not None:
            self.download_stats.downloaded_size_mb += task.estimated_size_mb

    def start_bulk_download(self, tasks: List[DownloadTask]) -> bool:
        """Start bulk download with progress tracking"""
        if not tasks:
            print(f"{Fore.YELLOW}No files to download{Style.RESET_ALL}")
            return False

        self.download_queue = tasks
        # Sum only known sizes; if any is None, total_size_mb will be 0 and UI will show N/A later
        known_sizes = [s.estimated_size_mb for s in tasks if s.estimated_size_mb is not None]
        total_size = sum(known_sizes) if known_sizes else 0.0
        self.download_stats = DownloadStats(
            total_files=len(tasks),
            total_size_mb=total_size
        )

        print(f"{Fore.CYAN}Starting download of {len(tasks)} audio files...")
        if self.download_stats.total_size_mb > 0:
            print(f"{Fore.CYAN}Estimated total size: {self.download_stats.total_size_mb:.1f} MB{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}Estimated total size: {Fore.YELLOW}N/A{Style.RESET_ALL}")
        print()

        start_time = time.time()
        self.is_downloading = True

        try:
            # Use ThreadPoolExecutor for concurrent downloads
            with ThreadPoolExecutor(max_workers=self.max_concurrent_downloads) as executor:
                # Create progress bar
                with tqdm.tqdm(total=len(tasks), desc=f"{Fore.RED}Downloading",
                              unit="files", colour='red', ncols=80,
                              disable=False) as pbar:

                    # Submit all download tasks
                    future_to_task = {
                        executor.submit(self._download_task_wrapper, task): task
                        for task in tasks
                    }

                    # Process completed tasks
                    try:
                        for future in concurrent.futures.as_completed(future_to_task):
                            # Check if user wants to cancel
                            if not self.is_downloading:
                                print(f"\n{Fore.YELLOW}Download cancelled.{Style.RESET_ALL}")
                                # Cancel all pending futures
                                for f in future_to_task:
                                    if not f.done():
                                        f.cancel()
                                pbar.close()
                                return False

                            task = future_to_task[future]
                            try:
                                success = future.result()
                                if success:
                                    self.completed_tasks.append(task)
                                else:
                                    self.failed_tasks.append(task)
                            except Exception as e:
                                print(f"{Fore.RED}Download task failed: {e}{Style.RESET_ALL}")
                                self.failed_tasks.append(task)

                            pbar.update(1)
                    except KeyboardInterrupt:
                        print(f"\n{Fore.YELLOW}Download interrupted by user. Cancelling remaining tasks...{Style.RESET_ALL}")
                        # Cancel all pending futures
                        for future in future_to_task:
                            if not future.done():
                                future.cancel()
                        pbar.close()
                        return False

            # Calculate final statistics
            self.download_stats.elapsed_time = time.time() - start_time

            # Send completion notification
            self._show_download_results()

            return len(self.failed_tasks) == 0

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Download interrupted by user{Style.RESET_ALL}")
            return False
        finally:
            self.is_downloading = False

    def _download_task_wrapper(self, task: DownloadTask) -> bool:
        """Wrapper to run async download in thread"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.download_single_file(task, self.download_progress_callback))
        except Exception as e:
            print(f"{Fore.RED}Error in download task: {e}{Style.RESET_ALL}")
            return False
        finally:
            loop.close()

    def _show_download_results(self):
        """Display download results and send notification"""
        success_count = len(self.completed_tasks)
        fail_count = len(self.failed_tasks)

        print(f"\n{Fore.GREEN}╭─ {Fore.CYAN}Download Complete!")
        print(f"{Fore.GREEN}├─ {Fore.WHITE}✓ Completed: {Fore.CYAN}{success_count} files")
        if fail_count > 0:
            print(f"{Fore.GREEN}├─ {Fore.RED}✗ Failed: {Fore.CYAN}{fail_count} files")
        print(f"{Fore.GREEN}├─ {Fore.CYAN}⏱️  Time: {Fore.WHITE}{self.download_stats.elapsed_time:.1f}s")
        print(f"{Fore.GREEN}├─ {Fore.CYAN}📦 Size: {Fore.WHITE}{self.download_stats.downloaded_size_mb:.1f} MB")
        print(f"{Fore.GREEN}╰" + "─" * 40)

        # Send notification
        if success_count > 0:
            title = "QuranCLI Download Complete"
            message = f"Downloaded {success_count} audio files ({self.download_stats.downloaded_size_mb:.1f} MB)"
            if fail_count > 0:
                message += f" | {fail_count} failed"
            self.send_notification(title, message)

        if self.failed_tasks:
            print(f"\n{Fore.YELLOW}Failed downloads:")
            for task in self.failed_tasks[:5]:  # Show first 5 failed
                print(f"  - Surah {task.surah_num} ({task.reciter})")
            if len(self.failed_tasks) > 5:
                print(f"  ... and {len(self.failed_tasks) - 5} more")

        # Offer a simple retry for failed tasks (one attempt)
        if self.failed_tasks:
            try:
                retry = input(f"\n{Fore.CYAN}Retry failed downloads? (y/N): {Fore.WHITE}").strip().lower()
                if retry == 'y':
                    to_retry = [t for t in self.failed_tasks]
                    self.failed_tasks = []
                    self.download_queue = to_retry
                    # reset stats for this retry
                    for t in to_retry:
                        t.status = 'pending'
                    # Run retry and return immediately to avoid duplicate reporting
                    self.start_bulk_download(to_retry)
                    return
            except KeyboardInterrupt:
                pass

    def get_disk_space_info(self) -> Tuple[float, float]:
        """Get available disk space in MB (total, available)"""
        try:
            if self.audio_manager.audio_dir:
                path = Path(self.audio_manager.audio_dir)
                # Use shutil.disk_usage for cross-platform support
                total_bytes, used_bytes, free_bytes = shutil.disk_usage(str(path))
                total_mb = total_bytes / (1024 * 1024)
                available_mb = free_bytes / (1024 * 1024)

                return total_mb, available_mb
            else:
                return 0, 0
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not check disk space: {e}{Style.RESET_ALL}")
            return 0, 0

    def run_download_wizard(self) -> Optional[bool]:
        """Run the complete download wizard"""
        try:
            # Step 1: Select reciter
            reciter = self._select_reciter()
            # If user chose to go back from reciter selection, return None to indicate
            # a user-initiated cancellation/back action (distinct from an error).
            if reciter is None:
                return None

            # Step 2: Select surahs
            surah_numbers = self._select_surahs()
            if surah_numbers is None:
                return None

            # Step 3: Confirm and download
            return self._confirm_and_download(reciter, surah_numbers)

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Download cancelled by user.{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}Error in download wizard: {e}{Style.RESET_ALL}")
            return False

    def _select_reciter(self) -> Optional[str]:
        """Step 1: Let user select a reciter"""
        reciters = self.get_available_reciters()

        if not reciters:
            print(f"{Fore.RED}No reciters available. Please check your internet connection.{Style.RESET_ALL}")
            return None

        while True:
            print(f"\n{Fore.CYAN}Step 1: Select Reciter{Style.RESET_ALL}")
            print(f"{Fore.RED}╭─ {Fore.GREEN}Available Reciters:")

            for i, (_, reciter_name) in enumerate(reciters.items(), 1):
                print(f"{Fore.RED}├─ {Fore.CYAN}{i}{Fore.WHITE} : {reciter_name}")

            print(f"{Fore.RED}├─ {Fore.CYAN}back{Fore.WHITE} : Return to previous menu")
            print(f"{Fore.RED}╰" + "─" * 40)

            # Helper text
            print(Style.DIM + Fore.WHITE + "\nEnter the number of the reciter you want to download from.")
            print(" ")

            try:
                choice = input(f"{Fore.RED}  ❯ {Fore.WHITE}").strip().lower()

                if choice == 'back':
                    return None

                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(reciters):
                        selected_reciter = list(reciters.keys())[index]
                        print(f"{Fore.GREEN}Selected: {reciters[selected_reciter]}{Style.RESET_ALL}")
                        return selected_reciter

                print(f"{Fore.YELLOW}Invalid choice. Please try again.{Style.RESET_ALL}")

            except KeyboardInterrupt:
                return None

    def _select_surahs(self) -> Optional[List[int]]:
        """Step 2: Let user select surahs to download"""
        while True:
            print(f"\n{Fore.CYAN}Step 2: Select Surahs{Style.RESET_ALL}")
            print(f"{Fore.RED}╭─ {Fore.GREEN}Download Options:")
            # Provide short aliases using the project's slash-style (cmd/alias)
            print(f"{Fore.RED}├─ {Fore.CYAN}all{Style.DIM}/a{Style.RESET_ALL}{Fore.WHITE}     : Download all 114 surahs")
            print(f"{Fore.RED}├─ {Fore.CYAN}specific{Style.DIM}/s{Style.RESET_ALL}{Fore.WHITE} : Download specific surahs (e.g., 1,2,3)")
            print(f"{Fore.RED}├─ {Fore.CYAN}list{Style.DIM}/l{Style.RESET_ALL}{Fore.WHITE}    : Show surah list")
            print(f"{Fore.RED}├─ {Fore.CYAN}back{Style.DIM}/b{Style.RESET_ALL}{Fore.WHITE}    : Return to previous menu")
            print(f"{Fore.RED}╰" + "─" * 40)

            # Helper text
            print(Style.DIM + Fore.WHITE + "\nChoose how you want to select surahs to download.")
            print(" ")

            try:
                choice = input(f"{Fore.RED}  ❯ {Fore.WHITE}").strip().lower()

                if choice in ('back', 'b'):
                    return None
                elif choice in ('all', 'a'):
                    return list(range(1, 115))
                elif choice in ('specific', 's'):
                    return self._get_specific_surahs()
                elif choice in ('list', 'l'):
                    if self.app:
                        self.app._display_surah_list()
                    else:
                        print(f"{Fore.YELLOW}Surah list not available.{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}Invalid choice. Please try again.{Style.RESET_ALL}")

            except KeyboardInterrupt:
                return None

    def _get_specific_surahs(self) -> Optional[List[int]]:
        """Get specific surahs from user"""
        # Helper text
        print(Style.DIM + Fore.WHITE + "\nEnter the specific surah numbers you want to download.")
        print(Style.DIM + Fore.WHITE + "Format: comma-separated numbers (e.g., 1,2,3 or 1, 5, 10)")
        print(" ")

        try:
            surahs_input = input(f"{Fore.RED}  ❯ {Fore.WHITE}").strip()

            # Handle both comma-separated and space-separated input
            surahs = []
            for part in surahs_input.replace(' ', '').split(','):
                if part:
                    surah_num = int(part)
                    if 1 <= surah_num <= 114:
                        surahs.append(surah_num)
                    else:
                        print(f"{Fore.YELLOW}Invalid surah number: {surah_num}{Style.RESET_ALL}")
                        return None

            if not surahs:
                print(f"{Fore.YELLOW}No valid surahs entered.{Style.RESET_ALL}")
                return None

            return sorted(set(surahs))  # Remove duplicates and sort

        except ValueError:
            print(f"{Fore.YELLOW}Invalid input. Please enter numbers only.{Style.RESET_ALL}")
            return None

    def _get_surah_names_display(self, surah_numbers: List[int]) -> str:
        """Get a display string of surah names for the given numbers"""
        if not self.app or not hasattr(self.app, 'surah_names'):
            return ', '.join(map(str, surah_numbers))

        names = []
        for num in surah_numbers:
            name = self.app.surah_names.get(num, f"Surah {num}")
            names.append(f"{num}. {name}")

        return ' | '.join(names)

    def _check_existing_downloads(self, surah_numbers: List[int], reciter: str) -> Tuple[List[int], List[int]]:
        """Check which surahs are already downloaded and which need to be downloaded"""
        existing_surahs = []
        missing_surahs = []

        # Get the actual reciter name from cache data (same way as prepare_download_queue)
        reciters = self.get_available_reciters()
        if reciter not in reciters:
            return existing_surahs, surah_numbers  # All are missing if reciter not found

        # Get the actual reciter name for file path generation
        reciter_name = reciters[reciter]

        for surah_num in surah_numbers:
            file_path = self.audio_manager.get_audio_path(surah_num, reciter_name)
            if file_path and file_path.exists():
                existing_surahs.append(surah_num)
            else:
                missing_surahs.append(surah_num)

        return existing_surahs, missing_surahs

    def _confirm_and_download(self, reciter: str, surah_numbers: List[int]) -> bool:
        """Step 3: Confirm download and start"""
        # Check which surahs are already downloaded
        existing_surahs, missing_surahs = self._check_existing_downloads(surah_numbers, reciter)

        # Calculate estimated size only for missing surahs
        if missing_surahs:
            # Let the user know we are probing remote files for accurate sizes
            try:
                # Minimal single-line message; tqdm will render its own in-place progress
                print(f"{Fore.CYAN}Probing remote files for {len(missing_surahs)} surah(s)...{Style.RESET_ALL}")
            except Exception:
                pass
            estimated_size = self.estimate_download_size(missing_surahs, reciter)
        else:
            estimated_size = 0

        total_files = len(surah_numbers)
        new_files = len(missing_surahs)
        existing_files = len(existing_surahs)

        # Check disk space
        _, available_space = self.get_disk_space_info()

        print(f"\n{Fore.CYAN}Step 3: Confirm Download{Style.RESET_ALL}")
        print(f"{Fore.RED}╭─ {Fore.GREEN}Download Summary:")
        print(f"{Fore.RED}├─ {Fore.WHITE}Reciter: {Fore.CYAN}{reciter}")
        print(f"{Fore.RED}├─ {Fore.WHITE}Total surahs: {Fore.CYAN}{total_files} surah(s)")

        if existing_files > 0:
            print(f"{Fore.RED}├─ {Fore.GREEN}✓ Already downloaded: {Fore.CYAN}{existing_files} surah(s)")
            if existing_files <= 3:
                existing_display = self._get_surah_names_display(existing_surahs)
                print(f"{Fore.RED}├─ {Fore.WHITE}  Existing: {Fore.GREEN}{existing_display}")

        if new_files > 0:
            print(f"{Fore.RED}├─ {Fore.YELLOW}⬇ To download: {Fore.CYAN}{new_files} surah(s)")
            if new_files <= 3:
                missing_display = self._get_surah_names_display(missing_surahs)
                print(f"{Fore.RED}├─ {Fore.WHITE}  New: {Fore.YELLOW}{missing_display}")
            elif new_files <= 10:
                print(f"{Fore.RED}├─ {Fore.WHITE}  New surahs: {Fore.YELLOW}{', '.join(map(str, missing_surahs))}")
            else:
                print(f"{Fore.RED}├─ {Fore.WHITE}  New range: {Fore.YELLOW}{missing_surahs[0]}-{missing_surahs[-1]}")

            if estimated_size is None:
                print(f"{Fore.RED}├─ {Fore.WHITE}Estimated size: {Fore.YELLOW}N/A")
            else:
                print(f"{Fore.RED}├─ {Fore.WHITE}Estimated size: {Fore.CYAN}{estimated_size:.1f} MB")

                if available_space > 0:
                    if available_space < estimated_size:
                        print(f"{Fore.RED}├─ {Fore.YELLOW}⚠️  Warning: Only {available_space:.1f} MB available!")
                    else:
                        print(f"{Fore.RED}├─ {Fore.GREEN}✓ Disk space: {available_space:.1f} MB available")
        else:
            print(f"{Fore.RED}├─ {Fore.GREEN}✓ All surahs already downloaded!")

        if new_files > 0:
            print(f"{Fore.RED}├─ {Fore.CYAN}y{Fore.WHITE} : Start download ({new_files} files)")
        print(f"{Fore.RED}├─ {Fore.CYAN}n{Fore.WHITE} : Cancel")
        print(f"{Fore.RED}╰" + "─" * 40)

        # Helper text
        if new_files > 0:
            print(Style.DIM + Fore.WHITE + "\nConfirm if you want to start the download.")
        else:
            print(Style.DIM + Fore.WHITE + "\nAll selected surahs are already downloaded.")
        print(" ")

        try:
            confirm = input(f"{Fore.RED}  ❯ {Fore.WHITE}").strip().lower()

            if confirm == 'y' and new_files > 0:
                # Prepare download queue only for missing surahs
                tasks = self.prepare_download_queue(missing_surahs, reciter)
                if tasks:
                    return self.start_bulk_download(tasks)
                else:
                    print(f"{Fore.YELLOW}No valid files to download.{Style.RESET_ALL}")
                    return False
            elif confirm == 'y' and new_files == 0:
                print(f"{Fore.GREEN}All surahs already downloaded. Nothing to do.{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.YELLOW}Download cancelled.{Style.RESET_ALL}")
                return False

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Download cancelled.{Style.RESET_ALL}")
            return False
