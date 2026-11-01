# SPS Browser - source package

**Start here**
| I want to... | Read / run |
|---|---|
| build everything on GitHub (no PC needed) | `GITHUB_SETUP.md` |
| build on my own Windows PC | `HOW_TO_BUILD.md` then `BUILD.bat` |
| publish an update to users | `UPDATE_PAGE_FORMAT.md` |
| understand code signing / "Unknown publisher" | `TRUSTED_PUBLISHER.md` |
| compare with Chrome | `CHROME_VS_SPS.md` |

**Folders**
* `src/` - the program (`SPS_BROWSER.py` + patches, sandbox, updater)
* `installer/` - Inno Setup script (AppId `{1F897549-179B-4C8C-9B8B-EC93AC62EAB3}`)
* `tools/` - `ci_build.py` (build), `install_ai.py`, `make_update_keys.py`, `publish_update.py`
* `tests/` - run: `python -m unittest discover -s tests -p "test_*.py"`
* `.github/workflows/build.yml` - the automatic Windows/Linux/macOS build

**Libraries** (all pinned): `requirements-build.txt` (required), `requirements-ai.txt` (local AI, llama-cpp-python 0.3.21 CPU wheel),
`requirements-optional.txt` (text-to-speech). A test checks that nothing the code imports is missing from these lists.

**Never publish:** `update_private_key.txt` (your update-signing key) or any `.pfx` certificate.

## SPS VPN - what it is (and is not)
SPS VPN is a **VPN client**, not a VPN service like Proton VPN. It has **no servers of its own**.
- **Browser mode** (Connect / Auto): only SPS Browser's traffic goes through your WireGuard / SOCKS5 / HTTP server or Tor. Kill switch included.
- **Whole-computer mode** ("Protect WHOLE computer"): uses the free official WireGuard program (Windows: WireGuard for Windows; Linux/macOS: wg-quick) with administrator approval, so every app is protected. Needs a WireGuard config. Not yet tested on real Windows/macOS.
- Where to get a server: see `VPN_GUIDE.md`.

## SPS Shield (Chrome/Edge extension)
See `EXTENSION_PUBLISH_GUIDE.md`. Build: `python tools/build_extension.py`.

## Install everything to build
`python -m pip install -r requirements.txt` then `python tools/ci_build.py`.
