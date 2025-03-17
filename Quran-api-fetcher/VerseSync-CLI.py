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

# Initialize colorama
init(autoreset=True)



VERSE_SYNC_ASCII = """
\033[31m██╗   ██╗███████╗██████╗ ███████╗███████╗███████╗██╗   ██╗███╗   ██╗ ██████╗
██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝
██║   ██║█████╗  ██████╔╝███████╗█████╗  ███████╗ ╚████╔╝ ██╔██╗ ██║██║     
╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝  ╚════██║  ╚██╔╝  ██║╚██╗██║██║     
 ╚████╔╝ ███████╗██║  ██║███████║███████╗███████║   ██║   ██║ ╚████║╚██████╗
  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝\033[0m"""

class EditionType(Enum):
    SIMPLE = "arabic2"
    UTHMANI = "arabic1"
    ENGLISH = "english"

class SurahInfo(BaseModel):
    surah_name: str
    surah_name_arabic: str
    total_ayah: int
    revelation_place: str

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
            revelation_place=data.get("revelationPlace", "Unknown")
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


class QuranApp:
    def __init__(self):
        self._clear_terminal()
        self.client = QuranAPIClient()
        # Get terminal size
        self.term_size = shutil.get_terminal_size()
        
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
            
            if total_pages > 1:
                print(Style.BRIGHT + Fore.RED + "\nNavigation:")
                print(Fore.WHITE + "n: Next page | p: Previous page | q: Return to menu")
                choice = input(Fore.RED + "\n└──╼ " + Fore.WHITE).lower()
                
                if choice == 'n' and current_page < total_pages:
                    current_page += 1
                elif choice == 'p' and current_page > 1:
                    current_page -= 1
                elif choice == 'q':
                    break
            else:
                input(Fore.RED + "\nPress Enter to continue...")
                return  # Return instead of break

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
        print(VERSE_SYNC_ASCII)
        print(Style.BRIGHT + Fore.RED + "=" * 70)
        print(Fore.WHITE + "📖 Welcome to " + Fore.RED + "VerseSync" + Fore.WHITE + " - Your Digital Quran Companion")
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
        print(Style.BRIGHT + Fore.CYAN + f"\n📖 {surah_info.surah_name}")
        print(Fore.WHITE + f"   {surah_info.surah_name_arabic}\n")
        self._paginate_output(ayahs, surah_info=surah_info)

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
                    print(Fore.RED + "\n✨ Thank you for using " + Fore.WHITE + "VerseSync" + Fore.RED + "!")
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
