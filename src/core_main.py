"""
SPS_Browser_Core.exe  -  the real browser. Normally started BY SPS_Browser.exe (the sandbox).

   SPS_Browser_Core.exe --selftest     checks that every library was packed correctly
"""
import sys
import os
import multiprocessing

FROZEN = getattr(sys, "frozen", False)
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
EXE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else BASE


def _fatal(msg):
    try:
        log = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "SPS_Browser_error.txt")
        with open(log, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg[-1800:], "SPS Browser - startup error", 0x10)
    except Exception:
        pass


_CRASH_FILE = None


def _enable_crash_log():
    """Native crashes (access violation in Qt/Chromium...) leave no Python traceback. Write them to a file so a
    'browser vanished' problem can always be diagnosed:  %TEMP%\\SPS_Browser_native_crash.txt"""
    global _CRASH_FILE
    try:
        import faulthandler
        path = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "SPS_Browser_native_crash.txt")
        _CRASH_FILE = open(path, "a", buffering=1, encoding="utf-8")
        faulthandler.enable(_CRASH_FILE, all_threads=True)
    except Exception:
        pass


def _find_webengine_helper(root):
    """Where the QtWebEngineProcess helper lives differs per system (Windows: bin, Linux: libexec, macOS: framework)."""
    name = "QtWebEngineProcess.exe" if sys.platform == "win32" else "QtWebEngineProcess"
    for rel in (("bin", name), ("libexec", name),
                ("lib", "QtWebEngineCore.framework", "Helpers", "QtWebEngineProcess.app", "Contents", "MacOS", "QtWebEngineProcess")):
        p = os.path.join(root, *rel)
        if os.path.exists(p):
            return p
    return ""


def _qt_roots():
    """Folders that may hold the bundled Qt: Windows/Linux = next to the exe, macOS = inside the .app (Frameworks / Resources)."""
    cands = [os.path.join(BASE, "PyQt6", "Qt6"), os.path.join(EXE_DIR, "PyQt6", "Qt6"),
             os.path.join(EXE_DIR, "..", "Frameworks", "PyQt6", "Qt6"), os.path.join(EXE_DIR, "..", "Resources", "PyQt6", "Qt6")]
    seen, out = set(), []
    for p in cands:
        p = os.path.normpath(p)
        if p not in seen and os.path.isdir(p):
            seen.add(p); out.append(p)
    return out


def _find_qt_item(name, want_dir=False):
    """Find a Qt WebEngine resource anywhere inside the bundled Qt (the macOS framework layout differs from Windows)."""
    seen = set()
    for root in _qt_roots():
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):   # macOS frameworks use symlinks
            real = os.path.realpath(dirpath)
            if real in seen:
                dirnames[:] = []
                continue
            seen.add(real)
            if want_dir and name in dirnames:
                return os.path.join(dirpath, name)
            if not want_dir and name in filenames:
                return os.path.join(dirpath, name)
    return ""


def _setup_qt_paths():
    """Tell QtWebEngine where its helper process and resources are inside the bundle."""
    for root in (os.path.join(BASE, "PyQt6", "Qt6"), os.path.join(EXE_DIR, "PyQt6", "Qt6")):
        helper = _find_webengine_helper(root)
        if helper:
            os.environ["QTWEBENGINEPROCESS_PATH"] = helper
            if os.path.isdir(os.path.join(root, "bin")):
                os.environ["PATH"] = os.path.join(root, "bin") + os.pathsep + os.environ.get("PATH", "")
            res = os.path.join(root, "resources")
            if os.path.isdir(res):
                os.environ.setdefault("QTWEBENGINE_RESOURCES_PATH", res)
            loc = os.path.join(root, "translations", "qtwebengine_locales")
            if os.path.isdir(loc):
                os.environ.setdefault("QTWEBENGINE_LOCALES_PATH", loc)
            break
    if sys.platform == "darwin":                  # macOS: the files live inside QtWebEngineCore.framework/Resources
        pak = _find_qt_item("qtwebengine_resources.pak")
        if pak:
            os.environ.setdefault("QTWEBENGINE_RESOURCES_PATH", os.path.dirname(pak))
        loc = _find_qt_item("qtwebengine_locales", want_dir=True)
        if loc:
            os.environ.setdefault("QTWEBENGINE_LOCALES_PATH", loc)


def _selftest():
    lines, ok = [], True

    def check(name, fn, hard=True):
        nonlocal ok
        try:
            fn()
            lines.append(f"OK    {name}")
        except Exception as e:
            lines.append(f"{'FAIL' if hard else 'WARN'}  {name}: {type(e).__name__}: {e}")
            if hard:
                ok = False

    for mod in ("pickle", "multiprocessing", "json", "sqlite3", "ssl", "socket", "email", "csv",
                "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "PyQt6.QtNetwork",
                "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtPrintSupport",
                "psutil", "requests", "certifi", "http.server", "urllib.request"):
        check("import " + mod, lambda m=mod: __import__(m))
    check("QtWebEngineProcess helper present",
          lambda: (_ for _ in ()).throw(FileNotFoundError(os.environ.get("QTWEBENGINEPROCESS_PATH", "not found")))
          if not os.path.exists(os.environ.get("QTWEBENGINEPROCESS_PATH", "")) else None)
    def _res(name):
        for root in _qt_roots():
            for sub in ("resources", "bin", "."):
                if os.path.exists(os.path.join(root, sub, name)):
                    return
        if _find_qt_item(name):
            return
        raise FileNotFoundError(name + " not packed (web pages would not render)")
    for _n in ("qtwebengine_resources.pak", "icudtl.dat"):
        check("WebEngine file " + _n, lambda n=_n: _res(n))

    def _loc():
        for r in _qt_roots():
            if os.path.isdir(os.path.join(r, "translations", "qtwebengine_locales")):
                return
        if not _find_qt_item("qtwebengine_locales", want_dir=True):
            raise FileNotFoundError("qtwebengine_locales")
    check("WebEngine locales", _loc)
    check("import QtMultimedia (video player for .mp4)", lambda: (__import__("PyQt6.QtMultimedia"), __import__("PyQt6.QtMultimediaWidgets")), hard=False)
    check("import llama_cpp (local AI)", lambda: __import__("llama_cpp"), hard=False)
    check("import sps_filter_engine (ad blocker)", lambda: __import__("sps_filter_engine"))
    check("updater: Ed25519 signature check", lambda: (__import__("sps_ed25519").self_test() or (_ for _ in ()).throw(RuntimeError("self-test failed"))))
    check("import sps_updater", lambda: __import__("sps_updater"))
    check("import sps_pages (error pages)", lambda: __import__("sps_pages"))
    check("import browser module", lambda: __import__("sps_browser_app"), hard=False)
    if not ok:                                     # help diagnose a missing file from the log alone
        lines.append("")
        lines.append("DEBUG  BASE=%s  EXE_DIR=%s  platform=%s" % (BASE, EXE_DIR, sys.platform))
        for r in _qt_roots():
            hits = []
            for dp, dn, fn in os.walk(r, followlinks=True):
                hits += [os.path.join(dp, x) for x in fn + dn if "qtwebengine" in x.lower() or x.lower() == "icudtl.dat"]
                if len(hits) > 25:
                    break
            lines.append("DEBUG  Qt root %s -> %s" % (r, hits[:25]))
    lines.append("")
    lines.append("SELFTEST " + ("PASSED" if ok else "FAILED"))
    with open(os.path.join(EXE_DIR, "selftest_result.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        if BASE not in sys.path:
            sys.path.insert(0, BASE)
        _setup_qt_paths()
        _enable_crash_log()
        if "--selftest" in sys.argv:
            _selftest()
        import sps_browser_app
        sps_browser_app.sps_main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        _fatal("SPS Browser crashed while starting:\n\n" + traceback.format_exc())
        sys.exit(1)
