import requests
import re
import time
import json
import os
from colorama import Fore
from pathlib import Path


class GithubUpdater:
    CACHE_FILE = Path(__file__).parent / "api_cache.json"
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
            if not self.CACHE_FILE.exists():
                # Create the cache file with a default structure
                default_cache = {"last_check": 0, "data": {}}
                with open(self.CACHE_FILE, "w") as f:
                    json.dump(default_cache, f, indent=4)
                return default_cache

            with open(self.CACHE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(Fore.YELLOW + "Cache file is corrupted. Resetting cache.")
            # Handle corrupted cache file by creating a new one
            default_cache = {"last_check": 0, "data": {}}
            with open(self.CACHE_FILE, "w") as f:
                json.dump(default_cache, f, indent=4)
            return default_cache
        except Exception as e:
            print(Fore.RED + f"Error loading cache: {e}")
            return {"last_check": 0, "data": {}}  # Return a default cache on error

    def _save_cache(self):
        """Saves the cache to the JSON file."""
        try:
            with open(self.CACHE_FILE, "w") as f:
                json.dump(self.cache, f, indent=4)
        except IOError as e:
            print(Fore.RED + f"Error saving cache: {e}")

    def get_latest_release_info(self):
        """Gets the latest tag name and URL of GitHub releases, using the cache."""
        now = time.time()
        cache_key = f"{self.repo_owner}/{self.repo_name}"

        if (
            "data" in self.cache
            and cache_key in self.cache["data"]
            and "expiry" in self.cache["data"][cache_key]
            and self.cache["data"][cache_key]["expiry"] > now
        ):
            # Cache hit
            #print(Fore.GREEN + "Using cached release info.")#no neded
            return (
                self.cache["data"][cache_key]["tag_name"],
                self.cache["data"][cache_key]["release_url"],
            )

        # Cache miss or expired
        #print(Fore.YELLOW + "Fetching new release info from GitHub API...")#no neded, lets no annoy the users.
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            release_info = response.json()
            latest_tag_name = release_info["tag_name"]
            latest_release_url = release_info["html_url"]

            # Update cache
            self.cache["data"][cache_key] = {
                "tag_name": latest_tag_name,
                "release_url": latest_release_url,
                "expiry": now + self.CACHE_EXPIRY,
            }
            self.cache["last_check"] = now  # Update last check timestamp
            self._save_cache()
            return latest_tag_name, latest_release_url

        except Exception as e:
           # print(Fore.RED + f"Failed to get release info: {e}")##No need to print to annoy them
            return "", ""  # Return empty strings on failure

    def compare_versions(self, version1, version2):
        """Compares two version strings (e.g., "v1.0.0", "v1.0.0-beta").
        Returns 1 if version1 is newer, -1 if version2 is newer, 0 if equal.
        Handles pre-release versions correctly.
        """

        def normalize(v):
            # Extract the numeric parts and pre-release identifier (if any)
            parts = re.match(r"v?(\d+(?:\.\d+)+)(?:-([a-zA-Z]+))?", v)
            if not parts:
                return None, None  # Invalid version format

            version_numbers = [int(x) for x in parts.group(1).split(".")]
            pre_release = parts.group(2) if parts.lastindex > 1 else None
            return version_numbers, pre_release

        v1_numbers, v1_pre = normalize(version1)
        v2_numbers, v2_pre = normalize(version2)

        if v1_numbers is None or v2_numbers is None:
            return 0  # Unable to compare due to invalid format.

        # Compare the numeric parts
        for i in range(max(len(v1_numbers), len(v2_numbers))):
            v1 = v1_numbers[i] if i < len(v1_numbers) else 0
            v2 = v2_numbers[i] if i < len(v2_numbers) else 0
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1

        # If the numeric parts are equal, compare pre-release identifiers
        if v1_pre is None and v2_pre is not None:
            return 1  # Non-pre-release is newer than pre-release
        elif v1_pre is not None and v2_pre is None:
            return -1  # Pre-release is older than non-pre-release
        elif v1_pre is not None and v2_pre is not None:
            if v1_pre > v2_pre:
                return 1
            elif v1_pre < v2_pre:
                return -1

        return 0  # Versions are equal