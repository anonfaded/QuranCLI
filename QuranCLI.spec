# -*- mode: python ; coding: utf-8 -*-
import os
import site # Keep just in case we need it later for manual additions

block_cipher = None

# --- Configuration ---
app_name = 'QuranCLI'
main_script = 'Quran-CLI.py'
icon_file = 'core/icon.ico' # Icon in the root directory

# --- Data files to bundle (Read-Only Assets) ---
datas = [
    ('core/web', 'core/web'),  # Bundle the web server assets
    ('README_APP.txt', '.')
]

# --- Hidden Imports ---
hiddenimports = [
    'pygame',
    'keyboard._winkeyboard', # Windows backend for 'keyboard'
    # 'pkg_resources.py2_warn', # Removed as it caused an error and is often unnecessary
    'bidi',
    'arabic_reshaper',
    'mutagen',
    'aiohttp',
    'aiofiles',
    'platformdirs', # Needed for Documents path in ui.py
    'requests',
    'colorama',
    'difflib',
    'http.server',
    'socketserver',
    # --- Dependencies of requests (often needed) ---
    'urllib3',
    'charset_normalizer',
    'idna',
    'certifi',
    # --- End Dependencies ---
]

# --- Analysis ---
a = Analysis(
    [main_script],
    pathex=[os.getcwd()], # Include current directory
    binaries=[], # Let PyInstaller auto-detect first
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- Manual DLL/Data Addition (Example - Not needed for python311.dll yet) ---
# If specific library DLLs (e.g., from pygame, though usually auto-detected)
# are found to be missing later, they could be added here similar to the
# FadCrypt example, adding tuples to a.datas or a.binaries.
# Example:
# for f in os.listdir(some_library_dll_path):
#     if f.endswith('.dll'):
#         a.binaries += [ (os.path.join(some_library_dll_path, f), '.') ] # Add to binaries tuple list

# --- Python Archive ---
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- Executable (Using FadCrypt's --onefile EXE structure) ---
exe = EXE(
    pyz,                    # The bundled Python bytecode
    a.scripts,              # The main script(s)
    a.binaries,             # Binaries detected by Analysis (or added manually)
    a.zipfiles,             # Zipped dependencies
    a.datas,                # Data files detected by Analysis (or added manually)
    [],                     # Legacy argument, usually empty
    name=app_name,          # Output executable name
    debug=False,            # Set True for more verbose error output from bootloader
    bootloader_ignore_signals=False,
    strip=False,            # Strip symbols (optional)
    upx=True,               # Use UPX compressor (set False if problematic)
    upx_exclude=[],
    runtime_tmpdir=None,    # Use default temp dir for extraction
    console=True,           # *** CRITICAL: Ensure this is TRUE for a CLI app ***
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,       # Auto-detect architecture
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_file],       # Specify icon (using list like FadCrypt)
)

# No COLLECT block needed for --onefile build