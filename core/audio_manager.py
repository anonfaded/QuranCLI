# core/audio_manager.py
import pygame
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from mutagen.mp3 import MP3
import os
import time
import threading
from colorama import Fore
import tqdm
import sys
import subprocess  # Import the subprocess module


class AudioManager:
    """Handles audio downloads and playback"""

    def __init__(self):
        # Add current_surah tracking
        self.current_surah = None
        self.audio_dir = Path(__file__).parent.parent / 'audio_cache'  # Adjusted path
        self.audio_dir.mkdir(exist_ok=True)
        self.audio_driver = self._detect_audio_driver()  # Detect driver
        self.mixer_initialized = False # Initialize to False
        self._init_mixer()  # Call init mixer after audio driver detect

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

    def _detect_audio_driver(self):
        """Detect the best available audio driver on Linux"""
        if sys.platform == "win32":
            return None  # Use default on Windows

        try:
            # Check for PulseAudio
            subprocess.run(["pactl", "info"], check=True, capture_output=True)
            print(Fore.CYAN + "PulseAudio detected.")
            os.environ['SDL_AUDIODRIVER'] = 'pulse'
            return 'pulse'
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        try:
            # Check for PipeWire (often emulates PulseAudio)
            subprocess.run(["pw-cli", "info"], check=True, capture_output=True)
            print(Fore.CYAN + "PipeWire detected.")
            os.environ['SDL_AUDIODRIVER'] = 'pipewire'
            return 'pipewire'
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Fallback to ALSA
        print(Fore.YELLOW + "Falling back to ALSA.")
        os.environ['SDL_AUDIODRIVER'] = 'alsa'
        return 'alsa'

    def _init_mixer(self):
        """Initialize pygame mixer, after setting env variable"""
        try:
            pygame.mixer.init()
            self.mixer_initialized = True
            print(Fore.GREEN + "Pygame mixer initialized successfully.")
        except pygame.error as e:
            print(Fore.RED + f"Error initializing Pygame mixer: {e}")
            print(Fore.YELLOW + f"Audio functionality might be limited. Trying driver: {self.audio_driver}")
            self.mixer_initialized = False
    
    def get_audio_path(self, surah_num: int, reciter: str) -> Path:
        """Get audio file path"""
        return self.audio_dir / f"surah_{surah_num}_reciter_{reciter}.mp3"

    async def download_audio(self, url: str, surah_num: int, reciter: str, max_retries: int = 5) -> Path:
        """Download audio file with resume support and retry handling"""
        filename = self.get_audio_path(surah_num, reciter)
        temp_file = filename.with_suffix('.tmp')

        for attempt in range(max_retries):
            try:
                # Verify existing file first
                if filename.exists():
                    if os.path.getsize(filename) > 0:
                        try:
                            MP3(str(filename))
                            return filename
                        except Exception:
                            os.remove(filename)
                    else:
                        os.remove(filename)

                # Get file size and resume position
                start_pos = os.path.getsize(temp_file) if temp_file.exists() else 0
                headers = {'Range': f'bytes={start_pos}-'} if start_pos > 0 else {}

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0)) + start_pos

                        if total_size == 0:
                            raise ValueError("Empty response from server")

                        print(Fore.CYAN + "\nConnected to server, starting download...")

                        # Convert sizes to MB for display
                        total_mb = total_size / (1024 * 1024)
                        downloaded_mb = start_pos / (1024 * 1024)

                        with tqdm.tqdm(
                            total=total_mb,
                            initial=downloaded_mb,
                            desc=f"{Fore.RED}Downloading (Attempt {attempt + 1}/{max_retries})",
                            unit='MB',
                            bar_format='{desc}: {percentage:3.0f}%|{bar:30}| {n:.1f}/{total:.1f} MB • {rate_fmt} • ETA: {remaining_s:.0f}s',
                            colour='red',
                            mininterval=0.1,
                            smoothing=0.1,
                            unit_scale=True,
                            unit_divisor=1
                        ) as pbar:
                            try:
                                mode = 'ab' if start_pos > 0 else 'wb'
                                async with aiofiles.open(temp_file, mode) as f:
                                    downloaded_size = start_pos
                                    chunk_size = 8192
                                    start_time = time.time()

                                    async for chunk in response.content.iter_chunked(chunk_size):
                                        await f.write(chunk)
                                        downloaded_size += len(chunk)
                                        chunk_mb = len(chunk) / (1024 * 1024)
                                        pbar.update(chunk_mb)

                                        # Small sleep to prevent high CPU usage
                                        await asyncio.sleep(0.0001)

                                if downloaded_size != total_size:
                                    raise ValueError(f"Download incomplete: {downloaded_size}/{total_size} bytes")

                                # Verify and move file
                                if os.path.exists(filename):
                                    os.remove(filename)
                                os.rename(temp_file, filename)

                                # Validate MP3
                                MP3(str(filename))
                                print(Fore.GREEN + "\n✓ Audio downloaded and verified!")
                                return filename

                            except Exception as e:
                                print(Fore.RED + f"\nDownload interrupted: {str(e)}")
                                raise e

            except aiohttp.ClientError as e:
                print(Fore.RED + f"\nNetwork error (Attempt {attempt + 1}/{max_retries}): {str(e)}")
            except Exception as e:
                print(Fore.RED + f"\nDownload failed (Attempt {attempt + 1}/{max_retries}): {str(e)}")

            if attempt < max_retries - 1:
                retry_delay = (attempt + 1) * 2
                print(Fore.YELLOW + f"\nRetrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

        # All attempts failed
        print(Fore.RED + "\n❌ Download failed after all attempts")
        print(Fore.YELLOW + "Would you like to try downloading again? (y/n): ", end="")
        try:
            if sys.platform == "win32":
                import msvcrt
                if msvcrt.getch().decode().lower() == 'y':
                    return await self.download_audio(url, surah_num, reciter)
            else:
                # Simulate getch for non-Windows systems
                if input().lower() == 'y':
                    return await self.download_audio(url, surah_num, reciter)
        except Exception:
            pass

        raise Exception("Failed to download audio")

    def load_audio(self, file_path: Path):
        """Load audio and get duration"""
        audio = MP3(str(file_path))
        self.duration = audio.info.length
        return audio

    def play_audio(self, file_path: Path, reciter: str):
        """Play audio file with progress tracking"""
        try:
            if not self.mixer_initialized:
                print(Fore.RED + "\nCannot play audio: Pygame mixer not initialized.")
                return

            if self.is_playing:
                self.stop_audio(reset_state=True)

            audio = self.load_audio(file_path)
            pygame.mixer.music.load(str(file_path))
            pygame.mixer.music.play()
            self.is_playing = True
            self.current_audio = file_path
            self.current_reciter = reciter
            self.current_position = 0
            self.start_time = time.time()

            # Update current surah from filename
            try:
                self.current_surah = int(file_path.stem.split('_')[1])
            except (IndexError, ValueError):
                self.current_surah = None

            self.start_progress_tracking()

        except Exception as e:
            print(Fore.RED + f"\nError playing audio: {e}")
            self.stop_audio(reset_state=True)

    def _track_progress(self):
        """Track progress with accurate timing"""
        try:
            while not self.should_stop:
                if self.is_playing and pygame.mixer.music.get_busy():  # Combined conditions
                    self.current_position = time.time() - self.start_time
                    if self.current_position >= self.duration:
                        self.stop_audio(reset_state=True)
                        break
                    self.update_event.set()
                    time.sleep(0.1)
                else:
                    time.sleep(0.1)  # Prevent busy-waiting

            if not pygame.mixer.music.get_busy() and self.is_playing:
                self.stop_audio(reset_state=True)  # Also resetting in this case
        except Exception:
            pass

    def seek(self, position: float):
        """Seek with accurate position tracking"""
        with self.seek_lock:
            try:
                if not self.current_audio:
                    return

                # Calculate new position
                position = max(0, min(position, self.duration))

                # Store playing state
                was_playing = self.is_playing

                # Stop current playback
                pygame.mixer.music.stop()

                # Start from new position
                pygame.mixer.music.load(str(self.current_audio))
                pygame.mixer.music.play(start=position)

                # Update timing
                self.current_position = position
                self.start_time = time.time() - position

                # Restore state
                self.is_playing = was_playing
                if self.is_playing:
                    self.start_progress_tracking()
                else:
                    pygame.mixer.music.pause()

            except Exception as e:
                print(Fore.RED + f"\nSeek error: {e}")

    def start_progress_tracking(self):
        """Start progress tracking thread safely"""
        self.should_stop = False
        self.progress_thread = threading.Thread(target=self._track_progress)
        self.progress_thread.daemon = True
        self.progress_thread.start()

    def stop_audio(self, reset_state=False):
        """Stop audio with cleanup"""
        self.should_stop = True
        if self.progress_thread:
            self.progress_thread.join(timeout=0.5)
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()  # Add this to fully unload the audio

        if reset_state:
            self.is_playing = False
            self.current_position = 0
            self.current_audio = None
            self.current_reciter = None
            self.current_surah = None
            self.duration = 0
            self.start_time = 0  # Add this to reset timing

    def pause_audio(self):
        """Pause audio playback and store position"""
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.current_position = time.time() - self.start_time
            print(Fore.YELLOW + "⏸ Audio paused")

    def resume_audio(self):
        """Resume audio from last position"""
        if self.current_audio and not self.is_playing:
            pygame.mixer.music.load(str(self.current_audio))
            # Start from last position
            pygame.mixer.music.play(start=self.current_position)
            self.is_playing = True
            self.start_time = time.time() - self.current_position
            self.start_progress_tracking()
            print(Fore.GREEN + "▶ Audio resumed")

    def format_time(self, seconds: float) -> str:
        """Format seconds to MM:SS"""
        return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

    def get_progress_bar(self, width: int = 40) -> str:
        """Generate progress bar with colors"""
        if not self.duration:
            return ""

        progress = min(self.current_position / self.duration, 1)
        filled = int(width * progress)
        empty = width - filled

        # Use block characters for better visibility
        bar = (Fore.RED + "█" * filled +
               Fore.WHITE + "░" * empty)

        current = self.format_time(self.current_position)
        total = self.format_time(self.duration)

        return f"{bar} {Fore.CYAN}{current}{Fore.WHITE}/{Fore.CYAN}{total}"