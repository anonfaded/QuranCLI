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

# Initialize colorama
init(autoreset=True)

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
        print(Fore.YELLOW + "Checking Quran data cache...")
        missing_surahs = self.cache.validate_cache()
        
        if missing_surahs:
            print(Fore.CYAN + f"Downloading {len(missing_surahs)} missing surahs...")
            self._download_surahs(missing_surahs)
            print(Fore.GREEN + "✓ Download complete!")

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
            
            with tqdm.tqdm(total=len(surah_numbers), desc="Progress", unit="surah") as pbar:
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
        self.client = QuranAPIClient()

    def run(self):
        print(Fore.MAGENTA + "Quran API Client\n" + "=" * 30)
        while True:
            surah_number = self._get_surah_number()
            surah_info = self.client.get_surah_info(surah_number)
            print(Fore.CYAN + f"\n📜 {surah_info.surah_name} ({surah_info.surah_name_arabic}) - {surah_info.revelation_place}")
            print(Fore.YELLOW + f"Total Ayahs: {surah_info.total_ayah}\n" + "-" * 40)

            while True:
                start, end = self._get_ayah_range(surah_info.total_ayah)
                ayahs = self.client.get_ayahs(surah_number, start, end)
                self._display_ayahs(ayahs, surah_info)
                if not self._ask_yes_no("Would you like to select another ayah range? (y/n): "):
                    break

    def _get_surah_number(self) -> int:
        while True:
            try:
                number = int(input(Fore.BLUE + "Enter Surah number (1-114): " + Fore.WHITE))
                if 1 <= number <= 114:
                    return number
            except ValueError:
                pass
            print(Fore.RED + "Invalid input. Please enter a valid surah number.")

    def _get_ayah_range(self, total_ayah: int) -> tuple:
        while True:
            try:
                print(Fore.GREEN + f"(Ayah range: 1-{total_ayah})")
                start = int(input(Fore.BLUE + "Enter start Ayah: " + Fore.WHITE))
                end = int(input(Fore.BLUE + "Enter end Ayah: " + Fore.WHITE))
                if 1 <= start <= end <= total_ayah:
                    return start, end
            except ValueError:
                pass
            print(Fore.RED + "Invalid range. Please enter valid ayah numbers.")

    def _display_ayahs(self, ayahs: List[Ayah], surah_info: SurahInfo):
        print(Fore.CYAN + f"\n📖 {surah_info.surah_name} ({surah_info.surah_name_arabic})\n" + "-" * 50)
        for ayah in ayahs:
            print(Fore.GREEN + f"[{ayah.number}] " + Fore.WHITE + ayah.text)
            print(Fore.YELLOW + f"Simple Arabic: {ayah.arabic_simple}")
            print(Fore.MAGENTA + f"Uthmani Script: {ayah.arabic_uthmani}")
            print("-" * 20)
        print("-" * 50)

    def _ask_yes_no(self, prompt: str) -> bool:
        while True:
            choice = input(Fore.BLUE + prompt + Fore.WHITE).strip().lower()
            if choice in ['y', 'yes']:
                return True
            if choice in ['n', 'no']:
                return False
            print(Fore.RED + "Invalid input. Please enter 'y' or 'n'.")

if __name__ == "__main__":
    QuranApp().run()
