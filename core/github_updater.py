# core/github_updater.py
import requests
import re
import time
import json
import os
from colorama import Fore
from pathlib import Path
# --- Use relative import for utils ---
from .utils import get_app_path

class GithubUpdater:
    # --- CORRECTED PATH: Use writable=True ---
    CACHE_FILE = Path(get_app_path('api_cache.json', writable=True)) # API cache next to exe
    # --- End Correction ---
    CACHE_EXPIRY = 3600  # Cache expiry time in seconds (1 hour)
    GITHUB_REPO_OWNER = "anonfaded"
    GITHUB_REPO_NAME = "QuranCLI"

    def __init__(self, repo_owner, repo_name, current_version):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        self.cache = self._load_cache()

    def _load_cache(self):
        """Loads the cache from the JSON file. Creates the file if it doesn't exist."""
        try:
            # get_app_path(writable=True) should ensure directory exists
            if not self.CACHE_FILE.exists():
                default_cache = {"last_check": 0, "data": {}}
                # Attempt to create the file with default content
                try:
                     with open(self.CACHE_FILE, "w", encoding='utf-8') as f:
                         json.dump(default_cache, f, indent=4)
                     return default_cache
                except IOError as e:
                     print(f"{Fore.RED}Error creating cache file {self.CACHE_FILE}: {e}")
                     return {"last_check": 0, "data": {}} # Return default on creation error
            else:
                 with open(self.CACHE_FILE, "r", encoding='utf-8') as f:
                     return json.load(f)
        except json.JSONDecodeError:
            print(Fore.YELLOW + f"Cache file {self.CACHE_FILE} is corrupted. Resetting cache.")
            default_cache = {"last_check": 0, "data": {}}
            try: # Attempt to overwrite corrupted file
                 with open(self.CACHE_FILE, "w", encoding='utf-8') as f:
                      json.dump(default_cache, f, indent=4)
            except IOError as e:
                 print(f"{Fore.RED}Error resetting corrupted cache file: {e}")
            return default_cache
        except Exception as e:
            print(Fore.RED + f"Error loading cache {self.CACHE_FILE}: {e}")
            return {"last_check": 0, "data": {}}  # Return a default cache on error

    def _save_cache(self):
        """Saves the cache to the JSON file."""
        try:
            # get_app_path(writable=True) should ensure directory exists
            with open(self.CACHE_FILE, "w", encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
        except IOError as e:
            print(Fore.RED + f"Error saving cache {self.CACHE_FILE}: {e}")
        except Exception as e:
             print(Fore.RED + f"Unexpected error saving cache: {e}")

    def get_latest_release_info(self):
        """Gets the latest tag name and URL of GitHub releases, using the cache."""
        now = time.time()
        cache_key = f"{self.repo_owner}/{self.repo_name}"

        # Check cache validity
        cached_data = self.cache.get("data", {}).get(cache_key)
        if cached_data and isinstance(cached_data, dict):
             expiry = cached_data.get("expiry", 0)
             tag_name = cached_data.get("tag_name")
             release_url = cached_data.get("release_url")
             if expiry > now and tag_name and release_url:
                 # print(Fore.GREEN + "Using cached release info.") # Debug only
                 return tag_name, release_url

        # Cache miss or expired, fetch from GitHub API
        # print(Fore.YELLOW + "Fetching new release info from GitHub API...") # Debug only
        try:
            response = requests.get(self.api_url, timeout=10) # Increased timeout slightly
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            release_info = response.json()
            latest_tag_name = release_info.get("tag_name")
            latest_release_url = release_info.get("html_url")

            if not latest_tag_name or not latest_release_url:
                 print(Fore.YELLOW + "Warning: Could not parse tag name or URL from GitHub API response.")
                 return "", "" # Return empty on parse failure

            # Update cache - ensure structure is correct
            if "data" not in self.cache: self.cache["data"] = {}
            self.cache["data"][cache_key] = {
                "tag_name": latest_tag_name,
                "release_url": latest_release_url,
                "expiry": now + self.CACHE_EXPIRY,
            }
            self.cache["last_check"] = now
            self._save_cache()
            return latest_tag_name, latest_release_url

        except requests.exceptions.RequestException as e:
           # print(Fore.RED + f"Failed to get release info: {e}") # Debug only
            return "", "" # Return empty strings on network failure
        except Exception as e: # Catch other potential errors (e.g., JSON decoding)
           # print(Fore.RED + f"Error processing release info: {e}") # Debug only
            return "", ""

    # --- compare_versions remains unchanged ---
    def compare_versions(self, version1, version2):
        """Compares two version strings (e.g., "v1.0.0", "v1.0.0-beta")."""
        def normalize(v):
            if not v: return None, None
            # Handle optional 'v' prefix, main version, and optional pre-release suffix
            match = re.match(r"v?(\d+(?:\.\d+)*)(?:-([a-zA-Z0-9.-]+))?", str(v))
            if not match: return None, None # Invalid format
            version_numbers = [int(x) for x in match.group(1).split('.')]
            pre_release = match.group(2) # Can be None
            return version_numbers, pre_release

        v1_numbers, v1_pre = normalize(version1)
        v2_numbers, v2_pre = normalize(version2)

        if v1_numbers is None or v2_numbers is None:
            # print(f"Warning: Could not compare invalid versions '{version1}' and '{version2}'")
            return 0 # Treat as equal if format is bad

        # Compare numeric parts
        max_len = max(len(v1_numbers), len(v2_numbers))
        for i in range(max_len):
            n1 = v1_numbers[i] if i < len(v1_numbers) else 0
            n2 = v2_numbers[i] if i < len(v2_numbers) else 0
            if n1 > n2: return 1
            if n1 < n2: return -1

        # Numeric parts are equal, compare pre-release identifiers
        # Rule: No pre-release > pre-release (e.g., 1.0.0 > 1.0.0-beta)
        if v1_pre is None and v2_pre is not None: return 1
        if v1_pre is not None and v2_pre is None: return -1
        if v1_pre is not None and v2_pre is not None:
            # Simple alphabetical comparison for pre-release tags
            if v1_pre > v2_pre: return 1
            if v1_pre < v2_pre: return -1

        return 0 # Versions are equal