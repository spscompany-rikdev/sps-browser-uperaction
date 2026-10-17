# SPS Browser — User Guide

<!-- This file is read by SPS AI whenever you ask how to do something in SPS Browser (or mention "SPS" / "this browser"). -->
<!-- You can edit it: every line starting with "## " or "### " begins a new topic. Keep each topic short and exact. -->
<!-- {DATA} and {MODELS} are replaced automatically by the real folders on this PC. -->

SPS Browser is a private, local-first desktop web browser. The toolbar has Back, Forward, Reload, the search-engine button, the address bar, the 🤖 AI Hub and the ⋮ main menu. The left sidebar has Home, Bookmarks, History, Downloads, Passwords, Reading List, Notes, Extensions, Cookies, Privacy Shield, Screenshot, PDF, Lens, Translate, Reader, Dev Tools, Profiles and Settings. Settings sections: General, Privacy & Security, Ad & Tracker Blocking, Appearance, Search, Downloads, Passwords, Network & Proxy, Extensions, Shortcuts, Notifications, Performance, Languages, Advanced. Ctrl+K opens the command palette and F1 shows all shortcuts.

## How to open Settings and change any setting
Open ⋮ main menu → **Settings** (or sidebar ⚙️ **Settings**), pick the section on the left, find the setting and switch it ON or OFF. Changes are saved automatically. Some settings need a restart — SPS then asks "Close && Restart now" or "Later" ("Later" leaves a yellow **Restart to apply changes** button in the status bar). You can also tell SPS AI "turn on dark mode" or "turn off ad blocker" — it always asks you before changing anything.

## Search engine
Keywords: search engine, default search, google, duckduckgo, sps search, change search

You can switch the search engine in two ways:
- Click the **search-engine button** on the toolbar (left of the address bar) — it cycles SPS Search → Google → DuckDuckGo.
- Or go to ⚙️ **Settings → Search**.

Whenever the engine changes, SPS **refreshes your tabs automatically** (search-result pages are searched again with the new engine).

## Password manager, saving & auto-fill
Keywords: password, passwords, autofill, auto fill, auto-fill, save password, saved login, login, credentials

**Passwords** are saved and filled in by SPS:
- When you sign in on a site, SPS asks **Save / Not now / Never for this site**.
- Next time you open that site, your login is **filled in automatically** (if you have several accounts, a small list appears on the username field).
- Everything is **encrypted** on your computer (Windows DPAPI) and never leaves it. Private (incognito) tabs never save or fill.
- Manage them: sidebar 🔐 **Passwords**, ⋮ menu → **Password Manager**, or type `@passwords` in the address bar.
- Turn saving / filling on or off: ⚙️ **Settings → Passwords** (*Save passwords*, *Auto-fill forms*).

## Downloads
Keywords: download, downloads, download manager, download folder, download location, pause download, resume download

Press **Ctrl+J** (or sidebar 📥 **Downloads**) to open the Download Manager: live speed and time left, pause / resume / cancel / retry, search and filters. Change the save folder in ⚙️ **Settings → Downloads**. Risky files (like .exe) are scanned and you are asked before keeping them.

## Restart / auto-restart
Keywords: restart, reboot, relaunch, hang, hangs, freeze, frozen, lag, lagging, not responding, stuck, slow browser

SPS **restarts itself** if it stops responding (about 45 s) or is badly lagging / out of memory, and your tabs come back. You can also restart any time from ⋮ menu → **🔄 Restart Browser**. When you change a setting that needs a restart, SPS asks if it may **close and restart automatically**. Settings are in ⚙️ **Settings → Performance** (*Auto-restart when the browser hangs or lags*).

## Where SPS stores its files
Keywords: data folder, where are files, where is data, profile folder, storage location, c drive, folder, models folder, ai models

SPS creates what it needs automatically on every PC:
- Your data: `{DATA}`
- Shared AI models folder: `{MODELS}`
Each Windows user gets their own data folder. Put `.gguf` AI model files into the models folder.

## SPS AI assistant
Keywords: ai, assistant, sps ai, chatbot, local ai, ai sidebar, model, gguf

Click the **🤖 AI Hub** button on the toolbar → **Open Local AI Sidebar**. SPS AI runs on your computer, answers questions about the browser, and asks before it runs any tool. It needs a `.gguf` model in `{MODELS}` and the `llama-cpp-python` package.

## Keyboard shortcuts
Keywords: shortcut, shortcuts, hotkey, keyboard, key combination, cheatsheet

Press **F1** for the full cheat-sheet. Main ones: **Ctrl+T** new tab · **Ctrl+W** close tab · **Ctrl+Shift+T** reopen tab · **Ctrl+L** address bar · **Ctrl+F** find · **Ctrl+D** bookmark · **Ctrl+H** history · **Ctrl+J** downloads · **Ctrl+B** sidebar · **Ctrl+K** command palette · **Ctrl+Shift+N** private tab · **F11** focus mode · **F12** developer tools.

## Tabs
Keywords: tab, tabs, new tab, close tab, reopen tab, tab organizer, mute tab, pin tab

**Ctrl+T** new tab, **Ctrl+W** close, **Ctrl+Shift+T** reopen the last closed tab, **Ctrl+Tab** next tab, **Ctrl+M** mute a tab, **Ctrl+Shift+A** tab organizer. Inactive tabs can sleep to save memory (⚙️ Settings → Performance).

## Private (incognito) tabs
Keywords: incognito, private, private tab, private window, off the record

Press **Ctrl+Shift+N** (or ⋮ menu → **New Incognito Tab**). Private tabs keep no cookies, history, passwords or downloads list.

## Bookmarks
Keywords: bookmark, bookmarks, favorite, favourites, star

**Ctrl+D** bookmarks the current page. Open the list from sidebar ⭐ **Bookmarks**. Show or hide the bookmarks bar in ⚙️ Settings → General.

## History
Keywords: history, browsing history, recent pages, visited

Press **Ctrl+H** or use sidebar 🕒 **History**. Export it from ⋮ menu → **Export History**. Auto-delete after N days is in ⚙️ Settings.

## Privacy & tracking protection
Keywords: privacy, tracker, trackers, tracking, ad block, adblock, ads, fingerprint, cookies, privacy dashboard

SPS blocks ads, trackers, crypto-miners and fingerprinting by default. See what was blocked in ⋮ menu → **Privacy Dashboard**; tune everything in ⚙️ **Settings → Privacy & Security** and **Ad & Tracker Blocking**. Manage cookies in ⋮ → **Cookie Manager**.

## Website permissions
Keywords: permission, permissions, camera, microphone, location, notifications, allow, block site

Sites must **ask** before using camera, microphone, location, notifications and similar. Review or revoke saved choices at **sps://permissions** (⋮ menu → Security & Privacy → Site Permissions).

## Security dashboard, lockdown & emergency tools
Keywords: security, lockdown, emergency, malware, phishing, safe browsing, isolation

⋮ menu → **Security & Privacy**: Security Dashboard (sps://security), Content Policy (sps://policy), Site Permissions (sps://permissions), Emergency Controls (sps://emergency), Lockdown mode (sps://lockdown), Kill WebRTC, Force HTTPS, Wipe all browser data.

## Extensions & user scripts
Keywords: extension, extensions, add-on, addon, userscript, user script, plugin

Open sidebar 🧩 **Extensions** or **sps://extensions** to install, enable or disable extensions and user scripts (JS/CSS). Buttons can show in the toolbar.

## Profiles
Keywords: profile, profiles, switch profile, new profile, account

⋮ menu → **Manage Profiles** (or sidebar 👤 Profiles). Each profile has its own bookmarks, history, cookies and passwords. Profile Sync can copy selected data between profiles.

## Zoom
Keywords: zoom, bigger text, smaller text, magnify, text size, font size

**Ctrl +** zoom in, **Ctrl −** zoom out, **Ctrl 0** reset. Default zoom and font size are in ⚙️ Settings → Appearance.

## Find in page
Keywords: find, search in page, search page

Press **Ctrl+F**, type your word, and use the arrows to jump between matches. **Esc** closes the bar.

## Reader mode, translate, print, PDF
Keywords: reader, reader mode, translate, print, pdf, save page, screenshot, lens

⋮ menu has **Toggle Reader Mode**, **Translate Page**, **Print (Ctrl+P)**, **Export PDF**, **Screenshot** (Ctrl+Shift+S) and **SPS Lens**.

## Developer tools
Keywords: devtools, developer tools, inspect, view source, f12, console

**F12** opens Developer Tools, **Ctrl+U** shows page source, and right-click → **Inspect Element**.

## New tab page
Keywords: new tab page, start page, homepage, home page, speed dial, dashboard, background

Choose what appears on the New Tab page in ⚙️ **Settings → General** (search box, quick tools, recent tabs, bookmarks, history, workspaces) and the background via ⋮ → **✨ Features → New Tab Background**. Set a custom homepage in Settings.

## Workspaces & sessions
Keywords: workspace, workspaces, session, restore tabs, snapshot, tab groups

⋮ menu → **Workspaces** saves and reopens sets of tabs. **Save Session Snapshot / Restore Snapshot** are in the same menu. Turn on *Restore previous tabs* in ⚙️ Settings → General to reopen tabs at startup.

## Command palette
Keywords: command palette, commands, palette, quick actions

Press **Ctrl+K** (or Ctrl+Shift+P) and type what you want — settings, tools and pages can all be found there.

## Guided tour
Keywords: tour, guide, tutorial, walkthrough, first run, learn browser

⋮ menu → **🧭 Take the Tour**, or open **sps://tour**. It walks you through the main parts of the browser.

## Night shift, dark filter, focus mode
Keywords: night shift, dark, dark mode, blue light, focus mode, text only, dark filter, eye strain

⋮ menu → **✨ Features**: Night Shift (warm tint), **Dark Filter** (dark pages), **Text Only Mode**, **Focus Mode (F11)**. Dark theme is in ⚙️ Settings → Appearance.

## Task manager / memory
Keywords: task manager, memory, ram, cpu, performance, slow, tab memory

⋮ menu → **✨ Features → Tab Task Manager** (or **sps://tasks**) shows each tab and lets you reload or close it. Memory saving options are in ⚙️ Settings → Performance.

## Profile sync
Keywords: sync, profile sync, backup, export bookmarks, import bookmarks

⋮ menu → **More Features → Profile Sync Manager** (sps://sync). Import bookmarks from ⋮ → **Import Bookmarks**.

## Browser flags
Keywords: flags, experimental, gpu, hardware acceleration, quic

⋮ menu → **More Features → SPS Browser Flags** (sps://flags). Flags take effect after a **restart** — SPS will offer to restart for you.

## Customize toolbar
Keywords: toolbar, customize toolbar, buttons, hide button

⋮ menu → **More Features → Customize Toolbar** (sps://toolbar). It needs a restart — SPS will offer to restart for you.

## Clear cache & browsing data
Keywords: clear cache, clear data, delete cookies, clear history, wipe, erase

⋮ menu → **Clear Cache**, **Clear Site Data** (this site only) or Security & Privacy → **Wipe All Browser Data**. You can also turn on *Clear data on exit* in ⚙️ Settings → Privacy & Security.

## Clipboard history & emoji
Keywords: clipboard, copy history, emoji, color picker, colour picker

**Ctrl+Shift+V** clipboard history, **Ctrl+.** emoji picker, **Ctrl+Shift+C** colour picker.

## Notes & reading list
Keywords: notes, note, reading list, read later, scratchpad

Sidebar 📝 **Notes** (quick notes) and 📚 **Reading List** (save pages for later). Right-click a page → **Add to Reading List**.

## About SPS Browser
Keywords: about, version, what is sps, who made

SPS Browser — a private, local-first browser. See the version in ⋮ menu → **About**. It never contacts a server for updates; install a newer setup to update.

## SPS AI assistant — modes, models and tools
Keywords: sps ai, ai modes, chat mode, agent mode, think mode, special mode, models, gguf, sandbox, permissions

- Open it: 🤖 **AI Hub** on the toolbar → **Open Local AI Sidebar**.
- **💬 Chat** — everyday questions; can search the web and give links; no computer actions.
- **🤖 Agent** — does real work in a private sandbox: writes and runs code, makes files (they appear as download cards in the chat), researches. It asks before touching your real files.
- **🧠 Think** — deep reasoning; shows its full thinking, then the answer.
- **⚡ Special** — thinks first (DeepSeek-R1), then hands the work to the Agent (Qwen-Coder) and tries again until it works.
- Models are `.gguf` files in `{MODELS}`. Use the model menu next to the send button → **Open models folder**, copy a model in, then **Re-scan**.
- Everything that touches your computer shows a permission box first. Dangerous commands are always blocked.
- Things SPS AI can do for you (it asks first): change the search engine, turn settings on/off, open Settings / Downloads / Passwords and other pages, restart the browser.

# Settings reference (every setting: where it is and what it does)

### Restore previous tabs
Where: ⚙️ **Settings → General → Restore previous tabs**. Reopen last session tabs on startup.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Restore previous tabs** and switch it.

### Bookmarks bar
Where: ⚙️ **Settings → General → Bookmarks bar**. Show bookmarks below the toolbar.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Bookmarks bar** and switch it.

### Status bar
Where: ⚙️ **Settings → General → Status bar**. Show URL and security info at bottom.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Status bar** and switch it.

### Show tab count in title bar
Where: ⚙️ **Settings → General → Show tab count in title bar**. Display open tab number in window title.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Show tab count in title bar** and switch it.

### Tab preview on hover
Where: ⚙️ **Settings → General → Tab preview on hover**. Show page thumbnail when hovering over tabs.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Tab preview on hover** and switch it.

### Confirm before closing
Where: ⚙️ **Settings → General → Confirm before closing**. Ask before the browser exits.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Confirm before closing** and switch it.

### Enable tab groups
Where: ⚙️ **Settings → General → Enable tab groups**. Allow workspaces and tab groups to be saved.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Enable tab groups** and switch it. It needs a restart — SPS will offer to restart for you.

### New tab search box
Where: ⚙️ **Settings → General → New tab search box**. Show the search bar on the about:newtab dashboard.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab search box** and switch it.

### New tab quick tools
Where: ⚙️ **Settings → General → New tab quick tools**. Show browser tool shortcuts on the new tab page.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab quick tools** and switch it.

### New tab recent tabs
Where: ⚙️ **Settings → General → New tab recent tabs**. Show recently opened tabs on the start page.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab recent tabs** and switch it.

### New tab bookmarks
Where: ⚙️ **Settings → General → New tab bookmarks**. Show favorite sites on the start page.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab bookmarks** and switch it.

### New tab stats
Where: ⚙️ **Settings → General → New tab stats**. Show browser stats on the dashboard.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab stats** and switch it.

### New tab shortcuts
Where: ⚙️ **Settings → General → New tab shortcuts**. Show shortcut chips on the start page.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab shortcuts** and switch it.

### New tab history
Where: ⚙️ **Settings → General → New tab history**. Show recent browsing history on the start page.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab history** and switch it.

### New tab workspaces
Where: ⚙️ **Settings → General → New tab workspaces**. Show saved workspaces on the start page.
To turn it on or off: open ⋮ → **Settings** → **General**, find **New tab workspaces** and switch it.

### Smooth scrolling
Where: ⚙️ **Settings → General → Smooth scrolling**. Animated page scrolling.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Smooth scrolling** and switch it.

### Compact mode
Where: ⚙️ **Settings → General → Compact mode**. Reduce UI padding for more content.
To turn it on or off: open ⋮ → **Settings** → **General**, find **Compact mode** and switch it. It needs a restart — SPS will offer to restart for you.

### Send 'Do Not Track'
Where: ⚙️ **Settings → Privacy & Security → Send 'Do Not Track'**. Sends DNT:1 header to every website.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Send 'Do Not Track'** and switch it.

### Enhanced Tracking Protection
Where: ⚙️ **Settings → Privacy & Security → Enhanced Tracking Protection**. Block known trackers and spy pixels.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Enhanced Tracking Protection** and switch it. It protects you, so keep it on unless a site truly does not work.

### Fingerprint Protection
Where: ⚙️ **Settings → Privacy & Security → Fingerprint Protection**. Reduce browser fingerprint exposure to sites.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Fingerprint Protection** and switch it. It protects you, so keep it on unless a site truly does not work.

### Canvas Noise
Where: ⚙️ **Settings → Privacy & Security → Canvas Noise**. Add random noise to canvas reads to defeat canvas fingerprinting.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Canvas Noise** and switch it.

### WebGL Spoof
Where: ⚙️ **Settings → Privacy & Security → WebGL Spoof**. Report generic GPU info to prevent WebGL fingerprinting.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **WebGL Spoof** and switch it.

### Audio API Protection
Where: ⚙️ **Settings → Privacy & Security → Audio API Protection**. Block AudioContext-based fingerprinting.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Audio API Protection** and switch it.

### Font Enumeration Block
Where: ⚙️ **Settings → Privacy & Security → Font Enumeration Block**. Prevent sites from enumerating your installed fonts.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Font Enumeration Block** and switch it.

### Block Battery API
Where: ⚙️ **Settings → Privacy & Security → Block Battery API**. Return dummy battery info (1.0 always charging).
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block Battery API** and switch it.

### Block Geolocation
Where: ⚙️ **Settings → Privacy & Security → Block Geolocation**. Deny location access to all sites.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block Geolocation** and switch it.

### Spoof Timezone as UTC
Where: ⚙️ **Settings → Privacy & Security → Spoof Timezone as UTC**. Report UTC as the browser timezone to all sites.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Spoof Timezone as UTC** and switch it.

### Spoof Language
Where: ⚙️ **Settings → Privacy & Security → Spoof Language**. Report en-US as Accept-Language to all sites.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Spoof Language** and switch it.

### Block ETag tracking
Where: ⚙️ **Settings → Privacy & Security → Block ETag tracking**. Strip ETag and If-None-Match headers to prevent cache-based tracking.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block ETag tracking** and switch it.

### Strip Referrer Header
Where: ⚙️ **Settings → Privacy & Security → Strip Referrer Header**. Don't send Referer on cross-origin requests.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Strip Referrer Header** and switch it.

### Block third-party cookies
Where: ⚙️ **Settings → Privacy & Security → Block third-party cookies**. Prevent cross-site cookie tracking.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block third-party cookies** and switch it. It protects you, so keep it on unless a site truly does not work.

### Total Cookie Protection
Where: ⚙️ **Settings → Privacy & Security → Total Cookie Protection**. Isolate cookies to each individual website.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Total Cookie Protection** and switch it. It protects you, so keep it on unless a site truly does not work.

### Block social trackers
Where: ⚙️ **Settings → Privacy & Security → Block social trackers**. Block Facebook, Twitter, LinkedIn tracking pixels.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block social trackers** and switch it.

### Block insecure downloads
Where: ⚙️ **Settings → Privacy & Security → Block insecure downloads**. Prevent downloads from insecure HTTP sources on secure pages.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block insecure downloads** and switch it.

### Scan downloads before saving
Where: ⚙️ **Settings → Privacy & Security → Scan downloads before saving**. Download to a temporary area, scan the file, then ask before risky downloads are kept.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Scan downloads before saving** and switch it. It protects you, so keep it on unless a site truly does not work.

### Warn for executable downloads
Where: ⚙️ **Settings → Privacy & Security → Warn for executable downloads**. Ask before saving EXE, MSI, script, shortcut, and registry files.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Warn for executable downloads** and switch it. It protects you, so keep it on unless a site truly does not work.

### Block double-extension tricks
Where: ⚙️ **Settings → Privacy & Security → Block double-extension tricks**. Warn on names such as invoice.pdf.exe.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block double-extension tricks** and switch it.

### Quarantine blocked downloads
Where: ⚙️ **Settings → Privacy & Security → Quarantine blocked downloads**. Keep blocked risky downloads in a private SPS quarantine folder.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Quarantine blocked downloads** and switch it.

### Safe Browsing
Where: ⚙️ **Settings → Privacy & Security → Safe Browsing**. Warn before visiting potentially dangerous sites.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Safe Browsing** and switch it. It protects you, so keep it on unless a site truly does not work.

### HTTPS-Only Mode
Where: ⚙️ **Settings → Privacy & Security → HTTPS-Only Mode**. Automatically upgrade all connections to HTTPS.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **HTTPS-Only Mode** and switch it. It protects you, so keep it on unless a site truly does not work.

### JavaScript
Where: ⚙️ **Settings → Privacy & Security → JavaScript**. Enable JavaScript on web pages.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **JavaScript** and switch it. It protects you, so keep it on unless a site truly does not work.

### Allow JavaScript popups
Where: ⚙️ **Settings → Privacy & Security → Allow JavaScript popups**. Let sites open new windows via JavaScript.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Allow JavaScript popups** and switch it.

### Block popups
Where: ⚙️ **Settings → Privacy & Security → Block popups**. Prevent unsolicited popup windows from opening.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Block popups** and switch it. It protects you, so keep it on unless a site truly does not work.

### XSS Protection
Where: ⚙️ **Settings → Privacy & Security → XSS Protection**. Block reflected cross-site scripting attacks.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **XSS Protection** and switch it. It protects you, so keep it on unless a site truly does not work.

### Allow insecure content
Where: ⚙️ **Settings → Privacy & Security → Allow insecure content**. Load HTTP resources on HTTPS pages (not recommended).
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Allow insecure content** and switch it. It protects you, so keep it on unless a site truly does not work.

### Open links in background
Where: ⚙️ **Settings → Privacy & Security → Open links in background**. Open clicked links without switching tabs.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Open links in background** and switch it.

### Open bookmarks in background
Where: ⚙️ **Settings → Privacy & Security → Open bookmarks in background**. Keep focus on the current tab when opening bookmarks.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Open bookmarks in background** and switch it.

### Local Storage
Where: ⚙️ **Settings → Privacy & Security → Local Storage**. Allow websites to use local browser storage.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Local Storage** and switch it.

### Local → Remote access
Where: ⚙️ **Settings → Privacy & Security → Local → Remote access**. Allow local files to access remote URLs.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Local → Remote access** and switch it.

### Clear data on exit
Where: ⚙️ **Settings → Privacy & Security → Clear data on exit**. Delete cookies and cache when browser closes.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Clear data on exit** and switch it.

### Auto-save session
Where: ⚙️ **Settings → Privacy & Security → Auto-save session**. Save open tabs every 5 minutes for crash recovery.
To turn it on or off: open ⋮ → **Settings** → **Privacy & Security**, find **Auto-save session** and switch it. It needs a restart — SPS will offer to restart for you.

### Ad Blocker
Where: ⚙️ **Settings → Ad & Tracker Blocking → Ad Blocker**. Block advertisements across all websites.
To turn it on or off: open ⋮ → **Settings** → **Ad & Tracker Blocking**, find **Ad Blocker** and switch it. It protects you, so keep it on unless a site truly does not work.

### Block Cryptomining
Where: ⚙️ **Settings → Ad & Tracker Blocking → Block Cryptomining**. Prevent hidden cryptocurrency mining scripts.
To turn it on or off: open ⋮ → **Settings** → **Ad & Tracker Blocking**, find **Block Cryptomining** and switch it. It protects you, so keep it on unless a site truly does not work.

### Allow browser plugins
Where: ⚙️ **Settings → Ad & Tracker Blocking → Allow browser plugins**. Enable plugins such as the built-in PDF viewer.
To turn it on or off: open ⋮ → **Settings** → **Ad & Tracker Blocking**, find **Allow browser plugins** and switch it.

### Notify when content is blocked
Where: ⚙️ **Settings → Ad & Tracker Blocking → Notify when content is blocked**. Show status bar message when ads/trackers are blocked.
To turn it on or off: open ⋮ → **Settings** → **Ad & Tracker Blocking**, find **Notify when content is blocked** and switch it.

### Spell check
Where: ⚙️ **Settings → Appearance → Spell check**. Highlight misspelled words in text fields.
To turn it on or off: open ⋮ → **Settings** → **Appearance**, find **Spell check** and switch it. It needs a restart — SPS will offer to restart for you.

### Focus mode
Where: ⚙️ **Settings → Appearance → Focus mode**. Hide all UI chrome for distraction-free browsing.
To turn it on or off: open ⋮ → **Settings** → **Appearance**, find **Focus mode** and switch it.

### Instant answers
Where: ⚙️ **Settings → Search → Instant answers**. Show quick results in URL bar (calculator, conversions, time).
To turn it on or off: open ⋮ → **Settings** → **Search**, find **Instant answers** and switch it.

### Voice search
Where: ⚙️ **Settings → Search → Voice search**. Enable microphone/voice search button in toolbar.
To turn it on or off: open ⋮ → **Settings** → **Search**, find **Voice search** and switch it. It needs a restart — SPS will offer to restart for you.

### DNS prefetching
Where: ⚙️ **Settings → Search → DNS prefetching**. Pre-resolve DNS for links to speed up navigation.
To turn it on or off: open ⋮ → **Settings** → **Search**, find **DNS prefetching** and switch it.

### Preload hovered links
Where: ⚙️ **Settings → Search → Preload hovered links**. Prefetch pages when you hover over links (uses more data).
To turn it on or off: open ⋮ → **Settings** → **Search**, find **Preload hovered links** and switch it.

### Save passwords
Where: ⚙️ **Settings → Passwords → Save passwords**. Offer to save passwords when you log in.
To turn it on or off: open ⋮ → **Settings** → **Passwords**, find **Save passwords** and switch it.

### Auto-fill forms
Where: ⚙️ **Settings → Passwords → Auto-fill forms**. Automatically fill saved login credentials in forms.
To turn it on or off: open ⋮ → **Settings** → **Passwords**, find **Auto-fill forms** and switch it.

### Use custom proxy
Where: ⚙️ **Settings → Network & Proxy → Use custom proxy**. Route browser traffic through a proxy server.
To turn it on or off: open ⋮ → **Settings** → **Network & Proxy**, find **Use custom proxy** and switch it. It needs a restart — SPS will offer to restart for you.

### Prevent screen sleep
Where: ⚙️ **Settings → Network & Proxy → Prevent screen sleep**. Keep screen awake while the browser is running.
To turn it on or off: open ⋮ → **Settings** → **Network & Proxy**, find **Prevent screen sleep** and switch it. It needs a restart — SPS will offer to restart for you.

### Show extension buttons in toolbar
Where: ⚙️ **Settings → Extensions → Show extension buttons in toolbar**. Display a button for each enabled extension that has 'Show in toolbar' checked.
To turn it on or off: open ⋮ → **Settings** → **Extensions**, find **Show extension buttons in toolbar** and switch it. It needs a restart — SPS will offer to restart for you.

### Hardware acceleration
Where: ⚙️ **Settings → Performance → Hardware acceleration**. Use GPU for rendering (faster; disable if glitchy).
To turn it on or off: open ⋮ → **Settings** → **Performance**, find **Hardware acceleration** and switch it. It needs a restart — SPS will offer to restart for you.

### Auto-restart when the browser hangs
Where: ⚙️ **Settings → Performance → Auto-restart when the browser hangs**. Restart by itself (tabs restored) if the browser stops responding.
To turn it on or off: open ⋮ → **Settings** → **Performance**, find **Auto-restart when the browser hangs** and switch it.

### Auto-restart when the browser lags
Where: ⚙️ **Settings → Performance → Auto-restart when the browser lags**. Restart (after a 10-second countdown) if very slow or out of memory.
To turn it on or off: open ⋮ → **Settings** → **Performance**, find **Auto-restart when the browser lags** and switch it.

### Auto-reload crashed tabs
Where: ⚙️ **Settings → Performance → Auto-reload crashed tabs**. Reload a tab automatically if its page process crashes.
To turn it on or off: open ⋮ → **Settings** → **Performance**, find **Auto-reload crashed tabs** and switch it.

### Auto-play media
Where: ⚙️ **Settings → Performance → Auto-play media**. Allow pages to auto-play audio and video.
To turn it on or off: open ⋮ → **Settings** → **Performance**, find **Auto-play media** and switch it.

### Load images
Where: ⚙️ **Settings → Performance → Load images**. Display images on pages (disable to save data and speed up).
To turn it on or off: open ⋮ → **Settings** → **Performance**, find **Load images** and switch it.

### Auto-refresh active tab
Where: ⚙️ **Settings → Performance → Auto-refresh active tab**. Keep the current tab refreshed on a timer.
To turn it on or off: open ⋮ → **Settings** → **Performance**, find **Auto-refresh active tab** and switch it.

### Custom error pages
Where: ⚙️ **Settings → Advanced → Custom error pages**. Show friendly error pages instead of browser default.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Custom error pages** and switch it.

### Allow fullscreen
Where: ⚙️ **Settings → Advanced → Allow fullscreen**. Let websites request fullscreen mode.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Allow fullscreen** and switch it.

### Dark filter on pages
Where: ⚙️ **Settings → Advanced → Dark filter on pages**. Invert and shift colors for easier night reading.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Dark filter on pages** and switch it.

### Text-only mode on pages
Where: ⚙️ **Settings → Advanced → Text-only mode on pages**. Hide media for faster, distraction-free reading.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Text-only mode on pages** and switch it.

### Picture-in-Picture auto-detect
Where: ⚙️ **Settings → Advanced → Picture-in-Picture auto-detect**. Auto-activate PiP when switching tabs with video.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Picture-in-Picture auto-detect** and switch it.

### Mouse gesture navigation
Where: ⚙️ **Settings → Advanced → Mouse gesture navigation**. Right-click drag to go back/forward.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Mouse gesture navigation** and switch it.

### Nature background on new tab
Where: ⚙️ **Settings → Advanced → Nature background on new tab**. Beautiful nature scene on the home/new tab page.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Nature background on new tab** and switch it.

### Daily quote
Where: ⚙️ **Settings → Advanced → Daily quote**. Show an inspirational quote on the new tab.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Daily quote** and switch it.

### Quick To-Do on new tab
Where: ⚙️ **Settings → Advanced → Quick To-Do on new tab**. Mini to-do list on the new tab page.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Quick To-Do on new tab** and switch it.

### Double-click word highlight
Where: ⚙️ **Settings → Advanced → Double-click word highlight**. Highlight all occurrences of a double-clicked word.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Double-click word highlight** and switch it.

### Tab sleep (memory saver)
Where: ⚙️ **Settings → Advanced → Tab sleep (memory saver)**. Discard inactive tabs after N minutes.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Tab sleep (memory saver)** and switch it. It needs a restart — SPS will offer to restart for you.

### Night shift (blue light filter)
Where: ⚙️ **Settings → Advanced → Night shift (blue light filter)**. Orange tint to reduce eye strain at night.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Night shift (blue light filter)** and switch it.

### Always on top
Where: ⚙️ **Settings → Advanced → Always on top**. Keep browser window above all other windows.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Always on top** and switch it. It needs a restart — SPS will offer to restart for you.

### Compact toolbar
Where: ⚙️ **Settings → Advanced → Compact toolbar**. Smaller icons and toolbar for small screens.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Compact toolbar** and switch it. It needs a restart — SPS will offer to restart for you.

### Screenshot tool (Ctrl+Shift+S)
Where: ⚙️ **Settings → Advanced → Screenshot tool (Ctrl+Shift+S)**. Capture current tab as PNG.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Screenshot tool (Ctrl+Shift+S)** and switch it.

### Colour picker (Ctrl+Shift+C)
Where: ⚙️ **Settings → Advanced → Colour picker (Ctrl+Shift+C)**. Open system colour dialog and copy hex value.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Colour picker (Ctrl+Shift+C)** and switch it.

### Clipboard history
Where: ⚙️ **Settings → Advanced → Clipboard history**. Remember last 20 copied text items (Ctrl+Shift+V).
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Clipboard history** and switch it.

### Emoji picker (Ctrl+.)
Where: ⚙️ **Settings → Advanced → Emoji picker (Ctrl+.)**. Quick emoji panel accessible from keyboard.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Emoji picker (Ctrl+.)** and switch it.

### Tab task manager
Where: ⚙️ **Settings → Advanced → Tab task manager**. View per-tab state and reload/close from sps://tasks.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Tab task manager** and switch it.

### Shortcuts cheatsheet (F1)
Where: ⚙️ **Settings → Advanced → Shortcuts cheatsheet (F1)**. Show all keyboard shortcuts at a glance.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Shortcuts cheatsheet (F1)** and switch it.

### Suggest strong passwords
Where: ⚙️ **Settings → Advanced → Suggest strong passwords**. Offer a strong password when a new password field is detected.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Suggest strong passwords** and switch it.

### Show Tools Pack
Where: ⚙️ **Settings → Advanced → Show Tools Pack**. Show the 20+ extra browser tools in the main menu.
To turn it on or off: open ⋮ → **Settings** → **Advanced**, find **Show Tools Pack** and switch it. It needs a restart — SPS will offer to restart for you.
