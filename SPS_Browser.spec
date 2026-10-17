# ═══════════════════════════════════════════════════════════════
#  SPS_Browser.spec  -  PyInstaller recipe (builds TWO exes in ONE folder)
#
#    dist/SPS_Browser/SPS_Browser.exe        <- the SANDBOX (users double-click this)
#    dist/SPS_Browser/SPS_Browser_Core.exe   <- the real browser (started by the sandbox)
#
#  Build with BUILD.bat   (or:  python -m PyInstaller SPS_Browser.spec --noconfirm --clean)
# ═══════════════════════════════════════════════════════════════
import os, sys, glob, shutil
sys.setrecursionlimit(sys.getrecursionlimit() * 5)     # big apps (Qt + numpy + llama) need this

HERE    = os.path.dirname(os.path.abspath(SPEC))
SRC     = os.path.join(HERE, "src")
GEN     = os.path.join(HERE, "_generated")
EXTRAS  = os.path.join(HERE, "extras")
IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"
# icon per system: .ico (Windows), .icns (macOS - made by the GitHub workflow from the png), none for Linux
ICON = os.path.join(HERE, "assets", "sps_browser.ico" if IS_WIN else ("sps_browser.icns" if IS_MAC else "none"))
if not os.path.isfile(ICON):
    ICON = None

# ── pick the browser file (any SPS_BROWSER*.py) and give it an importable name ──
cands = sorted(f for f in glob.glob(os.path.join(SRC, "SPS_BROWSER*.py")) if "sandbox" not in os.path.basename(f).lower())
if not cands:
    raise SystemExit("ERROR: no SPS_BROWSER*.py found in src/")
os.makedirs(GEN, exist_ok=True)
shutil.copyfile(cands[-1], os.path.join(GEN, "sps_browser_app.py"))
print("[spec] browser file:", cands[-1])

# ── Windows "Details" tab (version, company, product) for both exes ──
import re as _re
_vm = _re.search(r'^VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"', open(cands[-1], encoding="utf-8").read(), _re.M)
_vt = tuple(int(x) for x in _vm.groups()) + (0,) if _vm else (0, 0, 0, 0)
_vs = ".".join(str(x) for x in _vt)
def _version_file(name, desc):
    if not IS_WIN:                      # the "Details" tab only exists on Windows
        return None
    path = os.path.join(GEN, name + "_version.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={_vt}, prodvers={_vt}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'SPS Browser'),
      StringStruct('FileDescription', '{desc}'),
      StringStruct('FileVersion', '{_vs}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('LegalCopyright', 'Open source, GPL-3.0'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', 'SPS Browser'),
      StringStruct('ProductVersion', '{_vs}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")
    return path

SANDBOX_MODULES = ["sandbox_launcher", "sandbox_bridge", "network_monitor", "filesystem_watcher",
                   "sandbox_policy", "os_sandbox_windows"]

# IMPORTANT: do NOT exclude standard-library modules (pickle, email, csv, sqlite3 ...).
# multiprocessing / PyQt / requests need them - excluding "pickle" caused
# "ModuleNotFoundError: No module named 'pickle'".
EXCLUDES = ["tkinter", "pandas", "matplotlib", "scipy", "PIL"]      # numpy is NOT excluded: llama_cpp needs it

common_hidden = ["psutil", "requests", "PyQt6.sip", "pickle", "multiprocessing",
                 "ssl", "sqlite3", "json", "ctypes", "ctypes.wintypes", "http.server", "urllib.request", "email.mime.text"]

# certifi's CA list (HTTPS for requests) + watchdog's Windows file-watching backend
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
try:
    certifi_datas = collect_data_files("certifi")
except Exception:
    certifi_datas = []
try:
    watchdog_hidden = collect_submodules("watchdog")
except Exception:
    watchdog_hidden = ["watchdog", "watchdog.observers", "watchdog.events"]

# ── local AI: bundle llama-cpp-python (and its DLLs) if it is installed on THIS PC ──
from PyInstaller.utils.hooks import collect_all
llama_datas, llama_bins, llama_hidden = [], [], []
try:
    import llama_cpp
    llama_datas, llama_bins, llama_hidden = collect_all("llama_cpp")
    print("[spec] llama_cpp", getattr(llama_cpp, "__version__", "?"), "found -> bundling", len(llama_bins), "libraries/DLLs +", len(llama_datas), "data files")
except Exception as _e:
    print("[spec] WARNING: llama_cpp not importable (%s) -> building WITHOUT local AI" % _e)

# optional "Read aloud": pyttsx3 is only imported lazily from a patch file, so PyInstaller must be told about it
tts_hidden = []
try:
    import pyttsx3
    tts_hidden = ["pyttsx3", "pyttsx3.drivers", "pyttsx3.drivers.sapi5", "comtypes", "comtypes.client", "win32com.client", "pythoncom"] if IS_WIN \
        else ["pyttsx3", "pyttsx3.drivers"]
    print("[spec] pyttsx3 found -> bundling text-to-speech")
except Exception:
    print("[spec] pyttsx3 not installed -> 'Read aloud' will ask the user to install it")

# extra files that must sit next to the exe (guide + AI models folder)
extra_datas = []
if os.path.isdir(EXTRAS):
    for root, _d, files in os.walk(EXTRAS):
        for f in files:
            full = os.path.join(root, f)
            rel  = os.path.relpath(root, EXTRAS)
            extra_datas.append((full, "." if rel == "." else rel))

# V35: the V33/V34 feature patches are read from disk at start-up -> they MUST be inside the bundle
for _pf in ("_v33_patch.py", "_v34_patch.py", "_v36_patch.py"):
    _pp = os.path.join(SRC, _pf)
    if not os.path.isfile(_pp):
        raise SystemExit("ERROR: src/%s is missing - the browser would crash after choosing a profile" % _pf)
    extra_datas.append((_pp, "."))

# licence files must always be inside the build (GPL-3.0 requires the licence text to travel with the program)
for _f in ("LICENSE.txt", "SPS_BROWSER_NOTICE.txt", "THIRD_PARTY_NOTICES.txt"):
    if not os.path.isfile(os.path.join(EXTRAS, _f)):
        raise SystemExit("ERROR: extras/%s is missing - the licence files must be shipped" % _f)

# ── 1) SANDBOX exe ─────────────────────────────────────────────
a_sb = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=certifi_datas,
    hiddenimports=SANDBOX_MODULES + common_hidden + watchdog_hidden +
                  ["PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "PyQt6.QtNetwork"],
    hookspath=[], runtime_hooks=[], excludes=EXCLUDES, noarchive=False,
)
pyz_sb = PYZ(a_sb.pure)
exe_sb = EXE(pyz_sb, a_sb.scripts, [], exclude_binaries=True, name="SPS_Browser",
             debug=False, strip=False, upx=False, console=False, icon=ICON,
             version=_version_file("SPS_Browser", "SPS Browser"))

# ── 2) BROWSER exe ─────────────────────────────────────────────
a_core = Analysis(
    [os.path.join(SRC, "core_main.py")],
    pathex=[SRC, GEN],
    binaries=llama_bins,
    datas=extra_datas + llama_datas + certifi_datas,
    hiddenimports=["sps_browser_app", "sps_filter_engine", "sps_pages", "sps_updater", "sps_ed25519",
                   # modules that only the V33/V34 patch files import (PyInstaller cannot see inside data files)
                   "csv", "hashlib", "zipfile", "tempfile", "shutil", "subprocess", "importlib.util", "winreg"] + common_hidden + llama_hidden + tts_hidden +
                  (["numpy", "diskcache", "jinja2", "typing_extensions"] if llama_bins else []) +
                  ["PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "PyQt6.QtNetwork", "PyQt6.QtPrintSupport",
                   "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebChannel",
                   "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets"],
    hookspath=[], runtime_hooks=[], excludes=EXCLUDES, noarchive=False,
)
pyz_core = PYZ(a_core.pure)
exe_core = EXE(pyz_core, a_core.scripts, [], exclude_binaries=True, name="SPS_Browser_Core",
               debug=False, strip=False, upx=False, console=False, icon=ICON,
               version=_version_file("SPS_Browser_Core", "SPS Browser engine"))

# ── one shared folder (UPX is OFF: UPX corrupts Qt/Python DLLs -> "failed to load python dll") ──
coll = COLLECT(exe_sb,   a_sb.binaries,   a_sb.datas,
               exe_core, a_core.binaries, a_core.datas,
               strip=False, upx=False, name="SPS_Browser")

# ── macOS: wrap the folder into a double-clickable "SPS Browser.app" ──
if IS_MAC:
    app = BUNDLE(coll, name="SPS Browser.app", icon=ICON, bundle_identifier="com.spsbrowser.app",
                 info_plist={
                     "CFBundleName": "SPS Browser", "CFBundleDisplayName": "SPS Browser",
                     "CFBundleShortVersionString": _vs, "CFBundleVersion": _vs,
                     "NSHighResolutionCapable": True,
                     "NSCameraUsageDescription": "Websites you allow can use the camera.",
                     "NSMicrophoneUsageDescription": "Websites you allow can use the microphone.",
                     "NSLocationUsageDescription": "Websites you allow can use your location.",
                 })
