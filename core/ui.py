# core/ui.py
import sys
import math
import time
import asyncio
import keyboard
import json
import os
import datetime

if sys.platform == "win32":
    import msvcrt
    
from typing import List, Optional
from colorama import Fore, Style
from core.models import Ayah, SurahInfo
from core.audio_manager import AudioManager
import requests # Add Requests
from core.github_updater import GithubUpdater  # Import GithubUpdater
from core.version import VERSION  # Import VERSION

import socket #For Ip Adresses
import threading #Add threading for server
import http.server
import socketserver
import urllib.parse #for URL Encoding.

class UI:
    def __init__(self, audio_manager: AudioManager, term_size, data_handler, github_updater: Optional[GithubUpdater] = None, preferences: dict = None):
        self.audio_manager = audio_manager
        self.term_size = term_size
        self.data_handler = data_handler  # Store data_handler
        self.github_updater = github_updater  # Store GithubUpdater
        self.update_message = self._get_update_message() # Get the update message during initialization
        self.preferences = preferences or {} # Load preferences
        self.preferences_file = os.path.join(os.path.dirname(__file__), 'preferences.json') # Preferences file location
        self.httpd = None #Add HTTPServer
        
    def save_preferences(self):
        try:
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

    def display_header(self, QURAN_CLI_ASCII):
        """Display app header dynamically"""
        

        print(QURAN_CLI_ASCII)

        # Call _get_update_message() inside display_header to ensure latest updates
        update_message = self._get_update_message()

        if update_message:
            print(update_message)  # Print directly instead of wrapping

        print(Fore.RED + "╭──" + Style.BRIGHT + Fore.GREEN + "✨ As-salamu alaykum! " + Fore.RED + Style.NORMAL + "─" * 26 + "╮")
        print(Fore.RED + "│ " + Fore.LIGHTMAGENTA_EX + "QuranCLI - Your Digital Quran Companion".ljust(49) + Fore.RED + "│")
        print(Fore.RED + "├" + "─" * 50 + "┤")
        print(Fore.RED + "│ " + Style.BRIGHT + "Version: " + Style.NORMAL + f"v{VERSION}".ljust(40) + "│")
        print(Fore.RED + "│ " + Style.BRIGHT + "Author: " + Style.NORMAL + "https://github.com/anonfaded".ljust(41) + "│")
        print(Fore.RED + "├" + "─" * 50 + "┤")
        print(Fore.RED + "│ " + Style.BRIGHT + "Instructions:".ljust(49) + Style.NORMAL + "│")
        print(Fore.RED + "│ • " + Fore.WHITE + "Type 'quit' or 'exit' to close".ljust(47) + Fore.RED + "│")
        print(Fore.RED + "│ • " + Fore.WHITE + "Press Ctrl+C to cancel".ljust(47) + Fore.RED + "│")
        print(Fore.RED + "│ • " + Fore.WHITE + "Arabic text copies correctly".ljust(47) + Fore.RED + "│")
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
            print(Style.DIM + Fore.YELLOW + "Note: Arabic text may appear reversed but will be correct when copied\n")

            # Display ayahs for current page
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(ayahs))

            for ayah in ayahs[start_idx:end_idx]:
                self.display_single_ayah(ayah)

            # Navigation Menu
            box_width = 26  # Adjust width if needed
            separator = "─" * box_width

            print(Style.BRIGHT + Fore.RED + "\n╭─ " + Fore.WHITE + "🧭 Navigation")
            if total_pages > 1:
                print(Fore.RED + "│ → " + Fore.CYAN + "n " + Fore.WHITE + ": Next page")
                print(Fore.RED + "│ → " + Fore.CYAN + "p " + Fore.WHITE + ": Previous page")
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
            elif choice == 'q':
                return
            elif not choice:  # Enter was pressed
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



    def handle_audio_choice(self, choice: str, surah_info: SurahInfo):
        """Handle audio control input"""
        try:
            if choice == 'p':
                surah_num = surah_info.surah_number # Get surah number
                if not self.audio_manager.current_audio or self.audio_manager.current_surah != surah_num:
                    # Reset audio state for new surah
                    self.audio_manager.stop_audio(reset_state=True)
                    print(Fore.YELLOW + "\nℹ Loading default reciter...")

                    # Use saved reciter if available
                    if str(surah_num) in self.preferences:
                        reciter_data = self.preferences[str(surah_num)]
                        print(Fore.GREEN + f"\n✅ Using saved reciter for Surah {surah_num}: {reciter_data['reciter_name']}")
                        audio_url = reciter_data["reciter_url"]
                        reciter_name = reciter_data["reciter_name"]

                    else:
                        # Fallback to default reciter
                        reciter_id = next(iter(surah_info.audio))
                        audio_url = surah_info.audio[reciter_id]["url"]
                        reciter_name = surah_info.audio[reciter_id]["reciter"]

                    asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_name))
                elif self.audio_manager.is_playing:
                    self.audio_manager.pause_audio()
                else:
                    self.audio_manager.resume_audio()

            elif choice == 's':
                self.audio_manager.stop_audio(reset_state=True)

            elif choice == 'r':
                surah_num = surah_info.surah_number  # Get surah number
                if not surah_info.audio:
                    print(Fore.RED + "\nNo reciters available")
                    return

                while True:  # Add loop for reciter selection
                    self.clear_terminal()  # Clear before showing options
                    print(Style.BRIGHT + Fore.RED + "\nAudio Player - " +
                        Fore.WHITE + f"{surah_info.surah_name}")

                    print(Fore.CYAN + "\nAvailable Reciters:")
                    reciter_options = []
                    for rid, info in surah_info.audio.items():
                        print(f"{Fore.GREEN}{rid}{Fore.WHITE}: {info['reciter']}")
                        reciter_options.append((rid, info))

                    print(Fore.WHITE + "\nEnter reciter number" +
                        Fore.YELLOW + " (or 'q' to cancel)" +
                        Fore.WHITE + ": ", end="", flush=True)

                    try:
                        reciter_input = msvcrt.getch().decode()

                        if reciter_input.lower() == 'q':
                            # Clear and restore audio player display
                            self.clear_terminal()
                            print(self.get_audio_display(surah_info), end='', flush=True)
                            break

                        selected_reciter_info = surah_info.audio.get(reciter_input)

                        if selected_reciter_info:
                            audio_url = selected_reciter_info["url"]
                            reciter_name = selected_reciter_info["reciter"]
                            self.audio_manager.stop_audio()  # Stop current audio before changing
                            asyncio.run(self.handle_audio_playback(audio_url, surah_num, reciter_name))

                            # Save reciter preference
                            self.preferences[str(surah_num)] = {
                                "reciter_name": reciter_name,
                                "reciter_url": audio_url
                            }
                            self.save_preferences()
                            break
                        else:
                            print(Fore.RED + "\nInvalid selection. Please choose a valid reciter number.")
                            time.sleep(1.5)
                            continue

                    except (UnicodeDecodeError, AttributeError):
                        print(Fore.RED + "\nInvalid input. Please try again.")
                        time.sleep(1.5)
                        continue

        except Exception as e:
            print(Fore.RED + f"\nError handling audio command: {e}")
            time.sleep(1)

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
        """Display audio controls with real-time updates"""
        if not surah_info.audio:
            print(Fore.RED + "\n❌ Audio not available for this surah")
            return

        try:
            # Register safe keyboard shortcuts with error handling
            try:
                keyboard.unhook_all()  # Clean up any existing hooks
                keyboard.add_hotkey('left', lambda: self.audio_manager.seek(max(0, self.audio_manager.current_position - 5)))
                keyboard.add_hotkey('right', lambda: self.audio_manager.seek(min(self.audio_manager.duration, self.audio_manager.current_position + 5)))
                keyboard.add_hotkey('ctrl+left', lambda: self.audio_manager.seek(max(0, self.audio_manager.current_position - 30)))
                keyboard.add_hotkey('ctrl+right', lambda: self.audio_manager.seek(min(self.audio_manager.duration, self.audio_manager.current_position + 30)))
            except Exception as e:
                print(Fore.RED + f"\nWarning: Keyboard shortcuts not available: {e}")

            last_display = ""
            while True:
                try:
                    if msvcrt.kbhit():
                        try:
                            key_byte = msvcrt.getch()
                            # Handle arrow keys
                            if key_byte == b'\xe0':  # Special key prefix
                                arrow = msvcrt.getch()
                                if arrow == b'K':  # Left arrow
                                    self.audio_manager.seek(max(0, self.audio_manager.current_position - 5))
                                elif arrow == b'M':  # Right arrow
                                    self.audio_manager.seek(min(self.audio_manager.duration, self.audio_manager.current_position + 5))
                            else:
                                choice = key_byte.decode('ascii', errors='ignore').lower()
                                if choice == 'q':
                                    break
                                self.handle_audio_choice(choice, surah_info)
                        except UnicodeDecodeError:
                            continue  # Skip invalid characters

                    # Update display only if changed
                    current_display = self.get_audio_display(surah_info)
                    if current_display != last_display:
                        self.clear_terminal()
                        print(current_display, end='', flush=True)
                        last_display = current_display
                        sys.stdout.flush()  # Ensure cursor is at the correct position

                    time.sleep(0.1)  # Prevent high CPU usage

                except Exception as e:
                    print(Fore.RED + f"\nError in audio control loop: {e}")
                    time.sleep(1)
                    continue  # Continue instead of break to keep player running

        finally:
            try:
                keyboard.unhook_all()
                self.audio_manager.stop_audio()
            except Exception:
                pass

    def get_audio_display(self, surah_info: SurahInfo) -> str:
        """Get current audio display with input hints"""
        output = []
        output.append(Style.BRIGHT + Fore.RED + "\nAudio Player - " +
                    Fore.WHITE + f"{surah_info.surah_name}")

        # Check if audio file exists locally
        audio_file_exists = False
        if surah_info.audio:
            reciter_id = next(iter(surah_info.audio))  # Get first reciter
            audio_url = surah_info.audio[reciter_id]["url"]
            reciter_name = surah_info.audio[reciter_id]["reciter"]
            audio_file_path = self.audio_manager.get_audio_path(surah_info.surah_number, reciter_name)
            audio_file_exists = audio_file_path.exists()

        # Only show audio info if it matches current surah
        if (not self.audio_manager.current_audio or
            self.audio_manager.current_surah != surah_info.surah_number) and not audio_file_exists:
            output.append(Style.BRIGHT + Fore.YELLOW + "\n\nℹ Press 'p' to download and play audio")
        else:
            if self.audio_manager.is_playing and self.audio_manager.current_position < self.audio_manager.duration:
                state = "▶ Playing"
                state_color = Fore.GREEN
            elif self.audio_manager.current_audio and self.audio_manager.current_position >= self.audio_manager.duration: # check audip and position
                state = "Audio finished"
                state_color = Fore.YELLOW
            else:
                state = "⏸ Paused"
                state_color = Fore.YELLOW

            output.append(f"\nState: {state_color}{state}")
            output.append(f"Reciter: {Fore.CYAN}{self.audio_manager.current_reciter}")

            if self.audio_manager.duration:
                output.append("\nProgress:")
                output.append(self.audio_manager.get_progress_bar())

            if state == "Audio finished":#show only if that is the state
                output.append(Style.DIM + Fore.YELLOW + "\nPress 's' to stop and reset")

        output.append(Style.BRIGHT + Fore.RED + "\n\nControls:")
        output.append(Fore.GREEN + "p" + Fore.WHITE + ": Play/Pause")
        output.append(Fore.CYAN + "← / →" + Fore.WHITE + ": Seek 5s")
        output.append(Fore.CYAN + "Ctrl + ← / →" + Fore.WHITE + ": Seek 30s")
        output.append(Fore.RED + "s" + Fore.WHITE + ": Stop")
        output.append(Fore.YELLOW + "r" + Fore.WHITE + ": Change Reciter")
        output.append(Fore.MAGENTA + "q" + Fore.WHITE + ": Return")

        # Add dim input hint
        output.append(Style.DIM + Fore.WHITE + "\nPress any key to execute command (no Enter needed)")
        output.append(Fore.RED + "└──╼ " + Fore.WHITE)

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
        """Handles the subtitle creation process."""
        try:
            surah_number = surah_info.surah_number
            total_ayah = surah_info.total_ayah

            while True:
                try:
                    print(Fore.RED + "\n┌─" + Fore.RED + Style.BRIGHT + f" Subtitle Creation - Surah {surah_info.surah_name} (1-{total_ayah} Ayahs)")
                    print(Fore.RED + "├──╼ " + Fore.GREEN + "Start Ayah" + ":\n", end="")
                    start_ayah = int(input(Fore.RED + "│ ❯ " + Fore.WHITE))
                    print(Fore.RED + "├──╼ " + Fore.GREEN + "End Ayah" + ":\n", end="")
                    end_ayah = int(input(Fore.RED + "│ ❯ " + Fore.WHITE))
                    ayah_duration = 5.0

                    if 1 <= start_ayah <= end_ayah <= total_ayah:
                        break
                    else:
                        print(Fore.RED + "└──╼ " + "Invalid ayah range. Please try again.")
                except ValueError:
                    print(Fore.RED + "└──╼ " + "Invalid input. Please enter integers.")
                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n\n⚠ Interrupted! Returning to main menu.")
                    return #Return to main menu

            # Generate SRT content
            srt_content = self.generate_srt_content(surah_number, start_ayah, end_ayah, ayah_duration)

            # Save the SRT file
            documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
            quran_dir = os.path.join(documents_dir, "QuranCLI Subtitles")
            surah_dir = os.path.join(quran_dir, surah_info.surah_name)

            # Ensure the directories exist
            os.makedirs(surah_dir, exist_ok=True)

            # Create filename
            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            filename = f"Surah{surah_number:03d}_Ayah{start_ayah:03d}-Ayah{end_ayah:03d}_{date_str}.srt"
            filepath = os.path.join(surah_dir, filename)

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(srt_content)

                print(Fore.GREEN + f"\n✅ Subtitle file saved to: {Fore.RED}{filepath}") #Red color.

            except Exception as e:
                print(Fore.RED + f"\n❌ Error saving subtitle file: {e}")
                return  # Exit if file saving fails

            def start_server(directory, port, surah_name):
                """Starts an HTTP server serving a custom HTML page with file links."""
                try:
                    # Use the directory where the Surah's subtitles are saved.
                    web_dir = os.path.join(os.path.dirname(__file__), "web")  # Path to web directory

                    class CustomHandler(http.server.SimpleHTTPRequestHandler):
                        def do_GET(self):
                            # Force download for .srt files
                            filepath = os.path.join(directory, self.path[1:])  # Correctly construct file path
                            if os.path.isfile(filepath) and filepath.endswith(".srt"):
                                self.send_response(200)
                                self.send_header('Content-Type', 'application/octet-stream')  # Generic binary stream
                                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(filepath)}"')
                                self.end_headers()

                                try:
                                    with open(filepath, 'rb') as f:
                                        self.wfile.write(f.read())  # Write file content to response
                                    return
                                except Exception as e:
                                    print(Fore.RED + f"❌ Error reading file: {e}")
                                    self.send_error(500, "Error reading file")  # Internal Server Error
                                    return
                            elif self.path == "/":
                                # Serve the custom index.html
                                try:
                                    with open(os.path.join(web_dir, "index.html"), 'rb') as f:  # web_dir here
                                        content = f.read()
                                        files = [os.path.basename(f) for f in os.listdir(directory) if
                                                 os.path.isfile(os.path.join(directory, f))]  # directory here - getting filename only

                                        # Inject the file list and Surah name into the HTML
                                        files_str = str(files).replace("'", '"')  # Escape quotes for JavaScript
                                        content = content.replace(b'/*FILE_LIST*/',
                                                                f'const files = {files_str}; addFileLinks(files);'.encode())
                                        content = content.replace(b'<!--SURAH_NAME-->',
                                                                surah_name.encode())  # Surah Tag

                                        self.send_response(200)
                                        self.send_header('Content-type', 'text/html')
                                        self.end_headers()
                                        self.wfile.write(content)
                                        return
                                except FileNotFoundError:
                                    self.send_error(404, "index.html not found")
                                    return

                            elif self.path.startswith("/web/"):
                                try:
                                    filepath = os.path.join(web_dir, self.path[5:])
                                    with open(filepath, 'rb') as f:
                                        content = f.read()
                                        self.send_response(200)
                                        if self.path.endswith(".css"):
                                            self.send_header('Content-type', 'text/css')
                                        else:
                                            self.send_header('Content-type', 'text/html')  # Default
                                        self.end_headers()
                                        self.wfile.write(content)
                                        return
                                except FileNotFoundError:
                                    self.send_error(404, "File not found")
                                    return
                            self.send_error(404, "File not found")  # If reach here 404

                    

                    self.httpd = socketserver.TCPServer(("", port), CustomHandler)
                    print(Fore.GREEN + f"\n🌐 Serving custom webpage from: {Fore.CYAN}{directory} at port {port}. Press CTRL+C to stop." + Fore.WHITE)
                    self.httpd.serve_forever()

                except OSError as e:
                    print(Fore.RED + f"❌ Error starting server: {e}")

            def get_primary_ip_address():
                """Get a single IP Adress"""
                ip_address = ""
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.connect(("8.8.8.8", 80))  # Google's public DNS server
                    ip_address = sock.getsockname()[0]
                    sock.close()
                except Exception as e:
                    print(Fore.RED + f"❌ Could not get local IP address: {e}")
                return ip_address
            
            def stop_server():
                """Stop the thread."""
                if self.httpd:
                    print(Fore.YELLOW + "Stopping server..." + Fore.WHITE)
                    self.httpd.shutdown()
                    self.httpd.server_close()
                    self.httpd = None

            # start the server
            PORT = 8000 # Change port number to avoid conflict

            # construct the download url
            ip_address = get_primary_ip_address()
            print(Fore.GREEN + f"\nShare this link with other devices on the same network to browse and download subtitle files of {surah_info.surah_name}:" + Fore.WHITE)
            print(Fore.YELLOW + f"   http://{ip_address}:{PORT}"+ Fore.WHITE)
            #Directory to be accessed.
            server_thread = threading.Thread(target=start_server, args=(surah_dir, PORT, surah_info.surah_name), daemon=True)
            server_thread.start()

            while True:
                user_input = input(Fore.BLUE + "➡️  Type " + Fore.YELLOW + "'open'" + Fore.BLUE + " to open folder, or press " + Fore.CYAN + "Enter" + Fore.BLUE + " to return to menu: " + Fore.WHITE).strip().lower()
                if user_input == 'open':
                    try:
                        if os.name == 'nt':  # Windows
                            os.startfile(surah_dir)
                        elif os.name == 'posix':  # macOS and Linux
                            subprocess.run(['open', surah_dir])
                        else:
                            print(Fore.RED + "❌ Unsupported operating system for 'open' command.")
                    except Exception as e:
                        print(Fore.RED + f"❌ Error opening folder: {e}")
                    print(Fore.YELLOW + "Press Enter to continue..." + Fore.WHITE) # Clear indication of what to do.
                    input() #Just a clear input
                    break
                elif user_input == "": #Check if it is "" to proceed to the next selection
                     stop_server()# stop it
                     break
                else:
                    print(Fore.RED + "❌ Invalid Command. Press Enter or type 'open' and then press Enter")
                    continue
        except Exception as e:
            print(Fore.RED + f"\n❌ An error occurred in subtitle creation: {e}")


    def generate_srt_content(self, surah_number: int, start_ayah: int, end_ayah: int, ayah_duration: float) -> str:
        """Generates the SRT content."""
        try:
            ayahs = self.data_handler.get_ayahs(surah_number, start_ayah, end_ayah)
            srt_content = ""
            start_time = 0.0

            for i, ayah in enumerate(ayahs):
                end_time = start_time + ayah_duration
                srt_content += f"{i+1}\n"
                srt_content += f"{self.format_time_srt(start_time)} --> {self.format_time_srt(end_time)}\n"
                srt_content += f"{ayah.arabic_uthmani}\n"
                srt_content += f"{ayah.text}\n\n"  # English Translation.
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