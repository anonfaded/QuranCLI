# core/quran_api_client.py
import sys
import subprocess
import shutil
from typing import Dict, List, Tuple

def get_package_map() -> Dict[str, str]:
    """Map pip package names to their apt equivalents"""
    return {
        'requests': 'python3-requests',
        'pydantic': 'python3-pydantic',
        'colorama': 'python3-colorama',
        'python-bidi': 'python3-bidi',
        'arabic-reshaper': 'python3-arabic-reshaper',
        'tqdm': 'python3-tqdm',
        'pygame': 'python3-pygame',
        'aiohttp': 'python3-aiohttp',
        'aiofiles': 'python3-aiofiles',
        'keyboard': 'python3-keyboard',
        'mutagen': 'python3-mutagen'
    }
    
def check_dependencies():
    """Check and install required dependencies with improved output"""
    package_map = get_package_map()
    missing_packages: List[Tuple[str, bool]] = []
    failed_installs: List[str] = []
    
    print("\n" + "═" * 60)
    print("📦 Checking Dependencies...")
    print("═" * 60)
    
    # First pass: Check what's missing
    for pip_package in package_map.keys():
        try:
            __import__(pip_package.replace('-', '_'))
        except ImportError:
            apt_package = package_map[pip_package]
            apt_available = bool(shutil.which('apt'))
            missing_packages.append((pip_package, apt_available))
    
    if not missing_packages:
        print("\n" + "╭" + "─" * 58 + "╮")
        print("│" + f"{Fore.GREEN}✓ All dependencies are satisfied!".center(58) + Fore.RESET + "│")
        print("╰" + "─" * 58 + "╯\n")
        return

    # Second pass: Try to install missing packages
    for pip_package, apt_available in missing_packages:
        print(f"\n{Fore.RED}❌ Missing package: {Fore.YELLOW}{pip_package}{Fore.RESET}")
        installed = False
        
        # Try apt first if available
        if apt_available:
            apt_package = package_map[pip_package]
            print(f"\n{Fore.CYAN}📦 Attempting to install via apt...{Fore.RESET}")
            try:
                result = subprocess.run(['sudo', 'apt', 'install', '-y', apt_package], 
                                     check=True, capture_output=True, text=True)
                if "Unable to locate package" not in result.stderr:
                    installed = True
                    continue
            except subprocess.CalledProcessError:
                pass
        
        # If apt failed or not available, try pip installations
        if not installed:
            try:
                # Try pip install --user first
                print(f"\n{Fore.CYAN}📦 Attempting to install via pip...{Fore.RESET}")
                subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', pip_package],
                             check=True, capture_output=True, text=True)
                installed = True
            except subprocess.CalledProcessError:
                try:
                    # If that fails, try sudo pip3 install
                    print(f"\n{Fore.CYAN}📦 Attempting to install with sudo...{Fore.RESET}")
                    subprocess.run(['sudo', 'pip3', 'install', '--break-system-packages', pip_package],
                                 check=True, capture_output=True, text=True)
                    installed = True
                except subprocess.CalledProcessError:
                    failed_installs.append(pip_package)
    
    # If any installations failed, show manual instructions
    if failed_installs:
        print(f"\n{Fore.YELLOW}⚠️  Some packages need manual installation:{Fore.RESET}")
        print("\n╭" + "─" * 58 + "╮")
        print(f"│ {Fore.RED}Failed to install:{Fore.RESET}".ljust(59) + "│")
        for package in failed_installs:
            print(f"│ • {Fore.YELLOW}{package}".ljust(59) + Fore.RESET + "│")
        print("│" + " " * 58 + "│")
        print("│ " + Fore.GREEN + "Try these commands:".ljust(56) + Fore.RESET + " │")
        for package in failed_installs:
            print("│" + " " * 58 + "│")
            print(f"│ {Fore.CYAN}For {package}:".ljust(59) + Fore.RESET + "│")
            print(f"│   sudo pip3 install --break-system-packages {package}".ljust(59) + "│")
            print(f"│   # or".ljust(59) + "│")
            print(f"│   pip install --user {package}".ljust(59) + "│")
        print("╰" + "─" * 58 + "╯\n")
        sys.exit(1)

# Import colorama first for colored output
try:
    from colorama import Fore, init
    init(autoreset=True)
except ImportError:
    # Fallback if colorama isn't available yet
    class Fore:
        RED = YELLOW = GREEN = CYAN = RESET = ''

# Check dependencies before other imports
check_dependencies()


import requests
import json
from colorama import Fore
import concurrent.futures
import tqdm
import os
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

