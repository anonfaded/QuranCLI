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

    def _clear_terminal(self):
        self.ui.clear_terminal()

    def _display_header(self):
        self.ui.display_header(QURAN_CLI_ASCII)

    def run(self):
        # self.updater.check_for_updates() # Check for updates at start of run
        
        while True:
            try:
                self._clear_terminal()
                self._display_header()



                try:
                    while True:
                        print(Fore.RED + "┌─" + Fore.WHITE + " Select Surah")
                        surah_number = self._get_surah_number()
                        if surah_number is None:
                            return  # Exit completely instead of break

                        print(Style.BRIGHT + Fore.RED + "\n" + "=" * 52)

                        surah_info = self.data_handler.get_surah_info(surah_number)
                        # Surah Information Header
                        box_width = 52  # Adjust width if needed
                        separator = "─" * box_width

                        print(Style.BRIGHT + Fore.RED + "╭─ " + Fore.WHITE + "📜 Surah Information")
                        print(Fore.RED + f"│ • {Style.BRIGHT}{Fore.WHITE}Name:       {Fore.RED}{surah_info.surah_name}")
                        print(Fore.RED + f"│ • {Style.BRIGHT}{Fore.WHITE}Arabic:     {Fore.RED}{surah_info.surah_name_arabic}")
                        print(Fore.RED + f"│ • {Style.BRIGHT}{Fore.WHITE}Revelation: {Fore.RED}{surah_info.revelation_place}")
                        print(Fore.RED + f"│ • {Style.BRIGHT}{Fore.WHITE}Total Ayahs:{Fore.RED} {surah_info.total_ayah}")
                        print(Fore.RED + "╰" + separator)

                        # Note Section
                        print(Style.DIM + Fore.YELLOW + "⚠ Note: Arabic text may appear reversed in the terminal but will copy correctly.")
                        print(Style.BRIGHT + Fore.RED + separator)




                        while True:
                            start, end = self._get_ayah_range(surah_info.total_ayah)
                            ayahs = self.data_handler.get_ayahs(surah_number, start, end)
                            self.ui.display_ayahs(ayahs, surah_info)

                            # Cleaner ayah range selection prompt
                            print(Fore.BLUE + "\nSelect another range for " +
                                  Fore.RED + f"{surah_info.surah_name}" +
                                  Style.DIM + Fore.WHITE + " (y/n)" +
                                  Fore.WHITE + ": ", end="")

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

    def _get_surah_number(self) -> Optional[int]:
        while True:
            try:
                print(Fore.RED + "└──╼ " + Fore.WHITE + "Enter number (1-114) or 'quit': ", end="")
                user_input = input().strip().lower()
                if user_input in ['quit', 'exit']:
                    print(Fore.RED + "\n✨ Thank you for using " + Fore.WHITE + "QuranCLI" + Fore.RED + "!")
                    return None

                number = int(user_input)
                if 1 <= number <= 114:
                    return number
                raise ValueError
            except ValueError:
                print(Fore.RED + "└──╼ " + "Invalid input. Enter a number between 1-114")

    def _get_ayah_range(self, total_ayah: int) -> tuple:
        while True:
            try:
                print(Fore.RED + "\n┌─" + Fore.WHITE + f" Ayah Selection (1-{total_ayah})")
                print(Fore.RED + "├──╼ " + Fore.WHITE + "Start: ", end="")
                start = int(input())
                print(Fore.RED + "└──╼ " + Fore.WHITE + "End: ", end="")
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