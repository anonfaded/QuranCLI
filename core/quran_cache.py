# core/quran_cache.py
import os
import json
import threading
from typing import Dict
# --- Use relative import for utils ---
from .utils import get_app_path

class QuranCache:
    """Handles caching of Quran data"""
    # --- CORRECTED PATH: Use writable=True ---
    CACHE_DIR = get_app_path('cache', writable=True) # Cache dir next to exe
    CACHE_FILE = os.path.join(CACHE_DIR, 'quran_data.json')
    # --- End Correction ---
    TOTAL_SURAHS = 114

    def __init__(self):
        # get_app_path with writable=True ensures the directory exists
        self.cache_data: Dict[str, dict] = self.load_cache()
        self._lock = threading.Lock()

    # Remove or comment out ensure_cache_dir method if it only did os.makedirs
    # def ensure_cache_dir(self):
    #     """Create cache directory if it doesn't exist (Handled by get_app_path)"""
    #     # os.makedirs(self.CACHE_DIR, exist_ok=True) # Redundant now
    #     pass

    def load_cache(self) -> dict:
        """Load cached data or return empty dict"""
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                 print(f"Warning: Could not load cache file {self.CACHE_FILE}: {e}")
                 return {}
        return {}

    def save_cache(self):
        """Save current cache to disk"""
        try:
            # get_app_path(writable=True) should have created the dir, but check just in case
            os.makedirs(self.CACHE_DIR, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Error: Could not write cache file {self.CACHE_FILE}: {e}")
        except Exception as e:
             print(f"Unexpected error saving cache: {e}")


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