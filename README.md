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
