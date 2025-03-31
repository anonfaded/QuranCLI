# core/ui.py
import sys
import math
import time
import asyncio
# import keyboard
import json
import os
import datetime
import platformdirs

if sys.platform == "win32":
    import msvcrt
else:
    # Imports for Unix-like systems (Linux, macOS, Termux)
    import select
    import tty
    import termios
    # Keep track of original terminal settings
    _original_termios_settings = None
     
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


# --- Terminal Control for Unix-like systems ---
def _unix_getch_non_blocking():
    """Gets a single character from standard input on Unix without blocking.
       Returns None if no key is pressed. Needs terminal in cbreak mode."""
    # Check if stdin has data to read with a timeout of 0 (non-blocking)
    # Use select for portability (works on more Unix variants)
    rlist, _, _ = select.select([sys.stdin], [], [], 0)
    if rlist:
        # Data is available, read one character
        try:
            # Use os.read for lower-level reading after tty.setcbreak
            # Read up to 4 bytes to handle potential escape sequences
            char_bytes = os.read(sys.stdin.fileno(), 4)
            # Decode carefully
            try:
                return char_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # If decoding fails, might be a special key - return bytes?
                # Or return a placeholder/None? Let's return None for simplicity.
                return None
        except Exception:
             # Handle potential errors during read
             return None
    else:
        # No data available
        return None


def _restore_terminal_settings():
    """Restores terminal settings on Unix-like systems."""
    global _original_termios_settings
    if sys.platform != "win32" and _original_termios_settings is not None:
        try:
            # print("DEBUG: Attempting to restore terminal settings...") # Optional debug
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _original_termios_settings)
            # print("DEBUG: Restored terminal settings successfully.") # Optional debug
        except Exception as e:
            # Use stderr for errors potentially interfering with UI redraw
            print(f"\n{Fore.RED}Warning: Failed to restore terminal settings: {e}{Style.RESET_ALL}", file=sys.stderr)
        finally:
             # Always clear the stored settings after attempting restore
            _original_termios_settings = None

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
        self.httpd = None
        self.server_thread = None # Initialize server_thread attribute

    def _load_preferences(self) -> dict:
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




    def paginate_output(self, ayahs: List[Ayah], page_size: int = None, surah_info: SurahInfo = None):
        """Display ayahs with pagination"""
        if page_size is None:
            page_size = max(1, (self.term_size.lines - 10) // 6)

        total_pages = math.ceil(len(ayahs) / page_size)
        current_page = 1

        while True:
            self.clear_terminal()
            # Single consolidated header
            print(Style.BRIGHT + Fore.RED + "=" * self.term_size.columns)
            print(f"📖 {surah_info.surah_name} ({surah_info.surah_name_arabic}) • {surah_info.revelation_place} • {surah_info.total_ayah} Ayahs")
            print(f"Page {current_page}/{total_pages}")
            print(Style.BRIGHT + Fore.RED + "=" * self.term_size.columns)

            # Arabic display information - CONCISE NOTE
            print(Style.DIM + Fore.YELLOW + "⚠ Note: Arabic text is formatted for correct reading. If reversed or copying gives reversed output, use 'reverse' command, then 'q' and re-enter the input.")

            # Display ayahs for current page
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(ayahs))

            local_ayahs = ayahs[start_idx:end_idx]
            for ayah in local_ayahs:
                self.display_single_ayah(ayah)

            # Navigation Menu
            box_width = 26  # Adjust width if needed
            separator = "─" * box_width

            print(Fore.RED + "\n╭─ " + Style.BRIGHT + Fore.GREEN + "🧭 Navigation")
            if total_pages > 1:
                print(Fore.RED + "│ → " + Fore.CYAN + "n " + Fore.WHITE + ": Next page")
                print(Fore.RED + "│ → " + Fore.CYAN + "p " + Fore.WHITE + ": Previous page")
            print(Fore.RED + "│ → " + Fore.MAGENTA + "reverse " + Fore.WHITE + ": Toggle Arabic reversal")
            print(Fore.RED + "│ → " + Fore.YELLOW + "a " + Fore.WHITE + ": Play audio")
            print(Fore.RED + "│ → " + Fore.RED + "q " + Fore.WHITE + ": Return")
            print(Fore.RED + "╰" + separator)

            # User input prompt (aligned with box)
            choice = input(Fore.RED + "  ❯ " + Fore.WHITE).lower()

            if choice == 'n' and current_page < total_pages:
                current_page += 1
            elif choice == 'p' and current_page > 1:
                current_page -= 1
            elif choice == 'a':
                self.display_audio_controls(surah_info)
            elif choice == 'reverse':
                self.data_handler.toggle_arabic_reversal()
            elif choice == 'q':
                return
            elif not choice:
                if current_page < total_pages:
                    current_page += 1
                else:
                    return

    def display_single_ayah(self, ayah: Ayah):
        """Display a single ayah with proper formatting"""
        print(Style.BRIGHT + Fore.GREEN + f"\n[{ayah.number}]")
        wrapped_text = self.wrap_text(ayah.text, self.term_size.columns - 4)
        print(Style.NORMAL + Fore.WHITE + wrapped_text)

        # Arabic text with proper indentation and different title colors
        print(Style.BRIGHT + Fore.RED + "\nSimple Arabic:" + Style.BRIGHT + Fore.WHITE)
        print("    " + ayah.arabic_simple)

        print(Style.BRIGHT + Fore.RED + "\nUthmani Script:" + Style.BRIGHT + Fore.WHITE)
        print("    " + ayah.arabic_uthmani)

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
                load_new = (not self.audio_manager.current_audio or
                            self.audio_manager.current_surah != surah_num)

                if load_new:
                    self.audio_manager.stop_audio(reset_state=True)
                    print(Fore.YELLOW + "\nℹ Loading default reciter...") # Show status before potential long wait
                    reciter_pref = self.preferences.get(str(surah_num))
                    # ... (logic to determine audio_url and reciter_name - keep as before) ...
                    if reciter_pref and "reciter_url" in reciter_pref and "reciter_name" in reciter_pref:
                        audio_url, reciter_name = reciter_pref["reciter_url"], reciter_pref["reciter_name"]
                        print(Fore.GREEN + f" ✅ Using saved reciter: {reciter_name}")
                    elif surah_info.audio:
                        reciter_id = next(iter(surah_info.audio))
                        audio_url, reciter_name = surah_info.audio[reciter_id]["url"], surah_info.audio[reciter_id]["reciter"]
                        print(Fore.YELLOW + f" ⚠️ No preference saved, using default: {reciter_name}")
                    else:
                        print(Fore.RED + "\n❌ No audio data found."); return

                    # --- Run download and play ---
                    asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_name))
                    # --- Directly redraw after async call completes ---
                    self._redraw_audio_ui(surah_info) # Call the redraw helper
                    # --- End Direct Redraw ---

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

            elif choice == 'r': # Change Reciter
                surah_num = surah_info.surah_number
                if not surah_info.audio:
                    print(Fore.RED + "\n❌ No reciters available."); return

                original_display_needs_restore = True
                while True: # Reciter selection loop
                    self.clear_terminal()
                    print(Style.BRIGHT + Fore.RED + "\nAudio Player - Select Reciter" + Style.RESET_ALL)
                    # ... (display reciter options - keep as before) ...
                    reciter_options = list(surah_info.audio.items())
                    for i, (rid, info) in enumerate(reciter_options): print(f"{Fore.GREEN}{i+1}{Fore.WHITE}: {info['reciter']}")

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
                                 asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_name))
                                 # --- Directly redraw after async call ---
                                 self._redraw_audio_ui(surah_info)
                                 # --- End Direct Redraw ---

                                 # Save preference
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
            self.audio_manager.play_audio(file_path, reciter)
        except Exception as e:
            print(Fore.RED + f"\nError: {str(e)}")
            print(Fore.YELLOW + "Please try again or choose a different reciter.")
            time.sleep(2)

    def display_audio_controls(self, surah_info: SurahInfo):
        """Display audio controls with real-time updates (Cross-Platform Input)."""
        global _original_termios_settings # Access the global variable

        if not surah_info.audio:
            print(Fore.RED + "\n❌ Audio not available for this surah")
            time.sleep(1.5)
            return

        fd = None
        is_unix = sys.platform != "win32"

        # --- Setup Terminal for Non-Blocking Input (Unix) ---
        if is_unix:
            try:
                fd = sys.stdin.fileno()
                _original_termios_settings = termios.tcgetattr(fd)
                # --- Make a copy to modify ---
                new_settings = termios.tcgetattr(fd)
                # --- Explicitly set flags using setcbreak's logic source ---
                # Based on Python's tty.py source for setcbreak:
                # new_settings[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON) # iflags
                # new_settings[1] &= ~termios.OPOST # oflags
                new_settings[2] &= ~(termios.CSIZE | termios.PARENB) # cflags
                new_settings[2] |= termios.CS8
                new_settings[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN) # lflags
                new_settings[6][termios.VMIN] = 1 # Read 1 char at a time
                new_settings[6][termios.VTIME] = 0 # No timer, return immediately

                # --- Apply the modified settings ---
                termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)

                # --- DEBUG: Check flags AFTER setting ---
                # flags_after = termios.tcgetattr(fd)
                # print(f"DEBUG: lflags after set: {flags_after[3]:b}") # Print local flags in binary
                # print(f"DEBUG: ICANON set? {(flags_after[3] & termios.ICANON) == 0}") # Should be True (flag is OFF)
                # print(f"DEBUG: ECHO set? {(flags_after[3] & termios.ECHO) == 0}")    # Should be True (flag is OFF)
                # --- END DEBUG ---

                # --- Check if it actually worked (rudimentary check) ---
                if (termios.tcgetattr(fd)[3] & termios.ICANON) or \
                   (termios.tcgetattr(fd)[3] & termios.ECHO):
                    print(f"\n{Fore.YELLOW}Warning: Terminal did not fully enter cbreak mode (ICANON or ECHO still set).")
                    # Attempt to restore original settings if partial failure
                    _restore_terminal_settings() # Use helper
                    is_unix = False # Fallback to standard input
                    _original_termios_settings = None # Prevent further restore attempts
                    print(f"{Fore.YELLOW}Audio controls will require pressing Enter.{Style.RESET_ALL}")
                # else:
                    # print("DEBUG: Terminal successfully set to cbreak-like mode.") # Optional success debug

            except Exception as e:
                print(f"\n{Fore.YELLOW}Warning: Could not set terminal for instant key input: {e}")
                print(f"{Fore.YELLOW}Audio controls will require pressing Enter.{Style.RESET_ALL}")
                # Ensure restore isn't attempted if setup failed
                if _original_termios_settings:
                    try: termios.tcsetattr(fd, termios.TCSADRAIN, _original_termios_settings)
                    except: pass # Ignore errors during immediate restore on failure
                is_unix = False
                _original_termios_settings = None

        # --- Main Audio Control Loop ---
        last_display = ""
        running = True
        try:
            # Initial Draw
            last_display = self._redraw_audio_ui(surah_info) or ""

            while running:
                choice = None
                try:
                    # --- Platform-Specific Non-Blocking Input ---
                    if sys.platform == "win32":
                        if msvcrt.kbhit():
                            key_byte = msvcrt.getch()
                            # Handle potential special keys (like arrows) on Windows
                            if key_byte == b'\x00' or key_byte == b'\xe0':
                                msvcrt.getch() # Consume the second byte of special key
                                # Optionally map arrow keys here if desired, e.g., to seek
                                # key_code = msvcrt.getch()
                                # if key_code == b'K': choice = '[' # Left arrow example
                                # elif key_code == b'M': choice = ']' # Right arrow example
                                continue # Ignore other special keys for now
                            else:
                                try:
                                    choice = key_byte.decode('utf-8', errors='ignore').lower()
                                except UnicodeDecodeError:
                                    continue # Ignore undecodable bytes
                    elif is_unix: # Use the Unix non-blocking method if setup succeeded
                        # _unix_getch_non_blocking now returns the character or None
                        char_read = _unix_getch_non_blocking()
                        if char_read:
                            # Handle multi-byte sequences (like arrows) crudely for now
                            # A more robust solution uses libraries or more complex termios/escape code parsing
                            if len(char_read) > 1 and char_read.startswith('\x1b'): # Basic check for escape sequence
                                 # Could add mapping for arrow keys here, e.g., \x1b[D for left
                                 # if char_read == '\x1b[D': choice = '[' # Left arrow example
                                 # if char_read == '\x1b[C': choice = ']' # Right arrow example
                                 pass # Ignore other escape sequences for now
                            else:
                                 choice = char_read.lower() # Use the single character read
                    else:
                         # Fallback: Standard blocking input (requires Enter)
                         # This part shouldn't normally be reached if is_unix setup worked,
                         # but acts as a safeguard or if setup failed.
                         # We can't easily mix blocking/non-blocking, so we'll rely on the
                         # non-blocking methods above and the main loop sleep.
                         # If we *needed* blocking input here, we'd need to prompt.
                         pass # Do nothing here, let the loop continue

                except Exception as e_input:
                     print(f"\n{Fore.RED}Input Error: {e_input}{Style.RESET_ALL}")
                     time.sleep(1) # Prevent rapid error loops
                     continue # Skip processing this loop iteration


                # --- Process Input Choice (Largely Unchanged) ---
                if choice:
                    # print(f"DEBUG: Key pressed: {repr(choice)}") # Debug keys
                    if choice == 'q': running = False
                    # Handle seek keys
                    elif choice in ('[', ']', 'j', 'k'):
                        seek_amount = 0
                        if choice == '[': seek_amount = -5
                        elif choice == ']': seek_amount = 5
                        elif choice == 'j': seek_amount = -30
                        elif choice == 'k': seek_amount = 30

                        if self.audio_manager.duration > 0: # Only seek if audio is loaded
                             current_pos = self.audio_manager.current_position
                             target_pos = current_pos + seek_amount
                             # Clamp target position (handled better within seek now)
                             self.audio_manager.seek(target_pos)
                             # Redraw immediately after seek action
                             last_display = self._redraw_audio_ui(surah_info) or last_display
                        else:
                             # Optional: Notify user they can't seek yet
                             # print(Fore.YELLOW + "Load audio first ('p') to seek." + Style.RESET_ALL, end='\r')
                             pass

                    # Handle other commands (p, s, r)
                    elif choice in ['p', 's', 'r']:
                        # handle_audio_choice now handles redraw for these actions
                        self.handle_audio_choice(choice, surah_info)
                        # Update last_display after handle_audio_choice potentially redraws
                        current_state_str = self.get_audio_display(surah_info)
                        last_display = current_state_str

                    # Ignore unrecognized keys silently

                # --- Normal Display Update (Progress Bar) ---
                elif self.audio_manager.is_playing: # Update display only if playing and no key pressed
                     try:
                         current_display = self.get_audio_display(surah_info)
                         if current_display != last_display:
                             last_display = self._redraw_audio_ui(surah_info) or last_display
                     except Exception:
                         pass # Ignore minor update errors silently

                # --- Check if audio finished playing naturally ---
                if (not self.audio_manager.is_playing and self.audio_manager.current_audio and
                   self.audio_manager.duration > 0 and
                   self.audio_manager.current_position >= self.audio_manager.duration - 0.1):
                     current_state_str_check = self.get_audio_display(surah_info)
                     if last_display != current_state_str_check:
                         last_display = self._redraw_audio_ui(surah_info) or last_display

                # Main loop delay - crucial for non-blocking checks
                time.sleep(0.05) # Shorter sleep for more responsive input checks

        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nAudio controls interrupted.")
            # The finally block will handle cleanup
        except Exception as e_loop:
            print(f"\n{Fore.RED}Error in audio control loop: {e_loop}{Style.RESET_ALL}")
            # The finally block will handle cleanup
        finally:
            # --- ALWAYS Restore Terminal Settings (Unix) ---
            if is_unix and _original_termios_settings:
                _restore_terminal_settings() # Use the dedicated restore function

            # --- Stop Audio ---
            print(Fore.YELLOW + "\nExiting audio player.") # Moved here to appear after restore msg if any
            self.audio_manager.stop_audio(reset_state=True)
            # Optional short pause before returning to previous screen
            time.sleep(0.5)
        
# core/ui.py (inside class UI)

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
        # ... (rest of controls using safe variables) ...
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
        """Handles the subtitle creation process, saving to Documents."""
        try:
            surah_number = surah_info.surah_number
            total_ayah = surah_info.total_ayah

            # Ayah range input loop
            while True:
                try:
                    self.clear_terminal()
                    print(Fore.RED + "\n┌─" + Fore.GREEN + Style.BRIGHT + f" Subtitle Creation - Surah {surah_info.surah_name} (1-{total_ayah} Ayahs)")
                    print(Fore.RED + "├──╼ " + Fore.MAGENTA + "Start Ayah" + ":\n", end="")
                    start_ayah_str = input(Fore.RED + "│ ❯ " + Fore.WHITE)
                    print(Fore.RED + "├──╼ " + Fore.MAGENTA + "End Ayah" + ":\n", end="")
                    end_ayah_str = input(Fore.RED + "│ ❯ " + Fore.WHITE)
                    start_ayah = int(start_ayah_str)
                    end_ayah = int(end_ayah_str)
                    ayah_duration = 5.0 # Default duration
                    if 1 <= start_ayah <= end_ayah <= total_ayah:
                        break
                    else:
                        print(Fore.RED + "└──╼ " + Style.BRIGHT + "Invalid ayah range. Please try again.")
                        time.sleep(1.5)
                except ValueError:
                    print(Fore.RED + "└──╼ " + Style.BRIGHT + "Invalid input. Please enter numbers.")
                    time.sleep(1.5)
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to main menu.")
                    return

            # Generate SRT content
            srt_content = self.generate_srt_content(surah_number, start_ayah, end_ayah, ayah_duration)
            if not srt_content:
                print(Fore.RED + "❌ Failed to generate SRT content. Returning.")
                return

            # Determine Save Path using platformdirs
            try:
                documents_dir = platformdirs.user_documents_dir()
                quran_dir = os.path.join(documents_dir, "QuranCLI Subtitles")
                surah_dir = os.path.join(quran_dir, surah_info.surah_name)
                os.makedirs(surah_dir, exist_ok=True) # Ensure directories exist
            except Exception as e:
                print(Fore.RED + f"\n❌ Error accessing Documents directory: {e}")
                print(Fore.YELLOW + "Cannot save subtitle file.")
                return

            # Create Filename and Save
            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            filename = f"Surah{surah_number:03d}_Ayah{start_ayah:03d}-{end_ayah:03d}_{date_str}.srt"
            filepath = os.path.join(surah_dir, filename)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                print(Fore.GREEN + f"\n✅ Subtitle file saved to: {Fore.CYAN}{filepath}")
            except Exception as e:
                print(Fore.RED + f"\n❌ Error saving subtitle file: {e}")
                return

            # --- Get Bundled Web Assets Path using get_app_path ---
            web_assets_dir = None
            try:
                # Use writable=False (default) to get path relative to _MEIPASS/script root
                web_assets_dir = get_app_path('core/web')
                if not os.path.exists(os.path.join(web_assets_dir, 'index.html')):
                     print(Fore.RED + "\n❌ Web server assets (index.html) not found!")
                     web_assets_dir = None
            except Exception as e:
                 print(Fore.RED + f"\n❌ Error finding web assets: {e}")
                 web_assets_dir = None
            # --- End Get Bundled Web Assets Path ---

            # Start Server (if assets found)
            PORT = 8000
            ip_address = self.get_primary_ip_address()
            server_running = False
            if web_assets_dir and ip_address:
                print(Fore.GREEN + f"\nStarting web server to share subtitles...")
                self.start_server_thread(surah_dir, web_assets_dir, PORT, surah_info.surah_name)
                # Small delay to allow server thread to potentially print errors
                time.sleep(0.5)
                # Check if server actually started (httpd attribute would be set)
                if self.httpd:
                    server_running = True
                else:
                    print(Fore.YELLOW + "Web server failed to start (check console for errors).")

            else:
                 print(Fore.YELLOW + "\nWeb server cannot be started (Assets missing or IP not found).")


            # Management Console Loop
            while True:
                self.clear_terminal()
                print(Fore.RED + Style.BRIGHT + "Subtitle Management Console:")
                print(Fore.MAGENTA + f"      Subtitle generated for Surah {surah_info.surah_name}!")
                print(Fore.GREEN + f"\nFile saved in Documents folder:")
                print(Fore.CYAN + f"      {filepath}")

                if server_running:
                    print(Fore.GREEN + f"\nShare link on your network:")
                    print(f"      🚀✨ " + Back.MAGENTA + Fore.WHITE + f" http://{ip_address}:{PORT} " + Style.RESET_ALL + " ✨🚀      ")
                    print(Fore.WHITE + Style.DIM + "\n   Open this link in your browser to view and manage your subtitle files with a better UI.\n   You can also access it from your phone or any device connected to the same Wi-Fi network to download files easily.")
                    
                    print(Fore.CYAN + Style.BRIGHT + "\n📌 Next Steps: Adding Captions to your Video" + Fore.WHITE + Style.DIM + " (e.g., in CapCut) ")
                    print("    1️⃣  Download the .srt subtitle file on your phone.")
                    print("    2️⃣  Open CapCut and load your video.")
                    print("    3️⃣  Go to the 'Captions' section.")
                    print("    4️⃣  Click on 'Import Captions' and select the downloaded .srt file.")
                    print("    5️⃣  The captions will be auto-added! 🎉 You can now adjust and sync them manually.")
                else:
                    print(Fore.YELLOW + "\nWeb sharing disabled/failed.")

                box_width = 26
                separator = "─" * box_width
                print("\n" + Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "📜 Available Commands")
                print(Fore.RED + f"│ • {Fore.CYAN}open{Fore.WHITE}: Open folder containing subtitle")
                print(Fore.RED + f"│ • {Fore.CYAN}back{Fore.WHITE}: Return to Main Menu")
                print(Fore.RED + "╰" + separator)
                print(Style.DIM + Fore.WHITE + "\nType command and press Enter.")
                print(" ")

                try:
                    user_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠️ Please type 'back' and press Enter to return safely.")
                    continue

                if user_input == 'open':
                    try:
                        folder_to_open = os.path.normpath(surah_dir)
                        print(f"\nAttempting to open folder: {folder_to_open}")
                        if sys.platform == "win32": os.startfile(folder_to_open)
                        elif sys.platform == "darwin": subprocess.run(['open', folder_to_open], check=True)
                        else: subprocess.run(['xdg-open', folder_to_open], check=True)
                    except FileNotFoundError:
                         print(Fore.RED + f"❌ Error: Could not find command to open folder.")
                    except Exception as e:
                        print(Fore.RED + f"❌ Error opening folder: {e}")
                    input(Fore.YELLOW + "\nPress Enter to continue...") # Pause

                elif user_input == 'back':
                    if server_running: self.stop_server()
                    break # Exit management loop
                else:
                    print(Fore.RED + "❌ Invalid Command.")
                    time.sleep(1)

        except Exception as e:
            print(Fore.RED + f"\n❌ An unexpected error occurred in subtitle menu: {e}")
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













    def generate_srt_content(self, surah_number: int, start_ayah: int, end_ayah: int, ayah_duration: float) -> str:
        """Generates the SRT content with original Arabic text."""
        try:
            ayahs = self.data_handler.get_ayahs_raw(surah_number, start_ayah, end_ayah)  # Use raw ayahs
            srt_content = ""
            start_time = 0.0

            for i, ayah in enumerate(ayahs):
                end_time = start_time + ayah_duration
                srt_content += f"{i+1}\n"
                srt_content += f"{self.format_time_srt(start_time)} --> {self.format_time_srt(end_time)}\n"
                srt_content += f"{ayah.arabic_uthmani}\n"  # Use raw Arabic text
                srt_content += f"{ayah.text}\n\n"  # English Translation
                start_time = end_time

            return srt_content

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