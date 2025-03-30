      
<div align="center">

<!-- <img src="https://github.com/user-attachments/assets/b82e6f7b-850d-4561-8290-083ef4bebfd6" alt="QuranCLI Icon" width="64"> -->

![icon](https://github.com/user-attachments/assets/b82e6f7b-850d-4561-8290-083ef4bebfd6)


# QuranCLI ✨

**Your Terminal Companion for the Holy Quran: Read, Listen & Generate Subtitles for Video Editing!**

[![GitHub all releases](https://img.shields.io/github/downloads/anonfaded/QuranCLI/total?label=Downloads&logo=github)](https://github.com/anonfaded/QuranCLI/releases/)

[![ko-fi badge](https://img.shields.io/badge/buy_me_a-coffee-red)](https://ko-fi.com/D1D510FNSV)
[![Discord](https://img.shields.io/discord/1263384048194027520?label=Join%20Us%20on%20Discord&logo=discord)](https://discord.gg/kvAZvdkuuN )


 <img src="https://github.com/user-attachments/assets/a7de16d4-eba6-4645-b5a5-8e9c7978ded3" alt="Demo" width="800">



</div>

> [!Tip]
> This project is part of the [FadSec Lab suite](https://github.com/fadsec-lab). <br> Discover our focus on ad-free, privacy-first applications and stay updated on future releases!


---

QuranCLI brings the Quran to your Windows command line with a rich set of features designed for readers, listeners, and video creators.

## 🌟 Key Features

*   **📖 Read Anywhere:** Access all 114 Surahs with English translation (Simple & Uthmani Arabic scripts).
*   **🎧 Listen:** Stream audio recitations from various renowned reciters with full playback controls (play/pause/seek).
*   **🎬 Subtitle Generation:** Create `.srt` subtitle files (Arabic + English) for Ayah ranges – perfect for video editing!
*   **🌐 Subtitle Sharing:** **Built-in web server** to easily share generated subtitle files with other devices (phone, tablet, other PCs) on the same Wi-Fi network.
*   **💾 Smart Caching:** Works offline by caching Quran text and audio locally.
*   **🎨 Intuitive Interface:** Colorful, responsive, and easy-to-navigate terminal UI.
*   **🔄 Auto-Updates:** Notifies you of new versions available on GitHub.
*   **📊 Stats:** See total download counts directly in the header.

---

## 🎬 Demo & Screenshots

<div align="center">
  <img src="https://github.com/user-attachments/assets/be3ae1e9-ca4d-4d8d-abee-7a4d3e854450" alt="Reading View" width="550">
  <p><em>Reading View (Simple & Uthmani Scripts + Translation)</em></p>
</div>

<br>

<div align="center">
  <img src="https://github.com/user-attachments/assets/a60fd008-24df-4e41-90cb-92f77e6ffba6" alt="Audio Player" width="550">
  <p><em>Audio Player (with Progress Bar & Controls)</em></p>
</div>

<br>

<div align="center">
  <img src="https://github.com/user-attachments/assets/3b03bcc3-8a6e-4895-9a89-d6c6963c5b17" alt="Reciter Selection" width="550">
  <p><em>Reciter Selection Menu</em></p>
</div>

<br>

<div align="center">
  <img src="https://github.com/user-attachments/assets/b879b4d3-67b7-4fb6-9a86-81bcd25a8edb" alt="Surah List" width="550">
  <p><em>Full Surah List (`list` command)</em></p>
</div>

<br>

<div align="center">
  <img src="https://github.com/user-attachments/assets/63d4c123-1a86-48cf-b622-c8edcf6c9b0a" alt="Smart Search" width="550">
  <p><em>Smart Surah Search (Suggestions for "rehman")</em></p>
</div>

<br>

<div align="center">
  <img src="https://github.com/user-attachments/assets/7ce2b6e0-eff8-4180-8ca3-2587c7549f0b" alt="Info Page" width="550">
  <p><em>Information / Help Page (`info` command)</em></p>
</div>

<br>

<div align="center">
  <img src="https://github.com/user-attachments/assets/5499387f-8907-43a0-a0e3-a6cbe4cf46cc" alt="Subtitle Management" width="550">
  <p><em>Subtitle Management & Sharing (`sub` command)</em></p>
</div>

<br>

<div align="center">
  <img src="https://github.com/user-attachments/assets/fa1d8b3c-d6d2-41fa-9722-f4b36848aecd" alt="Web Server Interface" width="550">
  <p><em>Subtitle Web Server Interface (Accessible on Local Network)</em></p>
</div>

<br>





## 🚀 Installation

### Option 1: Windows Installer (Recommended)

[<img src="https://raw.githubusercontent.com/vadret/android/master/assets/get-github.png" alt="Get it on GitHub" height="70">](https://github.com/anonfaded/QuranCLI/releases)

1.  Go to the **[Releases Page](https://github.com/anonfaded/QuranCLI/releases)**.
2.  Download the latest `QuranCLI-Setup.exe` file.
3.  Run the installer and follow the on-screen instructions.
4.  Launch QuranCLI from your Start Menu or Desktop shortcut!


### Option 2: From Source (Developers / Other Platforms)

*   **Prerequisites:** Python 3.9+ and pip.
*   **Clone:**
    ```bash
    git clone https://github.com/anonfaded/QuranCLI.git
    cd QuranCLI
    ```
*   **Install Dependencies:** (Using a virtual environment is recommended)
    ```bash
    # Optional: Create and activate venv
    # python -m venv venv
    # .\venv\Scripts\activate  (Windows) or source venv/bin/activate (Linux/macOS)

    pip install -r requirements.txt
    ```
*   **Run:**
    ```bash
    python Quran-CLI.py
    ```

---

## 🎮 Quick Start & Usage

1.  **Launch:** Start QuranCLI (via Installer or `python Quran-CLI.py`).
2.  **Select Surah:** Enter the Surah number (1-114) or type part of its name (e.g., `rahman`).
3.  **Select Ayahs:** Enter the starting and ending Ayah numbers.
4.  **Read:** View Arabic text and English translation. Use `n` / `p` to navigate pages.
5.  **Listen:** Type `a` to open the Audio Player. Use keys like `p` (play/pause), `s` (stop), `r` (change reciter), `[` / `]` (seek 5s), `j` / `k` (seek 30s). Press `q` to return.
6.  **Subtitles & Share:**
    *   Type `sub` in the main menu.
    *   Select Surah and the Ayah range you want subtitles for.
    *   The `.srt` file is saved in `Documents\QuranCLI Subtitles`.
    *   A **local web server starts automatically**. You'll see a URL like `http://<Your-IP>:8000`.
    *   Open this URL on **other devices on the same Wi-Fi** to browse and download the subtitle files for that Surah.
    *   Use the `open` command in the subtitle menu to view the folder on your PC, or `back` to return to the main menu (this also stops the server).
7.  **Help:** Type `info` in the main menu for detailed commands and credits.
8.  **Quit:** Type `quit` or `exit` in the main menu.

*(Note: Use the `reverse` command in the reader if Arabic text appears incorrectly displayed on your specific terminal.)*

---





## 🤝 Contributing & Feedback

 - Bugs & Feature Requests: Found an issue or have an idea? Please Open an Issue.

 - Pull Requests: Contributions are welcome!

## 🫱🏽‍🫲🏽 Credits

- Quran Data & Audio API: Provided by [The Quran Project](https://github.com/The-Quran-Project/Quran-API). An API for the Holy Quran with no rate limit.

- Application Icon: Holy icon created by Atif Arshad - Flaticon.

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.
