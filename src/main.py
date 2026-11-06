"""
SPS_Browser.exe  -  the SANDBOX (this is the file users double-click).

It never shows web pages itself. It starts SPS_Browser_Core.exe (the real browser)
as a child process, watches it, asks the user for permissions, and starts the
browser again whenever the browser restarts itself - so the browser can NEVER run
outside the sandbox.
"""
import sys
import os
import multiprocessing


def _fatal(msg):
    """Windowed exes have no console - show errors in a message box and a log file."""
    try:
        log = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "SPS_Sandbox_error.txt")
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


def _trace(msg):
    """V40: one line per start-up stage in %TEMP%\\SPS_startup_log.txt (flushed at once). If the PC ever freezes while SPS Browser
    starts, the LAST line of this file after the restart shows how far it got."""
    try:
        import time as _t
        with open(os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "SPS_startup_log.txt"), "a", encoding="utf-8") as f:
            f.write("%s pid=%s %s\n" % (_t.strftime("%H:%M:%S"), os.getpid(), msg))
    except Exception:
        pass


def _drop_admin_rights():
    """A browser running as administrator breaks (Chromium refuses its sandbox). If this exe was started elevated
    (e.g. 'Run as administrator', or by an installer) and no arguments were given, start it again at normal level
    through explorer.exe - Explorer always starts programs without elevation - and quit."""
    try:
        if sys.platform != "win32" or len(sys.argv) > 1 or os.environ.get("SPS_KEEP_ELEVATED") == "1":
            return False
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return False
        import subprocess
        subprocess.Popen(["explorer.exe", sys.executable], close_fds=True)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _trace("sandbox: start (argv=%s)" % sys.argv[1:])
    if getattr(sys, "frozen", False) and _drop_admin_rights():
        _trace("sandbox: was elevated -> restarted through explorer, this copy quits")
        sys.exit(0)
    try:
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            if base not in sys.path:
                sys.path.insert(0, base)
        import sandbox_launcher
        _trace("sandbox: modules loaded, starting the window")
        sandbox_launcher.main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        _fatal("SPS Sandbox crashed while starting:\n\n" + traceback.format_exc())
        sys.exit(1)
