# core/settings_manager.py
from colorama import Fore, Style

class SettingsManager:
    """Manages application settings and configuration"""

    def __init__(self, app):
        self.app = app
        self.term_size = app.term_size

    def show_settings_menu(self):
        """Display main settings menu"""
        while True:
            self.app._clear_terminal()
            self.app._display_header()

            # Calculate max command length for alignment
            commands = [
                (f"{Fore.CYAN}theme{Style.DIM}/th{Style.RESET_ALL}", "Change ASCII art color"),
                (f"{Fore.CYAN}backup{Style.DIM}/bk{Style.RESET_ALL}", "Backup/restore all app settings"),
                (f"{Fore.CYAN}translation{Style.DIM}/tr{Style.RESET_ALL}", "Translation display settings"),
                (f"{Fore.RED}back{Style.DIM}/b{Style.RESET_ALL}", "Return to main menu")
            ]

            def strip_ansi(s):
                import re
                ansi_escape = re.compile(r'\x1B[\[][0-?]*[ -/]*[@-~]')
                return ansi_escape.sub('', s)

            max_cmd_len = max(len(strip_ansi(cmd)) for cmd, _ in commands)

            print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "⚙️ Settings")
            for cmd, desc in commands:
                pad = " " * (max_cmd_len - len(strip_ansi(cmd)))
                print(Fore.RED + f"├─ {cmd}{pad} : {Style.NORMAL}{Fore.WHITE}{desc}{Style.RESET_ALL}")
            print(Fore.RED + "╰────────────────────────────────────────")

            print(Style.BRIGHT + Fore.GREEN + "\nEnter command:" + Style.DIM + Fore.WHITE)
            try:
                user_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
            except KeyboardInterrupt:
                return

            if user_input in ['back', 'b', 'q']:
                return
            elif user_input in ['theme', 'th']:
                self.app._handle_theme_selection()
            elif user_input in ['backup', 'bk']:
                self.app.backup_restore_menu()
            elif user_input in ['translation', 'tr']:
                self._show_translation_settings()
            else:
                print(f"{Fore.YELLOW}Invalid option. Please try again.{Style.RESET_ALL}")
                self.app._wait_for_key()

    def _show_translation_settings(self):
        """Show translation display settings - migrated from reading settings"""
        while True:
            self.app._clear_terminal()
            self.app._display_header()

            box_width = 55
            separator = "─" * box_width

            # Header with box design
            print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "🌐 Translation Settings")
            print(Fore.RED + f"│ {Fore.WHITE}Configure which translations appear in reading view")
            print(Fore.RED + f"│ {Fore.WHITE}Arabic text is always shown")
            print(Fore.RED + "├" + separator)

            config = self.app.preferences.get("reading_config", {})

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
                ("b", "Back to settings")
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
                    current_value = self.app.preferences["reading_config"].get(key_to_toggle, True)
                    self.app.preferences["reading_config"][key_to_toggle] = not current_value
                    self.app.ui.save_preferences()
                    print(f"{Fore.GREEN}✓ Transliteration setting updated.{Style.RESET_ALL}")
                    self.app._wait_for_key()
                elif choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(translation_options):
                        key_to_toggle = translation_options[index][0]
                        current_value = self.app.preferences["reading_config"].get(key_to_toggle, True if key in ["show_urdu", "show_english"] else False)
                        self.app.preferences["reading_config"][key_to_toggle] = not current_value
                        self.app.ui.save_preferences()
                        print(f"{Fore.GREEN}✓ Setting '{translation_options[index][1]}' updated.{Style.RESET_ALL}")
                        self.app._wait_for_key()
                    else:
                        print(Fore.RED + "❌ Invalid number. Please enter 1-3.")
                        self.app._wait_for_key()
                else:
                    print(Fore.YELLOW + "❌ Invalid option. Please try again.")
                    self.app._wait_for_key()
            except KeyboardInterrupt:
                break

    def _show_audio_settings(self):
        """Show audio management settings"""
        while True:
            self.app._clear_terminal()
            self.app._display_header()

            # Calculate max command length for alignment
            commands = [
                (f"{Fore.CYAN}download{Style.DIM}/dl{Style.NORMAL}{Style.RESET_ALL}", "Download audio files"),
                (f"{Fore.CYAN}clear{Style.DIM}/clr{Style.NORMAL}{Style.RESET_ALL}", "Clear audio cache"),
                (f"{Fore.CYAN}path{Style.DIM}/ap{Style.NORMAL}{Style.RESET_ALL}", "Show and open audio cache folder"),
                (f"{Fore.RED}back{Style.DIM}/b{Style.RESET_ALL}", "Return to settings")
            ]

            def strip_ansi(s):
                import re
                ansi_escape = re.compile(r'\x1B[\[][0-?]*[ -/]*[@-~]')
                return ansi_escape.sub('', s)

            max_cmd_len = max(len(strip_ansi(cmd)) for cmd, _ in commands)

            print(Fore.RED + "╭─ " + Style.BRIGHT + Fore.GREEN + "🎵 Audio Management")
            for cmd, desc in commands:
                pad = " " * (max_cmd_len - len(strip_ansi(cmd)))
                print(Fore.RED + f"├─ {cmd}{pad} : {Style.NORMAL}{Fore.WHITE}{desc}{Style.RESET_ALL}")
            print(Fore.RED + "╰────────────────────────────────────────")

            print(Style.BRIGHT + Fore.GREEN + "\nEnter command:" + Style.DIM + Fore.WHITE)
            try:
                user_input = input(Fore.RED + "  ❯ " + Fore.WHITE).strip().lower()
            except KeyboardInterrupt:
                return

            if user_input in ['back', 'b']:
                return
            elif user_input in ['download', 'dl']:
                self._start_audio_download()
            elif user_input in ['clear', 'clr']:
                self.app._clear_audio_cache()
            elif user_input in ['path', 'ap']:
                self.app._show_audio_cache_path()
            else:
                print(f"{Fore.YELLOW}Invalid option. Please try again.{Style.RESET_ALL}")
                self.app._wait_for_key()

    def _start_audio_download(self):
        """Start the audio download wizard"""
        try:
            from .audio_download_manager import AudioDownloadManager
        except ImportError:
            from audio_download_manager import AudioDownloadManager

        download_manager = AudioDownloadManager(self.app.audio_manager, self.app.data_handler, self.app)

        # Run the download wizard
        result = download_manager.run_download_wizard()
        # None => user backed out; True => success; False => failed/cancelled
        if result is True:
            print(f"{Fore.GREEN}Audio download completed!{Style.RESET_ALL}")
        elif result is False:
            print(f"{Fore.YELLOW}Audio download cancelled or failed.{Style.RESET_ALL}")

        self.app._wait_for_key()
