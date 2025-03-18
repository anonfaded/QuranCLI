# Quran-CLI.py
from core.quran_api_client import QuranAPIClient
from core.quran_data_handler import QuranDataHandler
from core.audio_manager import AudioManager
from core.ui import UI
from core.github_updater import GithubUpdater
from core.version import VERSION

from colorama import Fore, Style, init
from typing import  Optional
import os
import shutil

import difflib

# Initialize colorama
init(autoreset=True)

QURAN_CLI_ASCII = """
\033[31m
 ██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗     ██████╗██╗     ██╗
██╔═══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║    ██╔════╝██║     ██║
██║   ██║██║   ██║██████╔╝███████║██╔██╗ ██║    ██║     ██║     ██║
██║▄▄ ██║██║   ██║██╔══██╗██╔══██║██║╚██╗██║    ██║     ██║     ██║
╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║    ╚██████╗███████╗██║
 ╚══▀▀═╝  ╚═════╝ ╚═╝  ██║╚═╝  ╚═╝╚═╝  ╚═══╝     ╚═════╝╚══════╝╚═╝
\033[0m"""

class QuranApp:
    def __init__(self):
        self.client = QuranAPIClient()
        # Get terminal size
        self.term_size = shutil.get_terminal_size()
        self.audio_manager = AudioManager()
        self.data_handler = QuranDataHandler(self.client.cache)
        self.ui = UI(self.audio_manager, self.term_size)  # Create UI
        self.updater = GithubUpdater("anonfaded", "QuranCLI", VERSION)#Replace owner and name
        self.ui = UI(self.audio_manager, self.term_size, self.updater)  # <---  Pass updater to UI
        self._clear_terminal()  # Calling it here, so the program clears the terminal on startup
        self.surah_names = self._load_surah_names()

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

                try:
                    while True:
                        print(Fore.RED + "┌─" + Fore.RED + Style.BRIGHT + " Select Surah")
                        surah_number = self._get_surah_number()
                        if surah_number is None:
                            return  # Exit completely instead of break

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
                            start, end = self._get_ayah_range(surah_info.total_ayah)
                            ayahs = self.data_handler.get_ayahs(surah_number, start, end)
                            self.ui.display_ayahs(ayahs, surah_info)

                            # Cleaner ayah range selection prompt
                            print(Fore.WHITE + "\nSelect another range for " +
                                  Fore.RED + f"{surah_info.surah_name}" +
                                  Style.DIM + Fore.WHITE + " (y/n)" + Style.NORMAL +
                                  Fore.WHITE + ":\n" + Fore.RED + "  ❯ " + Fore.WHITE, end="")

                            if not self._ask_yes_no(""):
                                self._clear_terminal()
                                self._display_header()
                                break

                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\nTo exit, please type 'quit' or 'exit'")
                    self.run()  # Restart the main loop
            except KeyboardInterrupt:
                self._clear_terminal()
                print(Style.BRIGHT + Fore.YELLOW + "⚠ To exit, please type 'quit' or 'exit'")
                continue

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

                # Prompt user for input
                print(Fore.RED + "└──╼ " + Fore.GREEN + "Enter number (1-114), surah name, 'list', or 'quit'" + Style.DIM + Fore.WHITE + ":\n" + Fore.RED + "  ❯ " + Fore.WHITE, end="")
                user_input = input().strip().lower()

                if user_input in ['quit', 'exit']:
                    print(Fore.RED + "\n✨ Thank you for using " + Fore.WHITE + "QuranCLI" + Fore.RED + "!")
                    return None
                elif user_input == 'list':
                    self._display_surah_list()
                    return self._get_surah_number()  # Re-prompt after list is displayed

                # Check if input is a number
                if user_input.isdigit():
                    number = int(user_input)
                    if 1 <= number <= 114:
                        return number
                    raise ValueError

                # Attempt fuzzy matching for Surah names
                close_matches = difflib.get_close_matches(user_input, self.surah_names.values(), n=5, cutoff=0.5)

                if close_matches:
                    print(Fore.YELLOW + "Did you mean one of these?" + Fore.WHITE)
                    for idx, match in enumerate(close_matches, 1):
                        surah_number = [num for num, name in self.surah_names.items() if name == match][0]
                        print(Fore.GREEN + f" {idx}. {match} (Surah {surah_number})")

                    # Ask user to select a Surah from the suggestions
                    while True:
                        print(Fore.RED + "└──╼ " + Fore.GREEN + "Select a number from the list, or 'r' to retry:" + Fore.WHITE)
                        user_choice = input("  ❯ ").strip()

                        if user_choice.isdigit():
                            choice_idx = int(user_choice) - 1
                            if 0 <= choice_idx < len(close_matches):
                                selected_surah = close_matches[choice_idx]
                                return [num for num, name in self.surah_names.items() if name == selected_surah][0]
                            else:
                                print(Fore.RED + "Invalid choice. Please select a number from the list or 'r' to retry.")
                        elif user_choice.lower() == 'r':
                            self._clear_terminal()
                            self._display_header()
                            break  # Restart input prompt
                        else:
                            print(Fore.RED + "Invalid choice. Please select a number from the list or 'r' to retry.")
                else:
                    print(Fore.RED + "└──╼ " + "No close matches found. Please enter a valid Surah number, name, 'list', or 'quit'")

            except ValueError:
                print(Fore.RED + "└──╼ " + "Invalid input. Enter a number between 1-114, a Surah name, 'list', or 'quit'")

    def _get_ayah_range(self, total_ayah: int) -> tuple:
        while True:
            try:
                print(Fore.RED + "\n┌─" + Fore.RED + Style.BRIGHT + f" Ayah Selection (1-{total_ayah})")
                print(Fore.RED + "├──╼ " + Fore.GREEN + "Start" + ":\n" + Fore.RED + "│ ❯ " + Fore.WHITE, end="")
                start = int(input())
                print(Fore.RED + "├──╼ " + Fore.GREEN + "End" + ":\n" + Fore.RED + "│ ❯ " + Fore.WHITE, end="")
                end = int(input())
                if 1 <= start <= end <= total_ayah:
                    return start, end
            except ValueError:
                pass
            print(Fore.RED + "└──╼ " + "Invalid range. Please try again.")

    def _ask_yes_no(self, prompt: str) -> bool:
        return self.ui.ask_yes_no(prompt)

if __name__ == "__main__":
    try:
        QuranApp().run()
    except KeyboardInterrupt:
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear terminal
        print(Style.BRIGHT + Fore.YELLOW + "⚠ To exit, please type 'quit' or 'exit'")
        QuranApp().run()