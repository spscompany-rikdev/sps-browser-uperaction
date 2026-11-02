# How to test the update system (step by step)

## What the key files are
* **Private key** = a text file `update_private_key.txt` with 64 letters/digits. SECRET. Keep it on your PC / USB stick, NOT in the project folder, NOT on GitHub.
* **Public key** = the matching 64 characters inside `src/sps_updater.py` (`UPDATE_PUBLIC_KEY_HEX`). Not secret; it ships inside the browser and is used to check that an update was really signed by you.

## Where to put the key (one time)
1. On GitHub: **Settings -> Secrets and variables -> Actions -> New repository secret**
   Name: `SPS_UPDATE_PRIVATE_KEY`   Value: the 64 characters from your private key file (open it with Notepad, copy the one line).
2. That is all. Every build now takes your key from the Secret and puts the matching PUBLIC key into the browser automatically
   (step "Use my update key" in `build.yml`), so the browser and the release signature always match.
   (If you want the same on your own PC: `python tools\use_my_key.py "C:\path\update_private_key.txt"`, then build.)

If the old key was ever uploaded to GitHub (a file in the repo, even deleted), make a NEW key first:
`python tools\make_update_keys.py "C:\somewhere-outside-the-project\update_private_key.txt"`, then use that new file for the Secret.

## Test run with two versions
1. Make release **A**: on GitHub **Releases -> Draft a new release**, tag `v38.0.0`, publish. Wait for the build (Actions) and install `SPS_Browser_Setup_v38.0.0.exe` from the release.
2. Make release **B**: tag `v38.1.0`. When the build is green, open that run -> **Summary**; at the bottom is the box
   "Update block". Copy the text between `SPS-UPDATE-BEGIN` and `SPS-UPDATE-END` (including both lines).
3. Open your Google Site page `https://sites.google.com/view/spsbrowserpro/updates`, paste the block as plain text, **Publish**.
4. Start the installed version A. Help -> About -> **Check for Updates** (or wait a few minutes). It downloads B, checks the
   SHA-256 and the signature, then shows the "Update now" window. Click it - the installer runs silently and the new browser opens.
5. Look in `update_log.txt` (browser data folder) if something does not work; it says what was checked.

Notes
* The release must be PUBLIC (the browser downloads the installer from the release address).
* Versions are compared numerically: the block's version must be higher than the installed one.
* Wrong key / changed file = the browser refuses the update and tells nobody to install it. That is the safety feature.
