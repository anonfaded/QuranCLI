# Quran-CLI.py

import re
import sys
import os
import platformdirs
import subprocess
import json
from time import sleep
from pathlib import Path
from datetime import datetime

# --- Add Path Hook for PyInstaller ---
try:
    # Attempt import relative to potential bundled structure
    from core.utils import add_core_to_path_if_frozen, get_app_path
    add_core_to_path_if_frozen() # IMPORTANT: Call this early
except ImportError:
    # Fallback if utils isn't found immediately (less likely with correct structure)
    try:
        # Try assuming Quran-CLI.py is project root
        from core.utils import add_core_to_path_if_frozen, get_app_path
        add_core_to_path_if_frozen()
    except ImportError:
        print("Fatal: Could not find core.utils. Path setup failed.", file=sys.stderr)
        sys.exit(1)
# --- End Path Hook ---


# --- Now import colorama and Initialize EARLY ---
try:
    from colorama import Fore, Back, Style, init
    # Initialize Colorama for the whole application run
    init(autoreset=True)
except ImportError:
    print("Warning: colorama not found. Colored output will be disabled.")
    # Define dummy Fore, Back, Style classes if colorama is missing
    class DummyColorama:
        def __getattr__(self, name): return "" # Return empty string for any attribute
    Fore = Back = Style = DummyColorama()
    def init(autoreset=True): pass # Dummy init function
# --- End Colorama Init ---


def get_termux_architecture():
    try:
        output = subprocess.check_output(["uname", "-m"]).decode("utf-8").strip()
        return output
    except FileNotFoundError:
        return None

def check_python_version():
    if sys.version_info < (3, 9):
        print("Error: QuranCLI requires Python 3.9 or higher in Termux.")
        print("Please upgrade your Python installation.")
        sys.exit(1)

# Check if running in Termux
if "TERMUX_VERSION" in os.environ:
    check_python_version()
    architecture = get_termux_architecture()
    if architecture:
        wheelhouse_path = os.path.join(os.path.dirname(__file__), "cache", architecture)
        if os.path.exists(wheelhouse_path):
            sys.path.insert(0, wheelhouse_path)
            print(f"Running in Termux (architecture: {architecture}), using local dependencies from {wheelhouse_path}.")
        else:
            print(f"Warning: No wheel files found for architecture {architecture}. Please check the 'cache' directory.")
    else:
        print("Warning: Could not determine Termux architecture.")

    # Now import everything else
    from core.quran_api_client import QuranAPIClient
    from core.quran_data_handler import QuranDataHandler
    from core.audio_manager import AudioManager
    from core.ui import UI
    from core.github_updater import GithubUpdater
    from core.version import VERSION

    from colorama import Fore, Style, init
    from typing import  Optional
    import shutil
    import difflib

    # Initialize colorama
    init(autoreset=True)
else:
    from colorama import Fore, Style, init
    init(autoreset=True)
    
    from core.quran_api_client import QuranAPIClient
    from core.quran_data_handler import QuranDataHandler
    from core.audio_manager import AudioManager
    from core.ui import UI
    from core.github_updater import GithubUpdater
    from core.download_counter import DownloadCounter
    from core.version import VERSION

    from typing import  Optional
    import shutil
    import difflib

QURAN_CLI_ASCII = """

 ██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗    
██╔═══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║   
██║   ██║██║   ██║██████╔╝███████║██╔██╗ ██║   
██║▄▄ ██║██║   ██║██╔══██╗██╔══██║██║╚██╗██║   
╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║   
 ╚══▀▀═╝  ╚═════╝ ╚═╝  ██║╚═╝  ╚═╝╚═╝  ╚═══╝ 𝘾𝙇𝙄
                        
     █▓▒­░⡷⠂ 𝒫𝓇𝑜𝒿𝑒𝒸𝓉 𝒷𝓎 𝐹𝒶𝒹𝒮𝑒𝒸 𝐿𝒶𝒷 ⠐⢾░▒▓█

"""

# --- Constants for platformdirs ---
APP_NAME = "QuranCLI"
APP_AUTHOR = "FadSecLab"

class QuranApp:
    def __init__(self):
        """Initialize QuranApp, set up preferences file path with new name everywhere."""
        self.client = QuranAPIClient()
        self.term_size = shutil.get_terminal_size()
        self.audio_manager = AudioManager()
        self.data_handler = QuranDataHandler(self.client.cache)

        # --- Platform-Specific Path for Preferences ---
        PREF_FILENAME = "QuranCLI-Settings.json"
        try:
            if sys.platform == "win32":
                self.preferences_file = get_app_path(PREF_FILENAME, writable=True)
            else:
                config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
                os.makedirs(config_dir, exist_ok=True)
                self.preferences_file = os.path.join(config_dir, PREF_FILENAME)
        except Exception as e_path:
            print(f"{Fore.RED}Critical Error determining preferences path: {e_path}")
            print(f"{Fore.YELLOW}Preferences may not save correctly.")
            self.preferences_file = None

        # --- Load preferences using the determined path ---
        self.preferences = self._load_preferences()
        self.theme_color = self.preferences.get('theme_color', 'red') # Load theme

        # --- Initialize Updaters (remain the same) ---
        self.updater = GithubUpdater("anonfaded", "QuranCLI", VERSION)
        self.download_counter = DownloadCounter(repo_owner="anonfaded", repo_name="QuranCLI")

        # --- Initialize UI (remains the same) ---
        self.ui = UI(
            audio_manager=self.audio_manager,
            term_size=self.term_size,
            data_handler=self.data_handler,
            github_updater=self.updater,
            preferences=self.preferences,
            preferences_file_path=self.preferences_file or "", # Convert None to empty string
            download_counter=self.download_counter
        )
        setattr(self.ui, 'app', self) # Set app reference via setattr
        self._clear_terminal()
        self.surah_names = self._load_surah_names()

    def _display_readme_page(self):
        """Reads and displays the content of the bundled README_APP.txt file."""
        readme_filename = 'README_APP.txt'
        try:
            # Get path to the bundled file (read-only)
            readme_path = get_app_path(readme_filename, writable=False)

            if not os.path.exists(readme_path):
                print(Fore.RED + f"Error: Application readme file '{readme_filename}' not found.")
                print(Fore.YELLOW + f"Expected location (approx): {readme_path}")
                sleep(3)
                return

            with open(readme_path, 'r', encoding='utf-8') as f:
                readme_content = f.read()

            self._clear_terminal()
            # Display a simple header for this page
            term_width = self.term_size.columns
            print(Fore.RED + Style.BRIGHT + "=" * term_width)
            print("QuranCLI - Application Notes & Updates".center(term_width))
            print(Fore.RED + Style.BRIGHT + "=" * term_width + Style.RESET_ALL)
            print("\n") # Add some space

            # Print the actual content from the file
            print(Fore.WHITE + readme_content)

            # Footer and wait prompt
            print("\n" + Fore.RED + Style.BRIGHT + "-" * term_width + Style.RESET_ALL)
            input(Fore.YELLOW + "\nPress Enter to return to the main menu..." + Style.RESET_ALL)
            # No need to clear here, main loop will handle it

        except FileNotFoundError:
            # This case is less likely now with the os.path.exists check, but keep for safety
            print(Fore.RED + f"Error: Could not find the application readme file '{readme_filename}'.")
            sleep(3)
        except Exception as e:
            print(Fore.RED + f"Error reading or displaying readme file: {e}")
            sleep(3)
        
    def _load_preferences(self):
        """Load preferences from file, always using QuranCLI-Settings.json."""
        if not self.preferences_file:
            return {}
        try:
            with open(self.preferences_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            print(Fore.YELLOW + f"Preferences file '{self.preferences_file}' is corrupted, resetting.")
            return {}
        except Exception as e:
            print(Fore.RED + f"Error loading preferences from '{self.preferences_file}': {e}")
            return {}

    def _save_preferences(self):
        """Save preferences to file, always using QuranCLI-Settings.json."""
        if not self.preferences_file:
            print(Fore.RED + "Error: Preferences file path not determined. Cannot save.")
            return
        try:
            pref_dir = os.path.dirname(self.preferences_file)
            if pref_dir:
                os.makedirs(pref_dir, exist_ok=True)
            
            # Add debug to check data validity
            try:
                # Make a copy to avoid JSON serialization issues
                import copy
                prefs_to_save = copy.deepcopy(self.preferences)
                
                # Test JSON serialization before writing
                json_data = json.dumps(prefs_to_save, ensure_ascii=False, indent=2)
                
                # If we get here, JSON serialization succeeded
                with open(self.preferences_file, 'w', encoding='utf-8') as f:
                    f.write(json_data)
            except TypeError as json_error:
                print(Fore.RED + f"JSON serialization error: {json_error}")
                # Identify the problematic part
                print(Fore.YELLOW + "Checking preferences for non-JSON-serializable objects...")
                for key, value in self.preferences.items():
                    try:
                        json.dumps({key: value})
                    except TypeError:
                        print(Fore.RED + f"Problem found in key: {key}, value type: {type(value)}")
                        if key == "bookmarks":
                            for surah_key, bookmarks in value.items():
                                try:
                                    json.dumps({surah_key: bookmarks})
                                except TypeError:
                                    print(Fore.RED + f"Problem in surah {surah_key}, bookmarks: {bookmarks}")
                raise
        except Exception as e:
            print(Fore.RED + f"Error saving preferences to '{self.preferences_file}': {e}")
            import traceback
            print(traceback.format_exc())

    def _load_surah_names(self):
        """Load simpler surah names directly from the CACHED data for search functionality."""
        surah_names = {}
        print(f"{Fore.YELLOW}Loading surah names from cache for search...{Style.RESET_ALL}") # Info message
        for i in range(1, 115):
            try:
                # Access the cache directly using the API client's cache instance
                cached_data = self.client.cache.get_surah(i)
                if cached_data and 'surahName' in cached_data:
                    # Use the 'surahName' field from the cached data (e.g., "Al-Fatiha")
                    surah_names[i] = cached_data['surahName']
                else:
                    # Fallback if cache is missing or incomplete for this surah
                    print(f"{Fore.YELLOW}Warning: Cache missing 'surahName' for Surah {i}. Using fallback.{Style.RESET_ALL}", file=sys.stderr)
                    surah_names[i] = f"Surah {i}" # Fallback name
            except Exception as e:
                 print(f"{Fore.RED}Error loading cached name for surah {i}: {e}{Style.RESET_ALL}", file=sys.stderr)
                 surah_names[i] = f"Surah {i}" # Fallback on error

        # Check if loading failed significantly
        if len(surah_names) < 114 or all(name.startswith("Surah ") for name in surah_names.values()):
             print(f"{Fore.RED}Error: Failed to load most surah names from cache. Search may be impaired.{Style.RESET_ALL}", file=sys.stderr)

        print(f"{Fore.GREEN}Finished loading surah names from cache.{Style.RESET_ALL}")
        return surah_names

    def _clear_terminal(self):
        self.ui.clear_terminal()

    def _display_header(self):
        # Pass the currently loaded theme color to the UI method
        self.ui.display_header(QURAN_CLI_ASCII, theme_color=self.theme_color)
        
    def _handle_theme_selection(self):
        """Handles the UI interaction for selecting a theme."""
        self._clear_terminal()
        self._display_header() # Show header in current theme before selection
        print(Fore.GREEN + Style.BRIGHT + "🎨 Select Theme Color for ASCII Art:")
        print(Fore.RED + "  1. Red (Default)")
        print(Fore.WHITE + "  2. White")
        print(Fore.GREEN + "  3. Green")
        print(Fore.BLUE + "  4. Blue")        # Added
        print(Fore.YELLOW + "  5. Yellow")      # Added
        print(Fore.MAGENTA + "  6. Magenta")    # Added
        print(Fore.CYAN + "  7. Cyan")        # Added
        print(Fore.YELLOW + "\n  q. Cancel")

        try:
            choice = input(Fore.BLUE + "\nEnter choice: " + Fore.WHITE).strip().lower()
            new_theme = None
            if choice == '1':
                new_theme = 'red'
            elif choice == '2':
                new_theme = 'white'
            elif choice == '3':
                new_theme = 'green'
            elif choice == '4':          # Added
                new_theme = 'blue'
            elif choice == '5':          # Added
                new_theme = 'yellow'
            elif choice == '6':          # Added
                new_theme = 'magenta'
            elif choice == '7':          # Added
                new_theme = 'cyan'
            elif choice == 'q':
                print(Fore.YELLOW + "Theme selection cancelled.")
                sleep(1)
                return # Go back without changing

            if new_theme:
                self.preferences['theme_color'] = new_theme
                self.theme_color = new_theme # Update the instance variable immediately
                self._save_preferences()
                print(Fore.GREEN + f"\n✅ Theme set to {new_theme.capitalize()}.")
                sleep(1.5)
            else:
                print(Fore.RED + "Invalid choice.")
                sleep(1)
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nTheme selection cancelled.")
            sleep(1)
        except Exception as e:
            print(Fore.RED + f"Error setting theme: {e}")
            sleep(1)

    def run(self):
        while True:
            try:
                self._clear_terminal()
                self._display_header()

                print(Fore.RED + "┌─" + Fore.RED + Style.BRIGHT + " Select Surah")  # Move this line here
                surah_number = self._get_surah_number()

                if surah_number is None:
                    # Exit the run loop if _get_surah_number returns None (quit or exit)
                    break

                try:
                    print(Style.BRIGHT + Fore.GREEN + "\n" + "=" * 52)

                    # --- Check if get_surah_info returned None ---
                    surah_info = self.data_handler.get_surah_info(surah_number)
                    if surah_info is None:
                        print(Fore.RED + f"Error: Could not retrieve information for Surah {surah_number}. Returning to main menu.")
                        sleep(2)
                        continue # Go back to the start of the main loop
                    # --- End Check ---

                    # Surah Information Header (This part remains the same, uses updated SurahInfo)
                    box_width = 52
                    separator = "─" * box_width
                    print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "📜 Surah Information")
                    print(Fore.RED + f"│ • {Fore.CYAN}Name:       {Fore.WHITE}{surah_info.surah_name}")
                    print(Fore.RED + f"│ • {Fore.CYAN}Arabic:     {Fore.WHITE}{surah_info.surah_name_ar}")
                    # --- ADD/MODIFY Fields based on new SurahInfo ---
                    print(Fore.RED + f"│ • {Fore.CYAN}Translation:{Fore.WHITE}{surah_info.translation}")
                    print(Fore.RED + f"│ • {Fore.CYAN}Type:       {Fore.WHITE}{surah_info.type.capitalize()}")
                    # --- Use total_verses from SurahInfo ---
                    print(Fore.RED + f"│ • {Fore.CYAN}Total Ayahs:{Fore.WHITE} {surah_info.total_verses}")
                    # --- REMOVE Revelation Place if not needed, replaced by Type ---
                    # print(Fore.RED + f"│ • {Fore.CYAN}Revelation: {Fore.WHITE}{surah_info.revelation_place}")
                    print(Fore.RED + "╰" + separator)

                    while True:
                        try:
                            # Use total_verses from the updated surah_info
                            start, end = self._get_ayah_range(surah_info.total_verses)
                            ayahs = self.data_handler.get_ayahs(surah_number, start, end)
                            # Check if ayahs list is empty due to error in get_ayahs
                            if not ayahs and start <= end : # Only show error if range was valid but no data returned
                                print(Fore.RED + f"Error: Could not retrieve ayahs {start}-{end} for Surah {surah_number}.")
                                sleep(2)
                                # Decide whether to break inner loop or allow retry
                                break # Break to ask_yes_no which likely returns to main menu
                            self.ui.display_ayahs(ayahs, surah_info) # display_ayahs now handles description internally

                            if not self._ask_yes_no(surah_info.surah_name):
                                # No need to clear/display header here, outer loop does it
                                # self._clear_terminal()
                                # self._display_header()
                                break
                        except KeyboardInterrupt:
                            # print(Fore.YELLOW + "\nAyah range selection cancelled.") # Optional message
                            break # Break the inner while loop (ayah range)

                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n" + Fore.RED + "⚠ Interrupted! Returning to main menu.")
                    continue  # Continue to the outer loop (surah selection)

            except KeyboardInterrupt:
                # Allow KeyboardInterrupt to propagate to the top level handler
                raise


    def _display_surah_list(self):
        """Display surah names in multiple columns."""
        self._clear_terminal()
        self._display_header()
        num_surahs = len(self.surah_names)
        columns = 5  # Adjust number of columns based on terminal width
        surahs_per_column = (num_surahs + columns - 1) // columns  # Ceiling division

        print(Fore.GREEN + Style.BRIGHT + "Quran - List of Surahs:")
        print(Fore.CYAN + "-" * 25)

        for i in range(surahs_per_column):
            row_output = []
            for j in range(columns):
                surah_number = i + j * surahs_per_column
                if surah_number < num_surahs:
                    number = surah_number + 1
                    name = self.surah_names[number]
                    row_output.append(Fore.GREEN + f"{number:3d}. {Fore.WHITE}{name}".ljust(30))  # Adjust spacing
            print("".join(row_output))

        print(Fore.CYAN + "-" * 25)
        input(Fore.YELLOW + "\nPress Enter to return to the surah selection...")  # Pause
        #Clear it before re-prompting.
        self._clear_terminal()
        self._display_header()



# -------------- Fix Start for this method(_display_info)-----------
    def _display_info(self):
        """
        Displays detailed information about the application and commands.
        Now includes both long and short (Linux-style) command aliases in the help.
        """
        self._clear_terminal()
        # Use terminal width for dynamic sizing, fallback for very small terminals
        box_width = self.term_size.columns - 4 if self.term_size.columns > 40 else 60
        separator_major = Fore.RED + Style.BRIGHT + "═" * box_width + Style.RESET_ALL
        separator_minor = Fore.RED + "─" * box_width + Style.RESET_ALL

        print(separator_major)
        print(Fore.GREEN + Style.BRIGHT + "QuranCLI - Information & Help".center(box_width + len(Fore.GREEN + Style.BRIGHT)))
        print(separator_major)

        # --- Description ---
        print(Fore.WHITE + "\nA powerful terminal-based tool for interacting with the Holy Quran.")
        print(Fore.CYAN + "Read, listen to recitations, and generate video subtitles (captions).")

        # --- GitHub and Support Links ---
        print(Fore.GREEN + "\nGitHub Repository:")
        print(Fore.MAGENTA + Style.BRIGHT + "https://github.com/anonfaded/QuranCLI" + Style.RESET_ALL)
        print(Fore.GREEN + "\nSupport & Buy Me a Ko-fi:")
        print(Fore.MAGENTA + Style.BRIGHT + "https://ko-fi.com/fadedx" + Style.RESET_ALL)
        print(Fore.GREEN + "\nJoin our Discord Community:")
        print(Fore.MAGENTA + Style.BRIGHT + "https://discord.gg/kvAZvdkuuN" + Style.RESET_ALL)

        # Function to remove ANSI escape codes for length calculations
        def strip_ansi(s):
            import re
            ansi_escape = re.compile(r'\x1B[\[][0-?]*[ -/]*[@-~]')
            return ansi_escape.sub('', s)
        
        # This line was using an undefined 'options' variable - we'll use commands_info instead
        # max_cmd_len = max(len(cmd) + (len(short) + 3 if short else 0) for cmd, _, short, _ in options)

        separator_minor = "-" * 120
        box_width = 120

        # --- Commands with Short Aliases ---
        print("\n" + separator_minor)
        print(Fore.GREEN + Style.BRIGHT + "Available Commands".center(box_width))
        print(separator_minor)

        commands_info = [
            (Fore.CYAN + "1-114", "Select a Surah directly by its number."),
            (Fore.CYAN + "Surah Name", "Search for a Surah by name (e.g., 'Fatiha', 'Rahman'). Provides suggestions."),
            (Fore.CYAN + "list" + Style.DIM + "/ls" + Style.NORMAL, "Display a list of all 114 Surahs with their numbers."),
            (Fore.CYAN + "sub" + Style.NORMAL, "Generate subtitle files (.srt format) for a range of Ayahs."),
            (Fore.YELLOW + "  ↳ Use Case", "Ideal for video editors needing Quran captions."),
            (Fore.YELLOW + "  ↳ How", "Creates timestamped Arabic/English text for import into editors (e.g., CapCut)."),
            (Fore.CYAN + "bm" + Style.DIM + "/bookmarks" + Style.NORMAL, "Manage bookmarks."),
            (Fore.CYAN + "clearaudio" + Style.DIM + "/clr" + Style.NORMAL, "Delete all downloaded audio files from the cache."),
            (Fore.CYAN + "audiopath" + Style.DIM + "/ap" + Style.NORMAL, "Show and open audio cache folder."),
            (Fore.CYAN + "reverse", "Toggle Arabic text display direction within the Ayah reader."),
            (Fore.YELLOW + "  ↳ Use Case", "Fixes display issues on some terminals where Arabic appears reversed."),
            (Fore.YELLOW + "  ↳ Note", "Copied text should generally be correct regardless of display."),
            (Fore.CYAN + "info" + Style.DIM + "/i" + Style.NORMAL, "Display this help and information screen."),
            (Fore.CYAN + "theme" + Style.DIM + "/th" + Style.NORMAL, "Change the color of the Quran CLI ASCII art."),
            (Fore.CYAN + "readme" + Style.DIM + "/rd" + Style.NORMAL, "View Notes by the developer & Updates."),
            (Fore.CYAN + "quit" + Style.DIM + "/q" + Style.NORMAL + Fore.CYAN + " / exit", "Close the QuranCLI application.")
        ]

        cmd_col_width = 20
        desc_col_width = box_width - cmd_col_width - 3

        def wrap_text(text, width):
            words = text.split()
            lines = []
            current_line = ""
            for word in words:
                if len(strip_ansi(current_line + " " + word).strip()) <= width:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            return "\n".join(lines)

        for cmd, desc in commands_info:
            plain_cmd = strip_ansi(cmd)
            padding = cmd_col_width - len(plain_cmd)
            if padding < 0:
                padding = 0
            cmd_part = cmd + " " * padding
            wrapped_desc = wrap_text(desc, desc_col_width)
            desc_lines = wrapped_desc.split("\n")
            print(f"{Fore.WHITE}{cmd_part} : {desc_lines[0]}")
            for line in desc_lines[1:]:
                print(" " * (cmd_col_width + 3) + line)

        # --- Credits and Feedback remain unchanged ---
        print("\n" + separator_minor)
        print(Fore.GREEN + Style.BRIGHT + "Credits".center(box_width))
        print(separator_minor)
        print(Fore.WHITE + "  Quran Data & Audio API provided by:")
        print(f"    {Fore.CYAN}The Quran Project{Fore.WHITE} ({Fore.MAGENTA}https://github.com/The-Quran-Project/Quran-API{Fore.WHITE})")
        print(f"      {Fore.YELLOW}(API has no rate limit)")
        print(Fore.WHITE + "\n  Databases used:")
        print(f"    ({Fore.MAGENTA}https://github.com/saikothasan/quran-cloud{Fore.WHITE})")
        print(f"    ({Fore.MAGENTA}https://gist.github.com/raz0229/ad8cb85f6a92c08f7acf50d245524a5f{Fore.WHITE})")

        print("\n" + separator_minor)
        print(Fore.GREEN + Style.BRIGHT + "Feedback & Bug Reports".center(box_width))
        print(separator_minor)
        print(f"""{Fore.RED + Style.BRIGHT}                          
                                      
 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ▒▒▒▒▒▒ ▒▒▒▒▒▒▒ ▒▒▒▒▒▒▒         
 ▓▓▓▓▓▓▓ ▓▓   ▓▓▓▓    ▓▓▒▒▒▒▒▒       ▒▒ ▒▒      ▓    ▓  
 ▓▓      ▓▓▓▓▓▓▓▓▓    ▓▓      ▒▒     ▒▒ ▒▒      ▓ ▓▓ ▓▓ 
 ▓▓      ▓▓   ▓▓▓▓▓▓▓▓▓ ▒▒▒▒▒▒▒ ▒▒▒▒▒▒▒ ▒▒▒▒▒▒▒         
              """.center(box_width + len(Fore.RED + Style.BRIGHT)) + Style.RESET_ALL)
        print(Fore.WHITE + "  Found an issue or have a feature request?")
        print(Fore.WHITE + "  Please open an issue on GitHub:")
        print(f"    {Fore.MAGENTA}{Style.BRIGHT}https://github.com/anonfaded/QuranCLI/issues{Style.RESET_ALL}")

        print("\n" + separator_major)
        input(Fore.YELLOW + "\nPress Enter to return to the main menu..." + Style.RESET_ALL)
# -------------- Fix Ended for this method(_display_info)-----------




# -------------- Fix Start for this method(_get_surah_number)-----------
    def _get_surah_number(self) -> Optional[int]:
        """
        Prompt user for Surah selection or command.
        Supports both long and short (Linux-style) commands.
        Displays commands in a clean, aligned, and readable format with colons aligned.
        Now includes a command to open the bookmark management menu.
        """
        box_width = 38  # Wider for better alignment
        separator = "─" * box_width

        # Command display tuples: (command(s), description)
        commands = [
            (f"{Fore.CYAN}1-114{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Select Surah by number"),
            (f"{Fore.CYAN}Surah Name{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Search Surah {Style.DIM}(e.g., 'Rahman'){Style.RESET_ALL}"),
            (f"{Fore.CYAN}list{Style.DIM}/ls{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Display list of Surahs"),
            (f"{Fore.CYAN}sub{Style.DIM}/sub{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Create subtitles for Ayahs"),
            (f"{Fore.CYAN}bookmarks{Style.DIM}/bm{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Manage bookmarks"),
            (f"{Fore.CYAN}backup{Style.DIM}/bk{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Backup/restore all app settings"),
            (f"{Fore.CYAN}clearaudio{Style.DIM}/clr{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Clear audio cache"),
            (f"{Fore.CYAN}audiopath{Style.DIM}/ap{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Show and open audio cache folder"),
            (f"{Fore.CYAN}info{Style.DIM}/i{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Show help and information"),
            (f"{Fore.CYAN}theme{Style.DIM}/th{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Change ASCII art color"),
            (f"{Fore.RED}readme{Style.DIM}/rd{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}View Notes by the developer & Updates"),
            (f"{Fore.CYAN}quit{Style.DIM}/q{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Exit the application"),
        ]

        # Calculate the max length of command strings (without color codes)
        def strip_ansi(s):
            import re
            ansi_escape = re.compile(r'\x1B[\[][0-?]*[ -/]*[@-~]')
            return ansi_escape.sub('', s)
        max_cmd_len = max(len(strip_ansi(cmd)) for cmd, _ in commands)

        while True:
            try:
                self._clear_terminal()
                self._display_header()

                # Display main menu in a clean, aligned format with colons aligned
                print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "📜 Available Commands")
                for cmd, desc in commands:
                    pad = " " * (max_cmd_len - len(strip_ansi(cmd)))
                    print(Fore.RED + f"│ → {cmd}{pad} : {Style.DIM}{desc}{Style.RESET_ALL}")
                print(Fore.RED + "╰" + separator)
                print(Style.DIM + Fore.WHITE + "\nType any of the above commands and press Enter.")

                print(Style.BRIGHT + Fore.GREEN + "\nEnter command:" + Style.DIM + Fore.WHITE )
                try:
                    user_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠️  No way out yet, you can't escape now. Try again.")
                    continue  # Restart the loop instead of exiting

                def typewriter_print(self, text: str, delay: float = 0.05):
                    """Print text with typewriter effect"""
                    for char in text:
                        print(Fore.RED + char, end='', flush=True)
                        sleep(delay)
                    print()  # New line at the end

                # Handle both long and short commands
                if user_input in ['quit', 'exit', 'q']:
                    message = "\n✨ As-salamu alaykum! Thank you for using QuranCLI!"
                    typewriter_print(self, message)
                    sleep(3.0)
                    return None
                elif user_input in ['list', 'ls']:
                    self._display_surah_list()
                    continue
                elif user_input == 'sub':
                    surah_number = self._get_surah_number_for_subtitle()
                    if surah_number is None:
                        continue
                    surah_info = self.data_handler.get_surah_info(surah_number)
                    self.ui.display_subtitle_menu(surah_info)
                    continue
                elif user_input in ['bm', 'bookmarks']:
                    self._bookmark_menu()
                    continue
                elif user_input in ['bk', 'backup']:
                    self.backup_restore_menu()
                    continue
                elif user_input in ['clearaudio', 'clr']:
                    self._clear_audio_cache()
                    continue
                elif user_input in ['audiopath', 'ap']:
                    self._show_audio_cache_path()
                    continue
                elif user_input in ['info', 'i']:
                    self._display_info()
                    continue
                elif user_input in ['readme', 'rd']:
                    self._display_readme_page()
                    continue
                elif user_input in ['theme', 'th']:
                    self._handle_theme_selection()
                    continue
                elif user_input.isdigit():
                    number = int(user_input)
                    if 1 <= number <= 114:
                        return number
                    raise ValueError

                # Attempt fuzzy matching for Surah names
                import difflib
                close_matches = difflib.get_close_matches(user_input, self.surah_names.values(), n=5, cutoff=0.5)
                if close_matches:
                    print("\n")
                    print(Fore.RED + "╭─" + Style.BRIGHT + Fore.MAGENTA + "🤔 Did you mean one of these?")
                    for idx, match in enumerate(close_matches, 1):
                        surah_number = [num for num, name in self.surah_names.items() if name == match][0]
                        print(f"{Fore.RED}├ {Fore.GREEN}{idx}. {Fore.CYAN}{match} {Style.DIM}{Fore.WHITE}(Surah {surah_number})")
                    print(Fore.RED + "╰" + separator + '\n')
                    while True:
                        try:
                            print(Fore.GREEN + "Select a number from the list, or 'r' to retry:")
                            user_choice = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                            if user_choice.isdigit():
                                choice_idx = int(user_choice) - 1
                                if 0 <= choice_idx < len(close_matches):
                                    selected_surah = close_matches[choice_idx]
                                    return [num for num, name in self.surah_names.items() if name == selected_surah][0]
                                else:
                                    print(Fore.RED + "Invalid choice. Please select a number from the list or 'r' to retry.")
                            elif user_choice.lower() == 'r':
                                break
                            else:
                                print(Fore.RED + "Invalid choice. Please select a number from the list or 'r' to retry.")
                        except KeyboardInterrupt:
                            print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to surah selection.")
                            break
            except ValueError:
                print(Fore.RED + "Invalid input. Enter a number between 1-114, a Surah name, 'list', 'sub', or 'quit'")
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to main menu.")
                break
    # -------------- Fix Ended for this method(_get_surah_number)-----------





    def backup_restore_menu(self):
        """
        Show only the backup/restore menu (for use from main menu).
        This does not enter the full bookmark manager.
        Multiplatform, robust, and user-friendly.
        """
        downloads_dir = str(Path.home() / "Downloads")
        default_filename = "QuranCLI-Settings.json"
        default_path = os.path.join(downloads_dir, default_filename)

        def open_file_picker(save=False, default_path=None):
            """
            Open a file picker dialog for import/export.
            Returns selected path or None.
            Tries to use a dark theme if available (Linux/Windows).
            """
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                try:
                    root.tk.call("tk", "scaling", 1.2)
                    root.option_add("*background", "#222222")
                    root.option_add("*foreground", "#e0e0e0")
                    root.option_add("*highlightBackground", "#222222")
                    root.option_add("*highlightColor", "#e0e0e0")
                except Exception:
                    pass
                file_path = None
                if save:
                    file_path = filedialog.asksaveasfilename(
                        initialdir=os.path.dirname(default_path) if default_path else None,
                        initialfile=os.path.basename(default_path) if default_path else None,
                        title="Select location to save preferences",
                        defaultextension=".json",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                    )
                else:
                    file_path = filedialog.askopenfilename(
                        initialdir=os.path.dirname(default_path) if default_path else None,
                        title="Select preferences file to import",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                    )
                root.destroy()
                return file_path if file_path else None
            except Exception as e:
                print(Fore.RED + f"File picker error: {e}")
                return None

        def confirm_path(path, action):
            """Ask user to confirm the chosen path before proceeding."""
            print(Fore.YELLOW + f"\nYou chose: {Fore.CYAN}{path}{Fore.YELLOW} for {action}.")
            confirm = input(Fore.YELLOW + "Proceed? (y/n): " + Fore.WHITE).strip().lower()
            return confirm == 'y'

        def find_json_files_in_downloads():
            """Return a list of .json files in the user's Downloads directory."""
            try:
                files = [str(f) for f in Path(downloads_dir).glob("*.json") if f.is_file()]
                return files
            except Exception as e:
                print(Fore.RED + f"Error searching Downloads: {e}")
                return []

        box_width = 60
        print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "Backup/Restore Options")
        print(Fore.RED + f"│ → {Fore.CYAN}export{Style.DIM}/e{Style.NORMAL}{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}Backup/export your settings")
        print(Fore.RED + f"│ → {Fore.CYAN}import{Style.DIM}/i{Style.NORMAL}{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}Restore/import settings from a backup")
        print(Fore.RED + f"│ → {Fore.RED}b{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}Cancel and go back")
        print(Fore.RED + "╰" + ("─" * (box_width-2)))
        action = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
        if action in ['export', 'e']:
            print(Fore.YELLOW + f"\nPress Enter to save backup to {Fore.CYAN}{default_path}{Fore.YELLOW},")
            print(Fore.YELLOW + "or type 'picker' to open a file picker dialog, or enter a custom path, or 'b' to cancel.")
            while True:
                dest = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                if dest.lower() == 'b':
                    break
                if dest.lower() == 'picker':
                    dest = open_file_picker(save=True, default_path=default_path)
                    if not dest:
                        print(Fore.YELLOW + "No file selected. Cancelled.")
                        input(Fore.YELLOW + "Press Enter to continue...")
                        break
                if not dest:
                    dest = default_path
                if not confirm_path(dest, "backup/export"):
                    print(Fore.YELLOW + "Cancelled by user.")
                    input(Fore.YELLOW + "Press Enter to continue...")
                    break
                try:
                    shutil.copy2(self.preferences_file, dest)
                    print(Fore.GREEN + f"Preferences exported to {Fore.CYAN}{dest}{Fore.GREEN}")
                except Exception as e:
                    print(Fore.RED + f"Export failed: {e}")
                input(Fore.YELLOW + "Press Enter to continue...")
                break
        elif action in ['import', 'i']:
            print(Fore.YELLOW + f"\nPlace your backup file in {Fore.CYAN}{downloads_dir}{Fore.YELLOW} and press Enter to auto-import,")
            print(Fore.YELLOW + "or type 'picker' to open a file picker dialog, or enter a custom path, or 'b' to cancel.")
            while True:
                src = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                if src.lower() == 'b':
                    break
                if src.lower() == 'picker':
                    src = open_file_picker(save=False, default_path=default_path)
                    if not src:
                        print(Fore.YELLOW + "No file selected. Cancelled.")
                        input(Fore.YELLOW + "Press Enter to continue...")
                        break
                if not src:
                    # If no input, search for .json files in Downloads
                    json_files = find_json_files_in_downloads()
                    if not json_files:
                        print(Fore.RED + "No .json files found in Downloads."); input(Fore.YELLOW + "Press Enter to continue..."); break
                    if len(json_files) == 1:
                        src = json_files[0]
                        print(Fore.YELLOW + f"Found backup: {Fore.CYAN}{src}")
                    else:
                        print(Fore.YELLOW + "Multiple .json files found in Downloads:")
                        for idx, f in enumerate(json_files, 1):
                            print(f"{Fore.CYAN}{idx}. {f}")
                        while True:
                            sel = input(Fore.YELLOW + "Select a file by number or 'b' to cancel: " + Fore.WHITE).strip()
                            if sel.lower() == 'b':
                                src = None
                                break
                            if sel.isdigit() and 1 <= int(sel) <= len(json_files):
                                src = json_files[int(sel)-1]
                                break
                        if not src:
                            break
                if not os.path.isfile(src):
                    print(Fore.RED + "File not found."); input(Fore.YELLOW + "Press Enter to continue..."); break
                if not confirm_path(src, "import/restore"):
                    print(Fore.YELLOW + "Cancelled by user.")
                    input(Fore.YELLOW + "Press Enter to continue...")
                    break
                print(Fore.YELLOW + "Importing will overwrite your current preferences and bookmarks. Continue? (y/n)")
                confirm = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
                if confirm == 'y':
                    try:
                        with open(src, "r", encoding="utf-8") as f:
                            data = f.read()
                        json.loads(data)  # Validate JSON
                        with open(self.preferences_file, "w", encoding="utf-8") as f:
                            f.write(data)
                        print(Fore.GREEN + "Preferences imported successfully.")
                        self.preferences = self._load_preferences()
                    except Exception as e:
                        print(Fore.RED + f"Import failed: {e}")
                else:
                    print(Fore.YELLOW + "Import cancelled.")
                input(Fore.YELLOW + "Press Enter to continue...")
                break
        # Return to main menu after backup/restore
        return




# -------------- Fix Start for this method(_bookmark_menu)-----------
    def _bookmark_menu(self):
        """
        Interactive bookmark management menu for QuranCLI.
        - Multiplatform, robust, and user-friendly.
        - Preferences file is always named 'QuranCLI-Settings.json'.
        - Backup/restore supports a dark-themed file picker (where possible) and default to Downloads.
        - Clear, aligned, and color-coded options.
        - Proper error handling and debug prints.
        """
        import sys
        import shutil
        from pathlib import Path
        import tkinter as tk
        from tkinter import filedialog

        def get_surah_number_from_input(user_input):
            """Fuzzy match surah name/number, return surah number or None."""
            import difflib
            if user_input.isdigit() and 1 <= int(user_input) <= 114:
                return int(user_input)
            matches = difflib.get_close_matches(user_input, self.surah_names.values(), n=5, cutoff=0.5)
            if matches:
                print(Fore.RED + "╭─" + Style.BRIGHT + Fore.MAGENTA + "🤔 Did you mean one of these?")
                for idx, match in enumerate(matches, 1):
                    surah_number = [num for num, name in self.surah_names.items() if name == match][0]
                    print(f"{Fore.RED}│ {Fore.GREEN}{idx}. {Fore.CYAN}{match} {Style.DIM}{Fore.WHITE}(Surah {surah_number})")
                print(Fore.RED + "╰" + ("─" * 38))
                while True:
                    print(Fore.GREEN + "Select a number from the list, or 'b' to go back:")
                    user_choice = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                    if user_choice.lower() == 'b':
                        return None
                    if user_choice.isdigit():
                        choice_idx = int(user_choice) - 1
                        if 0 <= choice_idx < len(matches):
                            selected_surah = matches[choice_idx]
                            return [num for num, name in self.surah_names.items() if name == selected_surah][0]
                    print(Fore.RED + "Invalid choice. Please select a number or 'b' to go back.")
            return None

        def input_note_with_limit(max_len):
            """Input note with max length, no live counter (terminal refresh not supported)."""
            print(Fore.CYAN + f"Enter a note for this bookmark (optional, max {max_len} chars, press Enter to skip):")
            print(Fore.LIGHTBLACK_EX + "e.g. 'Favorite ayah', 'For memorization', 'Check tafsir', etc.")
            note = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()[:max_len]
            return note

        def get_ayah_text(surah_num, ayah_num):
            """Get the ayah text for display in bookmark list."""
            try:
                ayahs = self.data_handler.get_ayahs(int(surah_num), int(ayah_num), int(ayah_num))
                if ayahs and hasattr(ayahs[0], "content"):
                    return ayahs[0].content
            except Exception as e:
                print(f"[DEBUG] Error fetching ayah text: {e}")
            return ""

        def open_preferences_folder():
            """Open the folder containing the preferences file in the system file explorer."""
            pref_path = self.preferences_file
            if not pref_path:
                print(Fore.RED + "Preferences file path not found.")
                input(Fore.YELLOW + "Press Enter to continue...")
                return
            folder = os.path.dirname(pref_path)
            print(Fore.GREEN + f"Preferences file location: {pref_path}")
            print(Fore.YELLOW + "Opening preferences folder in your file explorer...")
            try:
                if sys.platform == "win32":
                    os.startfile(folder)
                elif sys.platform == "darwin":
                    subprocess.run(['open', folder], check=False)
                else:
                    try:
                        subprocess.run(['xdg-open', folder], check=False)
                    except Exception:
                        for fm in ['nautilus', 'thunar', 'dolphin', 'pcmanfm']:
                            if shutil.which(fm):
                                subprocess.run([fm, folder], check=False)
                                break
                        else:
                            print(Fore.RED + "Could not open folder: No suitable file manager found.")
                print(Fore.GREEN + "Opened folder in file explorer.")
            except Exception as e:
                print(Fore.RED + f"Error opening folder: {e}")
            input(Fore.YELLOW + "Press Enter to continue...")

        def open_file_picker(save=False, default_path=None):
            """
            Open a file picker dialog for import/export.
            Returns selected path or None.
            Tries to use a dark theme if available (Linux/Windows).
            """
            try:
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                try:
                    root.tk.call("tk", "scaling", 1.2)
                    root.option_add("*background", "#222222")
                    root.option_add("*foreground", "#e0e0e0")
                    root.option_add("*highlightBackground", "#222222")
                    root.option_add("*highlightColor", "#e0e0e0")
                except Exception:
                    pass
                file_path = None
                if save:
                    file_path = filedialog.asksaveasfilename(
                        initialdir=os.path.dirname(default_path) if default_path else None,
                        initialfile=os.path.basename(default_path) if default_path else None,
                        title="Select location to save preferences",
                        defaultextension=".json",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                    )
                else:
                    file_path = filedialog.askopenfilename(
                        initialdir=os.path.dirname(default_path) if default_path else None,
                        title="Select preferences file to import",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                    )
                root.destroy()
                return file_path if file_path else None
            except Exception as e:
                print(Fore.RED + f"File picker error: {e}")
                return None

        def confirm_path(path, action):
            """Ask user to confirm the chosen path before proceeding."""
            print(Fore.YELLOW + f"\nYou chose: {Fore.CYAN}{path}{Fore.YELLOW} for {action}.")
            confirm = input(Fore.YELLOW + "Proceed? (y/n): " + Fore.WHITE).strip().lower()
            return confirm == 'y'

        def find_json_files_in_downloads():
            """Return a list of .json files in the user's Downloads directory."""
            downloads_dir = str(Path.home() / "Downloads")
            try:
                files = [str(f) for f in Path(downloads_dir).glob("*.json") if f.is_file()]
                return files
            except Exception as e:
                print(Fore.RED + f"Error searching Downloads: {e}")
                return []

        info_text = (
            f"{Fore.GREEN}Bookmarks let you save (pin) any ayah in any surah, with an optional note (max 300 chars).\n"
            f"You can search by surah number or name, and have multiple bookmarks per surah.\n"
            f"Features: jump to bookmarks, add/edit/delete, quick Ayatul Kursi bookmarking command, open settings folder, backup/restore, and toggle Arabic reversal.\n"
            f"Tip: Use 'reverse' to toggle Arabic display if it appears inverted or not correct, 'openprefs' to open settings folder, 'backup' to backup/restore.\n"
            f"Quick Ayatul Kursi: Type 'ayatul-kursi' to instantly bookmark Ayah 255 of Surah 2 (Al-Baqarah).\n"
        )
        
        options = [
            ("1", "Jump to a bookmark", "jump", Fore.CYAN),
            ("2", "Add a bookmark", "add", Fore.CYAN),
            ("3", "Edit/Delete a bookmark", "edit", Fore.CYAN),
            ("reverse", "Toggle Arabic reversal", "rev", Fore.CYAN),
            ("openprefs", "Open preferences/settings folder", "op", Fore.CYAN),
            ("backup", "Backup/restore all app settings", "bk", Fore.CYAN),
            ("ayatul-kursi", "Quick bookmark Ayatul Kursi", "ak", Fore.CYAN),
            ("info", "Show bookmark manager info/help", "i", Fore.CYAN),
            ("4", "Back to main menu", "back", Fore.RED + Style.BRIGHT),
        ]
        def strip_ansi(s):
            import re
            ansi_escape = re.compile(r'\x1B[\[][0-?]*[ -/]*[@-~]')
            return ansi_escape.sub('', s)
        max_cmd_len = max(len(cmd) + (len(short) + 3 if short else 0) for cmd, _, short, _ in options)

        while True:
            try:
                self._clear_terminal()
                box_width = 60
                separator = "─" * box_width
                print(Fore.RED + Style.BRIGHT + "\n📑 Bookmark Manager".ljust(box_width))
                print(Fore.RED + separator)
                print(Fore.GREEN + Style.BRIGHT + "\nSaved Bookmarks".center(box_width))
                print(Fore.RED + separator)
                bookmarks = self.list_bookmarks()
                grouped = {}
                for surah, data in bookmarks.items():
                    # Ensure each surah's bookmarks are a list of dicts
                    if isinstance(data, list):
                        bookmarks_list = [b for b in data if isinstance(b, dict)]
                        # Only add surah if it has valid bookmarks
                        if bookmarks_list:
                            grouped[surah] = bookmarks_list
                    elif isinstance(data, dict):
                        grouped[surah] = [data]
                    else:
                        grouped[surah] = []
                    
                    # Remove any surah that ended up with an empty list
                    if surah in grouped and not grouped[surah]:
                        del grouped[surah]
                        
                if grouped:
                    for surah in sorted(grouped, key=lambda x: int(x)):
                        surah_name = self.surah_names.get(int(surah), f"Surah {surah}")
                        print(Fore.CYAN + f"Surah {surah} ({surah_name}):")
                        for idx, entry in enumerate(grouped[surah], 1):
                            ayah = entry.get("ayah", '?')
                            ayah_text = get_ayah_text(surah, ayah)
                            note = entry.get("note", "")
                            date_added = entry.get("date_added", "")
                            
                            note_disp = (Fore.MAGENTA + f"Note: {note}" if note else Fore.LIGHTBLACK_EX + "No note")
                            date_disp = (Fore.YELLOW + f"Added: {date_added}" if date_added else "")
                            
                            print(f"  {Fore.GREEN}{idx}. Ayah {ayah} {Fore.LIGHTBLACK_EX}- {ayah_text}")
                            print(f"     {note_disp}")
                            if date_added:
                                print(f"     {date_disp}")
                        print(Fore.RED + ("─" * box_width))
                else:
                    print(Fore.LIGHTBLACK_EX + "  No bookmarks saved yet.")
                    print(Fore.RED + ("─" * box_width))
                print(Fore.CYAN + "\nOptions:")
                print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "Bookmark Actions")
                for cmd, desc, short, color in options:
                    if short:
                        cmd_str = f"{color}{cmd}{Style.DIM}/{short}{Style.NORMAL}{Style.RESET_ALL}"
                    else:
                        cmd_str = f"{color}{cmd}{Style.RESET_ALL}"
                    pad = " " * (max_cmd_len - len(cmd) - (len(short) + 1 if short else 0))
                    print(Fore.RED + f"│ → {cmd_str}{pad} : {Style.NORMAL}{Fore.WHITE}{desc}{Style.RESET_ALL}")
                print(Fore.RED + "╰" + ("─" * (box_width-2)))
                choice = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()

                # Map short commands to long
                cmd_map = {
                    "jump": "1", "add": "2", "edit": "3", "rev": "reverse", "op": "openprefs",
                    "bk": "backup", "ak": "ayatul-kursi", "back": "4", "i": "info"
                }
                for _, _, short, _ in options:
                    if choice == short:
                        choice = cmd_map[short]

                if choice == 'reverse':
                    self.data_handler.toggle_arabic_reversal()
                    print(Fore.GREEN + "Arabic reversal toggled.")
                    input(Fore.YELLOW + "Press Enter to continue...")
                    continue
                if choice == 'info':
                    self._clear_terminal()
                    print(Fore.RED + Style.BRIGHT + "\n📑 Bookmark Manager Info\n" + ("─" * 60))
                    print(info_text)
                    print("─" * 60)
                    input(Fore.YELLOW + "Press Enter to return to the bookmark manager...")
                    continue
                if choice == 'openprefs':
                    open_preferences_folder()
                    continue
                if choice == 'backup':
                    downloads_dir = str(Path.home() / "Downloads")
                    default_filename = "QuranCLI-Settings.json"
                    default_path = os.path.join(downloads_dir, default_filename)
                    print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "Backup/Restore Options")
                    print(Fore.RED + f"│ → {Fore.CYAN}export{Style.DIM}/e{Style.NORMAL}{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}Backup/export your settings")
                    print(Fore.RED + f"│ → {Fore.CYAN}import{Style.DIM}/i{Style.NORMAL}{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}Restore/import settings from a backup")
                    print(Fore.RED + f"│ → {Fore.RED}b{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}Cancel and go back")
                    print(Fore.RED + "╰" + ("─" * (box_width-2)))
                    action = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
                    if action in ['export', 'e']:
                        print(Fore.YELLOW + f"\nPress Enter to save backup to {Fore.CYAN}{default_path}{Fore.YELLOW},")
                        print(Fore.YELLOW + "or type 'picker' to open a file picker dialog, or enter a custom path, or 'b' to cancel.")
                        while True:
                            dest = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                            if dest.lower() == 'b':
                                break
                            if dest.lower() == 'picker':
                                dest = open_file_picker(save=True, default_path=default_path)
                                if not dest:
                                    print(Fore.YELLOW + "No file selected. Cancelled.")
                                    input(Fore.YELLOW + "Press Enter to continue...")
                                    break
                            if not dest:
                                dest = default_path
                            if not confirm_path(dest, "backup/export"):
                                print(Fore.YELLOW + "Cancelled by user.")
                                input(Fore.YELLOW + "Press Enter to continue...")
                                break
                            try:
                                if self.preferences_file:
                                    shutil.copy2(self.preferences_file, dest)
                                    print(Fore.GREEN + f"Preferences exported to {Fore.CYAN}{dest}{Fore.GREEN}")
                                else:
                                    print(Fore.RED + "Error: No preferences file path found.")
                            except Exception as e:
                                print(Fore.RED + f"Export failed: {e}")
                            input(Fore.YELLOW + "Press Enter to continue...")
                            break
                    elif action in ['import', 'i']:
                        print(Fore.YELLOW + f"\nPlace your backup file in {Fore.CYAN}{downloads_dir}{Fore.YELLOW} and press Enter to auto-import,")
                        print(Fore.YELLOW + "or type 'picker' to open a file picker dialog, or enter a custom path, or 'b' to cancel.")
                        while True:
                            src = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                            if src.lower() == 'b':
                                break
                            if src.lower() == 'picker':
                                src = open_file_picker(save=False, default_path=default_path)
                                if not src:
                                    print(Fore.YELLOW + "No file selected. Cancelled.")
                                    input(Fore.YELLOW + "Press Enter to continue...")
                                    break
                            if not src:
                                # If no input, search for .json files in Downloads
                                json_files = find_json_files_in_downloads()
                                if not json_files:
                                    print(Fore.RED + "No .json files found in Downloads."); input(Fore.YELLOW + "Press Enter to continue..."); break
                                if len(json_files) == 1:
                                    src = json_files[0]
                                    print(Fore.YELLOW + f"Found backup: {Fore.CYAN}{src}")
                                else:
                                    print(Fore.YELLOW + "Multiple .json files found in Downloads:")
                                    for idx, f in enumerate(json_files, 1):
                                        print(f"{Fore.CYAN}{idx}. {f}")
                                    while True:
                                        sel = input(Fore.YELLOW + "Select a file by number or 'b' to cancel: " + Fore.WHITE).strip()
                                        if sel.lower() == 'b':
                                            src = None
                                            break
                                        if sel.isdigit() and 1 <= int(sel) <= len(json_files):
                                            src = json_files[int(sel)-1]
                                            break
                                    if not src:
                                        break
                            if not os.path.isfile(src):
                                print(Fore.RED + "File not found."); input(Fore.YELLOW + "Press Enter to continue..."); break
                            if not confirm_path(src, "import/restore"):
                                print(Fore.YELLOW + "Cancelled by user.")
                                input(Fore.YELLOW + "Press Enter to continue...")
                                break
                            print(Fore.YELLOW + "Importing will overwrite your current preferences and bookmarks. Continue? (y/n)")
                            confirm = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
                            if confirm == 'y':
                                try:
                                    with open(src, "r", encoding="utf-8") as f:
                                        data = f.read()
                                    json.loads(data)  # Validate JSON
                                    if self.preferences_file:
                                        with open(self.preferences_file, "w", encoding="utf-8") as f:
                                            f.write(data)
                                        print(Fore.GREEN + "Preferences imported successfully.")
                                        self.preferences = self._load_preferences()
                                    else:
                                        print(Fore.RED + "Error: No preferences file path found.")
                                except Exception as e:
                                    print(Fore.RED + f"Import failed: {e}")
                            else:
                                print(Fore.YELLOW + "Import cancelled.")
                            input(Fore.YELLOW + "Press Enter to continue...")
                            break
                    else:
                        continue
                    continue
                if choice == 'ayatul-kursi':
                    print(Fore.GREEN + "Quick-adding Ayatul Kursi bookmark (Surah 2, Ayah 255)")
                    surah_key = "2" 
                    ayah_num = 255
                    note = "Ayatul Kursi (The Throne Verse)"
                    if "bookmarks" not in self.preferences:
                        self.preferences["bookmarks"] = {}
                    if surah_key not in self.preferences["bookmarks"]:
                        self.preferences["bookmarks"][surah_key] = []
                    
                    # Check if bookmark already exists
                    already_exists = False
                    for b in self.preferences["bookmarks"][surah_key]:
                        if isinstance(b, dict) and b.get("ayah") == ayah_num:
                            already_exists = True
                            break
                            
                    if already_exists:
                        print(Fore.YELLOW + "Ayatul Kursi already bookmarked.")
                        input(Fore.YELLOW + "Press Enter to continue...")
                        continue
                    
                    # Add current date and time in the desired format
                    current_datetime = datetime.now()
                    date_str = current_datetime.strftime("%A, %d %b %Y %I:%M %p")
                    
                    # Remove debug prints
                    try:
                        # Create bookmark object
                        new_bookmark = {
                            "ayah": ayah_num,
                            "note": note,
                            "date_added": date_str
                        }
                        
                        # Append to bookmarks and save
                        self.preferences["bookmarks"][surah_key].append(new_bookmark)
                        self._save_preferences()
                        print(Fore.GREEN + "Ayatul Kursi bookmarked (Surah 2, Ayah 255).")
                    except Exception as e:
                        print(Fore.RED + f"Error adding bookmark: {e}")
                        
                    input(Fore.YELLOW + "Press Enter to continue...")
                elif choice == '2':
                    # Add bookmark
                    print(Fore.CYAN + "Enter surah number or name to bookmark (or 'b' to go back):")
                    print(Fore.LIGHTBLACK_EX + "Example: 23 or Al-Muminoon")
                    surah_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                    if surah_input.lower() == 'b':
                        continue
                    surah_num = get_surah_number_from_input(surah_input)
                    if not surah_num:
                        print(Fore.RED + "Could not find surah. Try again."); input(Fore.YELLOW + "Press Enter to continue..."); continue
                    surah_info = self.data_handler.get_surah_info(int(surah_num))
                    if not surah_info:
                        print(Fore.RED + "Invalid surah."); input(Fore.YELLOW + "Press Enter to continue..."); continue
                    print(Fore.CYAN + f"Enter ayah number to bookmark in Surah {surah_num} (1-{surah_info.total_verses}, or 'b' to go back):")
                    while True:
                        ayah_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                        if ayah_input.lower() == 'b':
                            break
                        if ayah_input.isdigit() and 1 <= int(ayah_input) <= surah_info.total_verses:
                            break
                        print(Fore.RED + f"Invalid ayah number. Enter 1-{surah_info.total_verses} or 'b' to go back.")
                    if ayah_input.lower() == 'b':
                        continue
                    note = input_note_with_limit(300)
                    
                    # Initialize bookmarks structure if needed
                    if "bookmarks" not in self.preferences:
                        self.preferences["bookmarks"] = {}
                    surah_key = str(surah_num)
                    if surah_key not in self.preferences["bookmarks"]:
                        self.preferences["bookmarks"][surah_key] = []
                    
                    # Check if bookmark already exists - fixed the comparison logic
                    already_exists = False
                    ayah_num = int(ayah_input)
                    for b in self.preferences["bookmarks"][surah_key]:
                        if isinstance(b, dict) and b.get("ayah") == ayah_num:
                            already_exists = True
                            break
                            
                    if already_exists:
                        print(Fore.YELLOW + "Bookmark for this ayah already exists.")
                        input(Fore.YELLOW + "Press Enter to continue...")
                        continue
                    
                    # Add current date and time in the desired format
                    current_datetime = datetime.now()
                    date_str = current_datetime.strftime("%A, %d %b %Y %I:%M %p")
                    
                    try:
                        # Create bookmark object
                        new_bookmark = {
                            "ayah": ayah_num,
                            "note": note,
                            "date_added": date_str
                        }
                        
                        # Append to bookmarks and save
                        self.preferences["bookmarks"][surah_key].append(new_bookmark)
                        self._save_preferences()
                        print(Fore.GREEN + f"Bookmark set for Surah {surah_num}, Ayah {ayah_input}.")
                    except Exception as e:
                        print(Fore.RED + f"Error adding bookmark: {e}")
                        
                    input(Fore.YELLOW + "Press Enter to continue...")
                elif choice == '3':
                    # List all bookmarks with index and color same surahs
                    all_bookmarks = []
                    
                    # Get all bookmarks that exist and are properly formatted
                    if "bookmarks" in self.preferences:
                        for surah in sorted(self.preferences["bookmarks"].keys(), key=lambda x: int(x)):
                            if isinstance(self.preferences["bookmarks"][surah], list):
                                for entry in self.preferences["bookmarks"][surah]:
                                    if isinstance(entry, dict):
                                        all_bookmarks.append((surah, entry))
                                        
                    if not all_bookmarks:
                        print(Fore.YELLOW + "No bookmarks to edit or delete.")
                        input(Fore.YELLOW + "Press Enter to continue...")
                        continue
                    print(Fore.CYAN + "\nSelect a bookmark to edit/delete:")
                    # Assign a color to each surah for consistent coloring
                    surah_color_map = {}
                    surah_colors = [Fore.CYAN, Fore.GREEN, Fore.MAGENTA, Fore.YELLOW, Fore.BLUE, Fore.LIGHTCYAN_EX, Fore.LIGHTGREEN_EX, Fore.LIGHTMAGENTA_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTBLUE_EX]
                    color_idx = 0
                    for surah, _ in all_bookmarks:
                        if surah not in surah_color_map:
                            surah_color_map[surah] = surah_colors[color_idx % len(surah_colors)]
                            color_idx += 1
                    for idx, (surah, entry) in enumerate(all_bookmarks, 1):
                        surah_name = self.surah_names.get(int(surah), f"Surah {surah}")
                        ayah = entry.get("ayah", '?')
                        note = entry.get("note", "")
                        date_added = entry.get("date_added", "")
                        color = surah_color_map[surah]
                        
                        bookmark_info = f"Surah {surah} ({surah_name}), Ayah {ayah}"
                        if date_added:
                            bookmark_info += f" {Fore.LIGHTBLACK_EX}- Added: {date_added}"
                        if note:
                            bookmark_info += f" {Fore.LIGHTBLACK_EX}- {note}"
                            
                        print(f"{color}{idx}. {bookmark_info}{Style.RESET_ALL}")
                    print(Fore.YELLOW + "Enter the number of the bookmark to edit/delete, or 'b' to cancel.")
                    sel = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                    if sel.lower() == 'b':
                        continue
                    if sel.isdigit() and 1 <= int(sel) <= len(all_bookmarks):
                        surah, entry = all_bookmarks[int(sel) - 1]
                        ayah = entry.get("ayah", 1)
                        note = entry.get("note", "")
                        date_added = entry.get("date_added", "")
                        print(Fore.CYAN + f"Selected Surah {surah}, Ayah {ayah}.")
                        print(Fore.YELLOW + "Enter 'e' to edit note, 'd' to delete, or 'b' to cancel.")
                        action = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
                        if action == 'e':
                            new_note = input_note_with_limit(300)
                            # Update note in preferences
                            surah_key = str(surah)
                            for b in self.preferences["bookmarks"][surah_key]:
                                if isinstance(b, dict) and b.get("ayah") == ayah:
                                    b["note"] = new_note
                                    b["date_added"] = datetime.now().strftime("%A, %d %b %Y %I:%M %p")  # Update date when modifying bookmark
                                    self._save_preferences()
                                    print(Fore.GREEN + "Note updated.")
                                    break
                            input(Fore.YELLOW + "Press Enter to continue...")
                        elif action == 'd':
                            # Ask for confirmation before deletion
                            confirm = input(Fore.RED + "Are you sure you want to delete this bookmark? (y/n): " + Fore.WHITE).strip().lower()
                            if confirm != 'y':
                                print(Fore.YELLOW + "Deletion cancelled.")
                                input(Fore.YELLOW + "Press Enter to continue...")
                                continue
                            surah_key = str(surah)
                            before = len(self.preferences["bookmarks"][surah_key])
                            self.preferences["bookmarks"][surah_key] = [
                                b for b in self.preferences["bookmarks"][surah_key]
                                if not (isinstance(b, dict) and b.get("ayah") == ayah)
                            ]
                            after = len(self.preferences["bookmarks"][surah_key])
                            self._save_preferences()
                            if before != after:
                                print(Fore.GREEN + "Bookmark deleted.")
                            else:
                                print(Fore.YELLOW + "Bookmark not found.")
                            input(Fore.YELLOW + "Press Enter to continue...")
                        elif action == 'b':
                            continue
                        else:
                            print(Fore.RED + "Invalid action.")
                            input(Fore.YELLOW + "Press Enter to continue...")
                    else:
                        print(Fore.RED + "Invalid selection.")
                        input(Fore.YELLOW + "Press Enter to continue...")
                    continue
                elif choice == '4':
                    break
                else:
                    print(Fore.RED + "Invalid choice. Please enter a valid option."); input(Fore.YELLOW + "Press Enter to continue...")
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nBookmark menu cancelled. Returning to main menu.")
                break
            except Exception as e:
                print(Fore.RED + f"Error in bookmark menu: {e}")
                # Add the following debug information
                import traceback
                print(Fore.YELLOW + "Debug information:")
                print(Fore.YELLOW + f"Choice: {choice}")
                print(Fore.YELLOW + f"Error type: {type(e).__name__}")
                print(Fore.YELLOW + f"Full traceback: {traceback.format_exc()}")
                input(Fore.YELLOW + "Press Enter to continue...")
# -------------- Fix Ended for this method(_bookmark_menu)-----------

    def _get_surah_number_for_subtitle(self) -> Optional[int]:
            """Helper function to get surah number specifically for subtitle generation."""
            while True:
                try:
                    self._clear_terminal()
                    self._display_header()

                    box_width = 26  # Adjust width if needed
                    separator = "─" * box_width

                    # Descriptive command list with colors
                    print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "📜 Available Commands (Subtitle Creation)")
                    print(Fore.RED + f"│ • {Fore.CYAN}1-114{Fore.WHITE}: Select Surah by number")
                    print(Fore.RED + f"│ • {Fore.CYAN}q{Fore.WHITE}: Return to main menu")
                    print(Fore.RED + "╰" + separator)
                        
                    # Helper Text
                    print(Style.DIM + Fore.WHITE + "\nType any of the above commands and press Enter.")

                    # Prompt user for input
                    print(Fore.GREEN + "\nEnter Surah number:" + Style.DIM + Fore.WHITE)
                    user_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()

                    if user_input in ['q', 'quit', 'exit']:
                        return None  # User wants to quit

                    if user_input.isdigit():
                        number = int(user_input)
                        if 1 <= number <= 114:
                            return number
                        else:
                            print(Fore.RED + "Invalid Surah number. Please enter a number between 1 and 114 or 'q' to return")
                    else:
                        print(Fore.RED + "Invalid input. Please enter a number or 'q'")

                except ValueError:
                    print(Fore.RED + "Invalid input. Please enter a valid number.")
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to main menu.")
                    return None #Returning none as keyboard interupt.
            
    def _get_ayah_range(self, total_ayah: int) -> tuple:
        """
        Prompt the user for an ayah range, or accept 'all' to select the full surah.
        Empty input (just pressing Enter) also selects the full surah.
        Returns a tuple (start, end).
        """
        while True:
            try:
                print(Fore.RED + "\n┌─" + Fore.GREEN + Style.BRIGHT + f" Ayah Selection (1-{total_ayah})")
                print(Fore.RED + "├──╼ " + Fore.MAGENTA + "Start" + f" {Style.DIM}(or type 'all' or press Enter for the whole surah){Style.RESET_ALL}:\n", end="")
                user_input = input(Fore.RED + "│ ❯ " + Fore.WHITE).strip().lower()
                if user_input == 'all' or user_input == '':
                    return 1, total_ayah
                start = int(user_input)
                print(Fore.RED + "├──╼ " + Fore.MAGENTA + "End" + ":\n", end="")
                end = int(input(Fore.RED + "│ ❯ " + Fore.WHITE))
                if 1 <= start <= end <= total_ayah:
                    return start, end
            except ValueError:
                print(Fore.RED + "└──╼ " + "Invalid input. Please enter a valid number or 'all'.")
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\n\n" + Fore.RED + "⚠ Interrupted! Returning to surah selection.")
                raise KeyboardInterrupt

            print(Fore.RED + "└──╼ " + "Invalid range. Please try again.")

    def _ask_yes_no(self, surah_name:str) -> bool:
        while True:
            try:
                choice = input(Fore.MAGENTA + f"Select another range for {Fore.GREEN}{surah_name}{Fore.LIGHTBLACK_EX} (y/n){Fore.WHITE}: ").strip().lower()
                if choice in ['y', 'yes']:
                    return True
                if choice in ['n', 'no']:
                    return False
                print(Fore.RED + "Invalid input. Please enter 'y' or 'n'.")
            except KeyboardInterrupt: # Add this to handle control + c during input
                print(Fore.YELLOW + "\n\n" + Fore.RED + "⚠ Interrupted! Returning to surah selection.")
                return False  # Treat as 'no' and return to surah selection.

    def _clear_audio_cache(self):
        """Clears the audio cache directory."""
        audio_cache_dir = self.audio_manager.audio_dir
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(audio_cache_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)

            total_size_mb = total_size / (1024 * 1024)  # Convert to MB
            
            if total_size_mb > 0: #If there are files proceed
                # Confirm deletion
                if self.ui.ask_yes_no(f"{Fore.YELLOW}Are you sure you want to clear the audio cache ({total_size_mb:.2f} MB)? (y/n): {Fore.WHITE}"):
                    for filename in os.listdir(audio_cache_dir):
                        file_path = os.path.join(audio_cache_dir, filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            print(Fore.RED + f'Failed to delete {file_path}. Reason: {e}')
                    print(Fore.GREEN + "Audio cache cleared successfully.")
                    input(Fore.GREEN + "Press Enter to continue...")  # Pause
                else:
                    print(Fore.CYAN + "Audio cache clearing cancelled.")
                    input(Fore.GREEN + "Press Enter to continue...")  # Pause
            else:
                print(Fore.CYAN + "No audio files found in cache. They will be available after downloading")
                input(Fore.GREEN + "Press Enter to continue...")  # Pause
        except FileNotFoundError:
            print(Fore.YELLOW + "Audio cache directory not found.")
            input(Fore.GREEN + "Press Enter to continue...")  # Pause
        except OSError as e:
            print(Fore.RED + f"Error while clearing audio cache: {e}")
            input(Fore.GREEN + "Press Enter to continue...")  # Pause

    # -------------- Fix Start for this method(_show_audio_cache_path)-----------
    def _show_audio_cache_path(self):
        """
        Print the audio cache directory path, number of audio files, and total size.
        Offer to open it in the system file explorer (Windows/Linux robustly).
        """
        self._clear_terminal()
        audio_cache_dir = self.audio_manager.audio_dir
        print(f"{Fore.GREEN}Audio cache directory:{Fore.WHITE} {audio_cache_dir}\n")

        # Count files and calculate total size
        file_count = 0
        total_size = 0
        from pathlib import Path
        try:
            for f in Path(audio_cache_dir).glob("**/*"):
                if f.is_file():
                    file_count += 1
                    try:
                        total_size += f.stat().st_size
                    except Exception as e:
                        print(f"{Fore.YELLOW}Warning: Could not get size for {f}: {e}")
        except Exception as e:
            print(f"{Fore.RED}Error reading audio cache directory: {e}\n")

        total_size_mb = total_size / (1024 * 1024)
        print(f"{Fore.CYAN}Audio files: {file_count}   Total size: {total_size_mb:.2f} MB\n")
        print(f"{Fore.YELLOW}This is where downloaded audio files are stored.\n")

        try:
            open_choice = input(f"{Fore.CYAN}Open this folder in your file explorer? (y/n): {Fore.WHITE}").strip().lower()
            if open_choice in ['y', 'yes']:
                if sys.platform == "win32":
                    os.startfile(str(audio_cache_dir))
                elif sys.platform == "darwin":
                    subprocess.run(['open', str(audio_cache_dir)], check=False)
                else:
                    try:
                        subprocess.run(['xdg-open', str(audio_cache_dir)], check=False)
                    except Exception:
                        for fm in ['nautilus', 'thunar', 'dolphin', 'pcmanfm']:
                            if shutil.which(fm):
                                subprocess.run([fm, str(audio_cache_dir)], check=False)
                                break
                        else:
                            print(f"{Fore.RED}Could not open folder: No suitable file manager found.\n")
                print(f"{Fore.GREEN}Opened folder in file explorer.\n")
            else:
                print(f"{Fore.YELLOW}Folder not opened. You can browse to the above path manually.\n")
        except Exception as e:
            print(f"{Fore.RED}Error opening folder: {e}\n")
        print()
        input(f"{Fore.GREEN}Press Enter to continue...")
    # -------------- Fix Ended for this method(_show_audio_cache_path)-----------

    # -------------- Fix Start for this method(set_bookmark)-----------
    def set_bookmark(self, surah_number: int, ayah_number: int, note: str = ""):
        """
        Add a bookmark for a specific surah and ayah, supporting multiple bookmarks per surah.
        Stores the note (no 'extra' field, matches bookmark manager logic).
        """
        try:
            # Initialize bookmarks structure if needed
            if "bookmarks" not in self.preferences:
                self.preferences["bookmarks"] = {}
                
            surah_key = str(surah_number)
            
            # Initialize the surah's bookmark list if it doesn't exist
            if surah_key not in self.preferences["bookmarks"]:
                self.preferences["bookmarks"][surah_key] = []
            
            # Add current date and time in the desired format
            current_datetime = datetime.now()
            date_str = current_datetime.strftime("%A, %d %b %Y %I:%M %p")
            
            # Prevent duplicate for same ayah, update note if exists
            for b in self.preferences["bookmarks"][surah_key]:
                if isinstance(b, dict) and b.get("ayah") == ayah_number:
                    b["note"] = note
                    b["date_added"] = date_str  # Update date when modifying bookmark
                    self._save_preferences()
                    return
                    
            # Add new bookmark
            self.preferences["bookmarks"][surah_key].append({
                "ayah": ayah_number,
                "note": note,
                "date_added": date_str
            })
            self._save_preferences()
        except Exception as e:
            # Wrap the exception with a more descriptive message including surah number
            raise Exception(f"Error in set_bookmark: Surah {surah_number}, Ayah {ayah_number} - {str(e)}")
    # -------------- Fix Ended for this method(set_bookmark)-----------

    def get_bookmark(self, surah_number: int):
        """Get the bookmark for a surah, or None if not set."""
        return self.preferences.get("bookmarks", {}).get(str(surah_number))

    def remove_bookmark(self, surah_number: int):
        """Remove the bookmark for a surah if it exists."""
        if "bookmarks" in self.preferences and str(surah_number) in self.preferences["bookmarks"]:
            del self.preferences["bookmarks"][str(surah_number)]
            self._save_preferences()
            print(f"[DEBUG] Bookmark removed for Surah {surah_number}.")

    def list_bookmarks(self):
        """Return all saved bookmarks as a dict."""
        return self.preferences.get("bookmarks", {})

if __name__ == "__main__":
    # Wrap the entire app execution in a try-except block
    # to handle KeyboardInterrupt at the top level
    # to ensure Ctrl+C at the main menu does not crash the app
    # but gracefully prompts for 'quit' or 'exit'
    try:
        QuranApp().run()
        sys.exit(0) # Exit normally
    except KeyboardInterrupt:
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear terminal
        print(Style.BRIGHT + Fore.YELLOW + "⚠ To exit, please type 'quit' or 'exit'")
        sys.exit(1) # Exit with error code
    except Exception as e:
        # Catch unexpected errors during startup or run
        print(Fore.RED + Style.BRIGHT + "\n--- UNEXPECTED ERROR ---")
        import traceback
        traceback.print_exc() # Print detailed traceback
        print("-----------------------" + Style.RESET_ALL)
        input("Press Enter to exit.") # Keep console open
        sys.exit(1)