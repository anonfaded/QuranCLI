# 📖 QuranCLI

A feature-rich Command Line Interface for reading and listening to the Holy Quran.

![image](https://github.com/user-attachments/assets/e5fa1c2b-fb35-41f9-be34-98688d4bdbc0)


## ✨ Features

- 📑 Read all 114 Surahs of the Quran
- 🎯 Multiple Arabic script styles (Simple and Uthmani)
- 🌍 English translations
- 🔊 Audio recitation with multiple reciters
- ⏯️ Advanced audio controls (play, pause, seek)
- 💾 Smart caching system for both text and audio
- 📱 Responsive terminal interface
- 📖 Pagination for better readability
- 🎨 Colorful and intuitive interface

## 🚀 Getting Started

### Prerequisites

- Python 3.7+
- pip package manager

### Installation

1.  Clone the repository:

    ```bash
    git clone https://github.com/anonfaded/QuranCLI.git
    cd QuranCLI
    ```

2.  Install required packages:

    ```bash
    pip install -r requirements.txt
    ```

3.  Run the application:

    ```bash
    python Quran-CLI.py
    ```

## 🎮 Controls

### Navigation

*   Enter surah number (1-114)
*   Select ayah range
*   Use `n` for next page
*   Use `p` for previous page
*   Use `q` to go back/quit

### Audio Controls

*   `p`: Play/Pause
*   `s`: Stop
*   `r`: Change reciter
*   `←/→`: Seek 5 seconds
*   `Ctrl + ←/→`: Seek 30 seconds
*   `q`: Return to text view

## 🏗️ Architecture

The application is structured into several core modules:

*   `QuranAPIClient`: Handles API communication and data caching.
*   `QuranCache`: Provides efficient local caching.
*   `QuranDataHandler`: Handles data retrieval and formatting.
*   `AudioManager`: Manages audio playback and controls.
*   `UI`: Handles user interface elements.
*   `QuranApp`: Orchestrates the application.
*   version.py: Stores the version information for easy access.

*   ui.py: Displays the version in the application header.

*   github_updater.py:

        Fetches the latest release from the GitHub API.

        Compares VERSION_CODE with the latest release's tag.

        Informs the user about updates and provides a link.
## 🛠️ Dependencies

*   requests
*   pydantic
*   colorama
*   python-bidi
*   arabic-reshaper
*   tqdm
*   pygame
*   aiohttp
*   aiofiles
*   keyboard
*   mutagen

```python
pip install requests pydantic colorama python-bidi arabic-reshaper tqdm pygame aiohttp aiofiles keyboard mutagen
```

## 📝 Notes

*   Arabic text appears reversed in the terminal but copies correctly.
*   Audio files are cached locally.
*   Supports multiple reciters.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests.

## 📄 License

This project is licensed under the GPL-3.0 - see the LICENSE file for details.
