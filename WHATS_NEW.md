# What's new in SPS Browser v40

## Desktop
* **Chrome-style tab bar** - the tabs now sit at the very top of the window, to the left of the minimise / maximise / close buttons. Tabs are round (pill shaped). Drag the empty space to move the window; double-click it to maximise.
* **Round address bar** - the search / address bar in the toolbar is now round.
* **Search suggestions everywhere** - both the toolbar address bar and the New Tab search box show real options while you type (what you typed, your bookmarks, your history, search suggestions). The suggestion card under the address bar is solid and sharp, rows light up under the mouse, and it closes when you move the window or switch to another program. The New Tab box can only read your history inside the browser's own page - websites cannot.
* **Site controls button (🎚️)** - next to the lock icon. For the website you are on, switch each permission on or off: camera, microphone, location, notifications, screen sharing, clipboard, pop-ups, sound, JavaScript, images and more. Everything starts as "Ask first" - a website can do nothing until you allow it. "Block all" and "Reset" are one click. Some device features (USB, Bluetooth, Serial, HID, MIDI, motion sensors) are not offered by the browser engine at all, so they are always blocked.
* **Menu (⋮) button animation** - when you open the menu, the three dots spin half a turn and turn into the SPS Browser logo; they turn back when the menu closes.
* **Menu (⋮) drops down properly** - it now hangs right under the button, slides and fades in, and a long menu scrolls (mouse wheel or scroll bar) inside its own box instead of jumping to the top of the screen. The sub-menus (More Features, Help & About, Files & Media) scroll and stay fully on the screen too, and so does every other long menu of the browser.
* **Safer saved passwords** -
  * When you log in on a website, a small **"Save password?" card drops down under the toolbar** (top right): Save / Not now / Never for this site. You can peek at the password with 👁 before saving. Private tabs never save or fill.
  * In the Password Manager there is now **🔒 Set password**. Press it, the browser sends a **6-digit code as a normal Windows notification**, you type the code, then choose your password. After that, the Password Manager and auto-fill stay closed until you enter it (once each time you start the browser). Five wrong tries make you wait 30 seconds.
  * **Forgot password?** (on the lock screen): the browser sends a new code as a notification; with the right code the lock is switched off and you can choose a new password. **Your saved passwords are not lost.**
  * Works on **Windows, macOS and Linux**: the code appears as that system's own notification (Windows toast, macOS Notification Centre, Linux desktop notification - on Linux the `notify-send` tool, part of libnotify, is used if the tray cannot show it). If notifications are off, no code is shown and nothing is unlocked.
  * On macOS/Linux the saved-password key is protected by file permissions (only your user can read it), which is weaker than Windows' own account protection - the new password lock adds a second door there too.
  * Codes work once, last 5 minutes, and allow 5 tries.
  * Please note: your saved passwords are always encrypted with a key tied to your Windows account. The lock is an extra door. Because the "forgot" code arrives on the same computer, it keeps out people who are not at your computer, but not someone sitting at it while you are logged in - lock your Windows (Win + L) when you leave.
* **Password Checkup (🛡️)** - menu ⋮ → "Password Checkup…" or the 🛡️ Checkup button in the Password Manager. Press **Check now**: it finds saved passwords that are **leaked** in known data breaches, **reused** on several sites, or **weak**, and a "Change…" button opens the site. Nothing is checked until you press the button. For the leak check only the first 5 characters of a scrambled fingerprint of each password are sent to the Have I Been Pwned service - never the password. Without internet, reused and weak passwords are still checked.
* **Chrome extensions** - installed extensions show with their real logo in the toolbar. Several can be installed one after another.
* **Easy-access video panel** - roomy window with compact buttons: play / pause, previous / next, ±10 s, volume, all speeds (0.5× - 2×), Loop, PiP and Full screen are all visible at once, nothing is cut off, even on YouTube with long titles.
* **No more error box on exit**, no more mouse-flicker restart loop, and "Restart now" after removing an extension always works.
* A tab that crashed and is reloaded automatically can no longer take the whole browser down if you close it at the same moment.

## Also in this release
* Google sign-in window, safer updater, guest mode fix, lighter monitors (see `README.md`).

## Not in this release yet
* Android: installing several add-ons / user scripts one after another, and a final check of the Android easy panel.

## Honest notes
* All of this was tested automatically on Linux. It has not been tested on every Windows PC yet - if the tab bar misbehaves on yours, start the browser with the setting `SPS_NATIVE_FRAME=1` to get the normal window frame back, and tell us.
