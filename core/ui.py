# core/ui.py
import sys
import math
import time
import asyncio
# import keyboard
import json
import os
import datetime
import arabic_reshaper
import platformdirs
import subprocess  # Added for Linux/Mac folder opening
import re
import pygame

# Import termios conditionally - it's only available on Unix systems
import sys
if sys.platform != "win32":
    try:
        import termios
        import select
        HAS_TERMIOS = True
    except ImportError:
        HAS_TERMIOS = False
else:
    HAS_TERMIOS = False
    # These are needed for type checking
    termios = None
    select = None

# Import platform-specific modules
import sys

# Windows-specific modules
if sys.platform == "win32":
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False
# Unix-specific modules (Linux, macOS, etc.)
else:
    try:
        import select
        import tty
        import termios
        HAS_TERMIOS = True
    except ImportError:
        # Fallbacks for environments without termios (like non-terminal environments)
        HAS_TERMIOS = False
        select = None
        termios = None

from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING: # Avoid circular import issues for type hints
    from core.download_counter import DownloadCounter
from colorama import Fore, Style, Back
from core.models import Ayah, SurahInfo
from core.audio_manager import AudioManager
from core.github_updater import GithubUpdater  # Import GithubUpdater
from core.version import VERSION  # Import VERSION
from core.quran_data_handler import QuranDataHandler
from .utils import get_app_path # Keep this for web assets

import socket #For Ip Adresses
import threading #Add threading for server
import http.server
import socketserver

# Keep track of original terminal settings
_original_termios_settings = None

# --- Terminal Control for Unix-like systems ---
def _unix_getch_non_blocking():
    """Non-blocking character read function for Unix platforms.
    Returns a single character if available, or None if no input is available.
    """
    # Check if termios is available
    if 'HAS_TERMIOS' not in globals() or not HAS_TERMIOS or not select:
        return None
        
    try:
        # Check for available input with no timeout
        rlist, _, _ = select.select([sys.stdin], [], [], 0)
        if rlist:
            # Input is available, read one character
            char = sys.stdin.read(1)
            return char
        return None  # No input available
    except Exception:
        # Handle any errors during read
        return None


def _restore_terminal_settings():
    """Helper function to restore terminal settings if modified"""
    global _original_termios_settings
    
    # Only attempt restoration if the global is set and termios is available
    if _original_termios_settings is not None and 'HAS_TERMIOS' in globals() and HAS_TERMIOS:
        try:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, _original_termios_settings)
        except Exception as e:
            # Don't print anything (might interfere with rendering)
            pass

# --- End Terminal Control ---



class UI:


    def __init__(self, audio_manager: AudioManager, term_size, data_handler: QuranDataHandler, github_updater: Optional[GithubUpdater] = None, preferences: dict = None, preferences_file_path: str = None, download_counter: Optional['DownloadCounter'] = None):
        """
        Initialize the UI.

        Args:
            audio_manager: Instance for handling audio.
            term_size: Terminal size information.
            data_handler: Instance for handling Quran data.
            github_updater: Instance for checking updates.
            preferences: Dictionary containing loaded preferences.
            preferences_file_path: The absolute path to the preferences file (determined externally).
        """
        self.audio_manager = audio_manager
        self.term_size = term_size
        self.data_handler = data_handler
        self.github_updater = github_updater
        self.download_counter = download_counter 
        self.update_message = self._get_update_message()
        # Store the externally determined path for saving
        self.preferences_file = preferences_file_path
        # Use the already loaded preferences
        self.preferences = preferences if preferences is not None else self._load_preferences() # Keep fallback loading just in case
        # --- ADD Subtitle Config Loading with Defaults ---
        default_subtitle_config = {
            "include_urdu": True,
            "include_turkish": False,
            "include_english": True,
            "include_transliteration": False
        }
        # Load existing or set default
        if "subtitle_config" not in self.preferences:
            self.preferences["subtitle_config"] = default_subtitle_config
        else:
            # Ensure all keys exist in loaded config, add defaults if missing
            for key, default_value in default_subtitle_config.items():
                if key not in self.preferences["subtitle_config"]:
                    self.preferences["subtitle_config"][key] = default_value
        
        # --- ADD Reading Config Loading with Defaults ---
        default_reading_config = {
            "show_urdu": True,
            "show_turkish": False,
            "show_english": True,
            "show_transliteration": True
        }
        # Load existing or set default
        if "reading_config" not in self.preferences:
            self.preferences["reading_config"] = default_reading_config
        else:
            # Ensure all keys exist in loaded config, add defaults if missing
            for key, default_value in default_reading_config.items():
                if key not in self.preferences["reading_config"]:
                    self.preferences["reading_config"][key] = default_value
        # --- END ADD ---
        
        self.httpd = None
        self.server_thread = None # Initialize server_thread attribute

    def _display_subtitle_settings_menu(self):
        """Displays and handles the subtitle content settings menu with box design."""
        while True:
            self.clear_terminal()
            box_width = 55  # Adjust as needed
            separator = "─" * box_width

            # Header with box design
            print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "🎬 Subtitle Content Settings")
            print(Fore.RED + f"│ {Fore.WHITE}Configure what content appears in SRT files")
            print(Fore.RED + f"│ {Fore.WHITE}Arabic text is always included")
            print(Fore.RED + "├" + separator)

            config = self.preferences.get("subtitle_config", {})

            # Display options with current status
            options = [
                ("include_transliteration", "Transliteration"),
                ("include_urdu", "Urdu Translation"),
                ("include_turkish", "Turkish Translation"),
                ("include_english", "English Translation")
            ]

            print(Fore.RED + f"│ {Fore.YELLOW}Current Settings:")
            for i, (key, label) in enumerate(options):
                status = config.get(key, False)
                status_icon = Fore.GREEN + "✓" if status else Fore.RED + "✗"
                status_text = Fore.GREEN + "Enabled" if status else Fore.RED + "Disabled"
                pad = " " * (20 - len(label))
                print(Fore.RED + f"│   • {Fore.CYAN}{i+1}{Fore.WHITE} : {label}{pad} : [{status_icon} {status_text}{Fore.WHITE}]")

            print(Fore.RED + "├" + separator)
            print(Fore.RED + f"│ {Style.BRIGHT}{Fore.GREEN}Choose an action{Style.RESET_ALL}:")

            # Calculate max length for proper alignment
            actions = [
                ("1-4", "Toggle content on/off"),
                ("b", "Back to Subtitle Menu")
            ]

            max_action_len = max(len(action[0]) for action in actions)
            for action, desc in actions:
                pad = " " * (max_action_len - len(action))
                print(Fore.RED + f"│   • {Fore.CYAN}{action}{pad}{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}{desc}{Style.RESET_ALL}")

            print(Fore.RED + "╰" + separator)

            # Helper text
            print(Style.DIM + Fore.WHITE + "\n  Enter number to toggle setting, or 'b' to go back.")
            print(" ")

            try:
                choice = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()

                if choice == 'b':
                    break

                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(options):
                        key_to_toggle = options[index][0]
                        current_value = self.preferences["subtitle_config"].get(key_to_toggle, False)
                        self.preferences["subtitle_config"][key_to_toggle] = not current_value
                        self.save_preferences()
                        print(f"{Fore.GREEN}✓ Setting '{options[index][1]}' updated.{Style.RESET_ALL}")
                        time.sleep(1)
                    else:
                        print(Fore.RED + "❌ Invalid number.")
                        time.sleep(1)
                else:
                    print(Fore.RED + "❌ Invalid input.")
                    time.sleep(1)

            except ValueError:
                print(Fore.RED + "Invalid input. Please enter a number or 'b'.")
                time.sleep(1)
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nSettings cancelled. Returning to Subtitle Menu.")
                break # Exit settings menu on Ctrl+C
            except Exception as e:
                print(Fore.RED + f"An error occurred: {e}")
                time.sleep(1)
                
    def _display_reading_settings_menu(self):
        """Displays and handles the reading view content settings menu with box design."""
        while True:
            self.clear_terminal()
            box_width = 55  # Adjust as needed
            separator = "─" * box_width

            # Header with box design
            print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "📖 Reading View Settings")
            print(Fore.RED + f"│ {Fore.WHITE}Configure which translations appear in reading view")
            print(Fore.RED + f"│ {Fore.WHITE}Arabic text is always shown")
            print(Fore.RED + "├" + separator)

            config = self.preferences.get("reading_config", {})

            # Separate transliteration from translations
            transliteration_option = [("show_transliteration", "Transliteration")]
            translation_options = [
                ("show_urdu", "Urdu Translation"),
                ("show_turkish", "Turkish Translation"),
                ("show_english", "English Translation")
            ]

            print(Fore.RED + f"│ {Fore.YELLOW}Current Settings:")

            # Compute label column width from all labels so the right-hand colon aligns
            all_labels = [lab for _, lab in transliteration_option] + [lab for _, lab in translation_options]
            label_width = max(len(lab) for lab in all_labels) + 2
            index_width = 2

            # Display transliteration separately using 't' index to match style of numbered translations
            for key, label in transliteration_option:
                status = config.get(key, True)
                status_icon = Fore.GREEN + "✓" if status else Fore.RED + "✗"
                status_text = Fore.GREEN + "Enabled" if status else Fore.RED + "Disabled"
                pad = " " * (label_width - len(label))
                index_field = 't'.rjust(index_width)
                print(Fore.RED + f"│   • {Fore.CYAN}{index_field}{Fore.WHITE} : {label}{pad} : [{status_icon} {status_text}{Fore.WHITE}]")

            # Display translations (no extra "Translations:" header — it's already shown above)
            for i, (key, label) in enumerate(translation_options, start=1):
                status = config.get(key, True if key in ["show_urdu", "show_english"] else False)
                status_icon = Fore.GREEN + "✓" if status else Fore.RED + "✗"
                status_text = Fore.GREEN + "Enabled" if status else Fore.RED + "Disabled"
                pad = " " * (label_width - len(label))
                index_field = str(i).rjust(index_width)
                print(Fore.RED + f"│   • {Fore.CYAN}{index_field}{Fore.WHITE} : {label}{pad} : [{status_icon} {status_text}{Fore.WHITE}]")

            print(Fore.RED + "├" + separator)
            print(Fore.RED + f"│ {Style.BRIGHT}{Fore.GREEN}Choose an action{Style.RESET_ALL}:")

            # Calculate max length for proper alignment
            actions = [
                ("1-3", "Toggle translation on/off"),
                ("t", "Toggle transliteration on/off"),
                ("b", "Back to Main Menu")
            ]

            max_action_len = max(len(action[0]) for action in actions)
            for action, desc in actions:
                pad = " " * (max_action_len - len(action))
                # Action key in blue, colon and description in white (no dim)
                print(Fore.RED + f"│   • {Fore.CYAN}{action}{pad} {Fore.WHITE}: {desc}{Style.RESET_ALL}")

            print(Fore.RED + "╰" + separator)

            # Helper text
            print(Style.DIM + Fore.WHITE + "\nEnter your input.")
            print(" ")

            try:
                choice = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()

                if choice == 'b':
                    break
                elif choice == 't':
                    # Toggle transliteration
                    key_to_toggle = "show_transliteration"
                    current_value = self.preferences["reading_config"].get(key_to_toggle, True)
                    self.preferences["reading_config"][key_to_toggle] = not current_value
                    self.save_preferences()
                    print(f"{Fore.GREEN}✓ Transliteration setting updated.{Style.RESET_ALL}")
                    time.sleep(1)
                elif choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(translation_options):
                        key_to_toggle = translation_options[index][0]
                        current_value = self.preferences["reading_config"].get(key_to_toggle, True if key in ["show_urdu", "show_english"] else False)
                        self.preferences["reading_config"][key_to_toggle] = not current_value
                        self.save_preferences()
                        print(f"{Fore.GREEN}✓ Setting '{translation_options[index][1]}' updated.{Style.RESET_ALL}")
                        time.sleep(1)
                    else:
                        print(Fore.RED + "❌ Invalid number. Please enter 1-3.")
                        time.sleep(1)
                else:
                    print(Fore.RED + "❌ Invalid input. Please enter 1-3, 't', or 'b'.")
                    time.sleep(1)

            except ValueError:
                print(Fore.RED + "Invalid input. Please enter a number or 'b'.")
                time.sleep(1)
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nSettings cancelled. Returning to Main Menu.")
                break # Exit settings menu on Ctrl+C
            except Exception as e:
                print(Fore.RED + f"An error occurred: {e}")
                time.sleep(1)
        """Fallback method to load preferences if not provided or path is missing."""
        if not self.preferences_file or not os.path.exists(self.preferences_file):
            # print(Fore.YELLOW + "Preferences file path not set or file not found.") # Optional logging
            return {}
        try:
            with open(self.preferences_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            # print(Fore.RED + f"Error loading preferences in UI fallback: {e}") # Optional logging
            return {}
        


    def save_preferences(self):
        """Saves the current preferences dictionary to the file."""
        if not self.preferences_file:
            print(Fore.RED + "\nError: Preferences file path not set. Cannot save.")
            return
        try:
            # Ensure the directory exists (belt-and-suspenders, might be handled elsewhere)
            os.makedirs(os.path.dirname(self.preferences_file), exist_ok=True)
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(Fore.RED + f"\nError saving preferences: {e}")

    def clear_terminal(self):
        """Clear terminal with fallback and scroll reset"""
        # Clear screen
        print("\033[2J", end="")
        # Move cursor to top-left
        print("\033[H", end="")
        # Clear scroll buffer
        sys.stdout.write("\033[3J")
        sys.stdout.flush()

    def display_header(self, QURAN_CLI_ASCII, theme_color='red'):
        """Display app header dynamically with selectable theme color for ASCII art."""

        # Map color name to colorama code
        color_map = {
            'red': Fore.RED,
            'white': Fore.WHITE,
            'green': Fore.GREEN,
            'blue': Fore.BLUE,        # Added
            'yellow': Fore.YELLOW,    # Added
            'magenta': Fore.MAGENTA,  # Added
            'cyan': Fore.CYAN         # Added
        }
        # Get the color, default to Fore.RED if invalid or None
        selected_color = color_map.get(theme_color, Fore.RED)

        # Apply color to the ASCII art and print it *ONCE*
        themed_ascii_art = selected_color + QURAN_CLI_ASCII + Style.RESET_ALL
        print(themed_ascii_art)

        # --- REST OF THE HEADER (unchanged from your original code) ---
        # Call _get_update_message() inside display_header to ensure latest updates
        update_message = self._get_update_message()
        if update_message:
            print(update_message)

        # --- Fetch Download Count ---
        download_count_str = "N/A" # Default
        if self.download_counter:
            count = self.download_counter.get_total_downloads()
            if count is not None and count >= 0:
                try:
                    download_count_str = f"{count:,}" # Format with commas
                except ValueError: # Handle potential formatting errors
                    download_count_str = str(count)

        box_width = 53 # Keep consistent width

        print(Fore.RED + "╭──" + Style.BRIGHT + Fore.GREEN + "✨ As-salamu alaykum! " + Fore.RED + Style.NORMAL + "─" * 26 + "╮")
        print(Fore.RED + "│ " + Fore.LIGHTMAGENTA_EX + "QuranCLI – Read, Listen & Generate Captions".ljust(49) + Fore.RED + "│")
        print(Fore.RED + "├" + "─" * 50 + "┤")
        print(Fore.RED + "│ " + Style.BRIGHT + "Version: " + Style.NORMAL + f"v{VERSION}".ljust(40) + "│")
        # --- Add Downloads Line ---
        downloads_line = f"{Style.BRIGHT}Downloads: {Style.NORMAL}{Fore.MAGENTA}{download_count_str}✨"
        print(Fore.RED + "│ " + downloads_line.ljust(box_width + len(Style.BRIGHT+Style.NORMAL)) + Fore.RED + "│" + Style.RESET_ALL)
        # --- End Add ---
        print(Fore.RED + "│ " + Style.BRIGHT + "Author: " + Style.NORMAL + "https://github.com/anonfaded".ljust(41) + "│")
        # --- Add Discord Line ---
        print(Fore.RED + "│ " + Fore.MAGENTA + Style.BRIGHT + "Tried FadCam & FadCrypt apps?".ljust(49) + Style.NORMAL + Fore.RED + "│")
        print(Fore.RED + "│ " + Style.NORMAL + " ⤷ Join us! " + Fore.CYAN + "https://discord.gg/kvAZvdkuuN".ljust(37) + Fore.RED + "│" + Style.RESET_ALL)
        # --- End Discord Line ---
        print(Fore.RED + "├" + "─" * 50 + "┤")
        print(Fore.RED + "│ " + Style.BRIGHT + "Instructions:".ljust(49) + Style.NORMAL + "│")
        print(Fore.RED + "│ • " + Fore.WHITE + "Type " + Fore.RED + "'quit'" + Fore.WHITE + " or " + Fore.RED + "'exit'" + Fore.WHITE + " to close the program".ljust(26) + Fore.RED + "│")
        print(Fore.RED + "│ • " + Fore.WHITE + "Press" + Fore.RED + " Ctrl+C" + Fore.WHITE + " to cancel current action".ljust(35) + Fore.RED + "│")
        print(Fore.RED + "│ • " + Fore.MAGENTA + "Confused?" + Fore.WHITE + " Type " + Fore.RED + "'info'" + Fore.WHITE + " to see help page".ljust(26) + Fore.RED + "│")
        print(Fore.RED + "╰" + "─" * 50 + "╯\n")



    def _get_update_message(self) -> str:
        """Check for a new version and return the update message"""
        if not self.github_updater:
            return ""

        latest_tag_name, release_url = self.github_updater.get_latest_release_info()

        if not latest_tag_name or not release_url:
            return ""

        if self.github_updater.compare_versions(latest_tag_name, self.github_updater.current_version) > 0:
            return (
                f"\n{Fore.GREEN}{'─' * 60}\n"
                f"✨🚀 {Fore.YELLOW}UPDATE AVAILABLE! 🚀✨\n"
                f"{Fore.GREEN}New Version: {Fore.MAGENTA}{latest_tag_name}\n"
                f"{Fore.GREEN}🔗 Download: {Fore.MAGENTA}{release_url}\n"
                f"{Fore.GREEN}{'─' * 60}\n"
            )


        return ""




# -------------- Fix Start for this method(paginate_output)-----------
    def paginate_output(self, ayahs: List[Ayah], page_size: int = None, surah_info: SurahInfo = None, start_page: int = 1):
        """
        Display ayahs with pagination and allow bookmarking from the reader view.

        Args:
            ayahs (List[Ayah]): List of Ayah objects to display.
            page_size (int, optional): Number of ayahs per page.
            surah_info (SurahInfo, optional): Surah metadata.
        """
        if page_size is None:
            page_size = max(1, (self.term_size.lines - 10) // 6)

        total_pages = math.ceil(len(ayahs) / page_size)
        current_page = start_page

        while True:
            self.clear_terminal()
            print(Style.BRIGHT + Fore.RED + "=" * self.term_size.columns)
            print(f"\U0001F4D6 Surah {surah_info.surah_number}: {surah_info.surah_name} ({surah_info.surah_name_ar})")
            print(f"Page {current_page}/{total_pages}")
            print(Style.BRIGHT + Fore.RED + "=" * self.term_size.columns)

            # Display Surah Description
            if surah_info.description:
                print(Style.DIM + Fore.YELLOW + "Description:" + Style.RESET_ALL + Style.DIM)
                wrapped_desc = self.wrap_text(surah_info.description, self.term_size.columns - 4)
                for line in wrapped_desc.split('\n'):
                    print(Style.DIM + "  " + line + Style.RESET_ALL)
                print(Style.BRIGHT + Fore.RED + "-" * self.term_size.columns)

            # Display ayahs for current page
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(ayahs))
            local_ayahs = ayahs[start_idx:end_idx]
            for ayah in local_ayahs:
                self.display_single_ayah(ayah)

            # Navigation Menu (aligned, with short commands)
            nav_options = [
                (f"{Fore.CYAN}n{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Next page"),
                (f"{Fore.CYAN}p{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Previous page"),
                (f"{Fore.YELLOW}bookmark{Style.DIM}/bm{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Add bookmark for an ayah on this page"),
                (f"{Fore.MAGENTA}reverse{Style.DIM}/rev{Style.NORMAL}{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Toggle Arabic reversal"),
                (f"{Fore.YELLOW}a{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Play audio"),
            ]
            
            # Add special Ayatul Kursi option only for Surah 2
            if surah_info and surah_info.surah_number == 2:
                nav_options.insert(-1, (f"{Fore.GREEN}k{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Play Ayatul Kursi (Quick Link)"))
                
            nav_options.append((f"{Fore.RED}q{Style.RESET_ALL}", f"{Style.NORMAL}{Fore.WHITE}Return"))
            
            max_cmd_len = max(len(self._strip_ansi(cmd)) for cmd, _ in nav_options)
            box_width = 26
            separator = "─" * box_width
            print(Fore.RED + "\n╭─ " + Style.BRIGHT + Fore.GREEN + "\U0001F9ED Navigation")
            for cmd, desc in nav_options:
                pad = " " * (max_cmd_len - len(self._strip_ansi(cmd)))
                print(Fore.RED + f"│ → {cmd}{pad} : {desc}{Style.RESET_ALL}")
            print(Fore.RED + "╰" + separator)

            # User input prompt
            choice = input(Fore.RED + "  ❯ " + Fore.WHITE).lower().strip()

            if choice == 'n' and current_page < total_pages:
                current_page += 1
            elif choice == 'p' and current_page > 1:
                current_page -= 1
            elif choice == 'a':
                self.display_audio_controls(surah_info)
            elif choice == 'k' and surah_info and surah_info.surah_number == 2:
                # Special handling for Ayatul Kursi audio
                self.display_ayatul_kursi_audio_controls()
            elif choice in ['reverse', 'rev']:
                self.data_handler.toggle_arabic_reversal()
            elif choice in ['bookmark', 'bm']:
                # List ayahs on this page for user to select
                print(Fore.CYAN + "\nSelect an ayah to bookmark from this page:")
                for idx, ayah in enumerate(local_ayahs, 1):
                    ayah_num = getattr(ayah, 'number', None)
                    if ayah_num is None:
                        ayah_num = getattr(ayah, 'ayah_number', '?')
                    print(f"{Fore.GREEN}{idx}. Ayah {ayah_num}: {Fore.WHITE}{ayah.content[:60]}{'...' if len(ayah.content) > 60 else ''}")
                print(Fore.YELLOW + "Enter the number of the ayah to bookmark, or 'b' to cancel.")
                while True:
                    sel = input(Fore.RED + "  ❯ " + Fore.WHITE).strip()
                    if sel.lower() == 'b':
                        break
                    if sel.isdigit() and 1 <= int(sel) <= len(local_ayahs):
                        selected_ayah = local_ayahs[int(sel) - 1]
                        ayah_num = getattr(selected_ayah, 'number', None)
                        if ayah_num is None:
                            ayah_num = getattr(selected_ayah, 'ayah_number', '?')
                        note = input(Fore.CYAN + "Enter a note for this bookmark (optional, max 300 chars):\n" + Fore.RED + "  ❯ " + Fore.WHITE).strip()[:300]
                        try:
                            # Ensure we're working with proper integer values for ayah number
                            ayah_num = int(ayah_num) if isinstance(ayah_num, (int, str)) and str(ayah_num).isdigit() else None
                            
                            if ayah_num is None:
                                print(Fore.RED + "Invalid ayah number. Cannot bookmark.")
                                input(Fore.YELLOW + "Press Enter to continue...")
                                break
                                
                            # Make the bookmark call
                            self.app.set_bookmark(surah_info.surah_number, ayah_num, note)
                            print(Fore.GREEN + f"Bookmark added for Surah {surah_info.surah_number}, Ayah {ayah_num}.")
                        except Exception as e:
                            print(Fore.RED + f"Failed to add bookmark: {e}")
                            # Add more details for debugging
                            print(Fore.YELLOW + f"Surah: {surah_info.surah_number}, Ayah: {ayah_num}")
                        input(Fore.YELLOW + "Press Enter to continue...")
                        break
                    else:
                        print(Fore.RED + "Invalid selection. Please enter a valid number or 'b' to cancel.")
            elif choice == 'q':
                return
            elif not choice:
                if current_page < total_pages:
                    current_page += 1
                else:
                    return

    def _strip_ansi(self, s: str) -> str:
        """Remove ANSI escape codes for accurate length calculation."""
        import re
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        return ansi_escape.sub('', s)
# -------------- Fix Ended for this method(paginate_output)-----------


    def display_single_ayah(self, ayah: Ayah):
        """
        Display a single ayah with Arabic, Transliteration, Urdu, Turkish, and English.
        Display is controlled by reading_config settings - each translation can be toggled on/off.
        On Linux/macOS/Windows, applies reversal to Arabic and Urdu if Arabic reversal is enabled.
        Turkish is in Latin script so no reversal is applied.
        """
        print(Style.BRIGHT + Fore.GREEN + f"\n[{ayah.number}]")

        # Get reading config for conditional display
        reading_config = self.preferences.get("reading_config", {})
        print(Style.BRIGHT + Fore.RED + "Arabic:" + Style.NORMAL + Fore.WHITE)
        try:
            formatted_arabic = self.data_handler.fix_arabic_text(ayah.content)
            # Apply reversal on Linux/macOS/Windows if enabled
            if self.data_handler.arabic_reversed:
                import arabic_reshaper
                from bidi.algorithm import get_display
                reshaped = arabic_reshaper.reshape(formatted_arabic)
                formatted_arabic = get_display(reshaped)[::-1]
        except Exception as e:
            print(f"[DEBUG] Error formatting Arabic: {e}")
            formatted_arabic = ayah.content
        print("    " + formatted_arabic)

        # 2. Transliteration (conditional based on reading config)
        if reading_config.get("show_transliteration", True) and ayah.transliteration:
            print(Style.BRIGHT + Fore.RED + "\nTransliteration:" + Style.NORMAL + Fore.WHITE)
            wrapped_translit = self.wrap_text(ayah.transliteration, self.term_size.columns - 4)
            for line in wrapped_translit.split('\n'):
                print("    " + line)

        # 3. Urdu Translation (conditional based on reading config)
        if reading_config.get("show_urdu", True) and ayah.translation_ur:
            print(Style.BRIGHT + Fore.MAGENTA + "\nUrdu Translation:" + Style.NORMAL + Fore.WHITE)
            try:
                formatted_urdu = ayah.translation_ur
                if self.data_handler.arabic_reversed:
                    formatted_urdu = formatted_urdu[::-1]
            except Exception as e:
                print(f"[DEBUG] Error formatting Urdu: {e}")
                formatted_urdu = ayah.translation_ur
            wrapped_urdu = self.wrap_text(formatted_urdu, self.term_size.columns - 4)
            for line in wrapped_urdu.split('\n'):
                print("    " + line)

        # 4. Turkish Translation (conditional based on reading config)
        if reading_config.get("show_turkish", False) and ayah.translation_tr:
            print(Style.BRIGHT + Fore.MAGENTA + "\nTurkish Translation:" + Style.NORMAL + Fore.WHITE)
            try:
                formatted_turkish = ayah.translation_tr
                # Turkish is in Latin script, no reversal needed
                # if self.data_handler.arabic_reversed:
                #     formatted_turkish = formatted_turkish[::-1]
            except Exception as e:
                print(f"[DEBUG] Error formatting Turkish: {e}")
                formatted_turkish = ayah.translation_tr
            wrapped_turkish = self.wrap_text(formatted_turkish, self.term_size.columns - 4)
            for line in wrapped_turkish.split('\n'):
                print("    " + line)

        # 5. English Translation (conditional based on reading config)
        if reading_config.get("show_english", True) and ayah.text:
            print(Style.BRIGHT + Fore.MAGENTA + "\nEnglish Translation:" + Style.NORMAL + Fore.WHITE)
            cached_translation = ayah.text
            wrapped_translation = self.wrap_text(cached_translation, self.term_size.columns - 4)
            for line in wrapped_translation.split('\n'):
                print("    " + line)

        # Separator
        print(Style.BRIGHT + Fore.GREEN + "\n" + "-" * min(40, self.term_size.columns))


    def wrap_text(self, text: str, width: int) -> str:
        """Wrap text to specified width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def display_ayahs(self, ayahs: List[Ayah], surah_info: SurahInfo):
        """Display ayahs with pagination"""
        self.paginate_output(ayahs, surah_info=surah_info)



# core/ui.py (inside class UI)

    def handle_audio_choice(self, choice: str, surah_info: SurahInfo):
        """Handle audio control input and force display refresh after load/action."""
        needs_redraw = False # Flag to indicate if redraw is needed at the end
        try:
            if choice == 'p':
                surah_num = surah_info.surah_number
                # Check if current audio is finished playing
                is_finished = (self.audio_manager.current_audio and 
                              self.audio_manager.duration > 0 and 
                              self.audio_manager.current_position >= self.audio_manager.duration - 0.1)
                
                # New condition: replay from beginning if finished
                if is_finished:
                    # Make sure the audio file is still available
                    if self.audio_manager.current_audio and os.path.exists(self.audio_manager.current_audio):
                        try:
                            # Directly reload and play the audio instead of using seek
                            pygame.mixer.music.stop()
                            pygame.mixer.music.load(str(self.audio_manager.current_audio))
                            pygame.mixer.music.play()
                            
                            # Reset tracking variables
                            self.audio_manager.current_position = 0
                            self.audio_manager.start_time = time.time()
                            self.audio_manager.is_playing = True
                            
                            # Start progress tracking
                            self.audio_manager.start_progress_tracking()
                            
                            # Redraw UI immediately
                            self._redraw_audio_ui(surah_info)
                            return
                        except Exception as e:
                            print(Fore.RED + f"\nError replaying audio: {e}")
                            # Don't sleep here as it would block UI
                
                load_new = (not self.audio_manager.current_audio or
                            self.audio_manager.current_surah != surah_num)

                if load_new:
                    self.audio_manager.stop_audio(reset_state=True)
                    print(Fore.YELLOW + "\nℹ Loading default reciter...") # Show status before potential long wait
                    
                    # Determine if we should use Ayatul Kursi or regular surah preferences
                    # Check both the surah_info and whether last playback was Ayatul Kursi
                    using_ayatul_kursi_player = (surah_info.surah_name == "Ayatul Kursi" and 
                                               any(key.startswith("ayatul_kursi_") for key in surah_info.audio.keys()))
                    
                    # We only want to use normal Surah 2 preferences when:
                    # 1. We're in normal Surah 2 view (not Ayatul Kursi view)
                    # 2. We didn't just play Ayatul Kursi
                    force_regular_surah = (surah_num == 2 and 
                                          not using_ayatul_kursi_player and 
                                          not self.audio_manager.last_was_ayatul_kursi)
                    
                    if using_ayatul_kursi_player or (surah_num == 2 and self.audio_manager.last_was_ayatul_kursi and not force_regular_surah):
                        # Use the Ayatul Kursi-specific preferences
                        reciter_pref = self.preferences.get("ayatul_kursi")
                        pref_key = "ayatul_kursi"
                        is_ayatul_kursi = True
                    else:
                        # Use regular surah preferences
                        reciter_pref = self.preferences.get(str(surah_num))
                        pref_key = str(surah_num)
                        is_ayatul_kursi = False
                    
                    if reciter_pref and "reciter_url" in reciter_pref and "reciter_name" in reciter_pref:
                        audio_url = reciter_pref["reciter_url"]
                        reciter_name = reciter_pref["reciter_name"]
                        print(Fore.GREEN + f" ✅ Using saved reciter: {reciter_name}")
                    elif surah_info.audio:
                        reciter_id = next(iter(surah_info.audio))
                        audio_url = surah_info.audio[reciter_id]["url"] 
                        reciter_name = surah_info.audio[reciter_id]["reciter"]
                        print(Fore.YELLOW + f" ⚠️ No preference saved, using default: {reciter_name}")
                    else:
                        print(Fore.RED + "\n❌ No audio data found."); return

                    # --- Run download and play ---
                    if is_ayatul_kursi:
                        # Add special prefix for Ayatul Kursi
                        reciter_with_prefix = f"AyatulKursi_{reciter_name}"
                        asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_with_prefix))
                        # Set the flag to remember we're playing Ayatul Kursi
                        self.audio_manager.last_was_ayatul_kursi = True
                    else:
                        # Regular surah audio
                        asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_name))
                        # Clear the flag when playing regular surah
                        self.audio_manager.last_was_ayatul_kursi = False
                        
                    # --- Directly redraw after async call completes ---
                    self._redraw_audio_ui(surah_info) # Call the redraw helper
                    # --- End Direct Redraw ---
                
                # Add missing pause/resume handling
                elif self.audio_manager.is_playing:
                    self.audio_manager.pause_audio()
                    needs_redraw = True # Redraw after pause
                else:
                    self.audio_manager.resume_audio()
                    needs_redraw = True # Redraw after resume

            elif choice == 's':
                self.audio_manager.stop_audio(reset_state=True)
                print(Fore.RED + "⏹ Audio stopped and reset.")
                needs_redraw = True # Redraw after stop

            elif choice == 'l':  # Toggle loop mode
                self.audio_manager.toggle_loop()
                needs_redraw = True  # Redraw after toggling loop mode
                
            elif choice == 't':  # Set sleep timer
                # Show timer setting interface
                self._show_timer_settings(surah_info)
                needs_redraw = True  # Redraw after setting timer

            elif choice == 'r': # Change Reciter
                surah_num = surah_info.surah_number
                if not surah_info.audio:
                    print(Fore.RED + "\n❌ No reciters available."); return
                
                # Check if this is Ayatul Kursi playback
                is_ayatul_kursi = (surah_info.surah_name == "Ayatul Kursi" and 
                                  any(key.startswith("ayatul_kursi_") for key in surah_info.audio.keys()))

                original_display_needs_restore = True
                while True: # Reciter selection loop
                    self.clear_terminal()
                    print(Style.BRIGHT + Fore.RED + "\nAudio Player - Select Reciter" + Style.RESET_ALL)
                    # ... (display reciter options - keep as before) ...
                    reciter_options = list(surah_info.audio.items())
                    for i, (rid, info) in enumerate(reciter_options): print(f"{Fore.GREEN}{i+1}{Fore.WHITE} : {info['reciter']}")

                    print(Fore.WHITE + "\nEnter number ('q' to cancel): ", end="", flush=True)

                    try:
                         reciter_input = input().strip().lower()
                         if reciter_input == 'q': break

                         if reciter_input.isdigit():
                             choice_idx = int(reciter_input) - 1
                             if 0 <= choice_idx < len(reciter_options):
                                 # ... (get selected reciter info - keep as before) ...
                                 selected_id, selected_info = reciter_options[choice_idx]
                                 audio_url, reciter_name = selected_info["url"], selected_info["reciter"]

                                 print(f"\n{Fore.CYAN}Selected: {reciter_name}")
                                 self.audio_manager.stop_audio(reset_state=True)

                                 # --- Run download and play ---
                                 if is_ayatul_kursi:
                                     # For Ayatul Kursi, use special reciter naming
                                     reciter_prefix = f"AyatulKursi_{reciter_name}"
                                     asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_prefix))
                                     # Set the flag to remember we're playing Ayatul Kursi
                                     self.audio_manager.last_was_ayatul_kursi = True
                                 else:
                                     # Regular surah audio
                                     asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_name))
                                     # Clear the flag when playing regular surah
                                     self.audio_manager.last_was_ayatul_kursi = False
                                     
                                 # --- Directly redraw after async call ---
                                 self._redraw_audio_ui(surah_info)
                                 # --- End Direct Redraw ---

                                 # Save preference - special handling for Ayatul Kursi
                                 if is_ayatul_kursi:
                                     # Create special Ayatul Kursi preference key
                                     pref_key = "ayatul_kursi"
                                     self.preferences[pref_key] = {"reciter_name": reciter_name, "reciter_url": audio_url}
                                 else:
                                     # Normal surah preference
                                     self.preferences[str(surah_num)] = {"reciter_name": reciter_name, "reciter_url": audio_url}
                                     
                                 self.save_preferences()
                                 print(Fore.GREEN + " Preference saved.") # Add space
                                 original_display_needs_restore = False
                                 time.sleep(1.0) # Shorter pause
                                 break # Exit selection loop successfully
                             else: print(Fore.RED + "\nInvalid number.")
                         else: print(Fore.RED + "\nInvalid input.")

                    except ValueError: print(Fore.RED + "\nInvalid number input.")
                    except KeyboardInterrupt: print(Fore.YELLOW + "\nSelection cancelled."); break
                    except Exception as e_sel: print(Fore.RED + f"\nError during selection: {e_sel}")
                    time.sleep(1.5)
                # End reciter selection loop

                # Only redraw main UI if user cancelled or selection failed before loading new audio
                if original_display_needs_restore:
                    needs_redraw = True

            # If any action indicated a redraw is needed (pause, resume, stop, cancel reciter select)
            if needs_redraw:
                 self._redraw_audio_ui(surah_info)


        except Exception as e:
            print(Fore.RED + f"\nError handling audio command '{choice}': {e}")
            time.sleep(1)
            # Try to redraw even on error to restore some UI state
            self._redraw_audio_ui(surah_info)


    def _show_timer_settings(self, surah_info: SurahInfo):
        """Display the timer setting interface."""
        # Use the global _restore_terminal_settings function
        global _restore_terminal_settings
        if '_restore_terminal_settings' in globals():
            _restore_terminal_settings()
        
        try:
            self.clear_terminal()
            print(Style.BRIGHT + Fore.RED + "\nAudio Player - Sleep Timer Settings" + Style.RESET_ALL)
            
            # Show current timer status
            timer_status = self.audio_manager.get_timer_status()
            if timer_status['enabled']:
                remaining = timer_status['remaining']
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                seconds = int(remaining % 60)
                
                if hours > 0:
                    print(Fore.GREEN + f"\nCurrent timer: {hours}h {minutes}m {seconds}s remaining")
                else:
                    print(Fore.GREEN + f"\nCurrent timer: {minutes}m {seconds}s remaining")
            else:
                print(Fore.YELLOW + "\nNo timer currently set")
            
            # Helper text about the timer
            print(Fore.CYAN + "\n📌 About the Sleep Timer:")
            print(Fore.WHITE + "• The timer will automatically stop audio playback when it expires")
            print(Fore.WHITE + "• Make sure audio is playing before setting a timer")
            print(Fore.WHITE + "• You can cancel the timer at any time")
            print(Fore.WHITE + "• When timer expires, press 'p' to play the audio again")
            
            # Display options
            print(Fore.CYAN + "\nSelect an option:")
            print(Fore.GREEN + "1. Set timer (minutes)")
            print(Fore.GREEN + "2. Set timer (hours and minutes)")
            print(Fore.RED + "3. Cancel current timer")
            print(Fore.YELLOW + "0. Back to audio player")
            
            choice = input(Fore.RED + "\n> " + Fore.WHITE).strip()
            
            if choice == "1":
                # Set timer in minutes
                try:
                    print(Fore.CYAN + "\nEnter minutes for timer (1-300):" + Fore.WHITE)
                    minutes = int(input(Fore.RED + "> " + Fore.WHITE).strip())
                    
                    if 1 <= minutes <= 300:  # Reasonable limit
                        if self.audio_manager.set_timer(minutes):
                            print(Fore.GREEN + f"\n✅ Timer set for {minutes} minute(s)")
                            time.sleep(1.5)
                    else:
                        print(Fore.RED + "\n❌ Invalid time. Please enter a value between 1-300 minutes.")
                        time.sleep(1.5)
                except ValueError:
                    print(Fore.RED + "\n❌ Invalid input. Please enter a number.")
                    time.sleep(1.5)
                    
            elif choice == "2":
                # Set timer with hours and minutes
                try:
                    print(Fore.CYAN + "\nEnter hours (0-24):" + Fore.WHITE)
                    hours = int(input(Fore.RED + "> " + Fore.WHITE).strip())
                    
                    print(Fore.CYAN + "\nEnter minutes (0-59):" + Fore.WHITE)
                    minutes = int(input(Fore.RED + "> " + Fore.WHITE).strip())
                    
                    if 0 <= hours <= 24 and 0 <= minutes <= 59:
                        total_minutes = hours * 60 + minutes
                        if total_minutes > 0:
                            if self.audio_manager.set_timer(total_minutes):
                                if hours > 0:
                                    print(Fore.GREEN + f"\n✅ Timer set for {hours} hour(s) and {minutes} minute(s)")
                                else:
                                    print(Fore.GREEN + f"\n✅ Timer set for {minutes} minute(s)")
                                time.sleep(1.5)
                        else:
                            print(Fore.RED + "\n❌ Timer must be at least 1 minute.")
                            time.sleep(1.5)
                    else:
                        print(Fore.RED + "\n❌ Invalid time. Hours must be 0-24, minutes 0-59.")
                        time.sleep(1.5)
                except ValueError:
                    print(Fore.RED + "\n❌ Invalid input. Please enter a number.")
                    time.sleep(1.5)
                    
            elif choice == "3":
                # Cancel the current timer
                if timer_status['enabled']:
                    self.audio_manager.cancel_timer()
                    print(Fore.YELLOW + "\n⏹ Timer cancelled")
                    time.sleep(1.5)
                else:
                    print(Fore.YELLOW + "\nNo timer was set")
                    time.sleep(1.5)
            
            # Option "0" or any other input just returns to audio player
                    
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nTimer setting cancelled.")
            time.sleep(1)
        except Exception as e:
            print(Fore.RED + f"\nError in timer settings: {e}")
            time.sleep(1.5)

# core/ui.py (inside class UI)

    def _redraw_audio_ui(self, surah_info: SurahInfo):
        """Helper function to clear terminal and redraw the audio UI."""
        try:
            # Get the latest display string
            display_string = self.get_audio_display(surah_info)
            # --- ALWAYS CLEAR ---
            self.clear_terminal()
            # --- END ALWAYS CLEAR ---
            # Print the display string
            print(display_string, end='', flush=True)
            # Return the string that was printed, can be used for last_display
            return display_string
        except Exception as e:
            # Fallback if redraw fails
            # Avoid recursion if clear_terminal itself fails
            try: self.clear_terminal()
            except: pass
            print(f"\n{Fore.RED}Error during redraw: {e}{Style.RESET_ALL}")
            return None # Indicate failure
        
    async def handle_audio_playback(self, url: str, surah_num: int, reciter: str):
        """Handle audio download and playback"""
        try:
            print(Fore.YELLOW + "\n⏳ Starting download, please wait...")
            print(Fore.CYAN + "This may take a moment depending on your internet speed.")
                
            file_path = await self.audio_manager.download_audio(url, surah_num, reciter)
            print(Fore.GREEN + "\n✓ Starting playback...")
            
            # Check if this is an Ayatul Kursi reciter
            is_ayatul_kursi = reciter.startswith("AyatulKursi_")
            self.audio_manager.play_audio(file_path, reciter, is_ayatul_kursi)
        except Exception as e:
            print(Fore.RED + f"\nError: {str(e)}")
            print(Fore.YELLOW + "Please try again or choose a different reciter.")
            time.sleep(2)



    def display_audio_controls(self, surah_info: SurahInfo):
        """Display audio controls with real-time updates (Cross-Platform Input)."""
        global _original_termios_settings # Access the global variable
        global HAS_TERMIOS # Check if termios is available

        if not surah_info.audio:
            print(Fore.RED + "\n❌ Audio not available for this surah")
            time.sleep(1.5)
            return
            
        # Check if this is Ayatul Kursi special case
        is_ayatul_kursi = (surah_info.surah_name == "Ayatul Kursi" and 
                          any(key.startswith("ayatul_kursi_") for key in surah_info.audio.keys()))

        fd = None
        is_unix = sys.platform != "win32"
        # --- Define new_settings variable here to be accessible later ---
        new_settings = None

        # --- Setup Terminal for Non-Blocking Input (Unix) ---
        if is_unix and 'HAS_TERMIOS' in globals() and HAS_TERMIOS and termios is not None:
            try:
                fd = sys.stdin.fileno()
                if termios is not None:
                    _original_termios_settings = termios.tcgetattr(fd)
                    # --- Make a copy to modify and store in new_settings ---
                    new_settings = termios.tcgetattr(fd)
                    new_settings[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN) # lflags
                    new_settings[6][termios.VMIN] = 1
                    new_settings[6][termios.VTIME] = 0
                    termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)

                    # --- Check if it actually worked ---
                    if (termios.tcgetattr(fd)[3] & termios.ICANON) or \
                    (termios.tcgetattr(fd)[3] & termios.ECHO):
                        print(f"\n{Fore.YELLOW}Warning: Terminal did not fully enter cbreak mode (ICANON or ECHO still set).")
                        _restore_terminal_settings() # Use helper
                        is_unix = False
                        _original_termios_settings = None
                        new_settings = None # Clear modified settings as well
                        print(f"{Fore.YELLOW}Audio controls will require pressing Enter.{Style.RESET_ALL}")

            except Exception as e:
                print(f"\n{Fore.YELLOW}Warning: Could not set terminal for instant key input: {e}")
                print(f"{Fore.YELLOW}Audio controls will require pressing Enter.{Style.RESET_ALL}")
                if _original_termios_settings is not None and termios is not None: 
                    try: termios.tcsetattr(fd, termios.TCSADRAIN, _original_termios_settings)
                    except: pass
                is_unix = False
                _original_termios_settings = None
                new_settings = None

        # --- Main Audio Control Loop ---
        last_display = ""
        running = True
        try:
            # Initial Draw
            last_display = self._redraw_audio_ui(surah_info) or ""

            while running:
                choice = None
                reciter_selection_active = False # Flag to know if we are inside reciter menu

                # --- Platform-Specific Non-Blocking Input ---
                try:
                    if sys.platform == "win32":
                        # Handle Windows-specific input
                        import msvcrt  # Import inside the try block for safety
                        if msvcrt.kbhit():
                            key_byte = msvcrt.getch()
                            if key_byte == b'\x00' or key_byte == b'\xe0':
                                msvcrt.getch()  # Consume the second byte of extended keys
                                continue
                            else:
                                try: 
                                    choice = key_byte.decode('utf-8', errors='ignore').lower()
                                except UnicodeDecodeError: 
                                    continue
                    elif is_unix and 'HAS_TERMIOS' in globals() and HAS_TERMIOS: # Use the Unix non-blocking method if setup succeeded
                        char_read = _unix_getch_non_blocking()
                        if char_read:
                            if len(char_read) > 1 and char_read.startswith('\x1b'):
                                pass # Ignore escape sequences for now
                            else:
                                choice = char_read.lower()
                    else: # Fallback (shouldn't be reached often now)
                        pass
                except ImportError:
                    print(f"\n{Fore.YELLOW}Warning: Missing module for keyboard input.{Style.RESET_ALL}")
                    time.sleep(1)
                    continue
                except Exception as e_input:
                    print(f"\n{Fore.RED}Input Error: {e_input}{Style.RESET_ALL}")
                    time.sleep(1)
                    continue


                # --- Process Input Choice ---
                if choice:
                    # Remove debug message that prints key pressed
                    # print(f"\n{Fore.BLUE}Debug: Key pressed '{choice}'{Style.RESET_ALL}")
                    
                    if choice == 'q': running = False

                    # --- Handle Loop Toggle ('l') ---
                    elif choice == 'l':
                        self.audio_manager.toggle_loop()
                        # Force redraw to show updated loop status
                        last_display = self._redraw_audio_ui(surah_info) or ""
                        time.sleep(0.3) # Slight feedback delay
                        continue
                        
                    # --- Handle Timer Setting ('t') ---
                    elif choice == 't':
                        # Call our timer settings method and handle any errors
                        try:
                            print(f"\n{Fore.YELLOW}Opening timer settings...{Style.RESET_ALL}")
                            
                            # Restore terminal for input - call helper function instead of using termios directly
                            if is_unix and 'HAS_TERMIOS' in globals() and HAS_TERMIOS and '_restore_terminal_settings' in globals():
                                _restore_terminal_settings()
                            
                            # Call timer settings directly
                            self._show_timer_settings(surah_info)
                            
                        except Exception as e:
                            print(f"\n{Fore.RED}Error in timer settings: {e}{Style.RESET_ALL}")
                            time.sleep(1.5)
                        finally:
                            # Always redraw UI after timer setting
                            last_display = self._redraw_audio_ui(surah_info) or ""
                        continue

                    # --- Handle Reciter Selection ('r') ---
                    elif choice == 'r':
                        surah_num = surah_info.surah_number
                        if not surah_info.audio:
                            print(Fore.RED + "\n❌ No reciters available."); time.sleep(1); continue

                        reciter_selection_active = True # Set flag
                        original_display_needs_restore = True # Assume redraw needed unless selection successful

                        # --- Temporarily Restore Terminal for Input ---
                        if is_unix and _original_termios_settings:
                            try:
                                # print("DEBUG: Restoring terminal for reciter input...") # Debug
                                # Use original settings, NOT _restore_terminal_settings helper here
                                termios.tcsetattr(fd, termios.TCSADRAIN, _original_termios_settings)
                            except Exception as e_restore:
                                print(f"\n{Fore.RED}Warning: Failed to restore terminal for input: {e_restore}")
                                # Proceed anyway, input might just lack echo

                        # --- Reciter Selection Input Loop ---
                        selected_reciter_data = None
                        try:
                            while True: # Loop for reciter number input
                                self.clear_terminal() # Clear before showing options
                                print(Style.BRIGHT + Fore.RED + "\nAudio Player - Select Reciter" + Style.RESET_ALL)
                                reciter_options = list(surah_info.audio.items())
                                for i, (rid, info) in enumerate(reciter_options): print(f"{Fore.GREEN}{i+1}{Fore.WHITE} : {info['reciter']}")
                                print(Fore.WHITE + "\nEnter number ('q' to cancel): ", end="", flush=True) # Prompt

                                # *** Use standard input() now ***
                                reciter_input = input().strip().lower() # This will now echo

                                if reciter_input == 'q': break # Exit inner loop
                                if reciter_input.isdigit():
                                    choice_idx = int(reciter_input) - 1
                                    if 0 <= choice_idx < len(reciter_options):
                                        selected_id, selected_info = reciter_options[choice_idx]
                                        selected_reciter_data = {
                                            "url": selected_info["url"],
                                            "name": selected_info["reciter"],
                                            "surah_num": surah_num
                                        }
                                        print(f"\n{Fore.CYAN}Selected: {selected_reciter_data['name']}")
                                        
                                        # Save preference based on content type
                                        if is_ayatul_kursi:
                                            # Save Ayatul Kursi preference separately
                                            self.preferences["ayatul_kursi"] = {
                                                "reciter_name": selected_reciter_data['name'],
                                                "reciter_url": selected_reciter_data['url']
                                            }
                                        else:
                                            # Normal surah preference
                                            self.preferences[str(surah_num)] = {
                                                "reciter_name": selected_reciter_data['name'],
                                                "reciter_url": selected_reciter_data['url']
                                            }
                                            
                                        self.save_preferences()
                                        print(Fore.GREEN + " Preference saved.")
                                        original_display_needs_restore = False
                                        time.sleep(1.0)
                                        break # Exit inner loop successfully
                                    else: print(Fore.RED + "\nInvalid number."); time.sleep(1.5)
                                else: print(Fore.RED + "\nInvalid input."); time.sleep(1.5)
                        except KeyboardInterrupt:
                            print(Fore.YELLOW + "\nSelection cancelled.")
                        except Exception as e_sel:
                            print(Fore.RED + f"\nError during selection: {e_sel}")
                        # --- End Reciter Input Loop ---

                        # --- Re-apply Cbreak Settings AFTER input attempt ---
                        if is_unix and new_settings: # Check if we have settings to re-apply
                            try:
                                # print("DEBUG: Re-applying cbreak settings after reciter input...") # Debug
                                termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
                            except Exception as e_apply:
                                print(f"\n{Fore.RED}Warning: Failed to re-apply terminal settings: {e_apply}")
                                # If this fails, subsequent input might require Enter

                        reciter_selection_active = False # Clear flag

                        # --- Play selected reciter if chosen ---
                        if selected_reciter_data:
                            self.audio_manager.stop_audio(reset_state=True)
                            
                            # Prepare playback based on content type
                            reciter_name = selected_reciter_data["name"]
                            surah_num = selected_reciter_data["surah_num"]
                            audio_url = selected_reciter_data["url"]
                            
                            # For Ayatul Kursi, we need to add the special prefix
                            if is_ayatul_kursi:
                                reciter_with_prefix = f"AyatulKursi_{reciter_name}"
                                # Run download and play with Ayatul Kursi prefix
                                asyncio.run(self.handle_audio_playback(
                                    audio_url,
                                    surah_num,
                                    reciter_with_prefix
                                ))
                            else:
                                # Regular surah playback
                                asyncio.run(self.handle_audio_playback(
                                    audio_url,
                                    surah_num,
                                    reciter_name
                                ))
                                
                            # Update last_display after potential redraw in handle_audio_playback
                            last_display = self.get_audio_display(surah_info)


                        # --- Redraw if selection was cancelled/failed ---
                        elif original_display_needs_restore:
                            last_display = self._redraw_audio_ui(surah_info) or last_display


                    # Handle seek keys ([, ], j, k)
                    elif choice in ('[', ']', 'j', 'k'):
                        # (Seek logic remains the same as previous version)
                        seek_amount = 0
                        if choice == '[': seek_amount = -5
                        elif choice == ']': seek_amount = 5
                        elif choice == 'j': seek_amount = -30
                        elif choice == 'k': seek_amount = 30
                        if self.audio_manager.duration > 0:
                            self.audio_manager.seek(self.audio_manager.current_position + seek_amount)
                            last_display = self._redraw_audio_ui(surah_info) or last_display

                    # Handle play/pause/stop (p, s)
                    elif choice in ['p', 's']:
                        self.handle_audio_choice(choice, surah_info)
                        last_display = self.get_audio_display(surah_info) # Update last display state


                # --- Normal Display Update (If no key pressed and not in reciter menu) ---
                elif not reciter_selection_active and self.audio_manager.is_playing:
                    try:
                        current_display = self.get_audio_display(surah_info)
                        if current_display != last_display:
                            last_display = self._redraw_audio_ui(surah_info) or last_display
                    except Exception: pass # Ignore minor update errors silently

                # --- Check if audio finished ---
                # (Check remains the same)
                if not reciter_selection_active and \
                (not self.audio_manager.is_playing and self.audio_manager.current_audio and
                self.audio_manager.duration > 0 and
                self.audio_manager.current_position >= self.audio_manager.duration - 0.1):
                    current_state_str_check = self.get_audio_display(surah_info)
                    if last_display != current_state_str_check:
                        last_display = self._redraw_audio_ui(surah_info) or last_display

                # Main loop delay
                time.sleep(0.05)

        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nAudio controls interrupted.")
        except Exception as e_loop:
            print(f"\n{Fore.RED}Error in audio control loop: {e_loop}{Style.RESET_ALL}")
        finally:
            # --- ALWAYS Restore *Original* Terminal Settings (Unix) ---
            # The _restore_terminal_settings helper handles the check for _original_termios_settings
            _restore_terminal_settings()

            # --- Stop Audio ---
            print(Fore.YELLOW + "\nExiting audio player.")
            self.audio_manager.stop_audio(reset_state=True)
            
            # If we are in a regular Surah view (not Ayatul Kursi), explicitly clear the flag
            if surah_info.surah_name != "Ayatul Kursi":
                self.audio_manager.last_was_ayatul_kursi = False
                
            time.sleep(0.5)



    def get_audio_display(self, surah_info: SurahInfo) -> str:
        """Get current audio display string with controls (Defensive Version)."""
        # --- Try to import and get references ---
        _Style, _Fore, _RESET = None, None, ""
        try:
            # Import locally within the function call
            from colorama import Fore as ColoramaFore, Style as ColoramaStyle
            _Fore = ColoramaFore
            _Style = ColoramaStyle
            _RESET = _Style.RESET_ALL
        except (ImportError, NameError):
            # Fallback if colorama itself is missing or failed basic import
            # --- CORRECTED BLOCK ---
            class DummyColor:
                # Define __getattr__ with proper indentation
                def __getattr__(self, name):
                    return "" # Return empty string for any attribute
            # --- END CORRECTED BLOCK ---
            _Fore = _Style = DummyColor() # Assign instance of the dummy class
            _RESET = ""
            # print("DEBUG: Failed to import colorama in get_audio_display") # Optional Debug

        # --- Helper function to safely get attributes ---
        def safe_style(attr_name, fallback=""):
            if not _Style: return fallback
            try: return getattr(_Style, attr_name, fallback)
            except Exception: return fallback

        def safe_fore(attr_name, fallback=""):
            if not _Fore: return fallback
            try: return getattr(_Fore, attr_name, fallback)
            except Exception: return fallback

        # --- Use safe accessors ---
        _Style_BRIGHT = safe_style("BRIGHT")
        _Fore_RED = safe_fore("RED")
        _Fore_CYAN = safe_fore("CYAN")
        _Fore_GREEN = safe_fore("GREEN")
        _Fore_YELLOW = safe_fore("YELLOW")
        _Fore_WHITE = safe_fore("WHITE")
        _Fore_MAGENTA = safe_fore("MAGENTA")
        _Fore_BLUE = safe_fore("BLUE")
        # --- Try DIM again, safely ---
        _Style_DIM = safe_style("DIM")

        output = []
        output.append(_Style_BRIGHT + _Fore_RED + "\nAudio Player - " +
                      _Fore_CYAN + f"{surah_info.surah_name}" + _RESET)

        # Determine state (same logic as before)
        state = "⏹ Stopped"
        state_color = _Fore_RED
        reciter_name = self.audio_manager.current_reciter or "None"
        is_luhaidan = reciter_name == "Muhammad Al Luhaidan"
        if self.audio_manager.is_playing: state, state_color = "▶ Playing", _Fore_GREEN
        elif self.audio_manager.current_audio:
            is_finished = (self.audio_manager.duration > 0 and
                           self.audio_manager.current_position >= self.audio_manager.duration - 0.1)
            if is_finished: state, state_color = "✅ Finished", _Fore_YELLOW
            else: state, state_color = "⏸ Paused", _Fore_YELLOW
        else: state, state_color, reciter_name = "ℹ Not Loaded", _Fore_YELLOW, "None"
        current_reciter_display = self.audio_manager.current_reciter or reciter_name

        output.append(f"\nState  : {state_color}{state}{_RESET}")
        output.append(f"Reciter: {_Fore_CYAN}{current_reciter_display}{_RESET}")
        
        # --- Loop status display ---
        loop_status = "Enabled" if self.audio_manager.loop_enabled else "Disabled"
        loop_color = _Fore_GREEN if self.audio_manager.loop_enabled else _Fore_RED
        output.append(f"Loop   : {loop_color}{loop_status}{_RESET}")
        
        # --- Timer status display ---
        timer_display = self.audio_manager.format_timer_display()
        timer_color = _Fore_GREEN if self.audio_manager.timer_enabled else _Fore_RED
        
        # Special case: if audio is stopped or finished and timer was previously enabled
        if state in ["⏹ Stopped", "✅ Finished"] and not self.audio_manager.timer_enabled:
            # Check if we should show the timer expired message
            if self.audio_manager.duration > 0 and not self.audio_manager.is_playing:
                timer_display = "Timer expired! Press 'p' to play again"
                timer_color = _Fore_YELLOW
                
        output.append(f"Timer  : {timer_color}{timer_display}{_RESET}")
        # --- End Timer status display ---
        
        # Progress Bar
        if self.audio_manager.duration > 0:
            output.append("\nProgress:")
            # Assume get_progress_bar is also defensive or works
            output.append(self.audio_manager.get_progress_bar())
        elif state not in ["ℹ Not Loaded"]:
             # Use safe DIM
            output.append("\nProgress: " + _Style_DIM + "N/A" + _RESET)

        # Hints
        if state == "ℹ Not Loaded": output.append(_Fore_YELLOW + "\nPress 'p' to download and play." + _RESET)
        if state == "✅ Finished": output.append(_Fore_YELLOW + "\nPress 's' to stop/reset or 'p' to replay." + _RESET)

        # Controls Menu
        box_width = 26
        separator = "─" * box_width
        output.append(_Fore_RED + "\n╭─ " + _Style_BRIGHT + _Fore_GREEN + "🎛️  Audio Controls" + _RESET)
        output.append(_Fore_RED + "│ • " + _Fore_CYAN + "p " + _Fore_WHITE + ": Play/Pause/Replay" + _RESET)
        output.append(_Fore_RED + "│ • " + _Fore_YELLOW + "s " + _Fore_WHITE + ": Stop & Reset" + _RESET)
        # --- ADD loop control ---
        output.append(_Fore_RED + "│ • " + _Fore_MAGENTA + "l " + _Fore_WHITE + ": Toggle Loop Mode" + _RESET)
        # --- ADD timer control ---
        output.append(_Fore_RED + "│ • " + _Fore_CYAN + "t " + _Fore_WHITE + ": Set Sleep Timer" + _RESET)
        # --- END ADD ---
        output.append(_Fore_RED + "│ • " + _Fore_RED + "r " + _Fore_WHITE + ": Change Reciter" + _RESET)
        output.append(_Fore_RED + "│ • " + _Fore_GREEN + "[ " + _Fore_WHITE + ": Seek Back 5s" + _RESET)
        output.append(_Fore_RED + "│ • " + _Fore_GREEN + "] " + _Fore_WHITE + ": Seek Forward 5s" + _RESET)
        output.append(_Fore_RED + "│ • " + _Fore_MAGENTA + "j " + _Fore_WHITE + ": Seek Back 30s" + _RESET)
        output.append(_Fore_RED + "│ • " + _Fore_MAGENTA + "k " + _Fore_WHITE + ": Seek Forward 30s" + _RESET)
        output.append(_Fore_RED + "│ • " + _Fore_BLUE + "q " + _Fore_WHITE + ": Quit Audio Player" + _RESET)
        output.append(_Fore_RED + "╰" + separator + _RESET)

        # Input Hint - Use safe DIM
        output.append("") # Add a blank line before hint
        if sys.platform == "win32":
            output.append(_Style_DIM + _Fore_WHITE + "Press key directly (no Enter needed)" + _RESET)
        else:
             # Check if tty setup likely succeeded (based on _original_termios_settings being stored)
             # If it failed, input might still require Enter.
             if _original_termios_settings is not None:
                 output.append(_Style_DIM + _Fore_WHITE + "Press key directly (no Enter needed)" + _RESET)
             else:
                 output.append(_Style_DIM + _Fore_WHITE + "Type command (p,s,r,q...) and press Enter" + _RESET) # Fallback hint

        output.append(_Fore_RED + "└──╼ " + _Fore_WHITE) # Keep prompt indicator

        return '\n'.join(output)

    def ask_yes_no(self, prompt: str) -> bool:
        while True:
            choice = input(Fore.BLUE + prompt + Fore.WHITE).strip().lower()
            if choice in ['y', 'yes']:
                return True
            if choice in ['n', 'no']:
                return False
            print(Fore.RED + "Invalid input. Please enter 'y' or 'n'.")







    def display_subtitle_menu(self, surah_info: SurahInfo):
        """Handles the subtitle creation process, saving to Documents,
        with a redesigned settings confirmation menu."""
        try:
            surah_number = surah_info.surah_number
            total_ayah = surah_info.total_verses
            start_ayah = None
            end_ayah = None

            # --- Ayah range input loop (remains the same) ---
            while True:
                try:
                    self.clear_terminal()
                    print(Fore.RED + "\n┌─" + Fore.GREEN + Style.BRIGHT + f" Subtitle Creation - Surah {surah_info.surah_name} (1-{total_ayah} Ayahs)")
                    print(Fore.RED + "├──╼ " + Fore.MAGENTA + "Start Ayah" + ":\n", end="")
                    start_ayah_str = input(Fore.RED + "│ ❯ " + Fore.WHITE)
                    print(Fore.RED + "├──╼ " + Fore.MAGENTA + "End Ayah" + ":\n", end="")
                    end_ayah_str = input(Fore.RED + "│ ❯ " + Fore.WHITE)
                    temp_start_ayah = int(start_ayah_str)
                    temp_end_ayah = int(end_ayah_str)
                    if 1 <= temp_start_ayah <= temp_end_ayah <= total_ayah:
                        start_ayah = temp_start_ayah
                        end_ayah = temp_end_ayah
                        break # Valid range entered
                    else:
                        print(Fore.RED + "└──╼ " + Style.BRIGHT + "Invalid ayah range. Please try again.")
                        time.sleep(1.5)
                except ValueError:
                    print(Fore.RED + "└──╼ " + Style.BRIGHT + "Invalid input. Please enter numbers.")
                    time.sleep(1.5)
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to main menu.")
                    return
            # --- End Ayah range input loop ---

            # --- Redesigned Settings Confirmation Loop ---
            while True:
                self.clear_terminal()
                box_width = 60
                separator = "─" * box_width

                # --- Consistent Header Format ---
                print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "🎬 Confirm Subtitle Content & Generate")
                print(Fore.RED + f"│ → {Fore.CYAN}Surah{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}{surah_info.surah_name} ({surah_info.surah_number})")
                print(Fore.RED + f"│ → {Fore.CYAN}Ayahs{Style.RESET_ALL} : {Style.NORMAL}{Fore.WHITE}{start_ayah}-{end_ayah}")
                print(Fore.RED + "├" + separator)

                # --- Display Current Subtitle Settings ---
                print(Fore.RED + f"│ {Style.BRIGHT}{Fore.GREEN}Current Content Configuration{Style.RESET_ALL}:")
                subtitle_config = self.preferences.get("subtitle_config", {})

                # Define content parts with labels
                content_parts_info = [
                    ("Arabic Ayah", True, Fore.GREEN), # Arabic is always included
                    ("Transliteration", subtitle_config.get("include_transliteration", False), Fore.CYAN),
                    ("Urdu Translation", subtitle_config.get("include_urdu", False), Fore.MAGENTA),
                    ("Turkish Translation", subtitle_config.get("include_turkish", False), Fore.BLUE),
                    ("English Translation", subtitle_config.get("include_english", False), Fore.YELLOW),
                ]

                for label, enabled, color in content_parts_info:
                    status = Fore.GREEN + "✓ Included" if enabled else Fore.RED + "✗ Excluded"
                    print(Fore.RED + f"│   → {color}{label.ljust(20)} {status}")

                print(Fore.RED + "├" + separator)

                # --- Redesigned Options with Consistent Format ---
                print(Fore.RED + f"│ {Style.BRIGHT}{Fore.GREEN}Choose an action{Style.RESET_ALL}:")

                # Define actions with consistent formatting
                actions = [
                    ("1", "Generate SRT with current settings"),
                    ("2", "Change Content Settings"),
                    ("3", "Cancel (Back to Main Menu)")
                ]

                # Calculate max length for proper alignment
                def strip_ansi(s):
                    import re
                    ansi_escape = re.compile(r'\x1B[\[][0-?]*[ -/]*[@-~]')
                    return ansi_escape.sub('', s)
                max_action_len = max(len(action[0]) for action in actions)

                for action_num, desc in actions:
                    pad = " " * (max_action_len - len(action_num))
                    print(Fore.RED + f"│ → {Fore.CYAN}{action_num}{pad}{Style.NORMAL} : {Fore.WHITE}{desc}{Style.RESET_ALL}")

                print(Fore.RED + "╰" + separator)

                try:
                    confirm_choice = input(Fore.RED + "  ❯ " + Fore.CYAN + "Enter choice (1-3): " + Fore.WHITE).strip()

                    if confirm_choice == '1': # Generate
                        # Proceed to generate using current subtitle_config
                        break # Exit settings confirmation loop
                    elif confirm_choice == '2': # Settings
                        # Open settings menu (assuming _display_subtitle_settings_menu is okay)
                        self._display_subtitle_settings_menu()
                        # Loop back to show this confirmation screen again
                        continue
                    elif confirm_choice == '3': # Cancel
                        print(Fore.YELLOW + "Subtitle generation cancelled.")
                        time.sleep(1)
                        return # Return directly to main app menu
                    else:
                        print(Fore.RED + "Invalid choice. Please enter 1, 2, or 3.")
                        time.sleep(1)

                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\nGeneration cancelled.")
                    return # Return to main app menu
                except Exception as e:
                    print(Fore.RED + f"Error in confirmation menu: {e}")
                    time.sleep(1)
            # --- End Redesigned Settings Confirmation Loop ---

            # --- Generate SRT content ---
            final_subtitle_config = self.preferences.get("subtitle_config", {})
            # Build a string representation for the final feedback message
            final_content_parts = ["Arabic"]
            if final_subtitle_config.get("include_transliteration"): final_content_parts.append("Translit")
            if final_subtitle_config.get("include_urdu"): final_content_parts.append("Urdu")
            if final_subtitle_config.get("include_turkish"): final_content_parts.append("Turkish")
            if final_subtitle_config.get("include_english"): final_content_parts.append("English")
            final_config_str = " + ".join(final_content_parts)

            print(f"\n{Fore.YELLOW}⏳ Generating SRT file ({final_config_str})...{Style.RESET_ALL}")
            ayah_duration = 5.0 # Default duration
            srt_content = self.generate_srt_content(
                surah_number, start_ayah, end_ayah, ayah_duration, final_subtitle_config
            )
            # --- End Generate ---

            if not srt_content:
                print(Fore.RED + "❌ Failed to generate SRT content. Returning.")
                time.sleep(2)
                return

            # --- File Saving Logic (remains the same) ---
            try:
                documents_dir = platformdirs.user_documents_dir()
                quran_dir = os.path.join(documents_dir, "QuranCLI Subtitles")
                surah_dir = os.path.join(quran_dir, surah_info.surah_name)
                os.makedirs(surah_dir, exist_ok=True)
            except Exception as e:
                print(Fore.RED + f"\n❌ Error accessing Documents directory: {e}")
                print(Fore.YELLOW + "Cannot save subtitle file.")
                time.sleep(2)
                return

            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            filename = f"Surah{surah_number:03d}_Ayah{start_ayah:03d}-{end_ayah:03d}_{date_str}.srt"
            filepath = os.path.join(surah_dir, filename)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                print(Fore.GREEN + f"\n✅ Subtitle file saved successfully!")
                print(Fore.CYAN + f"   Location: {filepath}")
                time.sleep(2) # Increased pause to see save location
            except Exception as e:
                print(Fore.RED + f"\n❌ Error saving subtitle file: {e}")
                time.sleep(2)
                return
            # --- End File Saving Logic ---


            # --- Web Server Setup (remains the same) ---
            web_assets_dir = None
            try:
                web_assets_dir = get_app_path('core/web')
                if not os.path.exists(os.path.join(web_assets_dir, 'index.html')):
                    print(Fore.RED + "\n❌ Web server assets (index.html) not found!")
                    web_assets_dir = None
            except Exception as e:
                print(Fore.RED + f"\n❌ Error finding web assets: {e}")
                web_assets_dir = None

            PORT = 8000
            ip_address = self.get_primary_ip_address()
            server_running = False
            if web_assets_dir and ip_address:
                self.start_server_thread(surah_dir, web_assets_dir, PORT, surah_info.surah_name)
                time.sleep(0.5)
                if self.httpd: server_running = True
                else: print(Fore.YELLOW + "Web server failed to start.")
            else: print(Fore.YELLOW + "\nWeb server cannot be started (missing assets or IP).")
            # --- End Web Server Setup ---


            # --- Management Console Loop (Show generated content info) ---
            while True:
                self.clear_terminal()
                box_width = 80
                separator = "─" * box_width

                # --- Consistent Header ---
                print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "🎬 Subtitle Management Console")
                print(Fore.RED + f"│ → {Fore.CYAN}Surah{Style.NORMAL} : {Style.NORMAL}{Fore.WHITE}{surah_info.surah_name} ({start_ayah}-{end_ayah})")

                # --- Display generated content format ---
                # Construct current_config_str from subtitle_config
                subtitle_config = self.preferences.get("subtitle_config", {})
                current_config_parts = ["Arabic"]
                if subtitle_config.get("include_transliteration"):
                    current_config_parts.append("Translit")
                if subtitle_config.get("include_urdu"):
                    current_config_parts.append("Urdu")
                if subtitle_config.get("include_turkish"):
                    current_config_parts.append("Turkish")
                if subtitle_config.get("include_english"):
                    current_config_parts.append("English")
                current_config_str = " + ".join(current_config_parts)

                print(Fore.RED + f"│ → {Fore.CYAN}Content{Style.NORMAL} : {Style.NORMAL}{Fore.WHITE}{current_config_str}")
                print(Fore.RED + f"│ → {Fore.CYAN}File Path{Style.NORMAL} : {Style.NORMAL}{Fore.WHITE}{filepath}")
                print(Fore.RED + "├" + separator)

                # Web server info with consistent formatting
                if server_running:
                    print(Fore.RED + f"│ {Style.BRIGHT}{Fore.GREEN}Network Sharing{Style.NORMAL}:")
                    print(Fore.RED + f"│ → {Fore.CYAN}Local URL{Style.NORMAL} : {Style.NORMAL}{Back.MAGENTA}{Fore.WHITE} 🚀✨ http://{ip_address}:{PORT} ✨🚀 {Style.NORMAL}")
                    print(Fore.RED + f"│ → {Fore.YELLOW}Note{Style.NORMAL} : {Style.NORMAL}{Fore.WHITE}Open link in browser/phone (same Wi-Fi)")
                    print(Fore.RED + f"│ → {Fore.CYAN}CapCut Tip{Style.NORMAL} : {Style.NORMAL}{Fore.WHITE}Download SRT → Captions → Import Captions")
                else:
                    print(Fore.RED + f"│ {Style.BRIGHT}{Fore.YELLOW}Network Sharing{Style.NORMAL}: {Style.NORMAL}{Fore.WHITE}Disabled/Failed")

                print(Fore.RED + "├" + separator)

                # --- Redesigned Commands ---
                print(Fore.RED + f"│ {Style.BRIGHT}{Fore.GREEN}Available Commands{Style.NORMAL}:")

                commands = [
                    ("open", "Open folder containing subtitle"),
                    ("back", "Return to Main Menu")
                ]

                # Calculate max length for proper alignment
                def strip_ansi(s):
                    import re
                    ansi_escape = re.compile(r'\x1B[\[][0-?]*[ -/]*[@-~]')
                    return ansi_escape.sub('', s)
                max_cmd_len = max(len(cmd) for cmd, _ in commands)

                for cmd, desc in commands:
                    pad = " " * (max_cmd_len - len(cmd))
                    print(Fore.RED + f"│ → {Fore.CYAN}{cmd}{pad}{Style.NORMAL} : {Style.NORMAL}{Fore.WHITE}{desc}{Style.NORMAL}")

                print(Fore.RED + "╰" + separator)

                try:
                    user_input = input(Fore.RED + "  ❯ " + Fore.CYAN + "Enter command: " + Fore.WHITE).strip().lower()
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠️ Please type 'back' and press Enter to return safely.")
                    continue

                if user_input == 'open':
                    # Folder opening logic (remains same)
                    try:
                        folder_to_open = os.path.normpath(surah_dir)
                        print(f"\nAttempting to open folder: {folder_to_open}")
                        if sys.platform == "win32": os.startfile(folder_to_open)
                        elif sys.platform == "darwin": subprocess.run(['open', folder_to_open], check=True)
                        else: subprocess.run(['xdg-open', folder_to_open], check=True)
                    except FileNotFoundError: print(Fore.RED + f"❌ Error: Could not find command to open folder.")
                    except Exception as e: print(Fore.RED + f"❌ Error opening folder: {e}")
                    input(Fore.YELLOW + "\nPress Enter to continue...") # Pause

                elif user_input == 'back':
                    if server_running: self.stop_server()
                    break # Exit management loop
                else:
                    print(Fore.RED + "❌ Invalid Command.")
                    time.sleep(1)
            # --- End Management Console Loop ---

        except Exception as e:
            print(Fore.RED + f"\n❌ An unexpected error occurred in subtitle menu: {e}")
            # Optional: Add traceback for debugging
            # import traceback
            # traceback.print_exc()
            self.stop_server() # Attempt cleanup
            input(Fore.YELLOW + "\nPress Enter to return to main menu...")



    def start_server_thread(self, subtitle_dir: str, web_assets_dir: str, port: int, surah_name: str):
        """Starts the HTTP server in a separate thread."""
        self.stop_server() # Ensure any previous server is stopped

        try:
            def start_server(sub_dir, assets_dir, port_inner, name_inner):
                # Define Handler inside the thread function to access correct paths
                class CustomHandler(http.server.SimpleHTTPRequestHandler):
                    static_web_dir = assets_dir
                    dynamic_subtitle_dir = sub_dir

                    def do_GET(self):
                        try:
                            requested_path = self.path.lstrip('/')
                            # Prevent directory traversal
                            if ".." in requested_path:
                                self.send_error(403, "Forbidden")
                                return

                            # 1. Serve SRT file from dynamic subtitle directory
                            srt_filepath = os.path.join(self.dynamic_subtitle_dir, requested_path)
                            # Check it's within the intended dir and ends with .srt
                            if (os.path.abspath(srt_filepath).startswith(os.path.abspath(self.dynamic_subtitle_dir)) and
                                os.path.isfile(srt_filepath) and requested_path.endswith(".srt")):
                                self.send_response(200)
                                self.send_header('Content-Type', 'application/octet-stream')
                                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(srt_filepath)}"')
                                self.end_headers()
                                with open(srt_filepath, 'rb') as f:
                                    self.wfile.write(f.read())
                                return

                            # 2. Serve index.html from static web assets directory
                            elif self.path == "/":
                                index_path = os.path.join(self.static_web_dir, "index.html")
                                if not os.path.isfile(index_path):
                                    self.send_error(404, "index.html not found")
                                    return
                                with open(index_path, 'rb') as f:
                                    content = f.read()
                                    # Inject dynamic file list and surah name
                                    try:
                                        files = [f for f in os.listdir(self.dynamic_subtitle_dir) if os.path.isfile(os.path.join(self.dynamic_subtitle_dir, f)) and f.endswith('.srt')]
                                    except FileNotFoundError:
                                         files = [] # Handle case where dir might vanish
                                    files_str = json.dumps(files)
                                    content = content.replace(b'/*FILE_LIST*/', f'const files = {files_str}; addFileLinks(files);'.encode('utf-8'))
                                    content = content.replace(b'<!--SURAH_NAME-->', name_inner.encode('utf-8'))
                                self.send_response(200)
                                self.send_header('Content-type', 'text/html; charset=utf-8')
                                self.end_headers()
                                self.wfile.write(content)
                                return

                            # 3. Serve style.css from static web assets directory
                            elif requested_path == "style.css":
                                asset_path = os.path.join(self.static_web_dir, requested_path)
                                if not os.path.isfile(asset_path):
                                     self.send_error(404, "style.css not found")
                                     return
                                self.send_response(200)
                                self.send_header('Content-type', 'text/css; charset=utf-8')
                                # Add caching headers? Optional.
                                self.end_headers()
                                with open(asset_path, 'rb') as f:
                                    self.wfile.write(f.read())
                                return

                            # 4. Anything else is 404
                            else:
                                self.send_error(404, "File Not Found")

                        except Exception as handler_e:
                             print(Fore.RED + f"❌ HTTP Handler Error: {handler_e}")
                             # Try to send 500 if possible
                             try:
                                 if not self.headers_sent: self.send_error(500, "Internal Server Error")
                             except: pass

                    # Suppress standard request logging
                    def log_message(self, format, *args):
                        pass
                # --- End Custom Handler ---

                httpd_server = None
                try:
                    socketserver.TCPServer.allow_reuse_address = True
                    httpd_server = socketserver.TCPServer(("", port_inner), CustomHandler)
                    # Store reference ONLY if server starts successfully
                    outer_instance = self # Capture 'self' from outer scope
                    outer_instance.httpd = httpd_server
                    # print(Fore.GREEN + f"🌐 Server thread started, serving on port {port_inner}")
                    httpd_server.serve_forever() # Blocking call
                except OSError as os_e:
                    if "address already in use" in str(os_e).lower():
                         print(Fore.RED + f"❌ Error: Port {port_inner} is already in use.")
                    else:
                         print(Fore.RED + f"❌ OS Error starting server: {os_e}")
                    # Ensure httpd reference is cleared if server failed to start
                    if 'outer_instance' in locals(): outer_instance.httpd = None
                except Exception as e:
                    print(Fore.RED + f"❌ Unexpected error in server thread: {e}")
                    if 'outer_instance' in locals(): outer_instance.httpd = None
                finally:
                    # This block runs when serve_forever stops (due to shutdown) or an error occurs
                    if httpd_server:
                         httpd_server.server_close() # Ensure socket is closed
                    # Clear reference on the main UI instance when thread exits
                    if 'outer_instance' in locals(): outer_instance.httpd = None
                    print(Fore.YELLOW + "Server thread finished.")

            # --- End Inner Function ---

            # Create and start the thread
            self.server_thread = threading.Thread(
                target=start_server,
                args=(subtitle_dir, web_assets_dir, port, surah_name),
                daemon=True
            )
            self.server_thread.start()

        except Exception as e:
            print(Fore.RED + f"Error preparing server thread: {e}")
            self.httpd = None
            self.server_thread = None

    def get_primary_ip_address(self):
        """Get a single IP Address"""
        ip_address = ""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))  # Google's public DNS server
            ip_address = sock.getsockname()[0]
            sock.close()
        except Exception as e:
            print(Fore.RED + f"❌ Could not get local IP address: {e}")
        return ip_address



    def stop_server(self):
        """Stop the running HTTP server thread safely."""
        httpd_ref = self.httpd # Get current reference
        server_thread_ref = self.server_thread

        if httpd_ref:
            print(Fore.YELLOW + "\nStopping web server...")
            try:
                httpd_ref.shutdown() # Signal serve_forever to stop
            except Exception as e:
                print(Fore.RED + f"Error during server shutdown signal: {e}")
            # Don't call server_close here, let the thread do it in finally block
            self.httpd = None # Clear main reference immediately

        if server_thread_ref and server_thread_ref.is_alive():
            try:
                # Wait for the thread to exit gracefully
                server_thread_ref.join(timeout=2.0)
                if server_thread_ref.is_alive():
                     print(Fore.YELLOW + "Server thread did not stop within timeout.")
            except Exception as e:
                 print(Fore.RED + f"Error joining server thread: {e}")
            self.server_thread = None # Clear thread reference













    def generate_srt_content(self, surah_number: int, start_ayah: int, end_ayah: int, ayah_duration: float, config: dict) -> str:
        """Generates the SRT content based on the provided configuration,
        applying letter reshaping to Urdu and Turkish, ordering content as:
        Arabic -> Transliteration -> Urdu -> Turkish -> English."""
        try:
            ayahs = self.data_handler.get_ayahs_raw(surah_number, start_ayah, end_ayah)
            if not ayahs:
                print(Fore.RED + f"Error: No ayah data found for SRT generation {surah_number}:{start_ayah}-{end_ayah}.")
                return ""

            srt_content = ""
            start_time = 0.0

            include_urdu = config.get("include_urdu", False)
            include_turkish = config.get("include_turkish", False)
            include_english = config.get("include_english", False)
            include_translit = config.get("include_transliteration", False)

            for i, ayah in enumerate(ayahs):
                end_time = start_time + ayah_duration
                srt_content += f"{i+1}\n"
                srt_content += f"{self.format_time_srt(start_time)} --> {self.format_time_srt(end_time)}\n"

                # 1. Always include Arabic (Ayah)
                srt_content += f"{ayah.content}\n"

                # --- REORDERED: 2. Conditionally include Transliteration ---
                if include_translit and ayah.transliteration:
                    srt_content += f"{ayah.transliteration}\n"

                # --- REORDERED: 3. Conditionally include Urdu (Translation) ---
                if include_urdu and ayah.translation_ur:
                    try:
                        reshaped_urdu_srt = arabic_reshaper.reshape(ayah.translation_ur)
                        srt_content += f"{reshaped_urdu_srt}\n"
                    except Exception as reshape_err:
                        print(Fore.YELLOW + f"Warning: Could not reshape Urdu text for ayah {ayah.number}: {reshape_err}")
                        srt_content += f"{ayah.translation_ur}\n" # Fallback

                # --- 4. Conditionally include Turkish (Translation) ---
                if include_turkish and ayah.translation_tr:
                    # Turkish is in Latin script, no need for Arabic reshaping
                    srt_content += f"{ayah.translation_tr}\n"

                # --- REORDERED: 5. Conditionally include English (Translation) ---
                if include_english and ayah.text:
                    srt_content += f"{ayah.text}\n"

                # Add final newline for separation
                srt_content = srt_content.rstrip('\n') + "\n\n"
                start_time = end_time

            return srt_content.strip()

        except Exception as e:
            print(Fore.RED + f"\nError generating SRT content: {e}")
            return ""

    def format_time_srt(self, seconds: float) -> str:
        """Formats seconds to SRT timestamp format (HH:MM:SS,MS)."""
        milliseconds = int(seconds * 1000)
        hours = milliseconds // (3600 * 1000)
        milliseconds %= (3600 * 1000)
        minutes = milliseconds // (60 * 1000)
        milliseconds %= (60 * 1000)
        seconds = milliseconds // 1000
        milliseconds %= 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def display_ayatul_kursi_audio_controls(self):
        """
        Display audio control options specifically for Ayatul Kursi (Verse 255 of Surah 2).
        Presents a list of reciters with dedicated Ayatul Kursi audio files and then uses the main audio player.
        """
        # Ayatul Kursi audio URLs from github.com/fadsec-lab/quran-audios
        ayatul_kursi_reciters = [
            {
                "name": "Abu Bakr Al-Shatri",
                "url": "https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/abu-bakr-al-shatri/abu-bakr-al-shatri-ayatul-kursi.mp3"
            },
            {
                "name": "Mishary Rashid Alafasy",
                "url": "https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/al-afasy/al-afasy-ayatul-kursi.mp3"
            },
            {
                "name": "Muhammad Al Luhaidan",
                "url": "https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/muhammad_al_luhaidan/muhammad-al-luhaidan-ayatul-kursi.MP3"
            },
            {
                "name": "Nasser Al-Qatami",
                "url": "https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/nasser-al-qatami/nasser-al-qatami-ayatul-kursi.mp3"
            },
            {
                "name": "Yasser Al-Dossari",
                "url": "https://raw.githubusercontent.com/fadsec-lab/quran-audios/main/yasser-al-dossari/yasser-al-dossari-ayatul-kursi.mp3"
            }
        ]
        
        self.clear_terminal()
        print(Style.BRIGHT + Fore.GREEN + "🎧 Ayatul Kursi Audio Player" + Style.RESET_ALL)
        print(Fore.YELLOW + "\nAyatul Kursi - \"The Throne Verse\" - Surah Al-Baqarah (2:255)" + Style.RESET_ALL)
        print(Fore.CYAN + "\nSelect a reciter:" + Style.RESET_ALL)
        
        # Display reciter options
        for i, reciter in enumerate(ayatul_kursi_reciters, 1):
            print(f"{Fore.GREEN}{i}.{Fore.WHITE} {reciter['name']}")
        
        print(f"\n{Fore.RED}q.{Fore.WHITE} Return to Surah view")
        
        # Get user choice
        try:
            choice = input(Fore.RED + "\n  ❯ " + Fore.WHITE).strip().lower()
            
            if choice == 'q':
                return
                
            if choice.isdigit() and 1 <= int(choice) <= len(ayatul_kursi_reciters):
                selected_idx = int(choice) - 1
                selected_reciter = ayatul_kursi_reciters[selected_idx]
                
                print(f"\n{Fore.CYAN}Selected: {selected_reciter['name']}")
                
                # Create a temporary SurahInfo object to pass to display_audio_controls
                # This allows us to reuse the full audio player interface
                from core.models import SurahInfo
                
                # Build audio dictionary with all available reciters, not just the selected one
                audio_dict = {}
                for i, reciter_data in enumerate(ayatul_kursi_reciters):
                    reciter_id = f"ayatul_kursi_{i+1}"
                    audio_dict[reciter_id] = {
                        "reciter": reciter_data["name"],
                        "url": reciter_data["url"]
                    }
                
                ayatul_kursi_info = SurahInfo(
                    surah_number=2,  # Surah Al-Baqarah
                    surah_name="Ayatul Kursi",
                    surah_name_ar="آية الكرسي",
                    total_verses=1,  # Just one verse (Ayatul Kursi)
                    description="The Throne Verse (2:255)",
                    translation="The Throne Verse",  # Add required translation field
                    type="medinan",  # Add required type field - Al-Baqarah is Medinan
                    audio=audio_dict  # Include all reciters
                )
                
                # Stop any current audio
                self.audio_manager.stop_audio(reset_state=True)
                
                # Download and play Ayatul Kursi audio using the existing infrastructure
                # We'll directly start the download and playback to avoid showing reciter selection again
                audio_url = selected_reciter["url"]
                reciter_name = selected_reciter["name"]
                
                print(Fore.YELLOW + "\n⏳ Downloading Ayatul Kursi audio, please wait...")
                print(Fore.CYAN + "This may take a moment depending on your internet speed.")
                
                try:
                    # Use existing download/playback infrastructure with special Ayatul Kursi prefix
                    reciter_prefix = f"AyatulKursi_{reciter_name}"
                    file_path = asyncio.run(self.audio_manager.download_audio(
                        url=audio_url, 
                        surah_num=2,  # Al-Baqarah
                        reciter=reciter_prefix  # Special prefix
                    ))
                    
                    # Also save the preference
                    pref_key = "ayatul_kursi"
                    self.preferences[pref_key] = {"reciter_name": reciter_name, "reciter_url": audio_url}
                    self.save_preferences()
                    
                    if file_path and os.path.exists(file_path):
                        print(Fore.GREEN + "\n✓ Starting playback...")
                        # Play the audio and mark as Ayatul Kursi
                        self.audio_manager.play_audio(file_path, reciter_name, is_ayatul_kursi=True)
                        # Now show the full audio player interface
                        self.display_audio_controls(ayatul_kursi_info)
                    else:
                        print(Fore.RED + "\nFailed to download Ayatul Kursi audio.")
                        input(Fore.YELLOW + "\nPress Enter to return to Surah view...")
                except Exception as e:
                    print(Fore.RED + f"\nError: {e}")
                    input(Fore.YELLOW + "\nPress Enter to return to Surah view...")
            else:
                print(Fore.RED + "\nInvalid choice.")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nReturning to Surah view...")
        except Exception as e:
            print(Fore.RED + f"\nError: {e}")
            time.sleep(1)