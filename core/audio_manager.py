# core/audio_manager.py
import pygame
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from mutagen.mp3 import MP3
import platformdirs
import os
import time
import threading
from colorama import Fore, Style
import tqdm
import sys
from typing import Optional 

# --- Use relative import for utils ---
# Only needed if Windows path is used
if sys.platform == "win32":
    try:
        from .utils import get_app_path
    except ImportError: # Fallback if run directly
        from utils import get_app_path

if sys.platform == "win32":
    import msvcrt # Only relevant for seek key detection, not pathing

# --- Define constants for platformdirs ---
APP_NAME = "QuranCLI"
APP_AUTHOR = "FadSecLab"

class AudioManager:
    """Handles audio downloads and playback"""
    def __init__(self):
        self.current_surah = None
        self.audio_dir = None # Initialize path attribute

        # --- Platform-Specific Path for Audio Cache ---
        try:
            if sys.platform == "win32":
                # Windows: Save next to executable
                self.audio_dir = Path(get_app_path('audio_cache', writable=True))
                # get_app_path(writable=True) ensures directory exists
                # print(f"DEBUG: Audio cache path (Win): {self.audio_dir}") # Optional debug
            else:
                # Linux/macOS: Use user's cache directory
                cache_base_dir = platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR)
                self.audio_dir = Path(cache_base_dir) / 'audio_cache'
                os.makedirs(self.audio_dir, exist_ok=True) # Ensure directory exists
                # print(f"DEBUG: Audio cache path (Unix): {self.audio_dir}") # Optional debug

        except Exception as e_path:
            print(f"{Fore.RED}Critical Error determining audio cache path: {e_path}")
            print(f"{Fore.YELLOW}Audio download/playback may not work correctly.")
            # audio_dir remains None, subsequent operations should check

        # --- Pygame init ---
        try:
             pygame.mixer.init()
        except pygame.error as e:
             print(f"{Fore.RED}Error initializing pygame mixer: {e}")
             print(f"{Fore.YELLOW}Audio playback will be disabled.")
             self.mixer_initialized = False
        else:
             self.mixer_initialized = True

        # --- Rest of init variables ---
        self.current_audio = None
        self.current_reciter = None
        self.is_playing = False
        self.duration = 0
        self.current_position = 0
        self.progress_thread = None
        self.should_stop = False
        self.seek_lock = threading.Lock()
        self.update_event = threading.Event()
        self.start_time = 0

    def get_audio_path(self, surah_num: int, reciter: str) -> Path:
        """Get audio file path using the initialized audio_dir"""
        if not self.audio_dir: # Check if path determination failed
            print(f"{Fore.RED}Error: Audio directory not set, cannot get path.{Style.RESET_ALL}")
            return None
        # Sanitize reciter name
        safe_reciter = "".join(c for c in reciter if c.isalnum() or c in (' ', '_')).rstrip()
        safe_reciter = safe_reciter.replace(' ', '_')
        return self.audio_dir / f"surah_{surah_num}_reciter_{safe_reciter}.mp3"

    async def download_audio(self, url: str, surah_num: int, reciter: str, max_retries: int = 5) -> Optional[Path]:
        """Download audio file with resume support and retry handling"""
        if not self.mixer_initialized: return None # Skip download if mixer failed
        if not self.audio_dir: # Check if path determination failed
            print(f"{Fore.RED}Error: Audio directory not set, cannot download audio.{Style.RESET_ALL}")
            return None

        # Special case for Muhammad Al Luhaidan - validate URL structure
        is_luhaidan = reciter == "Muhammad Al Luhaidan"
        if is_luhaidan and "server8.mp3quran.net/lhdan" not in url:
            print(f"{Fore.RED}Error: Invalid URL format for Muhammad Al Luhaidan recitation.{Style.RESET_ALL}")
            return None

        filename_path = self.get_audio_path(surah_num, reciter)
        if not filename_path: return None # If get_audio_path failed

        filename = filename_path # Use the Path object directly
        temp_file = filename.with_suffix('.tmp')

        # Ensure parent directory exists (should be handled by init, but safe check)
        try:
             self.audio_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
             print(f"{Fore.RED}Error ensuring audio cache directory {self.audio_dir}: {e}")
             return None

        for attempt in range(max_retries):
            try:
                # Check if valid file already exists
                if filename.exists() and filename.stat().st_size > 0:
                    try:
                        MP3(filename) # Use Path object
                        return filename
                    except Exception:
                        print(f"{Fore.YELLOW}Existing audio file {filename.name} seems corrupt, removing.")
                        filename.unlink(missing_ok=True) # Use Path method
                elif filename.exists():
                     filename.unlink(missing_ok=True)

                # Resume logic
                start_pos = temp_file.stat().st_size if temp_file.exists() else 0
                headers = {'Range': f'bytes={start_pos}-'} if start_pos > 0 else {}
                mode = 'ab' if start_pos > 0 else 'wb'

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=30) as response:
                        if response.status == 416 and start_pos > 0:
                             if temp_file.exists():
                                  temp_file.rename(filename) # Use Path method
                                  print(f"{Fore.GREEN}\n✓ Resumed download appears complete.")
                                  return filename
                             else:
                                   start_pos = 0; headers={}; mode='wb'
                                   raise aiohttp.ClientError("Resume failed, retrying full download")

                        response.raise_for_status()

                        # Get total size for progress bar
                        content_length = response.headers.get('content-length')
                        if content_length is None and start_pos == 0:
                             total_size = None # Unknown total size
                             print(Fore.CYAN + "\nStarting download (total size unknown)...")
                        elif content_length:
                             total_size = int(content_length) + start_pos
                             total_mb = total_size / (1024 * 1024)
                             downloaded_mb = start_pos / (1024 * 1024)
                             print(Fore.CYAN + f"\nDownloading Surah {surah_num}...")
                        else: # Resuming but no content-length? Risky.
                             total_size = None
                             print(Fore.CYAN + "\nResuming download (remaining size unknown)...")


                        # Setup progress bar
                        pbar_desc = f"{Fore.RED}Downloading (Attempt {attempt + 1}/{max_retries})"
                        pbar_unit = 'MB'
                        pbar_total = total_mb if total_size is not None else None
                        pbar_initial = downloaded_mb if total_size is not None else 0
                        pbar_kwargs = {
                            "desc": pbar_desc,
                            "unit": pbar_unit,
                            "total": pbar_total,
                            "initial": pbar_initial,
                            "bar_format": '{desc}: {percentage:3.0f}%|{bar:30}| {n:.1f}/{total:.1f} MB • {rate_fmt} • ETA: {remaining_s:.0f}s' if total_size else '{desc}: {n:.1f} MB downloaded @ {rate_fmt}',
                            "colour": 'red',
                            "mininterval": 0.1,
                            "smoothing": 0.1,
                            "unit_scale": True,
                            "unit_divisor": 1024*1024 if pbar_unit == 'MB' else 1024, # Correct divisor based on unit
                            "disable": total_size is None # Disable bar if no total size
                        }

                        # Perform download with progress
                        downloaded_size_in_loop = start_pos
                        async with aiofiles.open(temp_file, mode=mode) as f:
                             with tqdm.tqdm(**pbar_kwargs) as pbar:
                                 chunk_size = 8192
                                 async for chunk in response.content.iter_chunked(chunk_size):
                                     if not chunk: break # Handle empty chunks
                                     await f.write(chunk)
                                     chunk_len = len(chunk)
                                     downloaded_size_in_loop += chunk_len
                                     if total_size is not None:
                                         pbar.update(chunk_len / (1024*1024)) # Update in MB if total is known
                                     else:
                                         pbar.update(chunk_len / (1024*1024)) # Or just track downloaded amount

                        # Verification after download
                        final_size = temp_file.stat().st_size
                        if total_size is not None and final_size != total_size:
                            raise ValueError(f"Download incomplete: Expected {total_size}, Got {final_size}")
                        if final_size == 0:
                             raise ValueError("Download resulted in empty file.")

                        # Validate MP3 and finalize
                        try:
                            MP3(temp_file) # Use Path object
                            filename.unlink(missing_ok=True) # Use Path method
                            temp_file.rename(filename) # Use Path method
                            print(Fore.GREEN + "\n✓ Audio downloaded and verified!")
                            return filename
                        except Exception as e_verify:
                            raise ValueError(f"MP3 validation failed: {e_verify}")


            except (aiohttp.ClientError, asyncio.TimeoutError) as e_net:
                print(Fore.RED + f"\nNetwork error (Attempt {attempt + 1}/{max_retries}): {e_net}")
            except ValueError as e_val:
                 print(Fore.RED + f"\nDownload error (Attempt {attempt + 1}/{max_retries}): {e_val}")
                 temp_file.unlink(missing_ok=True) # Use Path method
            except Exception as e_other:
                print(Fore.RED + f"\nUnexpected download error (Attempt {attempt + 1}/{max_retries}): {e_other}")
                temp_file.unlink(missing_ok=True) # Use Path method


            if attempt < max_retries - 1:
                retry_delay = (attempt + 1) * 2
                print(Fore.YELLOW + f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

        # All attempts failed
        print(Fore.RED + "\n❌ Audio download failed after all attempts.")
        temp_file.unlink(missing_ok=True) # Use Path method
        return None

    # --- load_audio, play_audio, _track_progress, seek, etc. remain mostly unchanged ---
    # Ensure they check self.mixer_initialized before using pygame.mixer
    def load_audio(self, file_path: Path):
        """Load audio and get duration"""
        if not self.mixer_initialized: return None
        try:
            audio = MP3(str(file_path))
            self.duration = audio.info.length
            return audio # Though we don't use the return value elsewhere currently
        except Exception as e:
             print(f"{Fore.RED}Error loading audio metadata for {file_path.name}: {e}")
             self.duration = 0
             return None

    def play_audio(self, file_path: Path, reciter: str):
        """Play audio file with progress tracking"""
        if not self.mixer_initialized:
            print(Fore.RED + "Audio system not initialized. Cannot play.")
            return
        try:
            if self.is_playing:
                self.stop_audio(reset_state=True) # Stop previous playback cleanly

            self.load_audio(file_path) # Load duration
            if self.duration <= 0:
                 print(f"{Fore.RED}Cannot play audio: Invalid duration or file error.")
                 return

            pygame.mixer.music.load(str(file_path))
            pygame.mixer.music.play()
            self.is_playing = True
            self.current_audio = file_path
            self.current_reciter = reciter
            self.current_position = 0
            self.start_time = time.time()

            try: # Extract surah number from filename for context
                self.current_surah = int(file_path.stem.split('_')[1])
            except (IndexError, ValueError):
                self.current_surah = None

            self.start_progress_tracking() # Start thread to update position

        except pygame.error as e_play:
            print(Fore.RED + f"\nError playing audio: {e_play}")
            self.stop_audio(reset_state=True) # Reset state on error
        except Exception as e: # Catch other potential errors (e.g., file not found if deleted between check and load)
            print(Fore.RED + f"\nUnexpected error preparing audio playback: {e}")
            self.stop_audio(reset_state=True)


    def _track_progress(self):
        """Tracks audio playback progress in a separate thread."""
        while not self.should_stop and self.is_playing:
            try:
                if not pygame.mixer.music.get_busy():
                    # Audio finished playing naturally or was stopped externally
                    # Check if position roughly matches duration before declaring finished
                    if self.duration > 0 and abs((time.time() - self.start_time) - self.duration) < 0.5:
                         self.current_position = self.duration # Snap to end
                    # Don't call stop_audio here, let the main loop handle state transition
                    break # Exit thread

                # Calculate current position based on elapsed time
                self.current_position = time.time() - self.start_time
                # Clamp position to duration just in case of timing issues
                if self.current_position > self.duration:
                    self.current_position = self.duration

                self.update_event.set() # Signal UI thread to update display (optional)
                time.sleep(0.1) # Check ~10 times per second

            except Exception as e:
                 # print(f"Error in progress tracking thread: {e}") # Avoid spamming console
                 break # Exit thread on error

        # Ensure flag is set correctly when loop finishes
        self.is_playing = False # Update playing state when thread exits
        # Signal UI one last time potentially
        self.update_event.set()


    def seek(self, position: float):
        """Seek to a specific position in the audio."""
        if not self.mixer_initialized or not self.current_audio or self.duration <= 0:
            return

        with self.seek_lock: # Prevent race conditions if seek called rapidly
            try:
                target_pos = max(0, min(position, self.duration - 0.1)) # Clamp position slightly before end

                was_playing = self.is_playing # Remember state

                # Pygame seek involves stop/play or set_pos+play
                # Stop/Load/Play(start=...) is generally more reliable
                pygame.mixer.music.stop()
                # No need to unload/load if same file, but doesn't hurt
                pygame.mixer.music.load(str(self.current_audio))
                pygame.mixer.music.play(start=target_pos)

                # Update internal tracking immediately
                self.current_position = target_pos
                self.start_time = time.time() - target_pos

                if not was_playing:
                    # If it wasn't playing before seek, pause it immediately after starting at new pos
                    pygame.mixer.music.pause()
                    self.is_playing = False
                else:
                    # If it was playing, ensure the tracking thread restarts if needed
                    self.is_playing = True
                    if self.progress_thread is None or not self.progress_thread.is_alive():
                         self.start_progress_tracking()

            except pygame.error as e_seek:
                print(Fore.RED + f"\nSeek error: {e_seek}")
            except Exception as e:
                 print(Fore.RED + f"\nUnexpected seek error: {e}")


    def start_progress_tracking(self):
        """Starts the progress tracking thread if not already running."""
        if not self.mixer_initialized: return

        # Clean up previous thread if it somehow exists but isn't alive
        if self.progress_thread and not self.progress_thread.is_alive():
            self.progress_thread = None

        # Start new thread only if playback is intended and no thread exists
        if self.is_playing and self.progress_thread is None:
            self.should_stop = False
            self.progress_thread = threading.Thread(target=self._track_progress, daemon=True)
            self.progress_thread.start()

    def stop_audio(self, reset_state=False):
        """Stops audio playback and cleans up resources."""
        if not self.mixer_initialized: return

        self.should_stop = True # Signal tracking thread to stop
        if self.progress_thread and self.progress_thread.is_alive():
            self.progress_thread.join(timeout=0.5) # Wait briefly for thread exit
        self.progress_thread = None # Clear thread reference

        try:
             pygame.mixer.music.stop()
             pygame.mixer.music.unload() # Important to release file handles
        except pygame.error as e:
             print(f"{Fore.YELLOW}Note: Pygame mixer error during stop/unload: {e}")

        self.is_playing = False # Update state

        if reset_state:
            self.current_position = 0
            self.current_audio = None
            self.current_reciter = None
            self.current_surah = None
            self.duration = 0
            self.start_time = 0
            # Don't reset mixer_initialized here

    def pause_audio(self):
        """Pause audio playback."""
        if not self.mixer_initialized: return
        if self.is_playing:
            try:
                pygame.mixer.music.pause()
                self.is_playing = False
                # Update position accurately based on elapsed time before pause
                self.current_position = time.time() - self.start_time
                # Clamp position just in case
                if self.duration > 0: self.current_position = min(self.current_position, self.duration)

                print(Fore.YELLOW + "⏸ Audio paused")
            except pygame.error as e:
                 print(f"{Fore.RED}Error pausing audio: {e}")

    def resume_audio(self):
        """Resume audio from the paused position."""
        if not self.mixer_initialized: return
        if self.current_audio and not self.is_playing:
            try:
                # Pygame's pause/unpause is simpler than reloading
                pygame.mixer.music.unpause()
                self.is_playing = True
                # Adjust start_time based on the position when paused
                self.start_time = time.time() - self.current_position
                # Ensure tracking thread is running
                self.start_progress_tracking()
                print(Fore.GREEN + "▶ Audio resumed")
            except pygame.error as e:
                 print(f"{Fore.RED}Error resuming audio: {e}")
                 # Fallback: Try reloading and playing from position?
                 # self.play_audio(self.current_audio, self.current_reciter) # Might restart from beginning


    # --- format_time and get_progress_bar remain unchanged ---
    def format_time(self, seconds: float) -> str:
        """Format seconds to MM:SS"""
        if seconds < 0: seconds = 0
        return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

    def get_progress_bar(self, width: int = 40) -> str:
        """Generate progress bar string with colors"""
        if not self.duration: return Style.DIM + "N/A"
        progress = min(self.current_position / self.duration, 1.0) if self.duration > 0 else 0
        filled_width = int(width * progress)
        empty_width = width - filled_width
        bar = (Fore.RED + "█" * filled_width +
               Fore.WHITE + "░" * empty_width + Style.RESET_ALL) # Use standard blocks
        current_time_str = self.format_time(self.current_position)
        total_time_str = self.format_time(self.duration)
        return f"{bar} {Fore.CYAN}{current_time_str}{Fore.WHITE}/{Fore.CYAN}{total_time_str}"