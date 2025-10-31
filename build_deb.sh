#!/bin/bash

# build_deb.sh - Automated script to build QuranCLI executable and Debian package
# Usage: ./build_deb.sh

set -e  # Exit on any error

echo "=== QuranCLI Debian Package Build Script ==="
echo "This script will:"
echo "1. Run PyInstaller to create the executable"
echo "2. Install build dependencies"
echo "3. Verify executable permissions"
echo "4. Build the Debian package"
echo "5. Move .deb file to root directory"
echo ""

# Check if we're in the correct directory
if [ ! -f "QuranCLI.spec" ]; then
    echo "Error: QuranCLI.spec not found. Please run this script from the project root."
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python not found. Please install python3 (3.9 or higher)."
    exit 1
fi

# Check if dpkg-buildpackage is available
if ! command -v dpkg-buildpackage &> /dev/null; then
    echo "Error: dpkg-buildpackage not found. Please install dpkg-dev package."
    exit 1
fi

# Check if dos2unix is available
if ! command -v dos2unix &> /dev/null; then
    echo "Error: dos2unix not found. Please install it."
    exit 1
fi

echo "Step 1: Running PyInstaller..."
/home/faded/.local/bin/pyinstaller QuranCLI.spec

echo ""
echo "Step 2: Installing build dependencies..."
sudo apt-get update
sudo apt-get install -y debhelper

echo ""
echo "Step 3: Verifying executable permissions..."
if [ -f "dist/QuranCLI" ]; then
    chmod +x dist/QuranCLI
    echo "✓ Executable permissions set for dist/QuranCLI"
else
    echo "Warning: Executable not found at dist/QuranCLI"
fi

echo ""
echo "Step 4: Building Debian package..."
cd core/linux
dos2unix debian/postinst debian/prerm debian/postrm
dpkg-buildpackage -us -uc -b
cd ../..

echo ""
echo "Step 5: Moving .deb file to root directory..."
DEB_FILE=$(ls core/qurancli_*.deb | head -1)
if [ -f "$DEB_FILE" ]; then
    mv "$DEB_FILE" .
    echo "✓ Moved $DEB_FILE to root directory"
else
    echo "Warning: No .deb file found in parent directory"
fi