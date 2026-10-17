# How updates work (SPS Browser)

## One-time setup (on your own PC)
1. `python tools/make_update_keys.py` - creates `update_private_key.txt` (SECRET, keep offline, back it up) and writes the
   matching public key into `src/sps_updater.py`. **The key that came in this package is only for testing - make your own
   before your first public release**, then rebuild.
2. Build the browser + installer (BUILD.bat, then Inno Setup on `installer/SPS_Browser_Setup.iss`).

## Releasing a new version
1. Raise `VERSION` in `src/SPS_BROWSER.py` and `#define APP_VERSION` in the .iss, rebuild, get `SPS_Browser_Setup_x.y.z.exe`.
2. Upload the installer to an **https** address (GitHub Releases is free).
3. `python tools/publish_update.py SPS_Browser_Setup_x.y.z.exe x.y.z https://.../SPS_Browser_Setup_x.y.z.exe --notes "What changed"`
   (add `--optional` if users may postpone; default is mandatory).
4. Paste the printed block as **plain text** into https://sites.google.com/view/spsbrowserpro/updates and publish the site.

```
SPS-UPDATE-BEGIN
version: 36.1.0
url: https://github.com/you/repo/releases/download/v36.1.0/SPS_Browser_Setup_36.1.0.exe
sha256: <64 hex>
size: <bytes>
mandatory: yes
signature: <128 hex>
notes: Security fixes
SPS-UPDATE-END
```
Old blocks may stay; the newest valid one wins. Do not edit a block by hand: any change breaks the signature (on purpose).

## What the browser does
* ~25 s after start and every 6 h it reads the page in the background (no window, no notice).
* It accepts a block only if: https URL, newer than the running version, size sane, **Ed25519 signature valid**.
* It downloads silently, checks size + **SHA-256**, and stores the file under `<install data>\updates`.
* On the next start (8 s after the window opens) it re-checks file + signature and shows the **Update** window.
  Mandatory updates cannot be closed or skipped.
* "Update now" runs the installer: `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /RELAUNCH`.
  The installer (same AppId `{1F897549-179B-4C8C-9B8B-EC93AC62EAB3}`) first uninstalls the old version keeping user data, installs the
  new one and starts it. Windows shows one administrator (UAC) prompt - it cannot be avoided for a program in Program Files.
  Unsigned installers show "Unknown publisher" there (see TRUSTED_PUBLISHER.md).
* Safety: a hacked web page cannot push a file (no private key = no valid signature); a swapped download is rejected (SHA-256);
  downgrades are refused (version must be newer). Log: `update_log.txt`. Disable for testing: env `SPS_DISABLE_UPDATER=1`.
