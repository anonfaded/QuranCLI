# core/download_counter.py
import requests
import time
import json
import sys
import os
from pathlib import Path
from colorama import Fore, Style # Use colorama for potential logging
from urllib.parse import urlparse  # Correct import for urlparse
import platformdirs # Use platformdirs for cross-platform path handling

# --- Use relative import for utils ---
# Only needed if Windows path is used
if sys.platform == "win32":
    try:
        from .utils import get_app_path
    except ImportError: # Fallback if run directly
        from utils import get_app_path

# --- Define constants for platformdirs ---
APP_NAME = "QuranCLI"
APP_AUTHOR = "FadSecLab"

class DownloadCounter:
    """Fetches and caches the total download count for a GitHub repository."""

    CACHE_FILE_NAME = 'download_cache.json' # Just the filename now
    DEFAULT_CACHE_EXPIRY = 3600  # 1 hour in seconds

    def __init__(self, repo_owner: str, repo_name: str, cache_expiry: int = DEFAULT_CACHE_EXPIRY):
        if not repo_owner or not repo_name:
            raise ValueError("Repository owner and name are required.")

        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
        self.cache_expiry = cache_expiry
        self.cache_file_path = None # Initialize path attribute

        # --- Platform-Specific Path for Download Cache ---
        try:
            if sys.platform == "win32":
                # Windows: Save next to executable
                self.cache_file_path = Path(get_app_path(self.CACHE_FILE_NAME, writable=True))
                # get_app_path(writable=True) ensures directory exists
                # print(f"DEBUG: Download cache path (Win): {self.cache_file_path}") # Optional debug
            else:
                # Linux/macOS: Use user's cache directory
                cache_base_dir = platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR)
                os.makedirs(cache_base_dir, exist_ok=True) # Ensure directory exists
                self.cache_file_path = Path(cache_base_dir) / self.CACHE_FILE_NAME
                # print(f"DEBUG: Download cache path (Unix): {self.cache_file_path}") # Optional debug

        except Exception as e_path:
            print(f"{Fore.RED}Critical Error determining download cache path: {e_path}")
            print(f"{Fore.YELLOW}Download count caching may not work correctly.")
            # cache_file_path remains None, load/save should handle this

        # --- Setup session ---
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": f"{repo_name}DownloadCounter/1.0"})

        # --- Load cache ---
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Loads download count cache from file."""
        default_cache = {"last_check": 0, "total_downloads": None}
        # Check if path was determined successfully
        if not self.cache_file_path or not self.cache_file_path.exists():
            return default_cache
        try:
            with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data.get("last_check"), (int, float)) and isinstance(data.get("total_downloads"), (int, type(None))):
                     return data
                else:
                     print(f"{Fore.YELLOW}Warning: Download cache format invalid, resetting.{Style.RESET_ALL}")
                     return default_cache
        except (json.JSONDecodeError, IOError) as e:
            print(f"{Fore.YELLOW}Warning: Could not load download cache ({self.cache_file_path}): {e}{Style.RESET_ALL}")
            return default_cache
        except Exception as e:
             print(f"{Fore.RED}Unexpected error loading download cache: {e}{Style.RESET_ALL}")
             return default_cache


    def _save_cache(self):
        """Saves the current download count cache to file."""
        # Check if path was determined successfully
        if not self.cache_file_path:
            print(f"{Fore.RED}Error: Cannot save download cache - path not set.{Style.RESET_ALL}")
            return
        try:
            # Ensure directory exists (should have been created in init)
            self.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2)
        except (IOError, OSError) as e:
            print(f"{Fore.RED}Error: Could not save download cache ({self.cache_file_path}): {e}{Style.RESET_ALL}")
        except Exception as e:
             print(f"{Fore.RED}Unexpected error saving download cache: {e}{Style.RESET_ALL}")



# core/download_counter.py (inside DownloadCounter class)

    def _fetch_total_downloads(self) -> int | None:
        """
        Fetches all releases and sums the download counts for all assets.
        Handles pagination and network errors gracefully.

        Returns:
            Total download count as int, or None if fetching fails.
        """
        total_downloads = 0
        page = 1
        per_page = 100 # Max allowed by GitHub API
        fetch_url = self.api_url
        # Initial message only if not fetching from cache later
        # print(f"{Fore.CYAN}Checking GitHub for download counts...{Style.RESET_ALL}")

        while fetch_url:
            response = None # Initialize response to None for error checking
            try:
                params = {'per_page': per_page}
                # Only add 'page' param if it's in the URL from Link header
                current_url_params = urlparse(fetch_url).query
                current_url_params = urlparse(fetch_url).query
                if 'page' in current_url_params:
                     # If page is already in the URL (from Link header), don't add it again via params
                     pass
                elif page > 1:
                     # This case shouldn't happen if Link header is used correctly, but as fallback
                     params['page'] = page

                response = self.session.get(fetch_url, params=params, timeout=10) # Shorter timeout for offline check
                response.raise_for_status() # Check for HTTP errors (4xx, 5xx)

                releases = response.json()
                if not releases: break # No more releases

                for release in releases:
                    if isinstance(release.get('assets'), list):
                        for asset in release['assets']:
                            count = asset.get('download_count', 0)
                            if isinstance(count, int): total_downloads += count

                # Pagination using Link header
                link_header = response.headers.get('Link')
                next_url = None
                if link_header:
                    links = requests.utils.parse_header_links(link_header)
                    for link in links:
                        if link.get('rel') == 'next': next_url = link.get('url'); break

                if next_url:
                    fetch_url = next_url
                    page += 1
                    # print(f"{Fore.CYAN}Fetching next page...{Style.RESET_ALL}") # Optional debug
                else:
                    fetch_url = None # No more pages

            # --- UPDATED ERROR HANDLING ---
            except requests.exceptions.ConnectionError as e_conn:
                 # Specific handling for connection/DNS errors (likely offline)
                 print(f"{Fore.YELLOW}Offline or cannot reach GitHub. Skipping download count check.{Style.RESET_ALL}")
                 # You could check e_conn.args here for more specific errors like NameResolutionError if needed
                 return None # Fail gracefully
            except requests.exceptions.Timeout:
                 print(f"{Fore.YELLOW}Timeout connecting to GitHub. Skipping download count check.{Style.RESET_ALL}")
                 return None # Fail gracefully
            except requests.exceptions.HTTPError as e_http:
                 # Handle specific HTTP errors (e.g., 403 Rate Limit, 404 Not Found)
                 if response is not None and response.status_code == 403:
                      print(f"{Fore.YELLOW}GitHub API rate limit likely exceeded. Using cached count if available.{Style.RESET_ALL}")
                 elif response is not None and response.status_code == 404:
                      print(f"{Fore.RED}Error: Repository not found on GitHub ({self.repo_owner}/{self.repo_name}).{Style.RESET_ALL}")
                 else:
                      print(f"{Fore.RED}Error fetching release data (HTTP {response.status_code if response else 'N/A'}): {e_http}{Style.RESET_ALL}")
                 return None # Fail, but potentially use cache later
            except requests.exceptions.RequestException as e_req:
                 # Catch other general requests errors
                 print(f"{Fore.RED}Network error fetching release data: {e_req}{Style.RESET_ALL}")
                 return None # Fail gracefully
             # --- END UPDATED ERROR HANDLING ---
            except (json.JSONDecodeError, KeyError, TypeError) as e_parse:
                 print(f"{Fore.RED}Error parsing GitHub API response: {e_parse}{Style.RESET_ALL}")
                 return None
            except Exception as e_other:
                 print(f"{Fore.RED}Unexpected error during download count fetch: {e_other}{Style.RESET_ALL}")
                 return None

        # Only print success if fetch was attempted and didn't hit immediate network error exit
        # print(f"{Fore.GREEN}Finished fetching counts. Total: {total_downloads}{Style.RESET_ALL}")
        return total_downloads


    def get_total_downloads(self, force_refresh: bool = False) -> int | None:
        """
        Gets the total download count, using cache if valid, otherwise fetches.

        Args:
            force_refresh: If True, ignore cache and fetch fresh data.

        Returns:
            Total download count as int, or None if unavailable.
        """
        now = time.time()
        last_check = self._cache.get("last_check", 0)
        cached_downloads = self._cache.get("total_downloads") # Can be None

        # Check cache validity
        if not force_refresh and (now - last_check) < self.cache_expiry and cached_downloads is not None:
            # print("DEBUG: Using cached download count.") # Debug only
            return cached_downloads

        # Cache invalid or forced refresh, fetch new data
        # print("DEBUG: Fetching new download count.") # Debug only
        fetched_downloads = self._fetch_total_downloads()

        if fetched_downloads is not None and fetched_downloads >= 0:
            # Update cache with fresh data
            self._cache["last_check"] = now
            self._cache["total_downloads"] = fetched_downloads
            self._save_cache()
            return fetched_downloads
        else:
            # Fetch failed, return stale data if available, otherwise None
            print(f"{Fore.YELLOW}Warning: Failed to fetch fresh download count.{Style.RESET_ALL}")
            if cached_downloads is not None:
                 print(f"{Fore.YELLOW}Returning stale cached count: {cached_downloads}{Style.RESET_ALL}")
                 return cached_downloads
            else:
                 print(f"{Fore.YELLOW}No download count available.{Style.RESET_ALL}")
                 return None # Indicate unavailability