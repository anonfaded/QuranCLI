# core/quran_cache.py
import os
import json
import threading
from typing import Dict

class QuranCache:
    """Handles caching of Quran data"""
    CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')  # Adjusted path
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