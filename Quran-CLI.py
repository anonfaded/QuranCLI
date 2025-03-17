import requests
from colorama import Fore, Style, init
from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum
import arabic_reshaper
from bidi.algorithm import get_display
import os
import json
import time
import concurrent.futures
import tqdm
import threading
import shutil
import sys
import math
import pygame
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from mutagen.mp3 import MP3
import keyboard
import msvcrt  # For Windows keyboard input

# Initialize colorama
init(autoreset=True)



QURAN_CLI_ASCII = """
\033[31m
 ██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗     ██████╗██╗     ██╗
██╔═══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║    ██╔════╝██║     ██║
██║   ██║██║   ██║██████╔╝███████║██╔██╗ ██║    ██║     ██║     ██║
██║▄▄ ██║██║   ██║██╔══██╗██╔══██║██║╚██╗██║    ██║     ██║     ██║
╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║    ╚██████╗███████╗██║
 ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝     ╚═════╝╚══════╝╚═╝
\033[0m"""

class EditionType(Enum):
    SIMPLE = "arabic2"
    UTHMANI = "arabic1"
    ENGLISH = "english"

class SurahInfo(BaseModel):
    surah_name: str
    surah_name_arabic: str
    total_ayah: int
    revelation_place: str
    surah_number: int
    audio: Dict[str, Dict[str, str]]

class Ayah(BaseModel):
    number: int
    text: str
    arabic_simple: str
    arabic_uthmani: str

class QuranAPIError(Exception):
    """Base exception for Quran API errors"""

class QuranCache:
    """Handles caching of Quran data"""
    CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
    CACHE_FILE = os.path.join(CACHE_DIR, 'quran_data.json')
    TOTAL_SURAHS = 114
    
    def __init__(self):
        self.ensure_cache_dir()
        self.cache_data: Dict[str, dict] = self.load_cache()
        self._lock = threading.Lock()
        
    def ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)
    
    def load_cache(self) -> dict:
        """Load cached data or return empty dict"""
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_cache(self):
        """Save current cache to disk"""
        with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.cache_data, f, ensure_ascii=False, indent=2)

    def get_surah(self, number: int) -> dict:
        """Get surah data from cache or None if not found"""
        return self.cache_data.get(str(number))

    def save_surah(self, number: int, data: dict):
        """Save surah data to cache thread-safely"""
        # Clean up bengali data
        if 'bengali' in data:
            del data['bengali']
            
        with self._lock:
            self.cache_data[str(number)] = data
            self.save_cache()

    def validate_cache(self) -> set:
        """Validate cache and return missing surah numbers"""
        missing = set()
        for surah_num in range(1, self.TOTAL_SURAHS + 1):
            surah_data = self.get_surah(surah_num)
            if not surah_data or not self._is_valid_surah(surah_data):
                missing.add(surah_num)
        return missing

    def _is_valid_surah(self, data: dict) -> bool:
        """Check if surah data is complete"""
        required_fields = {'surahName', 'surahNameArabic', 'totalAyah', 'arabic1', 'arabic2', 'english'}
        return all(field in data for field in required_fields)

class QuranAPIClient:
    BASE_URL = "https://quranapi.pages.dev/api/"
    TIMEOUT = 10

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "QuranClient/1.0"})
        self.cache = QuranCache()
        self._init_cache()

    def _init_cache(self):
        """Initialize and validate cache"""
        print(Fore.YELLOW + "\n📂 Checking Quran data cache...")
        missing_surahs = self.cache.validate_cache()
        
        if missing_surahs:
            print(Fore.CYAN + f"\n⏳ Downloading {len(missing_surahs)} missing surahs...")
            self._download_surahs(missing_surahs)
            print(Fore.GREEN + "\n✓ Download complete!")
        else:
            print(Fore.GREEN + "\n✓ All surahs available in cache!")

    def _handle_response(self, response: requests.Response) -> dict:
        """Handle API response and return JSON data"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise QuranAPIError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            raise QuranAPIError(f"Invalid JSON response: {e}")

    def _download_single_surah(self, surah_num: int) -> bool:
        """Download a single surah"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}{surah_num}.json",
                timeout=self.TIMEOUT
            )
            data = self._handle_response(response)
            
            # Remove bengali data if it exists
            if 'bengali' in data:
                del data['bengali']
                
            self.cache.save_surah(surah_num, data)
            return True
        except Exception as e:
            return False

    def _download_surahs(self, surah_numbers: set):
        """Download multiple surahs in parallel"""
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear terminal
        print(Fore.CYAN + "Downloading Quran data...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._download_single_surah, num): num for num in surah_numbers}
            failed_surahs = set()
            
            with tqdm.tqdm(total=len(surah_numbers), desc=Fore.RED + "Progress" + Fore.RESET, 
                          unit="surah", colour='red') as pbar:
                for future in concurrent.futures.as_completed(futures):
                    surah_num = futures[future]
                    if not future.result():
                        failed_surahs.add(surah_num)
                    pbar.update(1)

            # Retry failed downloads
            if failed_surahs:
                print(Fore.YELLOW + "\nRetrying failed downloads...")
                for surah_num in failed_surahs:
                    if self._download_single_surah(surah_num):
                        print(Fore.GREEN + f"Successfully downloaded Surah {surah_num}")
                    else:
                        print(Fore.RED + f"Failed to download Surah {surah_num}")

    def get_surah_info(self, surah_number: int) -> SurahInfo:
        """Get surah info from cache or download if missing"""
        data = self.cache.get_surah(surah_number)
        if not data:
            response = self.session.get(
                f"{self.BASE_URL}{surah_number}.json",
                timeout=self.TIMEOUT
            )
            data = self._handle_response(response)
            self.cache.save_surah(surah_number, data)
        
        return SurahInfo(
            surah_name=data.get("surahName", "Unknown"),
            surah_name_arabic=self.fix_arabic_text(data.get("surahNameArabic", "غير معروف")),
            total_ayah=data.get("totalAyah", 0),
            revelation_place=data.get("revelationPlace", "Unknown"),
            surah_number=surah_number,
            audio=data.get("audio", {})
        )

    def get_ayahs(self, surah_number: int, start: int, end: int) -> List[Ayah]:
        """Get ayahs from cache or download if missing"""
        data = self.cache.get_surah(surah_number)
        if not data:
            response = self.session.get(
                f"{self.BASE_URL}{surah_number}.json",
                timeout=self.TIMEOUT
            )
            data = self._handle_response(response)
            self.cache.save_surah(surah_number, data)

        total_ayah = data.get("totalAyah", 0)
        if not (1 <= start <= end <= total_ayah):
            raise ValueError("Invalid ayah range")

        return [
            Ayah(
                number=idx + 1,
                text=data.get("english", [""] * total_ayah)[idx],
                arabic_simple=self.fix_arabic_text(data.get("arabic2", [""] * total_ayah)[idx]),
                arabic_uthmani=self.fix_arabic_text(data.get("arabic1", [""] * total_ayah)[idx])
            )
            for idx in range(start - 1, end)
        ]

    @staticmethod
    def fix_arabic_text(text: str) -> str:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return "".join(reversed(bidi_text))  # Ensure correct order when copying


class AudioManager:
    """Handles audio downloads and playback"""
    def __init__(self):
        # Add current_surah tracking
        self.current_surah = None
        self.audio_dir = Path(__file__).parent / 'audio_cache'
        self.audio_dir.mkdir(exist_ok=True)
        pygame.mixer.init()
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
                            bar_format='{desc}: {percentage:3.0f}%|{bar:30}| {n:.1f}/{total:.1f} MB',
                            colour='red'
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
                                        
                                        # Calculate speed and ETA
                                        elapsed = time.time() - start_time
                                        speed = (downloaded_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                                        remaining = (total_size - downloaded_size) / (speed * 1024 * 1024) if speed > 0 else 0
                                        
                                        # Format time remaining
                                        mins = int(remaining // 60)
                                        secs = int(remaining % 60)
                                        
                                        # Update progress bar postfix
                                        pbar.set_postfix_str(
                                            f"Speed: {speed:.1f} MB/s | ETA: {mins:02d}:{secs:02d}"
                                        )
                                        
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
            if msvcrt.getch().decode().lower() == 'y':
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
            while not self.should_stop and pygame.mixer.music.get_busy():
                self.current_position = time.time() - self.start_time
                if self.current_position >= self.duration:
                    self.stop_audio()
                    break
                self.update_event.set()
                time.sleep(0.1)
            
            if not pygame.mixer.music.get_busy() and self.is_playing:
                self.stop_audio()
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
        return f"{int(seconds//60):02d}:{int(seconds%60):02d}"

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


class QuranApp:
    def __init__(self):
        self._clear_terminal()
        self.client = QuranAPIClient()
        # Get terminal size
        self.term_size = shutil.get_terminal_size()
        self.audio_manager = AudioManager()
        
    def _clear_terminal(self):
        """Clear terminal with fallback and scroll reset"""
        # Clear screen
        print("\033[2J", end="")
        # Move cursor to top-left
        print("\033[H", end="")
        # Clear scroll buffer
        sys.stdout.write("\033[3J")
        sys.stdout.flush()

    def _paginate_output(self, ayahs: List[Ayah], page_size: int = None, surah_info: SurahInfo = None):
        """Display ayahs with pagination"""
        if page_size is None:
            page_size = max(1, (self.term_size.lines - 10) // 6)
            
        total_pages = math.ceil(len(ayahs) / page_size)
        current_page = 1
        
        while True:
            self._clear_terminal()
            # Single consolidated header
            print(Style.BRIGHT + Fore.RED + "=" * self.term_size.columns)
            print(f"📖 {surah_info.surah_name} ({surah_info.surah_name_arabic}) • {surah_info.revelation_place} • {surah_info.total_ayah} Ayahs")
            print(f"Page {current_page}/{total_pages}")
            print(Style.BRIGHT + Fore.RED + "=" * self.term_size.columns)
            print(Style.DIM + Fore.YELLOW + "Note: Arabic text may appear reversed but will be correct when copied\n")
            
            # Display ayahs for current page
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(ayahs))
            
            for ayah in ayahs[start_idx:end_idx]:
                self._display_single_ayah(ayah)
            
            # Navigation options
            print(Style.BRIGHT + Fore.RED + "\nNavigation:")
            if total_pages > 1:
                print(Fore.CYAN + "n" + Fore.WHITE + ": Next page")
                print(Fore.CYAN + "p" + Fore.WHITE + ": Previous page")
            print(Fore.YELLOW + "a" + Fore.WHITE + ": Play audio")
            print(Fore.RED + "q" + Fore.WHITE + ": Return")
            
            choice = input(Fore.RED + "\n└──╼ " + Fore.WHITE).lower()
            
            if choice == 'n' and current_page < total_pages:
                current_page += 1
            elif choice == 'p' and current_page > 1:
                current_page -= 1
            elif choice == 'a':
                self._display_audio_controls(surah_info)
            elif choice == 'q':
                return
            elif not choice:  # Enter was pressed
                if current_page < total_pages:
                    current_page += 1
                else:
                    return

    def _display_single_ayah(self, ayah: Ayah):
        """Display a single ayah with proper formatting"""
        print(Style.BRIGHT + Fore.GREEN + f"\n[{ayah.number}]")
        wrapped_text = self._wrap_text(ayah.text, self.term_size.columns - 4)
        print(Style.NORMAL + Fore.WHITE + wrapped_text)
        
        # Arabic text with proper indentation and different title colors
        print(Style.BRIGHT + Fore.RED + "\nSimple Arabic:" + Style.BRIGHT + Fore.WHITE)
        print("    " + ayah.arabic_simple)
        
        print(Style.BRIGHT + Fore.RED + "\nUthmani Script:" + Style.BRIGHT + Fore.WHITE)
        print("    " + ayah.arabic_uthmani)
        
        print(Style.BRIGHT + Fore.WHITE + "\n" + "-" * min(40, self.term_size.columns))

    def _display_header(self):
        """Display app header"""
        print(QURAN_CLI_ASCII)
        print(Style.BRIGHT + Fore.RED + "=" * 70)
        print(Fore.WHITE + "📖 Welcome to " + Fore.RED + "QuranCLI" + Fore.WHITE + " - Your Digital Quran Companion")
        print(Style.BRIGHT + Fore.RED + "=" * 70 + "\n")

    @staticmethod
    def _wrap_text(text: str, width: int) -> str:
        """Wrap text to specified width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def _display_ayahs(self, ayahs: List[Ayah], surah_info: SurahInfo):
        """Display ayahs with pagination"""
        self._paginate_output(ayahs, surah_info=surah_info)

    def _handle_audio_choice(self, choice: str, surah_info: SurahInfo):
        """Handle audio control input"""
        try:
            if choice == 'p':
                if not self.audio_manager.current_audio or self.audio_manager.current_surah != surah_info.surah_number:
                    # Reset audio state for new surah
                    self.audio_manager.stop_audio(reset_state=True)
                    print(Fore.YELLOW + "\nℹ Loading default reciter...")
                    reciter_id = next(iter(surah_info.audio))
                    audio_url = surah_info.audio[reciter_id]["url"]
                    reciter_name = surah_info.audio[reciter_id]["reciter"]
                    asyncio.run(self._handle_audio_playback(audio_url, surah_info.surah_number, reciter_name))
                elif self.audio_manager.is_playing:
                    self.audio_manager.pause_audio()
                else:
                    self.audio_manager.resume_audio()
                    
            elif choice == 's':
                self.audio_manager.stop_audio()
                
            elif choice == 'r':
                if not surah_info.audio:
                    print(Fore.RED + "\nNo reciters available")
                    return

                print(Fore.CYAN + "\nAvailable Reciters:")
                for rid, info in surah_info.audio.items():
                    print(f"{Fore.GREEN}{rid}{Fore.WHITE}: {info['reciter']}")
                
                print(Fore.WHITE + "\nEnter reciter number: ", end="", flush=True)
                reciter_input = msvcrt.getch().decode()
                
                if reciter_input in surah_info.audio:
                    audio_url = surah_info.audio[reciter_input]["url"]
                    reciter_name = surah_info.audio[reciter_input]["reciter"]
                    self.audio_manager.stop_audio()  # Stop current audio before changing
                    asyncio.run(self._handle_audio_playback(audio_url, surah_info.surah_number, reciter_name))
                else:
                    print(Fore.RED + "\nInvalid reciter selection")
                    time.sleep(1)

        except Exception as e:
            print(Fore.RED + f"\nError handling audio command: {e}")
            time.sleep(1)

    async def _handle_audio_playback(self, url: str, surah_num: int, reciter: str):
        """Handle audio download and playback"""
        try:
            print(Fore.YELLOW + "\n⏳ Starting download, please wait...")
            print(Fore.CYAN + "This may take a moment depending on your internet speed.")
            file_path = await self.audio_manager.download_audio(url, surah_num, reciter)
            print(Fore.GREEN + "\n✓ Starting playback...")
            self.audio_manager.play_audio(file_path, reciter)
        except Exception as e:
            print(Fore.RED + f"\nError: {str(e)}")
            print(Fore.YELLOW + "Please try again or choose a different reciter.")
            time.sleep(2)

    def _display_audio_controls(self, surah_info: SurahInfo):
        """Display audio controls with real-time updates"""
        if not surah_info.audio:
            print(Fore.RED + "\n❌ Audio not available for this surah")
            return

        try:
            # Register safe keyboard shortcuts with error handling
            try:
                keyboard.unhook_all()  # Clean up any existing hooks
                keyboard.add_hotkey('left', lambda: self.audio_manager.seek(max(0, self.audio_manager.current_position - 5)))
                keyboard.add_hotkey('right', lambda: self.audio_manager.seek(min(self.audio_manager.duration, self.audio_manager.current_position + 5)))
                keyboard.add_hotkey('ctrl+left', lambda: self.audio_manager.seek(max(0, self.audio_manager.current_position - 30)))
                keyboard.add_hotkey('ctrl+right', lambda: self.audio_manager.seek(min(self.audio_manager.duration, self.audio_manager.current_position + 30)))
            except Exception as e:
                print(Fore.RED + f"\nWarning: Keyboard shortcuts not available: {e}")

            last_display = ""
            while True:
                try:
                    if msvcrt.kbhit():
                        try:
                            key_byte = msvcrt.getch()
                            # Handle arrow keys
                            if key_byte == b'\xe0':  # Special key prefix
                                arrow = msvcrt.getch()
                                if arrow == b'K':  # Left arrow
                                    self.audio_manager.seek(max(0, self.audio_manager.current_position - 5))
                                elif arrow == b'M':  # Right arrow
                                    self.audio_manager.seek(min(self.audio_manager.duration, self.audio_manager.current_position + 5))
                            else:
                                choice = key_byte.decode('ascii', errors='ignore').lower()
                                if choice == 'q':
                                    break
                                self._handle_audio_choice(choice, surah_info)
                        except UnicodeDecodeError:
                            continue  # Skip invalid characters

                    # Update display only if changed
                    current_display = self._get_audio_display(surah_info)
                    if current_display != last_display:
                        self._clear_terminal()
                        print(current_display, end='', flush=True)
                        last_display = current_display
                        sys.stdout.flush()  # Ensure cursor is at the correct position

                    time.sleep(0.1)  # Prevent high CPU usage

                except Exception as e:
                    print(Fore.RED + f"\nError in audio control loop: {e}")
                    time.sleep(1)
                    continue  # Continue instead of break to keep player running

        finally:
            try:
                keyboard.unhook_all()
                self.audio_manager.stop_audio()
            except Exception:
                pass

    def _get_audio_display(self, surah_info: SurahInfo) -> str:
        """Get current audio display with input hints"""
        output = []
        output.append(Style.BRIGHT + Fore.RED + "\nAudio Player - " + 
                    Fore.WHITE + f"{surah_info.surah_name}")
        
        # Only show audio info if it matches current surah
        if (not self.audio_manager.current_audio or 
            self.audio_manager.current_surah != surah_info.surah_number):
            output.append(Style.BRIGHT + Fore.YELLOW + "\n\nℹ Press 'p' to download and play audio")
        else:
            state = "▶ Playing" if self.audio_manager.is_playing else "⏸ Paused"
            state_color = Fore.GREEN if self.audio_manager.is_playing else Fore.YELLOW
            output.append(f"\nState: {state_color}{state}")
            output.append(f"Reciter: {Fore.CYAN}{self.audio_manager.current_reciter}")
            
            if self.audio_manager.duration:
                output.append("\nProgress:")
                output.append(self.audio_manager.get_progress_bar())
                
                if not self.audio_manager.is_playing and self.audio_manager.current_position >= self.audio_manager.duration:
                    output.append(Style.DIM + Fore.YELLOW + "\nAudio finished - Press 'p' to replay")
        
        output.append(Style.BRIGHT + Fore.RED + "\n\nControls:")
        output.append(Fore.GREEN + "p" + Fore.WHITE + ": Play/Pause")
        output.append(Fore.CYAN + "← / →" + Fore.WHITE + ": Seek 5s")
        output.append(Fore.CYAN + "Ctrl + ← / →" + Fore.WHITE + ": Seek 30s")
        output.append(Fore.RED + "s" + Fore.WHITE + ": Stop")
        output.append(Fore.YELLOW + "r" + Fore.WHITE + ": Change Reciter")
        output.append(Fore.MAGENTA + "q" + Fore.WHITE + ": Return")
        
        # Add dim input hint
        output.append(Style.DIM + Fore.WHITE + "\nPress any key to execute command (no Enter needed)")
        output.append(Fore.RED + "└──╼ " + Fore.WHITE)
        
        return '\n'.join(output)

    def run(self):
        while True:
            try:
                self._clear_terminal()
                self._display_header()
                
                # Print usage instructions
                print(Style.BRIGHT + Fore.RED + "Instructions:")
                print(Style.NORMAL + Fore.WHITE + "├─ Type 'quit' or 'exit' to close the application")
                print(Fore.WHITE + "├─ Press Ctrl+C to cancel current operation")
                print(Fore.WHITE + "└─ Arabic text may appear reversed in terminal but will copy correctly\n")
                print(Style.BRIGHT + Fore.RED + "=" * 70 + "\n")
                
                try:
                    while True:
                        print(Fore.RED + "┌─" + Fore.WHITE + " Select Surah")
                        surah_number = self._get_surah_number()
                        if surah_number is None:
                            return  # Exit completely instead of break
                        
                        print(Style.BRIGHT + Fore.RED + "\n" + "=" * 70)
                        
                        surah_info = self.client.get_surah_info(surah_number)
                        print(Style.BRIGHT + Fore.RED + f"\n📜 Surah Information:")
                        print(Fore.RED + "├─ " + Style.BRIGHT + Fore.WHITE + "Name: " + 
                              Style.BRIGHT + Fore.RED + f"{surah_info.surah_name}")
                        print(Fore.RED + "├─ " + Style.BRIGHT + Fore.WHITE + "Arabic: " + 
                              Style.BRIGHT + Fore.RED + f"{surah_info.surah_name_arabic}")
                        print(Fore.RED + "├─ " + Style.BRIGHT + Fore.WHITE + "Revelation: " + 
                              Style.BRIGHT + Fore.RED + f"{surah_info.revelation_place}")
                        print(Fore.RED + "└─ " + Style.BRIGHT + Fore.WHITE + "Total Ayahs: " + 
                              Style.BRIGHT + Fore.RED + f"{surah_info.total_ayah}")
                        print(Style.DIM + Fore.YELLOW + "\nNote: Arabic text appears reversed in terminal but copies correctly")
                        print(Style.BRIGHT + Fore.RED + "-" * 70)

                        while True:
                            start, end = self._get_ayah_range(surah_info.total_ayah)
                            ayahs = self.client.get_ayahs(surah_number, start, end)
                            self._display_ayahs(ayahs, surah_info)
                            
                            # Cleaner ayah range selection prompt
                            print(Fore.BLUE + "\nSelect another range for " + 
                                  Fore.RED + f"{surah_info.surah_name}" + 
                                  Style.DIM + Fore.WHITE + " (y/n)" + 
                                  Fore.WHITE + ": ", end="")
                            
                            if not self._ask_yes_no(""):
                                self._clear_terminal()
                                self._display_header()
                                break

                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\nTo exit, please type 'quit' or 'exit'")
                    self.run()  # Restart the main loop
            except KeyboardInterrupt:
                self._clear_terminal()
                print(Style.BRIGHT + Fore.YELLOW + "⚠ To exit, please type 'quit' or 'exit'")
                continue

    def _get_surah_number(self) -> Optional[int]:
        while True:
            try:
                print(Fore.RED + "└──╼ " + Fore.WHITE + "Enter number (1-114) or 'quit': ", end="")
                user_input = input().strip().lower()
                if user_input in ['quit', 'exit']:
                    print(Fore.RED + "\n✨ Thank you for using " + Fore.WHITE + "QuranCLI" + Fore.RED + "!")
                    return None
                    
                number = int(user_input)
                if 1 <= number <= 114:
                    return number
                raise ValueError
            except ValueError:
                print(Fore.RED + "└──╼ " + "Invalid input. Enter a number between 1-114")

    def _get_ayah_range(self, total_ayah: int) -> tuple:
        while True:
            try:
                print(Fore.RED + "\n┌─" + Fore.WHITE + f" Ayah Selection (1-{total_ayah})")
                print(Fore.RED + "├──╼ " + Fore.WHITE + "Start: ", end="")
                start = int(input())
                print(Fore.RED + "└──╼ " + Fore.WHITE + "End: ", end="")
                end = int(input())
                if 1 <= start <= end <= total_ayah:
                    return start, end
            except ValueError:
                pass
            print(Fore.RED + "└──╼ " + "Invalid range. Please try again.")

    def _ask_yes_no(self, prompt: str) -> bool:
        while True:
            choice = input(Fore.BLUE + prompt + Fore.WHITE).strip().lower()
            if choice in ['y', 'yes']:
                return True
            if choice in ['n', 'no']:
                return False
            print(Fore.RED + "Invalid input. Please enter 'y' or 'n'.")

if __name__ == "__main__":
    try:
        QuranApp().run()
    except KeyboardInterrupt:
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear terminal
        print(Style.BRIGHT + Fore.YELLOW + "⚠ To exit, please type 'quit' or 'exit'")
        QuranApp().run()
