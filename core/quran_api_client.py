# core/quran_api_client.py
import sys
import subprocess
import shutil
from typing import Dict, List, Tuple
import os
import sys # Make sure sys is imported
import requests
# --- Add this near the top imports ---
IS_FROZEN = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
# --- End Add ---

# ... (get_package_map function remains the same) ...

def check_dependencies():
    """
    Check and install required dependencies with improved output.
    Bypassed when frozen. Linux 'apt' logic is commented out for Windows focus.
    """
    # --- Bypass check for frozen applications ---
    if IS_FROZEN:
        # print("Dependency check bypassed (frozen app).") # Optional debug message
        return
    # --- End Bypass check ---

    # --- Comment out the Linux-only check for now ---
    # if os.name != 'posix':
    #     print("Dependency check skipped (not on Linux).") # Optional info
    #     return
    # --- End Comment out ---

    package_map = get_package_map()
    missing_packages: List[Tuple[str, bool]] = []
    failed_installs: List[str] = []

    print("\n" + "═" * 60)
    print("📦 Checking Dependencies...")
    print("═" * 60)

    # First pass: Check what's missing
    for pip_package in package_map.keys():
        try:
            # Use a simple replace for potential hyphens in package names for import
            import_name = pip_package.replace('-', '_')
            __import__(import_name)
            # print(f" Found: {pip_package}") # Optional debug
        except ImportError:
            # print(f" Missing: {pip_package}") # Optional debug
            # Check if apt is available (even on non-Linux, shutil.which works)
            apt_available = bool(shutil.which('apt'))
            missing_packages.append((pip_package, apt_available))

    if not missing_packages:
        print("\n" + "╭" + "─" * 58 + "╮")
        # Use standard print for colors if colorama isn't guaranteed yet
        print("│" + "\033[92m✓ All dependencies seem satisfied!\033[0m".center(76) + "│") # Manual color codes
        print("╰" + "─" * 58 + "╯\n")
        return

    # Second pass: Try to install missing packages
    for pip_package, apt_available in missing_packages:
        print(f"\n\033[91m❌ Missing package: \033[93m{pip_package}\033[0m") # Manual color codes
        installed = False

        # --- Comment out the 'apt' installation block ---
        """
        # Try apt first if available
        if apt_available:
            apt_package = package_map.get(pip_package) # Use .get for safety
            if apt_package:
                 print(f"\n\033[96m📦 Attempting to install via apt... (Requires sudo)\033[0m")
                 try:
                     # Use capture_output=True to suppress command output unless error
                     result = subprocess.run(['sudo', 'apt', 'install', '-y', apt_package],
                                             check=True, capture_output=True, text=True, timeout=60)
                     # Check stderr for common failure messages even if return code is 0
                     if "Unable to locate package" not in result.stderr and "Could not open lock file" not in result.stderr:
                         print(f"\033[92m   ✓ Successfully installed {apt_package} via apt.\033[0m")
                         installed = True
                         # Re-check import after install attempt (optional)
                         # try: __import__(pip_package.replace('-', '_')); installed = True except ImportError: pass
                     else:
                          print(f"\033[91m   ✗ apt command ran but failed to install {apt_package}.\033[0m")
                          if result.stderr: print(f"   apt stderr: {result.stderr.strip()}")

                 except FileNotFoundError:
                      print("\033[91m   ✗ 'sudo' command not found. Cannot use apt.\033[0m")
                 except subprocess.CalledProcessError as e:
                     print(f"\033[91m   ✗ apt install failed for {apt_package}. Error: {e}\033[0m")
                     if e.stderr: print(f"   apt stderr: {e.stderr.strip()}")
                 except subprocess.TimeoutExpired:
                      print(f"\033[91m   ✗ apt install timed out for {apt_package}.\033[0m")
                 except Exception as e_apt: # Catch other potential errors
                      print(f"\033[91m   ✗ Unexpected error during apt install: {e_apt}\033[0m")
            else:
                 print(f"\033[93m   ⓘ No apt mapping found for {pip_package}.\033[0m")
        """
        # --- End Comment out 'apt' block ---

        # If apt was skipped, not available, or failed, try pip installations
        if not installed:
            # Try pip install --user first
            print(f"\n\033[96m📦 Attempting to install via pip (user)...")
            try:
                # Use sys.executable to ensure using the correct pip
                result_user = subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', pip_package],
                                             check=True, capture_output=True, text=True, timeout=120)
                print(f"\033[92m   ✓ Successfully installed {pip_package} via pip (user).\033[0m")
                installed = True
            except subprocess.CalledProcessError as e_pip_user:
                print(f"\033[91m   ✗ pip install --user failed for {pip_package}.\033[0m")
                # Optionally print stderr for debugging:
                # if e_pip_user.stderr: print(f"     pip stderr: {e_pip_user.stderr.strip()}")
            except subprocess.TimeoutExpired:
                 print(f"\033[91m   ✗ pip install --user timed out for {pip_package}.\033[0m")
            except Exception as e_user:
                 print(f"\033[91m   ✗ Unexpected error during pip install --user: {e_user}\033[0m")


            # If user install failed, try system-wide pip (might need sudo/admin)
            # This is less likely to work without permissions but included per request
            if not installed:
                 print(f"\n\033[96m📦 Attempting to install via pip (system)... (May require admin/sudo)\033[0m")
                 try:
                     # On Linux, might need --break-system-packages depending on Python/pip version
                     pip_command = [sys.executable, '-m', 'pip', 'install', pip_package]
                     if os.name == 'posix':
                         # Attempt with sudo on Linux, add break-system-packages for robustness
                         pip_command = ['sudo', sys.executable, '-m', 'pip', 'install', '--break-system-packages', pip_package]

                     result_sys = subprocess.run(pip_command,
                                                 check=True, capture_output=True, text=True, timeout=120)
                     print(f"\033[92m   ✓ Successfully installed {pip_package} via pip (system).\033[0m")
                     installed = True
                 except FileNotFoundError:
                      print(f"\033[91m   ✗ {'sudo' if os.name=='posix' else 'pip'} command not found for system install.\033[0m")
                 except subprocess.CalledProcessError as e_pip_sys:
                     print(f"\033[91m   ✗ pip install (system) failed for {pip_package}.\033[0m")
                     # Optionally print stderr for debugging:
                     # if e_pip_sys.stderr: print(f"     pip stderr: {e_pip_sys.stderr.strip()}")
                 except subprocess.TimeoutExpired:
                     print(f"\033[91m   ✗ pip install (system) timed out for {pip_package}.\033[0m")
                 except Exception as e_sys:
                      print(f"\033[91m   ✗ Unexpected error during pip install (system): {e_sys}\033[0m")

        # If still not installed after all attempts, add to failed list
        if not installed:
            failed_installs.append(pip_package)

    # If any installations failed, show manual instructions
    if failed_installs:
        print(f"\n\033[93m⚠️ Some packages could not be installed automatically:\033[0m")
        print("\n╭" + "─" * 58 + "╮")
        print(f"│ \033[91mFailed to install:\033[0m".ljust(68) + "│") # Adjust ljust for color codes
        for package in failed_installs:
            print(f"│ • \033[93m{package}\033[0m".ljust(68) + "│")
        print("│" + " " * 58 + "│")
        print("│ \033[92mPlease try installing them manually:\033[0m".ljust(74) + "│")
        for package in failed_installs:
            print("│" + " " * 58 + "│")
            print(f"│ \033[96mFor {package}:\033[0m".ljust(70) + "│")
            # Suggest user install first as it's generally safer
            print(f"│   \033[97mpip install --user {package}\033[0m".ljust(69) + "│")
            print(f"│   \033[90m# or, if needed (might require admin/sudo):\033[0m".ljust(80) + "│")
            print(f"│   \033[97mpip install {package}\033[0m".ljust(69) + "│")
            if os.name == 'posix':
                 print(f"│   \033[90m# (On Linux, you might need: sudo pip install --break-system-packages {package})\033[0m".ljust(95)+"│")
        print("╰" + "─" * 58 + "╯\n")
        # Decide if failure is critical
        # For a bundled app, maybe just warn and continue, hoping PyInstaller included it?
        # Or exit if essential packages failed? Let's warn and continue for now.
        print(Fore.RED + "Attempting to continue, but functionality may be limited.")
        # sys.exit(1) # Uncomment to make dependency failure critical

# --- Colorama Import/Init (keep this structure) ---
try:
    # Ensure colorama is imported AFTER the check_dependencies definition
    # but potentially before its first implicit call (if it runs on module import)
    from colorama import Fore, init
    init(autoreset=True)
except ImportError:
    # Define fallback Fore class if colorama is missing
    class Fore:
        RED = YELLOW = GREEN = CYAN = RESET = BLUE = MAGENTA = WHITE = LIGHTBLACK_EX = '\033[0m' # Basic reset
        # Add manual codes if needed elsewhere, but relying on installed colorama is better
        # Example: RED = '\033[91m'
    print("Warning: colorama not found, colors disabled.")
    def init(autoreset=True): pass # Dummy init

# --- Implicit Call or Explicit Call ---
# If check_dependencies runs automatically when this module is imported (due to being at top level),
# then no explicit call is needed here.
# If it needs an explicit call:
# check_dependencies()

# --- Rest of the file ---
import requests
import json
# from colorama import Fore # Already handled above
import concurrent.futures
import tqdm
# import os # Already imported
from core.quran_cache import QuranCache

class QuranAPIError(Exception):
    """Base exception for Quran API errors"""

class QuranAPIClient:
    BASE_URL = "https://quranapi.pages.dev/api/"
    TIMEOUT = 10

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "QuranClient/1.0"})
        self.cache = QuranCache()
        self._init_cache()

    def _init_cache(self):
        """Initialize and validate cache"""
        print(Fore.YELLOW + "\n📂 Checking Quran data cache...")
        missing_surahs = self.cache.validate_cache()
        
        if missing_surahs:
            print(Fore.CYAN + f"\n⏳ Downloading {len(missing_surahs)} missing surahs...")
            self._download_surahs(missing_surahs)
            print(Fore.GREEN + "\n✓ Download complete!")
        else:
            print(Fore.GREEN + "\n✓ All surahs available in cache!")

    def _handle_response(self, response: requests.Response) -> dict:
        """Handle API response and return JSON data"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise QuranAPIError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            raise QuranAPIError(f"Invalid JSON response: {e}")

    def _download_single_surah(self, surah_num: int) -> bool:
        """Download a single surah"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}{surah_num}.json",
                timeout=self.TIMEOUT
            )
            data = self._handle_response(response)
            
            # Remove bengali data if it exists
            if 'bengali' in data:
                del data['bengali']
                
            self.cache.save_surah(surah_num, data)
            return True
        except Exception as e:
            return False

    def _download_surahs(self, surah_numbers: set):
        """Download multiple surahs in parallel"""
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear terminal
        print(Fore.CYAN + "Downloading Quran data...")
        print(Fore.GREEN + "Please wait, it won't take long...\n")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._download_single_surah, num): num for num in surah_numbers}
            failed_surahs = set()
            
            with tqdm.tqdm(total=len(surah_numbers), desc=Fore.RED + "Progress" + Fore.RESET, 
                          unit="surah", colour='red') as pbar:
                for future in concurrent.futures.as_completed(futures):
                    surah_num = futures[future]
                    if not future.result():
                        failed_surahs.add(surah_num)
                    pbar.update(1)

            # Retry failed downloads
            if failed_surahs:
                print(Fore.YELLOW + "\nRetrying failed downloads...")
                for surah_num in failed_surahs:
                    if self._download_single_surah(surah_num):
                        print(Fore.GREEN + f"Successfully downloaded Surah {surah_num}")
                    else:
                        print(Fore.RED + f"Failed to download Surah {surah_num}")

