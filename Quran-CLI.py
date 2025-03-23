# Quran-CLI.py
import sys
import os
import subprocess
import json

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
    from core.version import VERSION

    from typing import  Optional
    import shutil
    import difflib

QURAN_CLI_ASCII = """
\033[31m
 ██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗     ██████╗██╗     ██╗
██╔═══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║    ██╔════╝██║     ██║
██║   ██║██║   ██║██████╔╝███████║██╔██╗ ██║    ██║     ██║     ██║
██║▄▄ ██║██║   ██║██╔══██╗██╔══██║██║╚██╗██║    ██║     ██║     ██║
╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║    ╚██████╗███████╗██║
 ╚══▀▀═╝  ╚═════╝ ╚═╝  ██║╚═╝  ╚═╝╚═╝  ╚═══╝     ╚═════╝╚══════╝╚═╝
                        
                       𝒫𝓇𝑜𝒿𝑒𝒸𝓉 𝒷𝓎 𝐹𝒶𝒹𝒮𝑒𝒸 𝐿𝒶𝒷

\033[0m"""

class QuranApp:
    def __init__(self):
        self.client = QuranAPIClient()
        # Get terminal size
        self.term_size = shutil.get_terminal_size()
        self.audio_manager = AudioManager()
        self.data_handler = QuranDataHandler(self.client.cache)

        # Load preferences
        self.preferences_file = os.path.join(os.path.dirname(__file__), 'core', 'preferences.json')
        self.preferences = self._load_preferences()

        self.ui = UI(self.audio_manager, self.term_size, self.data_handler, preferences=self.preferences)  # Create UI and pass preferences

        self.updater = GithubUpdater("anonfaded", "QuranCLI", VERSION)#Replace owner and name
        self.ui = UI(self.audio_manager, self.term_size, self.data_handler, self.updater, self.preferences)  # <---  Pass updater to UI
        self._clear_terminal()  # Calling it here, so the program clears the terminal on startup
        self.surah_names = self._load_surah_names()

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
        self.ui.display_header(QURAN_CLI_ASCII)

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

                    print(Style.BRIGHT + Fore.RED + "╭─ " + Fore.RED + "📜 Surah Information")
                    print(Fore.RED + f"│ • {Fore.WHITE}Name:       {Fore.CYAN}{surah_info.surah_name}")
                    print(Fore.RED + f"│ • {Fore.WHITE}Arabic:     {Fore.CYAN}{surah_info.surah_name_arabic}")
                    print(Fore.RED + f"│ • {Fore.WHITE}Revelation: {Fore.CYAN}{surah_info.revelation_place}")
                    print(Fore.RED + f"│ • {Fore.WHITE}Total Ayahs:{Fore.CYAN} {surah_info.total_ayah}")
                    print(Fore.RED + "╰" + separator)

                    # Note Section
                    print(Style.DIM + Fore.YELLOW + "⚠ Note: Arabic text may appear reversed but will copy correctly.")
                    print(Style.BRIGHT + Fore.RED + separator)

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
        # Removed this duplicate thank you message that appears when control c is pressed on first input 
        # print(Fore.RED + "\n✨ Thank you for using " + Fore.WHITE + "QuranCLI" + Fore.RED + "!") # Print exit message after loop ends

    def _display_surah_list(self):
        """Display surah names in multiple columns."""
        self._clear_terminal()
        self._display_header()
        num_surahs = len(self.surah_names)
        columns = 5  # Adjust number of columns based on terminal width
        surahs_per_column = (num_surahs + columns - 1) // columns  # Ceiling division

        print(Fore.RED + Style.BRIGHT + "Quran - List of Surahs:")
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

    def _get_surah_number(self) -> Optional[int]:
        while True:
            try:
                # Clear terminal and display header before prompt
                self._clear_terminal()
                self._display_header()

                # Descriptive command list with colors
                print(Fore.GREEN + "Available Commands:")
                print(Fore.CYAN + "  1-114" + Fore.WHITE + ": Select Surah by number")
                print(Fore.CYAN + "  Surah Name" + Fore.WHITE + ": Search Surah (e.g., 'Rahman')")
                print(Fore.CYAN + "  list" + Fore.WHITE + ": Display list of Surahs")
                print(Fore.CYAN + "  sub" + Fore.WHITE + ": Create subtitles for Ayahs")
                print(Fore.CYAN + "  quit" + Fore.WHITE + ": Exit the application")

                # Helper Text
                print(Style.DIM + Fore.WHITE + "\nType any of the above commands and press Enter.")

                # Prompt user for input
                print(Fore.GREEN + "\nEnter command:" + Style.DIM + Fore.WHITE )
                try:
                    user_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠️  No way out yet, you can't escape now. Try again.")
                    continue  # Restart the loop instead of exiting

                if user_input in ['quit', 'exit']:
                    print(Fore.RED + "\n✨ Thank you for using " + Fore.WHITE + "QuranCLI" + Fore.RED + "!")
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
                # Check if input is a number
                elif user_input.isdigit():
                    number = int(user_input)
                    if 1 <= number <= 114:
                        return number
                    raise ValueError

                # Attempt fuzzy matching for Surah names
                close_matches = difflib.get_close_matches(user_input, self.surah_names.values(), n=5, cutoff=0.5)

                if close_matches:
                    print(Fore.YELLOW + "Did you mean one of these?" + Fore.WHITE + '\n')
                    for idx, match in enumerate(close_matches, 1):
                        surah_number = [num for num, name in self.surah_names.items() if name == match][0]
                        print(Fore.WHITE + f" {idx}. " + Fore.CYAN + f"(Surah {surah_number}) "+ Fore.WHITE + f"{match} \n")

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

                    print(Fore.GREEN + "Available Commands (Subtitle Creation):")
                    print(Fore.CYAN + "  1-114" + Fore.WHITE + ": Select Surah by number")
                    print(Fore.CYAN + "  q" + Fore.WHITE + ": Return to main menu")

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
                print(Fore.RED + "\n┌─" + Fore.RED + Style.BRIGHT + f" Ayah Selection (1-{total_ayah})")
                print(Fore.RED + "├──╼ " + Fore.GREEN + "Start" + ":\n" , end="")
                start = int(input(Fore.RED + "│ ❯ " + Fore.WHITE))
                print(Fore.RED + "├──╼ " + Fore.GREEN + "End" + ":\n" , end="")
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
                choice = input(Fore.BLUE + f"Select another range for {Fore.GREEN}{surah_name}{Fore.LIGHTBLACK_EX} (y/n){Fore.WHITE}: ").strip().lower()
                if choice in ['y', 'yes']:
                    return True
                if choice in ['n', 'no']:
                    return False
                print(Fore.RED + "Invalid input. Please enter 'y' or 'n'.")
            except KeyboardInterrupt: # Add this to handle control + c during input
                print(Fore.YELLOW + "\n\n" + Fore.RED + "⚠ Interrupted! Returning to surah selection.")
                return False  # Treat as 'no' and return to surah selection.

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