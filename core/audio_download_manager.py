# core/audio_download_manager.py
import asyncio
import concurrent.futures
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import aiofiles
from mutagen.mp3 import MP3
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

# --- Use relative import for utils ---
try:
    from .utils import get_app_path
except ImportError:
    from utils import get_app_path

# --- Use relative import for quran_data_handler ---
try:
    from .quran_data_handler import QuranDataHandler
except ImportError:
    from quran_data_handler import QuranDataHandler

@dataclass
class DownloadTask:
    """Represents a single audio download task"""
    surah_num: int
    reciter: str
    url: str
    filename: str
    estimated_size_mb: float
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

        try:
            if sys.platform == "win32":
                self.notifier.show_toast(title, message, duration=5)
            else:
                n = notify2.Notification(title, message)
                n.show()
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not send notification: {e}{Style.RESET_ALL}")

    def get_available_reciters(self) -> Dict[str, str]:
        """Get available reciters from cache"""
        reciters = {}

        # Check cache for available reciters
        for surah_num in range(1, 3):  # Check first few surahs for reciter data
            cached_data = self.data_handler.cache.get_surah(surah_num)
            if cached_data and "audio" in cached_data:
                for reciter_id, reciter_data in cached_data["audio"].items():
                    if reciter_id not in reciters:
                        reciters[reciter_id] = reciter_data.get("reciter", reciter_id)

        # Always include Muhammad Al Luhaidan as fallback
        if "luhaidan" not in reciters:
            reciters["luhaidan"] = "Muhammad Al Luhaidan"

        return reciters

    def estimate_download_size(self, surah_numbers: List[int], reciter: str) -> float:
        """Estimate total download size in MB using real file size requests"""
        async def get_file_size(session, url):
            try:
                async with session.head(url) as response:
                    if response.status == 200:
                        content_length = response.headers.get('Content-Length')
                        if content_length:
                            return int(content_length) / (1024 * 1024)  # Convert to MB
                # Fallback to GET request if HEAD doesn't work
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        return len(content) / (1024 * 1024)  # Convert to MB
            except Exception:
                pass
            return 0.0

        async def estimate_sizes():
            total_size = 0.0
            reciters = self.get_available_reciters()

            if reciter not in reciters:
                return self._estimate_fallback_size(surah_numbers)

            base_url = f"https://server8.mp3quran.net/{reciter}/"

            # Sample a few representative surahs to estimate average size
            sample_surahs = []
            if len(surah_numbers) <= 10:
                # For small selections, get exact sizes
                sample_surahs = surah_numbers
            else:
                # For large selections, sample a few representative surahs
                sample_surahs = [1, 2, 50, 100, 114][:min(5, len(surah_numbers))]

            async with aiohttp.ClientSession() as session:
                tasks = []
                for surah_num in sample_surahs:
                    surah_str = f"{surah_num:03d}.mp3"
                    url = base_url + surah_str
                    tasks.append(get_file_size(session, url))

                # Execute requests concurrently
                sizes = await asyncio.gather(*tasks, return_exceptions=True)

                valid_sizes = []
                for size in sizes:
                    if isinstance(size, float) and size > 0:
                        valid_sizes.append(size)

                if valid_sizes:
                    # Calculate average size from samples
                    avg_size = sum(valid_sizes) / len(valid_sizes)
                    total_size = avg_size * len(surah_numbers)

                    # Add 10% overhead for network/protocol overhead
                    total_size *= 1.1
                    return total_size
                else:
                    # If no valid sizes, use fallback
                    return self._estimate_fallback_size(surah_numbers)

        try:
            return asyncio.run(estimate_sizes())
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not get real file sizes: {e}{Style.RESET_ALL}")
            # Fallback to old estimation method
            return self._estimate_fallback_size(surah_numbers)

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

        for surah_num in surah_numbers:
            # Get surah info to build URL
            surah_info = self.data_handler.get_surah_info(surah_num)
            if not surah_info or not surah_info.audio or reciter not in surah_info.audio:
                print(f"{Fore.YELLOW}Warning: No audio data for Surah {surah_num}, reciter {reciter}{Style.RESET_ALL}")
                continue

            audio_data = surah_info.audio[reciter]
            url = audio_data["url"]
            reciter_name = audio_data["reciter"]

            # Get filename
            filename_path = self.audio_manager.get_audio_path(surah_num, reciter_name)
            if not filename_path:
                continue

            # Estimate size
            estimated_size = 2.5 if surah_num <= 10 else (5.0 if surah_num <= 50 else 8.0)

            task = DownloadTask(
                surah_num=surah_num,
                reciter=reciter_name,
                url=url,
                filename=str(filename_path),
                estimated_size_mb=estimated_size
            )
            tasks.append(task)

        return tasks

    async def download_single_file(self, task: DownloadTask, progress_callback=None) -> bool:
        """Download a single audio file"""
        try:
            task.status = "downloading"

            # Use existing download_audio method but with custom progress handling
            file_path = await self.audio_manager.download_audio(
                url=task.url,
                surah_num=task.surah_num,
                reciter=task.reciter,
                max_retries=3
            )

            if file_path and file_path.exists():
                task.status = "completed"
                if progress_callback:
                    progress_callback(task)
                return True
            else:
                task.status = "failed"
                return False

        except Exception as e:
            print(f"{Fore.RED}Error downloading Surah {task.surah_num}: {e}{Style.RESET_ALL}")
            task.status = "failed"
            return False

    def download_progress_callback(self, task: DownloadTask):
        """Handle progress updates"""
        self.download_stats.completed_files += 1
        self.download_stats.downloaded_size_mb += task.estimated_size_mb

    def start_bulk_download(self, tasks: List[DownloadTask]) -> bool:
        """Start bulk download with progress tracking"""
        if not tasks:
            print(f"{Fore.YELLOW}No files to download{Style.RESET_ALL}")
            return False

        self.download_queue = tasks
        self.download_stats = DownloadStats(
            total_files=len(tasks),
            total_size_mb=sum(task.estimated_size_mb for task in tasks)
        )

        print(f"{Fore.CYAN}Starting download of {len(tasks)} audio files...")
        print(f"{Fore.CYAN}Estimated total size: {self.download_stats.total_size_mb:.1f} MB{Style.RESET_ALL}")
        print()

        start_time = time.time()
        self.is_downloading = True

        try:
            # Use ThreadPoolExecutor for concurrent downloads
            with ThreadPoolExecutor(max_workers=self.max_concurrent_downloads) as executor:
                # Create progress bar
                with tqdm.tqdm(total=len(tasks), desc=f"{Fore.RED}Downloading",
                              unit="files", colour='red', ncols=80) as pbar:

                    # Submit all download tasks
                    future_to_task = {
                        executor.submit(self._download_task_wrapper, task): task
                        for task in tasks
                    }

                    # Process completed tasks
                    for future in concurrent.futures.as_completed(future_to_task):
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

        print(f"\n{Fore.GREEN}┌{'─'*50}┐")
        print(f"│{'Download Complete!':^50}│")
        print(f"└{'─'*50}┘{Style.RESET_ALL}")

        print(f"{Fore.GREEN}│ ✓ Completed: {success_count} files{'':<25}│")
        if fail_count > 0:
            print(f"{Fore.RED}│ ✗ Failed: {fail_count} files{'':<27}│")
        print(f"{Fore.CYAN}│ ⏱️  Time: {self.download_stats.elapsed_time:.1f}s{'':<28}│")
        print(f"{Fore.CYAN}│ 📦 Size: {self.download_stats.downloaded_size_mb:.1f} MB{'':<24}│{Style.RESET_ALL}")

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

    def get_disk_space_info(self) -> Tuple[float, float]:
        """Get available disk space in MB (total, available)"""
        try:
            if self.audio_manager.audio_dir:
                path = Path(self.audio_manager.audio_dir)

                if sys.platform == "win32":
                    # Windows: use shutil.disk_usage
                    total_bytes, used_bytes, free_bytes = shutil.disk_usage(path)
                    total_mb = total_bytes / (1024 * 1024)
                    available_mb = free_bytes / (1024 * 1024)
                else:
                    # Unix/Linux: use os.statvfs
                    stat = os.statvfs(str(path))
                    total_bytes = stat.f_blocks * stat.f_frsize
                    available_bytes = stat.f_bavail * stat.f_frsize
                    total_mb = total_bytes / (1024 * 1024)
                    available_mb = available_bytes / (1024 * 1024)

                return total_mb, available_mb
            else:
                return 0, 0
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not check disk space: {e}{Style.RESET_ALL}")
            return 0, 0

    def run_download_wizard(self) -> bool:
        """Run the complete download wizard"""
        try:
            # Step 1: Select reciter
            reciter = self._select_reciter()
            if not reciter:
                return False

            # Step 2: Select surahs
            surah_numbers = self._select_surahs()
            if not surah_numbers:
                return False

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

            for i, (reciter_id, reciter_name) in enumerate(reciters.items(), 1):
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
            print(f"{Fore.RED}├─ {Fore.CYAN}all{Fore.WHITE} : Download all 114 surahs")
            print(f"{Fore.RED}├─ {Fore.CYAN}specific{Fore.WHITE} : Download specific surahs (e.g., 1,2,3)")
            print(f"{Fore.RED}├─ {Fore.CYAN}list{Fore.WHITE} : Show surah list")
            print(f"{Fore.RED}├─ {Fore.CYAN}back{Fore.WHITE} : Return to previous menu")
            print(f"{Fore.RED}╰" + "─" * 40)

            # Helper text
            print(Style.DIM + Fore.WHITE + "\nChoose how you want to select surahs to download.")
            print(" ")

            try:
                choice = input(f"{Fore.RED}  ❯ {Fore.WHITE}").strip().lower()

                if choice == 'back':
                    return None
                elif choice == 'all':
                    return list(range(1, 115))
                elif choice == 'specific':
                    return self._get_specific_surahs()
                elif choice == 'list':
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

    def _confirm_and_download(self, reciter: str, surah_numbers: List[int]) -> bool:
        """Step 3: Confirm download and start"""
        # Calculate estimated size
        estimated_size = self.estimate_download_size(surah_numbers, reciter)
        total_files = len(surah_numbers)

        # Check disk space
        total_space, available_space = self.get_disk_space_info()

        print(f"\n{Fore.CYAN}Step 3: Confirm Download{Style.RESET_ALL}")
        print(f"{Fore.RED}╭─ {Fore.GREEN}Download Summary:")
        print(f"{Fore.RED}├─ {Fore.WHITE}Reciter: {Fore.CYAN}{reciter}")
        print(f"{Fore.RED}├─ {Fore.WHITE}Surahs: {Fore.CYAN}{total_files} surah(s)")

        if len(surah_numbers) <= 5:
            surah_display = self._get_surah_names_display(surah_numbers)
            print(f"{Fore.RED}├─ {Fore.WHITE}Surah details: {Fore.CYAN}{surah_display}")
        else:
            print(f"{Fore.RED}├─ {Fore.WHITE}Surah range: {Fore.CYAN}{surah_numbers[0]}-{surah_numbers[-1]}")

        print(f"{Fore.RED}├─ {Fore.WHITE}Estimated size: {Fore.CYAN}{estimated_size:.1f} MB")

        if available_space > 0:
            if available_space < estimated_size:
                print(f"{Fore.RED}├─ {Fore.YELLOW}⚠️  Warning: Only {available_space:.1f} MB available!")
            else:
                print(f"{Fore.RED}├─ {Fore.GREEN}✓ Disk space: {available_space:.1f} MB available")

        print(f"{Fore.RED}├─ {Fore.CYAN}y{Fore.WHITE} : Start download")
        print(f"{Fore.RED}├─ {Fore.CYAN}n{Fore.WHITE} : Cancel")
        print(f"{Fore.RED}╰" + "─" * 40)

        # Helper text
        print(Style.DIM + Fore.WHITE + "\nConfirm if you want to start the download.")
        print(" ")

        try:
            confirm = input(f"{Fore.RED}  ❯ {Fore.WHITE}").strip().lower()

            if confirm == 'y':
                # Prepare download queue
                tasks = self.prepare_download_queue(surah_numbers, reciter)
                if tasks:
                    return self.start_bulk_download(tasks)
                else:
                    print(f"{Fore.YELLOW}No valid files to download.{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.YELLOW}Download cancelled.{Style.RESET_ALL}")
                return False

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Download cancelled.{Style.RESET_ALL}")
            return False
