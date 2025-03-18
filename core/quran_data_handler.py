# core/quran_data_handler.py
import arabic_reshaper
from bidi.algorithm import get_display
from typing import List
from core.models import SurahInfo, Ayah
from core.quran_cache import QuranCache

class QuranDataHandler:
    def __init__(self, cache: QuranCache):
        self.cache = cache

    @staticmethod
    def fix_arabic_text(text: str) -> str:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return "".join(reversed(bidi_text))  # Ensure correct order when copying

    def get_surah_info(self, surah_number: int) -> SurahInfo:
        """Get surah info from cache or download if missing"""
        data = self.cache.get_surah(surah_number)
        if not data:
            #This will be replaced later.
            raise ValueError("Surah data not found in cache")
        
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