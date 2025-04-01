# core/quran_cache.py
import sys
import os
import json
import threading
from typing import Dict
from colorama import Fore
import platformdirs # Use platformdirs for cross-platform path handling
# --- Use relative import for utils ---

# --- Use relative import for utils ---
try:
    from .utils import get_app_path
except ImportError:
    from utils import get_app_path

# --- Define constants for platformdirs ---
APP_NAME = "QuranCLI"
APP_AUTHOR = "FadSecLab"

class QuranCache:
    """Handles caching of Quran data"""
    # --- CORRECTED PATH: Use writable=True ---
    CACHE_DIR = get_app_path('cache', writable=True) # Cache dir next to exe
    CACHE_FILE_NAME = 'quran_data.json' # Just the filename
    # --- End Correction ---
    TOTAL_SURAHS = 114

    def __init__(self):
        self.CACHE_DIR = ""  # Initialize path attributes
        self.CACHE_FILE = ""

        # --- Platform-Specific Path for Quran Cache ---
        try:
            if sys.platform == "win32":
                # Windows: Save next to executable
                self.CACHE_DIR = get_app_path('cache', writable=True)
                self.CACHE_FILE = os.path.join(self.CACHE_DIR, self.CACHE_FILE_NAME)
                # get_app_path(writable=True) ensures directory exists
                print(f"DEBUG: Quran cache path (Win): {self.CACHE_FILE}") # Optional debug
            else:
                # Linux/macOS: Use user's cache directory
                cache_base_dir = platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR)
                self.CACHE_DIR = os.path.join(cache_base_dir) # Store base cache dir
                self.CACHE_FILE = os.path.join(self.CACHE_DIR, self.CACHE_FILE_NAME)
                os.makedirs(self.CACHE_DIR, exist_ok=True) # Ensure directory exists
                print(f"DEBUG: Quran cache path (Unix): {self.CACHE_FILE}") # Optional debug

        except Exception as e_path:
            print(f"{Fore.RED}Critical Error determining Quran cache path: {e_path}")
            print(f"{Fore.YELLOW}Quran data caching may not work correctly.")
            # Paths remain empty strings, load/save will fail gracefully

        # --- Load cache data ---
        self.cache_data: Dict[str, dict] = self.load_cache()
        self._lock = threading.Lock()

    def load_cache(self) -> dict:
        """Load cached data or return empty dict"""
        # Check if path was determined successfully
        if not self.CACHE_FILE or not os.path.exists(self.CACHE_FILE):
            return {}
        try:
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
             # Use Fore from colorama if available, otherwise plain text
             try: from colorama import Fore, Style; yellow = Fore.YELLOW; reset = Style.RESET_ALL
             except ImportError: yellow = reset = ""
             print(f"{yellow}Warning: Could not load cache file {self.CACHE_FILE}: {e}{reset}")
             return {}
        except Exception as e:
             try: from colorama import Fore, Style; red = Fore.RED; reset = Style.RESET_ALL
             except ImportError: red = reset = ""
             print(f"{red}Unexpected error loading Quran cache: {e}{reset}")
             return {}

    def save_cache(self):
        """Save current cache to disk"""
        # Check if path was determined successfully
        if not self.CACHE_FILE:
             try: from colorama import Fore, Style; red = Fore.RED; reset = Style.RESET_ALL
             except ImportError: red = reset = ""
             print(f"{red}Error: Cannot save Quran cache - path not set.{reset}")
             return
        try:
            # Ensure directory exists (should have been created in init)
            if self.CACHE_DIR: # Only try making dirs if path seems valid
                 os.makedirs(self.CACHE_DIR, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            try: from colorama import Fore, Style; red = Fore.RED; reset = Style.RESET_ALL
            except ImportError: red = reset = ""
            print(f"{red}Error: Could not write cache file {self.CACHE_FILE}: {e}{reset}")
        except Exception as e:
             try: from colorama import Fore, Style; red = Fore.RED; reset = Style.RESET_ALL
             except ImportError: red = reset = ""
             print(f"{red}Unexpected error saving Quran cache: {e}{reset}")


    def get_surah(self, number: int) -> dict:
        """Get surah data from cache or None if not found"""
        return self.cache_data.get(str(number))

    def save_surah(self, number: int, data: dict):
        """Save surah data to cache thread-safely"""
        # Clean up bengali data if present
        data.pop('bengali', None) # Safely remove if exists

        with self._lock:
            self.cache_data[str(number)] = data
            self.save_cache() # Save immediately after modification

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
        # Adjust required fields based on actual API response/needs
        required_fields = {'surahName', 'surahNameArabic', 'totalAyah', 'arabic1', 'arabic2', 'english'}
        return all(field in data for field in required_fields)