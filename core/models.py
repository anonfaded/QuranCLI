# core/models.py
from pydantic import BaseModel
from typing import Dict, Optional # Optional might be needed if description can be null

# Note: EditionType is no longer directly relevant for text display based on the new DB
# Keeping it might be useful if we ever re-introduce multiple Arabic sources or specific behaviors.
# For now, it's unused by the core text display logic.
# from enum import Enum
# class EditionType(Enum):
#     SIMPLE = "arabic2" # Kept for reference, but not used for display logic
#     UTHMANI = "arabic1" # Kept for reference, but not used for display logic
#     ENGLISH = "english" # Kept for reference, but not used for display logic

class SurahInfo(BaseModel):
    surah_name: str         # e.g., "AL-FĀTIḤAH"
    surah_name_ar: str      # Arabic name (will be processed by fix_arabic_text)
    translation: str        # e.g., "THE OPENING"
    type: str               # "meccan" or "medinan"
    total_verses: int
    description: Optional[str] = None # Surah description (can be long)
    surah_number: int
    # Audio data is still sourced from the downloaded cache, structure remains the same
    audio: Dict[str, Dict[str, str]]

class Ayah(BaseModel):
    number: int             # The ayah number within the surah (e.g., 1, 2, 3...)
    content: str            # The primary Arabic text (Uthmani script from NEW local DB)
    transliteration: str    # Transliteration from the NEW local DB
    text: str               # English Translation from the OLD CACHED data (quran_data.json)

    # --- REMOVED ---
    # translation_eng: str    # No longer needed as we use 'text' from cache
    # --- END REMOVED ---