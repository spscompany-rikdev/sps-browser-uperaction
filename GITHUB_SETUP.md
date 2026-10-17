# Build SPS Browser automatically on GitHub (Windows + Linux + macOS)

You do NOT need to build anything on your own PC. GitHub does it for free (public repositories have free build time).

## One-time setup (about 10 minutes)
1. Create a free account at https://github.com and click **New repository**. Name it e.g. `sps-browser`, choose **Public**
   (Public = free build minutes + people can read the code, which helps trust). Do not add a README.
2. Upload this project: open the new repository, click **uploading an existing file**, drag the **contents** of the
   `sps_build_v36` folder in (the `.github` folder must end up at the top level of the repository - if your file manager hides
   it, use GitHub Desktop or `git`, see below), and click **Commit changes**.
   With git instead:
   ```
   cd sps_build_v36
   git init && git add . && git commit -m "SPS Browser"
   git branch -M main
   git remote add origin https://github.com/YOUR_NAME/sps-browser.git
   git push -u origin main
   ```
3. Open the **Actions** tab. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
4. Settings -> Actions -> General -> *Workflow permissions*: choose **Read and write permissions** -> Save.
5. (Recommended) Settings -> Secrets and variables -> Actions -> **New repository secret**
   Name `SPS_UPDATE_PRIVATE_KEY`, value = the one line inside your `update_private_key.txt` (made with `tools/make_update_keys.py`).
   With it, every release automatically produces the signed update block for your Google Sites page.
   Without it everything else still works.

## Every time you want new files
* **Quick test build:** Actions tab -> *Build SPS Browser* -> **Run workflow**. After ~15-25 minutes open the run and download
  the files at the bottom, under **Artifacts** (`windows`, `linux`, `macos`).
* **Real release:** change the version, then tag it:
  ```
  git tag v36.1.0
  git push origin v36.1.0
  ```
  (or GitHub -> Releases -> *Draft a new release* -> create tag `v36.1.0`). The workflow then
  1. runs all tests, 2. writes the version into the code and the installer, 3. builds on Windows, Linux and macOS,
  4. runs the program's self-test, 5. makes the Windows installer (Inno Setup, same AppId), 6. publishes a **Release**
  with all downloads + `SHA256SUMS.txt` + build provenance, 7. prints the **signed update block** in the run's *Summary* page.
* Paste that update block into your Google Sites **updates** page (plain text). Done - users get the update.

## What you get in the Release
| File | For |
|---|---|
| `SPS_Browser_Setup_vX.Y.Z.exe` | Windows installer (recommended; the browser's updater uses this one) |
| `SPS_Browser_Windows_x64_Portable_vX.Y.Z.zip` | Windows without installing |
| `SPS_Browser_Linux_x64_vX.Y.Z.tar.gz` | Linux (needs `libxcb-cursor0`; run `./SPS_Browser`) |
| `SPS_Browser_macOS_arm64_vX.Y.Z.zip` | Apple-silicon Macs. First start: right-click -> Open (the app is not Apple-notarised) |
| `SHA256SUMS.txt` | lets anyone check the files were not changed |

## Honest notes
* Windows is the tested target. Linux and macOS builds are produced and self-tested by the workflow but "best effort": if one
  fails, the Windows release is still made. Look at the red job's log and send it to me to fix.
* The Windows installer is **not code-signed** (see TRUSTED_PUBLISHER.md) - Windows will say "Unknown publisher".
* Anyone with write access to the repository can run the workflow. Keep the repository under your own account and protect it
  with two-factor login. The GitHub secret is encrypted and never printed in logs.
* Library versions are pinned in `requirements-build.txt`; Dependabot proposes updates monthly.
