# core/quran_data_handler.py
import arabic_reshaper
from bidi.algorithm import get_display
from typing import List, Dict, Optional
import os
import json
import sys

# --- Use relative import for utils ---
try:
    from .utils import get_app_path
except ImportError:
    from utils import get_app_path

# --- Use relative import for models ---
try:
    from .models import SurahInfo, Ayah
except ImportError:
    from models import SurahInfo, Ayah

# --- Use relative import for QuranCache ---
# We still need QuranCache to access the *downloaded* audio URLs
try:
    from .quran_cache import QuranCache
except ImportError:
    from quran_cache import QuranCache

# --- Colorama for potential errors ---
try:
    from colorama import Fore, Style
    init_colorama = True
except ImportError:
    init_colorama = False
    # Define dummy Fore/Style if needed for inline messages
    class DummyColor:
        def __getattr__(self, name): return ""
    Fore = Style = DummyColor()


class QuranDataHandler:
    DATABASE_FILENAME = "core/database/quran-translation-and-transliteration.json"
    # --- ADD URDU DB FILENAME ---
    URDU_DATABASE_FILENAME = "core/database/quran_ur.json"

    def __init__(self, cache: QuranCache):
        """
        Initializes the data handler.

        Args:
            cache: The QuranCache instance (used ONLY for accessing downloaded audio URLs).
        """
        self.cache = cache # Keep cache reference for audio URLs
        self.quran_db = self._load_quran_database(self.DATABASE_FILENAME, "main") # Load the new local DB
        # --- ADD URDU DB LOADING ---
        self.urdu_db = self._load_quran_database(self.URDU_DATABASE_FILENAME, "Urdu")

        # --- ADDED arabic_reversed flag and related logic ---
        self.arabic_reversed = False

    def toggle_arabic_reversal(self):
        """Toggles the arabic_reversed flag."""
        self.arabic_reversed = not self.arabic_reversed
        print(f"{Fore.YELLOW}Arabic display reversal toggled: {'ON' if self.arabic_reversed else 'OFF'}{Style.RESET_ALL}") # Optional feedback
        import time
        time.sleep(0.7) # Brief pause to see feedback
    
    def _load_quran_database(self, db_filename: str, db_name: str = "database") -> Optional[Dict]:
        """Loads Quran data from a specified local JSON database file."""
        try:
            db_path = get_app_path(db_filename, writable=False)

            if not os.path.exists(db_path):
                print(f"{Fore.RED}Fatal Error: Quran {db_name} database not found at {db_path}{Style.RESET_ALL}", file=sys.stderr)
                return None

            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"{Fore.GREEN}Successfully loaded local Quran {db_name} database.{Style.RESET_ALL}")
            return data

        except json.JSONDecodeError as e:
            print(f"{Fore.RED}Fatal Error: Failed to parse Quran {db_name} database file ({db_path}): {e}{Style.RESET_ALL}", file=sys.stderr)
            return None
        except FileNotFoundError:
             print(f"{Fore.RED}Fatal Error: Quran {db_name} database file not found ({db_path} does not exist).{Style.RESET_ALL}", file=sys.stderr)
             return None
        except Exception as e:
            print(f"{Fore.RED}Fatal Error: An unexpected error occurred loading the Quran {db_name} database: {e}{Style.RESET_ALL}", file=sys.stderr)
            return None


    def fix_arabic_text(self, text: str) -> str:
        """Reshapes and applies BiDi algorithm, optionally reversing for display."""
        if not text:
            return ""
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            bidi_text = get_display(reshaped_text)
            # --- ADD REVERSAL LOGIC BACK ---
            if self.arabic_reversed:
                # Simple string reversal - might not be perfect for complex scripts but matches previous behavior
                return "".join(reversed(str(bidi_text)))
            else:
                return str(bidi_text)
            # --- END ADD ---
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Error processing Arabic text ('{text[:20]}...'): {e}{Style.RESET_ALL}", file=sys.stderr)
            return text # Return original text on error

    def get_surah_info(self, surah_number: int) -> Optional[SurahInfo]:
        """Get surah info from the local DB and audio info from the cache."""
        if not self.quran_db:
            print(f"{Fore.RED}Error: Local Quran database not loaded.{Style.RESET_ALL}", file=sys.stderr)
            return None

        surah_key = str(surah_number)
        if surah_key not in self.quran_db.get("chapters", {}):
            print(f"{Fore.RED}Error: Surah {surah_number} not found in local database.{Style.RESET_ALL}", file=sys.stderr)
            return None

        db_data = self.quran_db["chapters"][surah_key]

        # --- Get Audio Data from the CACHED downloaded file ---
        # This assumes QuranAPIClient still downloads the original structure
        cached_surah_data = self.cache.get_surah(surah_number)
        if cached_surah_data:
            audio_data = cached_surah_data.get("audio", {})
            # Add Muhammad Al Luhaidan reciter logic (same as before)
            padded_surah = str(surah_number).zfill(3)
            luhaidan_url = f"https://server8.mp3quran.net/lhdan/{padded_surah}.mp3"
            audio_data["luhaidan"] = {
                "reciter": "Muhammad Al Luhaidan",
                "url": luhaidan_url
            }
        else:
            # If cached data is missing (e.g., initial run failed download), provide empty audio dict
            print(f"{Fore.YELLOW}Warning: Cached data for Surah {surah_number} not found. Audio URLs may be unavailable.{Style.RESET_ALL}", file=sys.stderr)
            audio_data = {}
            # Still add Luhaidan URL as a fallback if needed
            padded_surah = str(surah_number).zfill(3)
            luhaidan_url = f"https://server8.mp3quran.net/lhdan/{padded_surah}.mp3"
            audio_data["luhaidan"] = {
                "reciter": "Muhammad Al Luhaidan",
                "url": luhaidan_url
            }
            # TODO: Consider if we need a mechanism to *trigger* a download if cache is missing here.
            # For now, it relies on the initial check in QuranAPIClient.

        # --- Construct SurahInfo using data from both sources ---
        try:
            return SurahInfo(
                surah_name=db_data.get("surah_name", "Unknown"),
                surah_name_ar=self.fix_arabic_text(db_data.get("surah_name_ar", "")),
                translation=db_data.get("translation", "N/A"),
                type=db_data.get("type", "Unknown"),
                total_verses=db_data.get("total_verses", 0),
                description=db_data.get("description", None), # Get description
                surah_number=surah_number,
                audio=audio_data # Use audio data fetched from cache
            )
        except Exception as e: # Catch potential Pydantic validation errors or others
             print(f"{Fore.RED}Error creating SurahInfo for Surah {surah_number}: {e}{Style.RESET_ALL}", file=sys.stderr)
             return None

    def get_ayahs(self, surah_number: int, start: int, end: int) -> List[Ayah]:
        """Get ayahs combining data from local DBs (Arabic, Translit, Urdu) and Cache (English)."""
        if not self.quran_db: return [] # Main DB check
        # Optional: Add check for self.urdu_db if Urdu is critical
        # if not self.urdu_db: print(...) ; return []

        surah_key = str(surah_number)
        chapters = self.quran_db.get("chapters", {})
        if surah_key not in chapters: return []

        db_verses_data = chapters[surah_key].get("verses", {})
        total_ayah_db = chapters[surah_key].get("total_verses", 0)

        # --- Get Urdu Verses for this Surah (Handle potential errors) ---
        urdu_verses_list = []
        urdu_surah_index = surah_number - 1 # Urdu DB uses 0-based list index
        if self.urdu_db and isinstance(self.urdu_db, list) and 0 <= urdu_surah_index < len(self.urdu_db):
            urdu_surah_data = self.urdu_db[urdu_surah_index]
            if isinstance(urdu_surah_data, dict):
                 urdu_verses_list = urdu_surah_data.get("verses", [])
            if not isinstance(urdu_verses_list, list):
                 print(f"{Fore.YELLOW}Warning: Invalid 'verses' format in Urdu DB for Surah {surah_number}.{Style.RESET_ALL}", file=sys.stderr)
                 urdu_verses_list = []
        elif self.urdu_db: # Only warn if urdu_db was loaded but index was bad
            print(f"{Fore.YELLOW}Warning: Surah {surah_number} not found or invalid structure in Urdu DB.{Style.RESET_ALL}", file=sys.stderr)
        # --- End Urdu Verse Fetching ---

        # Fetch cached data for English text (remains the same)
        cached_surah_data = self.cache.get_surah(surah_number)
        cached_english_texts = []
        if cached_surah_data:
            cached_english_texts = cached_surah_data.get("english", [])
            if not isinstance(cached_english_texts, list): cached_english_texts = []
        # else: # Warning printed below if needed

        total_ayah_ref = total_ayah_db # Use main DB count as reference
        # (Optional: Add warning if total_ayah count mismatches between DBs)

        if not (1 <= start <= end <= total_ayah_ref): return [] # Range check

        ayah_list = []
        for ayah_num in range(start, end + 1):
            ayah_key = str(ayah_num)
            db_ayah_data = db_verses_data.get(ayah_key)

            # Get Arabic and Transliteration from local DB
            arabic_content = self.fix_arabic_text(db_ayah_data.get("content", "")) if db_ayah_data else ""
            transliteration = db_ayah_data.get("transliteration", "") if db_ayah_data else ""

            # Get English from Cache
            english_text = ""
            cache_index = ayah_num - 1
            if 0 <= cache_index < len(cached_english_texts):
                english_text = cached_english_texts[cache_index]
                if not isinstance(english_text, str): english_text = str(english_text)
            elif cached_surah_data: # Warn only if cache existed but index was out of bounds
                 print(f"{Fore.YELLOW}Warning: English text missing in cache for Ayah {surah_number}:{ayah_num}.{Style.RESET_ALL}", file=sys.stderr)

            # --- Get Urdu from Urdu DB ---
            urdu_translation = ""
            urdu_ayah_index = ayah_num - 1 # Urdu verses list is 0-based
            if 0 <= urdu_ayah_index < len(urdu_verses_list):
                urdu_ayah_data = urdu_verses_list[urdu_ayah_index]
                if isinstance(urdu_ayah_data, dict):
                    urdu_translation = urdu_ayah_data.get("translation", "")
                if not isinstance(urdu_translation, str): urdu_translation = str(urdu_translation)
            elif self.urdu_db: # Warn only if urdu_db was loaded but index was out of bounds
                print(f"{Fore.YELLOW}Warning: Urdu translation missing in Urdu DB for Ayah {surah_number}:{ayah_num}.{Style.RESET_ALL}", file=sys.stderr)
            # --- End Urdu Fetching ---

            # Construct Ayah model
            try:
                ayah_list.append(Ayah(
                    number=ayah_num,
                    content=arabic_content,
                    transliteration=transliteration,
                    text=english_text,
                    translation_ur=urdu_translation # Add Urdu text
                ))
            except Exception as e:
                print(f"{Fore.RED}Error creating Ayah object for {surah_number}:{ayah_num}: {e}{Style.RESET_ALL}", file=sys.stderr)

        return ayah_list

    def get_ayahs_raw(self, surah_number: int, start: int, end: int) -> List[Ayah]:
        """Get ayahs for SRT: Raw Arabic, Translit, Urdu (local DBs) + English (Cache)."""
        if not self.quran_db: return []

        surah_key = str(surah_number)
        chapters = self.quran_db.get("chapters", {})
        if surah_key not in chapters: return []

        db_verses_data = chapters[surah_key].get("verses", {})
        total_ayah_db = chapters[surah_key].get("total_verses", 0)

        # Get Urdu Verses (same logic as get_ayahs)
        urdu_verses_list = []
        urdu_surah_index = surah_number - 1
        if self.urdu_db and isinstance(self.urdu_db, list) and 0 <= urdu_surah_index < len(self.urdu_db):
            urdu_surah_data = self.urdu_db[urdu_surah_index]
            if isinstance(urdu_surah_data, dict): urdu_verses_list = urdu_surah_data.get("verses", [])
            if not isinstance(urdu_verses_list, list): urdu_verses_list = []
        # else: # Warnings handled by get_ayahs if called first

        # Fetch cached data for English text (same logic as get_ayahs)
        cached_surah_data = self.cache.get_surah(surah_number)
        cached_english_texts = []
        if cached_surah_data:
            cached_english_texts = cached_surah_data.get("english", [])
            if not isinstance(cached_english_texts, list): cached_english_texts = []

        total_ayah_ref = total_ayah_db
        if not (1 <= start <= end <= total_ayah_ref): return []

        ayah_list = []
        for ayah_num in range(start, end + 1):
            ayah_key = str(ayah_num)
            db_ayah_data = db_verses_data.get(ayah_key)

            # Get RAW Arabic and Transliteration
            raw_arabic_content = db_ayah_data.get("content", "") if db_ayah_data else ""
            transliteration = db_ayah_data.get("transliteration", "") if db_ayah_data else ""

            # Get English from Cache
            english_text = ""
            cache_index = ayah_num - 1
            if 0 <= cache_index < len(cached_english_texts):
                english_text = cached_english_texts[cache_index]
                if not isinstance(english_text, str): english_text = str(english_text)

            # Get Urdu from Urdu DB
            urdu_translation = ""
            urdu_ayah_index = ayah_num - 1
            if 0 <= urdu_ayah_index < len(urdu_verses_list):
                urdu_ayah_data = urdu_verses_list[urdu_ayah_index]
                if isinstance(urdu_ayah_data, dict): urdu_translation = urdu_ayah_data.get("translation", "")
                if not isinstance(urdu_translation, str): urdu_translation = str(urdu_translation)

            # Construct Ayah model
            try:
                ayah_list.append(Ayah(
                    number=ayah_num,
                    content=raw_arabic_content, # RAW Arabic
                    transliteration=transliteration,
                    text=english_text,
                    translation_ur=urdu_translation
                ))
            except Exception as e:
                 print(f"{Fore.RED}Error creating raw Ayah object for {surah_number}:{ayah_num}: {e}{Style.RESET_ALL}", file=sys.stderr)

        return ayah_list

    def get_all_surah_names(self) -> Dict[int, str]:
        """Gets a dictionary of {surah_number: surah_name} from the local DB."""
        if not self.quran_db:
            print(f"{Fore.RED}Error: Local Quran database not loaded, cannot get surah names.{Style.RESET_ALL}", file=sys.stderr)
            # Fallback to generate numbers 1-114? Or return empty? Let's return empty.
            return {}

        surah_names = {}
        chapters = self.quran_db.get("chapters", {})
        for surah_key, surah_data in chapters.items():
            try:
                surah_number = int(surah_key)
                surah_name = surah_data.get("surah_name", f"Surah {surah_number}") # Use DB name, fallback
                surah_names[surah_number] = surah_name
            except (ValueError, TypeError):
                 print(f"{Fore.YELLOW}Warning: Skipping invalid surah key '{surah_key}' while loading names.{Style.RESET_ALL}", file=sys.stderr)
                 continue # Skip invalid keys

        # Ensure all 114 are present, even if DB is incomplete (though it shouldn't be)
        for i in range(1, 115):
            if i not in surah_names:
                print(f"{Fore.YELLOW}Warning: Surah {i} missing from local DB names list, adding fallback.{Style.RESET_ALL}", file=sys.stderr)
                surah_names[i] = f"Surah {i}"

        return surah_names