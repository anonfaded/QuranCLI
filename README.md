# 📖 QuranCLI

A feature-rich Command Line Interface for reading and listening to the Holy Quran.

```ascii
 ██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗     ██████╗██╗     ██╗
██╔═══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║    ██╔════╝██║     ██║
██║   ██║██║   ██║██████╔╝███████║██╔██╗ ██║    ██║     ██║     ██║
██║▄▄ ██║██║   ██║██╔══██╗██╔══██║██║╚██╗██║    ██║     ██║     ██║
╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║    ╚██████╗███████╗██║
 ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝     ╚═════╝╚══════╝╚═╝
```

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

1. Clone the repository:
```bash
git clone https://github.com/anonfaded/QuranCLI.git
cd QuranCLI
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python Quran-CLI.py
```

## 🎮 Controls

### Navigation
- Enter surah number (1-114)
- Select ayah range
- Use 'n' for next page
- Use 'p' for previous page
- Use 'q' to go back/quit

### Audio Controls
- `p`: Play/Pause
- `s`: Stop
- `r`: Change reciter
- `←/→`: Seek 5 seconds
- `Ctrl + ←/→`: Seek 30 seconds
- `q`: Return to text view

## 🏗️ Technical Architecture

### Core Components

1. **QuranAPIClient**
   - Handles API communication
   - Manages data caching
   - Processes Arabic text formatting

2. **AudioManager**
   - Controls audio playback
   - Manages audio downloads
   - Provides seeking and progress tracking

3. **QuranCache**
   - Implements efficient caching system
   - Handles data persistence
   - Validates cached content

4. **QuranApp**
   - Main application interface
   - Manages user interaction
   - Coordinates all components

### Data Management
- Local caching of Quran text
- Efficient audio file management
- Thread-safe operations
- Automatic data validation

## 🛠️ Dependencies

- requests: API communication
- pydantic: Data validation
- colorama: Terminal colors
- pygame: Audio playback
- arabic-reshaper: Arabic text processing
- python-bidi: Bidirectional text support
- aiohttp: Async downloads
- mutagen: Audio metadata

## 📝 Notes

- Arabic text appears reversed in terminal but copies correctly
- Audio files are cached locally for faster access
- Supports multiple Quran reciters
- Auto-resumes from last position

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests.

## 📄 License

This project is licensed under the GPL: 3.0 - see the LICENSE file for details.