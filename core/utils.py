# core/utils.py
import sys
import os

# This file provides utility functions for path handling,
# supporting both normal script execution and PyInstaller frozen bundles.

def get_app_path(resource_path: str = '', writable: bool = False) -> str:
    """
    Get the absolute path to a resource or writable directory.

    Handles both script execution and PyInstaller frozen bundles.

    Args:
        resource_path: Relative path to a resource/directory.
                       Leave empty for the base directory itself.
        writable:
            If True: Returns a path relative to the EXECUTABLE's directory.
                     Use this for cache, config, logs that should live
                     alongside the application executable.
                     Ensures the target directory exists.
            If False: Returns a path relative to the application's internal
                      root (sys._MEIPASS when frozen, script's project root
                      otherwise). Use this for accessing READ-ONLY bundled
                      assets (like web files, data files).

    Returns:
        Absolute path as a string.
    """
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running in a PyInstaller bundle
            if writable:
                # Writable files go next to the executable file itself
                base_path = os.path.dirname(sys.executable)
            else:
                # Read-only bundled resources are relative to the temporary _MEIPASS dir
                base_path = sys._MEIPASS
        else:
            # Running as a normal Python script
            # Assume utils.py is in core/, so project root is the parent directory
            # This provides a consistent base path during development
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Construct the full path by joining the base path and the relative resource path
        full_path = os.path.join(base_path, resource_path) if resource_path else base_path

        # If a writable path is requested, ensure the directory exists
        if writable and resource_path:
            # Determine if the resource_path looks like a file or a directory
            # If it looks like a file (contains '.' in the last part and doesn't end with '/'),
            # ensure the parent directory exists. Otherwise, ensure the full path exists as a directory.
            if '.' in os.path.basename(resource_path) and not resource_path.endswith(('/', '\\')):
                target_dir = os.path.dirname(full_path)
            else:
                target_dir = full_path

            # Create the target directory if it doesn't exist.
            # exist_ok=True prevents an error if the directory already exists.
            # parents=True creates any necessary parent directories as well.
            if target_dir: # Avoid trying to create empty dir if base_path was requested
                 os.makedirs(target_dir, exist_ok=True)

        return full_path

    except Exception as e:
        # Fallback or error logging if path determination fails
        print(f"Error determining application path for '{resource_path}' (writable={writable}): {e}", file=sys.stderr)
        # Return a sensible fallback, perhaps the current working directory, though this is risky.
        # Returning relative path might be safer in case of total failure.
        return resource_path


def add_core_to_path_if_frozen():
    """
    Modify sys.path when running as a PyInstaller frozen executable.

    This ensures that modules bundled within subdirectories (like 'core')
    can be imported correctly using standard import statements (e.g., `from core.ui import UI`).
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # sys._MEIPASS is the root directory where PyInstaller extracted the bundle

        # Add the _MEIPASS directory itself to sys.path first.
        # This allows importing modules or accessing files bundled at the root.
        if sys._MEIPASS not in sys.path:
            sys.path.insert(0, sys._MEIPASS)
            # print(f"DEBUG: Added _MEIPASS to sys.path: {sys._MEIPASS}", file=sys.stderr) # Optional debug

        # Specifically add the 'core' subdirectory within _MEIPASS to sys.path.
        # This allows imports like `from ui import UI` if run from within core,
        # or more commonly `from core.ui import UI` from the main script.
        core_path = os.path.join(sys._MEIPASS, 'core')
        if os.path.isdir(core_path) and core_path not in sys.path:
            sys.path.insert(0, core_path) # Insert at beginning for priority
            # print(f"DEBUG: Added bundled 'core' to sys.path: {core_path}", file=sys.stderr) # Optional debug

    # No changes needed to sys.path when running as a normal script,
    # as Python's standard import mechanism should work based on file structure.

# --- Example Usage (for understanding, not needed in production) ---
# if __name__ == "__main__":
#     print(f"Running as frozen app: {getattr(sys, 'frozen', False)}")
#     if hasattr(sys, '_MEIPASS'): print(f"_MEIPASS: {sys._MEIPASS}")
#     print("-" * 20)
#     print(f"Executable Dir (approx): {os.path.dirname(sys.executable)}")
#     print("-" * 20)
#     print(f"Bundled Asset Root (get_app_path()): {get_app_path()}")
#     print(f"Bundled 'core/web' (read-only): {get_app_path('core/web')}")
#     print("-" * 20)
#     print(f"Writable Root (get_app_path(writable=True)): {get_app_path(writable=True)}")
#     print(f"Writable 'cache' Dir: {get_app_path('cache', writable=True)}")
#     print(f"Writable 'config.json' Path: {get_app_path('config.json', writable=True)}")
#     print("-" * 20)
#     print("Current sys.path:")
#     for p in sys.path: print(f"  {p}")