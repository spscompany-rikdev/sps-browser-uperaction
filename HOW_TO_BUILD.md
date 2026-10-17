# SPS Browser — How to Build (V33)

## Prerequisites
- Windows 10/11 (build machine)
- Python 3.11+ with pip
- PyQt6, PyQt6-WebEngine, requests, psutil
- PyInstaller: `pip install pyinstaller`
- UPX (optional, speeds up EXE): https://upx.github.io/
- Inno Setup 6 (for the installer): https://jrsoftware.org/isinfo.php

## Install dependencies
```
pip install PyQt6 PyQt6-WebEngine requests psutil pyinstaller
```

## Quick build
```
BUILD.bat
```
This runs PyInstaller, copies licence/logo files, runs the self-test, then (if Inno Setup is found) builds the installer.

## Manual build
```
pyinstaller SPS_Browser.spec
```

## V33 file layout
| File | What it is |
|---|---|
| `src/SPS_BROWSER.py` | Main browser (~18 500 lines). VERSION = 36.0.0 |
| `src/_v33_patch.py`, `src/_v34_patch.py` | V33/V34 feature patches — packed into the exe as data files and loaded at startup (the spec fails the build if they are missing) |
| `src/sps_filter_engine.py` | Ad-blocker / filter engine |
| `src/sps_pages.py` | HTML for error / cert / threat pages |
| `src/main.py` | Sandbox supervisor (SPS_Browser.exe) |
| `src/core_main.py` | Browser entry point (SPS_Browser_Core.exe) |

## V33 new features (35+ added this build)
1. **⭐ Bookmark Manager** — full window with search, folders, drag-drop, duplicate detection, open-all
2. **🕒 Recently Closed Tabs** — list and reopen from ✨V33 menu or `sps://recently-closed`
3. **👤 Guest Mode** — temporary private window, nothing saved
4. **🔍 Custom Search Engines** — add/edit/remove with `%s` URL and shortcut keyword
5. **📱 Install Site as App** — chromeless PWA-style window + Windows desktop shortcut
6. **🌙 Follow System Dark Mode** — polls Windows registry, switches theme automatically
7. **⌨️ Custom Keyboard Shortcuts** — remap any of 20 actions in Settings → Shortcuts
8. **🎵 Media Hub** — global play/pause/seek/speed/volume controls for any tab
9. **🔊 Read Aloud** — pyttsx3 or Windows SAPI text-to-speech for any page
10. **🔐 Password Breach Check** — HaveIBeenPwned k-anonymity API, no passwords leave device
11. **🔄 Check for Updates** — About page button + GitHub Releases API check
12. **🛡️ Privacy Guide** — 6-step wizard to review and lock down privacy settings
13. **🔐 Secure DNS (DoH)** — Cloudflare/Google/Quad9/AdGuard/Custom DoH provider
14. **🏠 Address Autofill** — save name/address/email/phone, manage from Settings
15. **👤 Profile Switcher** — profile button in toolbar, switch or create profiles instantly
16. **🌐 Set as Default Browser** — popup bar on first launch + menu item + Windows registry registration
17. **🔵 Background Mode** — keep running in tray after last window closes
18. **🚀 Run on Windows Startup** — writes Windows registry Run key
19. **🍪 Cookie Banner Dismiss** — auto-click Accept on GDPR banners (opt-in)
20. **🦕 Dino Game** — `sps://dino` offline runner game
21. **🆕 What's New** — styled page showing all V33 additions
22. **⬇ Download Bubble** — progress pill in the toolbar during active downloads
23. **📋 Paste & Go / Paste & Search** — context menu items + `sps://paste-go`
24. **🔗 Copy Link to Highlight** — `#:~:text=` fragment link for selected text
25. **📂 Open All in Bookmark Folder** — open a whole folder's bookmarks as tabs
26. **← Back History List** — right-click Back button shows navigation history
27. **⚠ Auto-translate Bar** — offer to translate pages in foreign languages
28. **⚠ Insecure Form Warning** — status bar warning when typing on HTTP pages
29. **📂 Auto-Open File Types** — configure which download extensions auto-open
30. **🔔 Notification Settings** — quiet UI mode, block-all option
31. **🔍 Per-Site Zoom List** — view and clear per-site zoom overrides
32. **🪟 Name Window** — set a custom title for any browser window
33. **📊 Import Passwords CSV** — Chrome/Firefox password CSV import
34. **🐛 Crash Reports** — view/clear the error log from Help menu
35. **📊 Usage Statistics** — opt-in anonymous stats dialog

## Running the tests
```
python tests/test_all.py
python tests/test_bridge.py
python tests/test_engine.py
python tests/test_integration.py
python tests/test_qt_flows.py
python tests/test_profiles.py
```
All six test suites pass in the Claude sandbox (no Windows, no PyQt6, no internet).

## What was NOT tested on real Windows
- Default browser registration (requires real Windows registry access)
- System dark mode polling (requires Windows registry)
- Run on startup (requires Windows registry)
- pyttsx3 read-aloud (requires audio device)
- Install as App desktop shortcut creation
- Download bubble real-time progress (requires live downloads)
- Auto-translate bar (heuristic, needs non-ASCII pages)

## V36 notes
* `src/SPS_BROWSER.py` (was SPS_BROWSER_PRO_V32.py) - the product is called **SPS Browser**, no "Pro".
* `src/_v36_patch.py` - What's New, Support page, Chrome shortcuts, Clear browsing data.
* `extras/support_form.txt` - paste your Google Form link here (one line). BUILD.bat copies it next to the exe so it can be changed without rebuilding.
* The uninstaller (installer/SPS_Browser_Setup.iss) removes the program, C:\SPS_Browser (all profiles), %LOCALAPPDATA%\SPS_Browser, the sandbox folder and the registry entries.
* Code signing: see TRUSTED_PUBLISHER.md.

## V36 updater
See `UPDATE_PAGE_FORMAT.md`. Before the first public build run `python tools/make_update_keys.py` (own key!) and keep
`update_private_key.txt` out of the build folder. All installers use the Inno AppId `{1F897549-179B-4C8C-9B8B-EC93AC62EAB3}`.

## Build on GitHub instead of your PC
See `GITHUB_SETUP.md` (`.github/workflows/build.yml`, `tools/ci_build.py`). The same script works locally:
`python tools/ci_build.py --version 36.1.0` (Windows, macOS or Linux).

## Libraries (complete list)
`requirements-build.txt` - PyQt6 6.11.0 (+ WebEngine), psutil, watchdog, requests, certifi, PyInstaller (all pinned).
`requirements-ai.txt` - llama-cpp-python 0.3.21 (ready-made CPU wheel from abetlen.github.io/llama-cpp-python/whl/cpu) + numpy, diskcache, Jinja2, typing-extensions.
`requirements-optional.txt` - pyttsx3 (Read aloud, Windows). `python tools/install_ai.py` installs the AI library and falls back
to the newest available wheel, or to "no local AI", instead of failing.
