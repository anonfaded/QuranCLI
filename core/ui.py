# core/ui.py
import sys
import math
import time
import asyncio
import keyboard
import msvcrt
from typing import List
from colorama import Fore, Style
from core.models import Ayah, SurahInfo
from core.audio_manager import AudioManager

class UI:
    def __init__(self, audio_manager: AudioManager, term_size):
        self.audio_manager = audio_manager
        self.term_size = term_size

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
        """Display app header"""
        print(QURAN_CLI_ASCII)
        print(Style.BRIGHT + Fore.RED + "=" * 70)
        print(Fore.WHITE + "📖 Welcome to " + Fore.RED + "QuranCLI" + Fore.WHITE + " - Your Digital Quran Companion")
        print(Style.BRIGHT + Fore.RED + "=" * 70 + "\n")

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
            
            # Navigation options
            print(Style.BRIGHT + Fore.RED + "\nNavigation:")
            if total_pages > 1:
                print(Fore.CYAN + "n" + Fore.WHITE + ": Next page")
                print(Fore.CYAN + "p" + Fore.WHITE + ": Previous page")
            print(Fore.YELLOW + "a" + Fore.WHITE + ": Play audio")
            print(Fore.RED + "q" + Fore.WHITE + ": Return")
            
            choice = input(Fore.RED + "\n└──╼ " + Fore.WHITE).lower()
            
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
        
        print(Style.BRIGHT + Fore.WHITE + "\n" + "-" * min(40, self.term_size.columns))

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
                if not self.audio_manager.current_audio or self.audio_manager.current_surah != surah_info.surah_number:
                    # Reset audio state for new surah
                    self.audio_manager.stop_audio(reset_state=True)
                    print(Fore.YELLOW + "\nℹ Loading default reciter...")
                    reciter_id = next(iter(surah_info.audio))
                    audio_url = surah_info.audio[reciter_id]["url"]
                    reciter_name = surah_info.audio[reciter_id]["reciter"]
                    asyncio.run(self.handle_audio_playback(audio_url, surah_info.surah_number, reciter_name))
                elif self.audio_manager.is_playing:
                    self.audio_manager.pause_audio()
                else:
                    self.audio_manager.resume_audio()
                    
            elif choice == 's':
                self.audio_manager.stop_audio()
                
            elif choice == 'r':
                if not surah_info.audio:
                    print(Fore.RED + "\nNo reciters available")
                    return

                while True:  # Add loop for reciter selection
                    self.clear_terminal()  # Clear before showing options
                    print(Style.BRIGHT + Fore.RED + "\nAudio Player - " + 
                        Fore.WHITE + f"{surah_info.surah_name}")
                        
                    print(Fore.CYAN + "\nAvailable Reciters:")
                    for rid, info in surah_info.audio.items():
                        print(f"{Fore.GREEN}{rid}{Fore.WHITE}: {info['reciter']}")
                    
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
                            
                        if reciter_input in surah_info.audio:
                            audio_url = surah_info.audio[reciter_input]["url"]
                            reciter_name = surah_info.audio[reciter_input]["reciter"]
                            self.audio_manager.stop_audio()  # Stop current audio before changing
                            asyncio.run(self.handle_audio_playback(audio_url, surah_info.surah_number, reciter_name))
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
        
        # Only show audio info if it matches current surah
        if (not self.audio_manager.current_audio or 
            self.audio_manager.current_surah != surah_info.surah_number):
            output.append(Style.BRIGHT + Fore.YELLOW + "\n\nℹ Press 'p' to download and play audio")
        else:
            state = "▶ Playing" if self.audio_manager.is_playing else "⏸ Paused"
            state_color = Fore.GREEN if self.audio_manager.is_playing else Fore.YELLOW
            output.append(f"\nState: {state_color}{state}")
            output.append(f"Reciter: {Fore.CYAN}{self.audio_manager.current_reciter}")
            
            if self.audio_manager.duration:
                output.append("\nProgress:")
                output.append(self.audio_manager.get_progress_bar())
                
                if not self.audio_manager.is_playing and self.audio_manager.current_position >= self.audio_manager.duration:
                    output.append(Style.DIM + Fore.YELLOW + "\nAudio finished - Press 'p' to replay")
        
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