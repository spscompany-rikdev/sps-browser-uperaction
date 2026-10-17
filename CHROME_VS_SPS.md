# SPS Browser vs Google Chrome - honest gap list (V36)

**HAVE** = works like Chrome · **DIFFERENT** = works, but another way · **CANNOT** = needs something SPS does not have

## Everything day-to-day
| Area | Chrome | SPS Browser V36 |
|---|---|---|
| Tabs, groups, pinned, search tabs, reopen closed tab | yes | HAVE |
| Ctrl+1…9, Ctrl+PgUp/PgDn, Ctrl+N, Ctrl+Shift+W, F6, Alt+D, Alt+Home, F3/Ctrl+G, Shift+Esc | yes | HAVE (added in V36) |
| Ctrl+Shift+Del "Clear browsing data" with time range | yes | HAVE (added in V36) |
| Ctrl+Shift+B / O / D / J, F11 full screen, F12 | yes | HAVE (F11 is now real full screen) |
| Bookmarks, bookmark manager, import, reading list | yes | HAVE |
| Passwords: save, autofill, breach check, CSV import | yes | HAVE (local only, no Google sync) |
| Incognito / Guest / several profiles at once | yes | HAVE |
| Downloads bubble + manager, safe-download scan | yes | HAVE |
| Built-in PDF viewer, print, Save as PDF | yes | HAVE |
| Translate page | Google built in | DIFFERENT - uses translate.goog, falls back to Microsoft Translator |
| Google Lens / search by image | yes | DIFFERENT - opens Google Lens, falls back to image search |
| Task manager (Shift+Esc), DevTools, view source | yes | HAVE |
| Ad blocker, tracker blocking, HTTPS-only, phishing lists | partly (extensions) | HAVE - built in |
| Local video files (.mp4 .mkv .mov …) | in a tab | HAVE - built-in player window |
| YouTube / full-screen video | yes | HAVE (V35: GPU video decoding) |
| Local AI assistant (offline) | no | SPS only |
| What's New page, Support page | yes | HAVE (V36) |

## Things SPS cannot do (and why)
| Chrome feature | Why SPS cannot match it |
|---|---|
| Chrome Web Store extensions | needs Chrome's extension engine; QtWebEngine has no extension support. SPS has its own extension system. |
| Sync with a Google account (passwords, bookmarks across devices) | needs Google's private sync servers. SPS has local profile backup/restore. |
| Widevine DRM (Netflix/Prime in HD) | Widevine is licensed to Google and approved browsers only. |
| H.264/AAC inside web pages | the free web engine is built without these licensed codecs (YouTube works - it uses VP9/AV1). Local files use the built-in player. |
| Chrome Safe Browsing live API | SPS uses its own downloadable block lists instead. |
| Cast to TV, Chrome mobile apps | Google services. |
| Windows-wide trust ("verified publisher") | needs a certificate from a certificate authority - see TRUSTED_PUBLISHER.md. |

## Sandbox - what is real
* **Chromium process sandbox**: ON (renderers run with a restricted token, like Chrome).
* **Job Object** (V36): the browser and every helper process are in one Windows job - they all die with the sandbox, and the browser cannot log you off or change display settings. (The old 20-process limit that made Google sign-in crash the browser was removed.)
* **Permission prompts**: camera, mic, location, notifications, screen, files - always ask.
* **File monitor** (V36): alerts only when the browser creates a NEW program/script file (.exe .bat .ps1 …) outside its own folders. A file that already exists, or a file you saved on purpose, never raises an alert.
