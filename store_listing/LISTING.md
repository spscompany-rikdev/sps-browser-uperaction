# Store listing text (copy & paste)

## Name
SPS Shield - Privacy, Reader & Area Print

## Short description (max 132 characters)
Block trackers, clean tracking links, print a selected area, reader view and dark mode. Free. No data collected.

## Detailed description
SPS Shield is a free privacy and productivity toolbox.

PRIVACY
- Blocks known third-party trackers and ad networks
- Removes tracking parts from links (utm_*, fbclid, gclid and more)
- Stops WebRTC from revealing your real IP address
- Blocks third-party cookies and link click-tracking pings
- Chrome's Safe Browsing protection always stays ON

TOOLS
- Print selected area: drag a box on the page and print only that part (Ctrl+Shift+P)
- Reader view: clean, easy-to-read text
- Dark mode: per-website, remembered
- Memory saver: puts unused tabs to sleep (optional)
- Pause on this site: one click if a site misbehaves

PRIVATE BY DESIGN
No accounts, no analytics, no servers. Everything runs on your computer. SPS Shield never sends your data anywhere.

## Category
Productivity  (or "Privacy & Security" on Edge)

## Single purpose (Chrome asks for this)
Protect browsing privacy (tracker/ad blocking, link cleaning) and provide page tools (reader view, dark mode, print selected area).

## Permission justifications
- declarativeNetRequest: blocks known tracker requests and removes tracking parameters from links.
- storage: saves your settings and the list of paused sites.
- scripting + activeTab: runs reader view, dark mode and area print only when you click them.
- host permissions (<all_urls>): dark mode and reader view must work on any site you choose; tracker rules apply on all sites.
- alarms + tabs: memory saver checks periodically and sleeps tabs you have not used.
- privacy: turns on WebRTC IP protection, third-party cookie blocking and disables link-click pings (only when you keep "Privacy hardening" on).
- No remote code is used. All code is inside the package.

## Privacy policy URL
Publish PRIVACY_POLICY.md with GitHub Pages or use its GitHub link, e.g. https://github.com/<you>/<repo>/blob/main/PRIVACY_POLICY.md

## Data-use form answers (Chrome)
Collects no user data: leave every box unchecked, then tick the three certifications (no selling, no unrelated use, no creditworthiness use).

## Screenshots
shot1_popup.png, shot2_reader.png, shot3_dark.png, shot4_settings.png  (1280x800)
Icon: extension/icons/128.png
