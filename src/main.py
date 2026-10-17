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


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            if base not in sys.path:
                sys.path.insert(0, base)
        import sandbox_launcher
        sandbox_launcher.main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        _fatal("SPS Sandbox crashed while starting:\n\n" + traceback.format_exc())
        sys.exit(1)
