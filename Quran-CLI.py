# Quran-CLI.py

import sys
import os
import subprocess
import json
from time import sleep

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

class QuranApp:
    def __init__(self):
        self.client = QuranAPIClient()
        # Get terminal size
        self.term_size = shutil.get_terminal_size()
        self.audio_manager = AudioManager()
        self.data_handler = QuranDataHandler(self.client.cache)

        # Define preference file path (next to exe)
        self.preferences_file = get_app_path('preferences.json', writable=True)
        # Load preferences using the defined path
        self.preferences = self._load_preferences()
        # Add this line immediately after:
        self.theme_color = self.preferences.get('theme_color', 'red') # Load theme, default red

        # Initialize GithubUpdater
        self.updater = GithubUpdater("anonfaded", "QuranCLI", VERSION)
        
        # --- Create DownloadCounter Instance ---
        self.download_counter = DownloadCounter(repo_owner="anonfaded", repo_name="QuranCLI")

        # --- Initialize UI ONCE, passing necessary arguments ---
        self.ui = UI(
            audio_manager=self.audio_manager,
            term_size=self.term_size,
            data_handler=self.data_handler,
            github_updater=self.updater,
            preferences=self.preferences, # Pass loaded preferences dict
            preferences_file_path=self.preferences_file, # Pass the path string
            download_counter=self.download_counter # Pass the download counter instance
        )
        # --- End UI Initialization ---

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
        """Load preferences from file"""
        try:
            with open(self.preferences_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(Fore.YELLOW + "Preferences file not found, creating new one.")
            return {}
        except json.JSONDecodeError:
            print(Fore.YELLOW + "Preferences file is corrupted, resetting.")
            return {}
        except Exception as e:
            print(Fore.RED + f"Error loading preferences: {e}")
            return {}

    def _save_preferences(self):
         """Save preferences to file"""
         try:
             with open(self.preferences_file, 'w', encoding='utf-8') as f:
                 json.dump(self.preferences, f, ensure_ascii=False, indent=2)
         except Exception as e:
             print(Fore.RED + f"Error saving preferences: {e}")

    def _load_surah_names(self):
        surah_names = {}
        for i in range(1, 115):
            try:
                surah_info = self.data_handler.get_surah_info(i)
                surah_names[i] = surah_info.surah_name
            except ValueError:
                print(Fore.RED + f"Warning: Could not load surah info for surah {i}")
                surah_names[i] = "Unknown"
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

                    surah_info = self.data_handler.get_surah_info(surah_number)
                    # Surah Information Header
                    box_width = 52  # Adjust width if needed
                    separator = "─" * box_width

                    print(Fore.RED + "╭─ " + Style.BRIGHT +  Fore.GREEN + "📜 Surah Information")
                    print(Fore.RED + f"│ • {Fore.CYAN}Name:       {Fore.WHITE}{surah_info.surah_name}")
                    print(Fore.RED + f"│ • {Fore.CYAN}Arabic:     {Fore.WHITE}{surah_info.surah_name_arabic}")
                    print(Fore.RED + f"│ • {Fore.CYAN}Revelation: {Fore.WHITE}{surah_info.revelation_place}")
                    print(Fore.RED + f"│ • {Fore.CYAN}Total Ayahs:{Fore.WHITE} {surah_info.total_ayah}")
                    print(Fore.RED + "╰" + separator)

                    # Note Section
                    # print(Style.DIM + Fore.YELLOW + "⚠ Note: Arabic text may appear reversed but will copy correctly.")
                    # print(Style.BRIGHT + Fore.RED + separator)

                    while True:
                        try:
                            start, end = self._get_ayah_range(surah_info.total_ayah)
                            ayahs = self.data_handler.get_ayahs(surah_number, start, end)
                            self.ui.display_ayahs(ayahs, surah_info)

                            if not self._ask_yes_no(surah_info.surah_name):
                                self._clear_terminal()
                                self._display_header()
                                break
                        except KeyboardInterrupt:
                            break #Break the inner while loop

                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n" + Fore.RED + "⚠ Interrupted! Returning to main menu.")
                    continue  # Continue to the outer loop

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



    def _display_info(self):
        """Displays detailed information about the application and commands."""
        self._clear_terminal()
        # Assuming self._display_header() is called before this in the main loop is sufficient
        # Or call it here if needed: self._display_header()

        # Use terminal width for dynamic sizing, fallback for very small terminals
        box_width = self.term_size.columns - 4 if self.term_size.columns > 40 else 60
        separator_major = Fore.RED + Style.BRIGHT + "═" * box_width + Style.RESET_ALL
        separator_minor = Fore.RED + "─" * box_width + Style.RESET_ALL

        print(separator_major)
        print(Fore.GREEN + Style.BRIGHT + "QuranCLI - Information & Help".center(box_width + len(Fore.GREEN + Style.BRIGHT))) # Adjust center for color codes
        print(separator_major)

        # --- Description ---
        print(Fore.WHITE + "\nA powerful terminal-based tool for interacting with the Holy Quran.")
        print(Fore.CYAN + "Read, listen to recitations, and generate video subtitles (captions).")
        print(Fore.GREEN + "\nGitHub Repository:")
        print(Fore.MAGENTA + Style.BRIGHT + "https://github.com/anonfaded/QuranCLI" + Style.RESET_ALL)

        # --- Commands ---
        print("\n" + separator_minor)
        print(Fore.GREEN + Style.BRIGHT + "Available Commands".center(box_width + len(Fore.GREEN + Style.BRIGHT)))
        print(separator_minor)

        commands_info = [
            (Fore.CYAN + "1-114", Fore.WHITE + ": Select a Surah directly by its number."),
            (Fore.CYAN + "Surah Name", Fore.WHITE + ": Search for a Surah by name (e.g., 'Fatiha', 'Rahman'). Provides suggestions."),
            (Fore.CYAN + "list", Fore.WHITE + ": Display a list of all 114 Surahs with their numbers."),
            (Fore.CYAN + "sub", Fore.WHITE + ": Generate subtitle files (.srt format) for a range of Ayahs."),
            (Fore.YELLOW + "  ↳ Use Case:", Fore.WHITE + "Ideal for video editors needing Quran captions."),
            (Fore.YELLOW + "  ↳ How:", Fore.WHITE + "Creates timestamped Arabic/English text for import into editors (e.g., CapCut)."),
            (Fore.CYAN + "clearaudio", Fore.WHITE + ": Delete all downloaded audio files from the cache."),
            (Fore.CYAN + "reverse", Fore.WHITE + ": Toggle Arabic text display direction within the Ayah reader."),
            (Fore.YELLOW + "  ↳ Use Case:", Fore.WHITE + "Fixes display issues on some terminals where Arabic appears reversed."),
            (Fore.YELLOW + "  ↳ Note:", Fore.WHITE + "Copied text should generally be correct regardless of display."),
            (Fore.CYAN + "info", Fore.WHITE + ": Display this help and information screen."),
            (Fore.CYAN + "quit / exit", Fore.WHITE + ": Close the QuranCLI application.")
        ]

        cmd_col_width = 15 # Width for the command name part
        desc_col_width = box_width - cmd_col_width - 1 # Remaining width for description

        for cmd, desc in commands_info:
            cmd_part = f"{cmd}".ljust(cmd_col_width + len(cmd) - len(cmd.replace('\033[','').split('m')[-1])) # Adjust ljust for color codes

            # Use the UI's wrap_text method if available and needed
            if hasattr(self.ui, 'wrap_text') and desc_col_width > 10:
                 desc_lines = self.ui.wrap_text(desc, desc_col_width).split('\n')
            else: # Basic fallback wrapping
                 desc_lines = [desc[i:i+desc_col_width] for i in range(0, len(desc), desc_col_width)]

            # Print first line
            print(f"{cmd_part}{Fore.WHITE}{desc_lines[0]}")
            # Print subsequent lines indented
            for line in desc_lines[1:]:
                print(f"{' '.ljust(cmd_col_width)}{Fore.WHITE}{line}")

            # Add spacing after multi-line descriptions (like sub and reverse)
            if cmd.startswith(Fore.CYAN + "sub") or cmd.startswith(Fore.CYAN + "reverse"):
                 print("")

        # --- Credits ---
        print("\n" + separator_minor)
        print(Fore.GREEN + Style.BRIGHT + "Credits".center(box_width + len(Fore.GREEN + Style.BRIGHT)))
        print(separator_minor)

        print(Fore.WHITE + "  Quran Data & Audio API provided by:")
        print(f"    {Fore.CYAN}The Quran Project{Fore.WHITE} ({Fore.MAGENTA}https://github.com/The-Quran-Project/Quran-API{Fore.WHITE})")
        print(f"      {Fore.YELLOW}(API has no rate limit)")

        print(Fore.WHITE + "\n  Application Icon sourced from Flaticon:")
        print(f"    {Fore.CYAN}Holy icons created by Atif Arshad - Flaticon{Fore.WHITE}")
        print(f"      ({Fore.MAGENTA}https://www.flaticon.com/free-icons/holy{Fore.WHITE})")


        # --- Feedback / Bug Reports ---
        print("\n" + separator_minor)
        print(Fore.GREEN + Style.BRIGHT + "Feedback & Bug Reports".center(box_width + len(Fore.GREEN + Style.BRIGHT)))
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


        # --- Footer ---
        print("\n" + separator_major)
        input(Fore.YELLOW + "\nPress Enter to return to the main menu..." + Style.RESET_ALL)
        # No need to clear here, the main loop will handle it before the next prompt
        # self._clear_terminal()
        # self._display_header()

    def _get_surah_number(self) -> Optional[int]:
        # Navigation Menu
        box_width = 26  # Adjust width if needed
        separator = "─" * box_width

        while True:
            try:
                # Clear terminal and display header before prompt
                self._clear_terminal()
                self._display_header()
                box_width = 26  # Adjust width if needed
                separator = "─" * box_width

                # Descriptive command list with colors
                print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "📜 Available Commands")
                print(Fore.RED + f"│ • {Fore.CYAN}1-114{Fore.WHITE}: Select Surah by number")
                print(Fore.RED + f"│ • {Fore.CYAN}Surah Name{Fore.WHITE}: Search Surah {Style.DIM}(e.g., 'Rahman')")
                print(Fore.RED + f"│ • {Fore.CYAN}list{Fore.WHITE}: Display list of Surahs")
                print(Fore.RED + f"│ • {Fore.CYAN}sub{Fore.WHITE}: Create subtitles for Ayahs")
                print(Fore.RED + f"│ • {Fore.CYAN}clearaudio{Fore.WHITE}: Clear audio cache")
                print(Fore.RED + f"│ • {Fore.CYAN}info{Fore.WHITE}: Show help and information")
                print(Fore.RED + f"│ • {Fore.CYAN}theme{Fore.WHITE}: Change ASCII art color")
                print(Fore.RED + f"│ • {Fore.RED}readme{Fore.WHITE}: View Notes by the developer & Updates")
                print(Fore.RED + f"│ • {Fore.CYAN}quit{Fore.WHITE}: Exit the application")
                print(Fore.RED + "╰" + separator)
                    
                    
                # Helper Text
                print(Style.DIM + Fore.WHITE + "\nType any of the above commands and press Enter.")

                # Prompt user for input
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
        
                if user_input in ['quit', 'exit']:
                    message = "\n✨ As-salamu alaykum! Thank you for using QuranCLI!"
                    typewriter_print(self,message)
                    sleep(3.0)  # Shorter pause after typewriter effect
                    return None
                elif user_input == 'list':
                    self._display_surah_list()
                    continue
                elif user_input == 'sub':
                    #Ask the user for the surah they want to generate subtitles for.
                    surah_number = self._get_surah_number_for_subtitle()
                    if surah_number is None:
                        continue #Return to main selection.
                    surah_info = self.data_handler.get_surah_info(surah_number)
                    self.ui.display_subtitle_menu(surah_info)
                    continue # After subtitle, return to main
                elif user_input == 'clearaudio':
                    self._clear_audio_cache()
                    continue
                elif user_input == 'info': # Handle the 'info' command
                    self._display_info()
                    continue # Go back to the start of the loop to show the prompt again
                elif user_input == 'readme':
                    self._display_readme_page()
                    continue # Go back to the main menu prompt
                elif user_input == 'theme':
                    self._handle_theme_selection()
                    continue # Go back to the main menu prompt
                # Check if input is a number
                elif user_input.isdigit():
                    number = int(user_input)
                    if 1 <= number <= 114:
                        return number
                    raise ValueError

                # Attempt fuzzy matching for Surah names
                close_matches = difflib.get_close_matches(user_input, self.surah_names.values(), n=5, cutoff=0.5)

                if close_matches:
                    print("\n")
                    print( Fore.RED + "╭─" + Style.BRIGHT + Fore.MAGENTA + "🤔 Did you mean one of these?")
                    for idx, match in enumerate(close_matches, 1):
                        surah_number = [num for num, name in self.surah_names.items() if name == match][0]
                        print(f"{Fore.RED}├ {Fore.GREEN}{idx}. {Fore.CYAN}{match} {Style.DIM}{Fore.WHITE}(Surah {surah_number})")
                    print(Fore.RED + "╰" + separator + '\n')    

                    # Ask user to select a Surah from the suggestions
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
                                break  # Restart input prompt
                            else:
                                print(Fore.RED + "Invalid choice. Please select a number from the list or 'r' to retry.")
                        except KeyboardInterrupt:
                            print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to surah selection.")
                            break # Return to surah selection.
            except ValueError:
                print(Fore.RED + "Invalid input. Enter a number between 1-114, a Surah name, 'list', 'sub', or 'quit'")
            except KeyboardInterrupt:  # Add this to handle control + c during input
                print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to main menu.")
                break # Return to main menu immediately, *without exiting app*.

    
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
        while True:
            try:
                print(Fore.RED + "\n┌─" + Fore.GREEN + Style.BRIGHT + f" Ayah Selection (1-{total_ayah})")
                print(Fore.RED + "├──╼ " + Fore.MAGENTA + "Start" + ":\n" , end="")
                start = int(input(Fore.RED + "│ ❯ " + Fore.WHITE))
                print(Fore.RED + "├──╼ " + Fore.MAGENTA + "End" + ":\n" , end="")
                end = int(input(Fore.RED + "│ ❯ " + Fore.WHITE))
                if 1 <= start <= end <= total_ayah:
                    return start, end
            except ValueError:
                pass
            except KeyboardInterrupt: # Add this to handle control + c during input
                print(Fore.YELLOW + "\n\n" + Fore.RED + "⚠ Interrupted! Returning to surah selection.")
                raise KeyboardInterrupt # Re-raise to go to surah selection.

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


if __name__ == "__main__":
    # Wrap the entire app execution in a try-except block
    # to handle KeyboardInterrupt at the top level. This
    # ensures Ctrl+C at the main menu does not crash the app
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