# core/github_updater.py
import requests
import re
from colorama import Fore

class GithubUpdater:
    def __init__(self, repo_owner, repo_name, current_version):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

    def get_latest_release_info(self):
        """Gets the latest tag name and URL of GitHub releases. Returns empty strings on failure."""
        try:
            response = requests.get(self.api_url, timeout=3) # Timeout after 3 seconds
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            release_info = response.json()
            latest_tag_name = release_info["tag_name"]
            release_url = release_info["html_url"]
            return latest_tag_name, release_url
        except:
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