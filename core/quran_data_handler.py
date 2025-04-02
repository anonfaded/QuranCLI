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

    def __init__(self, cache: QuranCache):
        """
        Initializes the data handler.

        Args:
            cache: The QuranCache instance (used ONLY for accessing downloaded audio URLs).
        """
        self.cache = cache # Keep cache reference for audio URLs
        self.quran_db = self._load_quran_database() # Load the new local DB

        # --- ADDED arabic_reversed flag and related logic ---
        self.arabic_reversed = False

    def toggle_arabic_reversal(self):
        """Toggles the arabic_reversed flag."""
        self.arabic_reversed = not self.arabic_reversed
        print(f"{Fore.YELLOW}Arabic display reversal toggled: {'ON' if self.arabic_reversed else 'OFF'}{Style.RESET_ALL}") # Optional feedback
        import time
        time.sleep(0.7) # Brief pause to see feedback
    
    def _load_quran_database(self) -> Optional[Dict]:
        """Loads the Quran data from the local JSON database file."""
        try:
            # Use get_app_path to locate the database file correctly
            # writable=False ensures it looks inside _MEIPASS or relative to script
            db_path = get_app_path(self.DATABASE_FILENAME, writable=False)

            if not os.path.exists(db_path):
                print(f"{Fore.RED}Fatal Error: Quran database not found at {db_path}{Style.RESET_ALL}", file=sys.stderr)
                return None # Indicate failure

            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"{Fore.GREEN}Successfully loaded local Quran database.{Style.RESET_ALL}")
            return data

        except json.JSONDecodeError as e:
            print(f"{Fore.RED}Fatal Error: Failed to parse Quran database file ({db_path}): {e}{Style.RESET_ALL}", file=sys.stderr)
            return None
        except FileNotFoundError:
            # This case is less likely now with os.path.exists, but good practice
             print(f"{Fore.RED}Fatal Error: Quran database file not found ({db_path} does not exist).{Style.RESET_ALL}", file=sys.stderr)
             return None
        except Exception as e:
            print(f"{Fore.RED}Fatal Error: An unexpected error occurred loading the Quran database: {e}{Style.RESET_ALL}", file=sys.stderr)
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
        """Get ayahs combining local DB (Arabic, Translit) and Cache (English Translation)."""
        if not self.quran_db:
            print(f"{Fore.RED}Error: Local Quran database not loaded.{Style.RESET_ALL}", file=sys.stderr)
            return []

        surah_key = str(surah_number)
        chapters = self.quran_db.get("chapters", {})
        if surah_key not in chapters:
            print(f"{Fore.RED}Error: Surah {surah_number} not found in local database.{Style.RESET_ALL}", file=sys.stderr)
            return []

        db_verses_data = chapters[surah_key].get("verses", {})
        total_ayah_db = chapters[surah_key].get("total_verses", 0)

        # --- Fetch cached data for English text ---
        cached_surah_data = self.cache.get_surah(surah_number)
        cached_english_texts = []
        total_ayah_cache = 0
        if cached_surah_data:
            cached_english_texts = cached_surah_data.get("english", [])
            total_ayah_cache = cached_surah_data.get("totalAyah", 0) # Get total ayah count from cache too
            if not isinstance(cached_english_texts, list): # Basic type check
                 print(f"{Fore.YELLOW}Warning: Invalid 'english' data type in cache for Surah {surah_number}. Expected list.{Style.RESET_ALL}", file=sys.stderr)
                 cached_english_texts = []
        else:
            print(f"{Fore.YELLOW}Warning: Cached data not found for Surah {surah_number}. English translation will be unavailable.{Style.RESET_ALL}", file=sys.stderr)

        # Use the total ayah count from the *local DB* as the primary reference
        total_ayah_ref = total_ayah_db
        if total_ayah_db != total_ayah_cache and total_ayah_cache > 0:
             print(f"{Fore.YELLOW}Warning: Mismatch in total ayah count for Surah {surah_number} (DB: {total_ayah_db}, Cache: {total_ayah_cache}). Using DB count.{Style.RESET_ALL}", file=sys.stderr)
             # You might want a more robust strategy here depending on data source reliability

        if not (1 <= start <= end <= total_ayah_ref):
            print(f"{Fore.YELLOW}Warning: Invalid ayah range ({start}-{end}) for Surah {surah_number} (Total: {total_ayah_ref}){Style.RESET_ALL}", file=sys.stderr)
            return []

        ayah_list = []
        for ayah_num in range(start, end + 1):
            ayah_key = str(ayah_num)
            db_ayah_data = db_verses_data.get(ayah_key)

            # Get Arabic and Transliteration from local DB
            arabic_content = ""
            transliteration = ""
            if db_ayah_data:
                arabic_content = self.fix_arabic_text(db_ayah_data.get("content", "")) # Apply BiDi fix
                transliteration = db_ayah_data.get("transliteration", "")
            else:
                print(f"{Fore.YELLOW}Warning: Ayah {surah_number}:{ayah_num} data missing in local DB.{Style.RESET_ALL}", file=sys.stderr)

            # Get English from Cache (adjusting for 0-based index)
            english_text = ""
            cache_index = ayah_num - 1
            if 0 <= cache_index < len(cached_english_texts):
                english_text = cached_english_texts[cache_index]
                if not isinstance(english_text, str): # Ensure it's a string
                    english_text = str(english_text) # Attempt conversion
            elif cached_surah_data: # Only warn if cache existed but index was out of bounds
                print(f"{Fore.YELLOW}Warning: English text missing in cache for Ayah {surah_number}:{ayah_num}.{Style.RESET_ALL}", file=sys.stderr)

            # Construct Ayah model
            try:
                ayah_list.append(Ayah(
                    number=ayah_num,
                    content=arabic_content,
                    transliteration=transliteration,
                    text=english_text # Use English from cache
                ))
            except Exception as e:
                print(f"{Fore.RED}Error creating Ayah object for {surah_number}:{ayah_num}: {e}{Style.RESET_ALL}", file=sys.stderr)

        return ayah_list

    def get_ayahs_raw(self, surah_number: int, start: int, end: int) -> List[Ayah]:
        """Get ayahs for SRT: local DB (RAW Arabic, Translit) and Cache (English Translation)."""
        # This method is very similar to get_ayahs, differing only in not calling fix_arabic_text
        if not self.quran_db: return []

        surah_key = str(surah_number)
        chapters = self.quran_db.get("chapters", {})
        if surah_key not in chapters: return []

        db_verses_data = chapters[surah_key].get("verses", {})
        total_ayah_db = chapters[surah_key].get("total_verses", 0)

        # Fetch cached data for English text
        cached_surah_data = self.cache.get_surah(surah_number)
        cached_english_texts = []
        total_ayah_cache = 0
        if cached_surah_data:
            cached_english_texts = cached_surah_data.get("english", [])
            total_ayah_cache = cached_surah_data.get("totalAyah", 0)
            if not isinstance(cached_english_texts, list): cached_english_texts = []
        # else: pass # Warning printed in get_ayahs if called

        total_ayah_ref = total_ayah_db
        # if total_ayah_db != total_ayah_cache and total_ayah_cache > 0: pass # Warning printed in get_ayahs

        if not (1 <= start <= end <= total_ayah_ref): return []

        ayah_list = []
        for ayah_num in range(start, end + 1):
            ayah_key = str(ayah_num)
            db_ayah_data = db_verses_data.get(ayah_key)

            # Get RAW Arabic and Transliteration from local DB
            raw_arabic_content = ""
            transliteration = ""
            if db_ayah_data:
                raw_arabic_content = db_ayah_data.get("content", "") # DO NOT call fix_arabic_text
                transliteration = db_ayah_data.get("transliteration", "")
            # else: pass # Warning printed in get_ayahs

            # Get English from Cache
            english_text = ""
            cache_index = ayah_num - 1
            if 0 <= cache_index < len(cached_english_texts):
                english_text = cached_english_texts[cache_index]
                if not isinstance(english_text, str): english_text = str(english_text)
            # elif cached_surah_data: pass # Warning printed in get_ayahs

            # Construct Ayah model
            try:
                ayah_list.append(Ayah(
                    number=ayah_num,
                    content=raw_arabic_content, # Use RAW Arabic
                    transliteration=transliteration,
                    text=english_text # Use English from cache
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