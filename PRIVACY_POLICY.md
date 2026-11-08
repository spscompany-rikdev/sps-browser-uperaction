# SPS Browser & SPS Shield - Privacy Policy

SPS Shield (the Chrome/Chromium extension), SPS Browser and SPS VPN do **not collect, store on a server, sell or share any personal data**.

- Settings (switches, paused sites, dark-mode sites) are kept only in your own browser (chrome.storage).
- SPS Shield makes no network requests of its own. It only blocks or edits requests your browser already makes.
- Area print takes a picture of the visible tab only when you press it; the picture stays on your computer and is only shown to you for printing.
- SPS VPN has no servers. Connections go to the WireGuard/SOCKS5/HTTP server or Tor network that **you** choose. The server you choose can see your traffic metadata - use only servers you trust.
- Permissions: declarativeNetRequest (block trackers), storage (settings), scripting + activeTab (tools you start), alarms + tabs (memory saver), privacy (WebRTC/cookie hardening).

Contact: use the support form linked in the app.

---

## SPS Browser: every network connection it can make

SPS Browser has **no accounts and no usage analytics**, and the project runs **no server that receives your data**. Besides the websites you open, the program can contact the services below. Each is used only for the purpose given.

| When | Service | What is sent | Can be switched off |
|---|---|---|---|
| You type in the address bar and "Search suggestions" is on | Your search engine's suggestion service (for example Google or DuckDuckGo) | The text you type | Yes - turn off "Search suggestions" in Settings |
| Ad / tracker / phishing blocking updates its lists | Public block-list hosts (uBlock Origin lists, URLhaus, Phishing Army, StevenBlack hosts) on GitHub / abuse.ch / similar | A normal download request (your IP address is visible to that host) | Turn off the blocker in Settings |
| Update check | The SPS update page (address in Settings → Updates) and GitHub Releases | A normal request; no personal data | Yes - turn off automatic updates in Settings |
| You press **Check now** in Password Checkup | `api.pwnedpasswords.com` (Have I Been Pwned) | Only the first 5 characters of the SHA-1 fingerprint of each password (never the password) | Only runs when you press the button |
| You open a site's tab | Website favicon service | The site's address, to get its small icon | Not needed for browsing |
| You use the AI hub, translate or search buttons | The service you choose (ChatGPT, Gemini, Claude, Meta AI, Perplexity, Grok, Google Translate, search engines) | What you type there, under that service's own privacy policy | Only when you open them |
| You choose to download an optional local AI model | The model host named in the download dialog | A normal download request | Only when you ask |

Everything else - passwords, history, bookmarks, notes, settings - stays on your computer. Passwords are stored encrypted; on Windows the key belongs to your Windows account.
