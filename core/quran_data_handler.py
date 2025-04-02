# core/quran_data_handler.py
import arabic_reshaper
from bidi.algorithm import get_display
from typing import List
from core.models import SurahInfo, Ayah
from core.quran_cache import QuranCache

class QuranDataHandler:
    def __init__(self, cache: QuranCache):
        self.cache = cache
        self.arabic_reversed = False  # Flag to track if Arabic is reversed for display

    def toggle_arabic_reversal(self):
        """Toggles the arabic_reversed flag."""
        self.arabic_reversed = not self.arabic_reversed

    def fix_arabic_text(self, text: str) -> str:
        """Fixes Arabic text based on the current reversal setting."""
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        if self.arabic_reversed:
            return "".join(reversed(text))
        else:
            return str(bidi_text)

    def get_surah_info(self, surah_number: int) -> SurahInfo:
        """Get surah info from cache or download if missing"""
        data = self.cache.get_surah(surah_number)
        if not data:
            #This will be replaced later.
            raise ValueError("Surah data not found in cache")
        
        # Get the regular reciters from the API data
        audio_data = data.get("audio", {})
        
        # Add Muhammad Al Luhaidan reciter with the special URL format
        # Format surah number with leading zeros for URL (001, 002, etc.)
        padded_surah = str(surah_number).zfill(3)
        luhaidan_url = f"https://server8.mp3quran.net/lhdan/{padded_surah}.mp3"
        
        # Add as a new reciter with ID "luhaidan"
        audio_data["luhaidan"] = {
            "reciter": "Muhammad Al Luhaidan",
            "url": luhaidan_url
        }
        
        return SurahInfo(
            surah_name=data.get("surahName", "Unknown"),
            surah_name_arabic=self.fix_arabic_text(data.get("surahNameArabic", "غير معروف")),
            total_ayah=data.get("totalAyah", 0),
            revelation_place=data.get("revelationPlace", "Unknown"),
            surah_number=surah_number,
            audio=audio_data
        )

    def get_ayahs(self, surah_number: int, start: int, end: int) -> List[Ayah]:
        """Get ayahs from cache or download if missing"""
        data = self.cache.get_surah(surah_number)
        if not data:
            #This will be replaced later.
            raise ValueError("Surah data not found in cache")

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
        
    def get_ayahs_raw(self, surah_number: int, start: int, end: int) -> List[Ayah]:
        """Get ayahs with raw Arabic text without any text processing"""
        data = self.cache.get_surah(surah_number)
        if not data:
            raise ValueError("Surah data not found in cache")

        total_ayah = data.get("totalAyah", 0)
        if not (1 <= start <= end <= total_ayah):
            raise ValueError("Invalid ayah range")

        return [
            Ayah(
                number=idx + 1,
                text=data.get("english", [""] * total_ayah)[idx],
                arabic_simple=data.get("arabic2", [""] * total_ayah)[idx],  # Raw text
                arabic_uthmani=data.get("arabic1", [""] * total_ayah)[idx]  # Raw text
            )
            for idx in range(start - 1, end)
        ]        