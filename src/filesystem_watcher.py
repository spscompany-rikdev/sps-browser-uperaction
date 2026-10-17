"""
╔══════════════════════════════════════════════════════════════════╗
║  SPS SANDBOX — Filesystem Watcher  v1.0                          ║
║  Monitors all file operations by the browser process             ║
╚══════════════════════════════════════════════════════════════════╝

Uses:
  - psutil open_files() polling (cross-platform, always works)
  - watchdog (optional, for real-time file events)
  - inotify on Linux (most precise)

Intercepts:
  - File reads from sensitive directories
  - File writes (any file the browser creates or modifies)
  - File deletions
  - Access to system files (/etc/passwd, registry hives, etc.)
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from typing import Callable, Dict, Optional, Set
from datetime import datetime


# Try to import optional watchers
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")

# ══════════════════════════════════════════════════════════════════
#  SENSITIVE PATH DEFINITIONS
# ══════════════════════════════════════════════════════════════════

# Paths that require READ permission
SENSITIVE_READ = []
if IS_WINDOWS:
    SENSITIVE_READ = [
        os.path.expanduser("~\\Documents"),
        os.path.expanduser("~\\Desktop"),
        os.path.expanduser("~\\Downloads"),
        os.path.expanduser("~\\Pictures"),
        os.path.expanduser("~\\Videos"),
        os.path.expanduser("~\\Music"),
        "C:\\Windows\\System32",
        "C:\\Windows\\SysWOW64",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\Users",
    ]
else:
    SENSITIVE_READ = [
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Pictures"),
        os.path.expanduser("~/Videos"),
        os.path.expanduser("~/Music"),
        "/etc",
        "/usr/local",
        "/var/log",
        "/home",
        "/root",
    ]

# Paths that require WRITE permission (everything the browser writes)
SENSITIVE_WRITE_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".sh", ".bash", ".zsh",
    ".py", ".rb", ".php", ".js", ".ts",
    ".dll", ".so", ".dylib",
    ".reg",                       # Windows registry
    ".lnk",                       # Windows shortcuts
    ".vbs", ".wsf", ".hta",       # Windows scripts
    ".scr",                       # Windows screensavers (often malware)
    ".crt", ".cer", ".pem", ".key",  # Certificates / keys
    ".jar",                       # Java archives
    ".dmg", ".pkg", ".deb", ".rpm",  # Installers
}

# Paths always safe — never ask about these
ALWAYS_SAFE_PREFIXES = [
    str(Path.home() / ".sps_sandbox"),
    str(Path.home() / ".cache"),
    str(Path.home() / ".config" / "sps"),
    "/proc",
    "/sys",
    "/dev",
]
if IS_WINDOWS:
    ALWAYS_SAFE_PREFIXES += [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "SPS"),
        os.path.join(os.environ.get("TEMP", ""), ""),
        os.path.join(os.environ.get("TMP", ""), ""),
    ]


# ══════════════════════════════════════════════════════════════════
#  FILE ACCESS LOG
# ══════════════════════════════════════════════════════════════════

class FileAccessLog:
    LOG_FILE = Path.home() / ".sps_sandbox" / "file_access.log"

    def __init__(self):
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._entries = []

    def record(self, path: str, access_type: str, decision: str):
        entry = {
            "time":        datetime.now().isoformat(timespec="seconds"),
            "path":        path,
            "access_type": access_type,
            "decision":    decision,
        }
        self._entries.append(entry)
        try:
            with open(self.LOG_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
        return entry

    def recent(self, n=100):
        return list(reversed(self._entries[-n:]))


# ══════════════════════════════════════════════════════════════════
#  PSUTIL-BASED FILE MONITOR  (polls open file handles)
# ══════════════════════════════════════════════════════════════════

class PsutilFileMonitor(threading.Thread):
    """
    Polls the browser process's open file handles.
    When a new sensitive file appears, calls permission_callback.

    permission_callback(path, access_type) → bool
    """

    def __init__(
        self,
        pid: int,
        permission_callback: Callable[[str, str], bool],
        browser_dir: str,
        poll_interval: float = 0.4,
        file_log: Optional[FileAccessLog] = None,
    ):
        super().__init__(daemon=True)
        self.pid                 = pid
        self.permission_callback = permission_callback
        self.browser_dir         = str(Path(browser_dir).resolve())
        self.poll_interval       = poll_interval
        self.file_log            = file_log or FileAccessLog()

        self._stop_event  = threading.Event()
        self._seen_paths: Set[str]    = set()
        self._allowed:    Set[str]    = set()
        self._denied:     Set[str]    = set()

    def stop(self):
        self._stop_event.set()

    def _is_always_safe(self, path: str) -> bool:
        # Browser's own directory — always safe
        try:
            if Path(path).is_relative_to(Path(self.browser_dir)):
                return True
        except Exception:
            pass
        # Sandbox own dir — always safe
        for prefix in ALWAYS_SAFE_PREFIXES:
            if prefix and path.startswith(prefix):
                return True
        # Python stdlib and site-packages — always safe
        import site
        for sp in site.getsitepackages() + [site.getusersitepackages()]:
            if sp and path.startswith(sp):
                return True
        stdlib = getattr(sys, "prefix", "")
        if stdlib and path.startswith(stdlib):
            return True
        return False

    def _needs_permission(self, path: str) -> Optional[str]:
        """Returns "file_read" / "file_write" when the user must be asked, None when it is fine.
        Only personal folders (Documents, Desktop, Pictures ...) and dangerous file types outside the
        browser's own folders count - see sandbox_policy.py."""
        try:
            from sandbox_policy import classify
            return classify(path, self.browser_dir)
        except Exception:
            return None

    def run(self):
        if not HAS_PSUTIL:
            print("[FileMonitor] psutil not available")
            return
        try:
            proc = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            return

        print(f"[FileMonitor] Watching file access for PID {self.pid}")

        while not self._stop_event.is_set():
            try:
                open_files = proc.open_files()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception:
                time.sleep(self.poll_interval)
                continue

            for f in open_files:
                path = str(f.path)
                if path in self._seen_paths:
                    continue
                self._seen_paths.add(path)

                perm_type = self._needs_permission(path)
                if perm_type is None:
                    continue

                # Already decided?
                if path in self._allowed:
                    self.file_log.record(path, perm_type, "allow [cached]")
                    continue
                if path in self._denied:
                    self.file_log.record(path, perm_type, "deny [cached]")
                    continue

                print(f"[FileMonitor] Sensitive access: {perm_type} → {path}")

                try:
                    allowed = self.permission_callback(path, perm_type)
                except Exception as e:
                    print(f"[FileMonitor] Callback error: {e}")
                    allowed = False

                decision = "allow" if allowed else "deny"
                self.file_log.record(path, perm_type, decision)

                if allowed:
                    self._allowed.add(path)
                    # Also allow the parent directory loosely
                    parent = str(Path(path).parent)
                    self._allowed.add(parent)
                else:
                    self._denied.add(path)

            time.sleep(self.poll_interval)

        print("[FileMonitor] Stopped")


# ══════════════════════════════════════════════════════════════════
#  WATCHDOG-BASED WRITE MONITOR  (real-time, uses OS hooks)
# ══════════════════════════════════════════════════════════════════

if HAS_WATCHDOG:
    class SandboxFileEventHandler(FileSystemEventHandler):
        """
        Handles real-time filesystem events in the watched dirs.
        Used to catch WRITES even if psutil misses them.
        """

        def __init__(
            self,
            permission_callback: Callable[[str, str], bool],
            file_log: FileAccessLog,
        ):
            super().__init__()
            self.permission_callback = permission_callback
            self.file_log            = file_log
            self._seen: Set[str]     = set()
            self._allowed: Set[str]  = set()

        def on_created(self, event):
            if event.is_directory:
                return
            self._handle(event.src_path, "file_write")

        def on_modified(self, event):
            if event.is_directory:
                return
            self._handle(event.src_path, "file_write")

        def _handle(self, path: str, perm_type: str):
            """LOG ONLY.  A watchdog event does not say WHICH program changed the file (Explorer, OneDrive, an editor,
            the antivirus ... all touch the Desktop), so asking "the browser wants to write <file>" here produced false
            alerts - even for files that already existed.  Questions are asked only by PsutilFileMonitor, which watches
            the browser's own process."""
            name = os.path.basename(path).lower()
            if name in ("desktop.ini", "thumbs.db", ".ds_store") or name.startswith("~$") or name.endswith((".tmp", ".crdownload")):
                return
            if path in self._seen:
                return
            self._seen.add(path)
            if len(self._seen) > 5000:
                self._seen.clear()
            self.file_log.record(path, perm_type, "logged (not attributed to the browser)")


class WatchdogFileMonitor:
    """
    Watches Downloads and Documents with watchdog for real-time write detection.
    Complements PsutilFileMonitor.
    """

    def __init__(
        self,
        permission_callback: Callable[[str, str], bool],
        file_log: Optional[FileAccessLog] = None,
    ):
        self.permission_callback = permission_callback
        self.file_log            = file_log or FileAccessLog()
        self._observers = []

    def start(self):
        if not HAS_WATCHDOG:
            print("[WatchdogMonitor] watchdog not installed (pip install watchdog)")
            return

        watch_dirs = []
        if IS_WINDOWS:
            watch_dirs = [
                os.path.expanduser("~\\Downloads"),
                os.path.expanduser("~\\Desktop"),
                os.path.expanduser("~\\Documents"),
            ]
        else:
            watch_dirs = [
                os.path.expanduser("~/Downloads"),
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
            ]

        handler = SandboxFileEventHandler(self.permission_callback, self.file_log)

        for d in watch_dirs:
            if not Path(d).exists():
                continue
            obs = Observer()
            obs.schedule(handler, d, recursive=True)
            obs.start()
            self._observers.append(obs)
            print(f"[WatchdogMonitor] Watching: {d}")

    def stop(self):
        for obs in self._observers:
            obs.stop()
            obs.join()
        self._observers.clear()


# ══════════════════════════════════════════════════════════════════
#  COMBINED FILE MONITOR  (uses both psutil + watchdog)
# ══════════════════════════════════════════════════════════════════

class CombinedFileMonitor:
    """
    Use this — it combines psutil polling + watchdog real-time events.
    Gives the best coverage.
    """

    def __init__(
        self,
        pid: int,
        permission_callback: Callable[[str, str], bool],
        browser_dir: str,
    ):
        self.file_log    = FileAccessLog()
        self.psutil_mon  = PsutilFileMonitor(
            pid, permission_callback, browser_dir, file_log=self.file_log
        )
        self.watchdog_mon = WatchdogFileMonitor(
            permission_callback, file_log=self.file_log
        ) if HAS_WATCHDOG else None

    def start(self):
        self.psutil_mon.start()
        if self.watchdog_mon:
            self.watchdog_mon.start()
        print("[CombinedFileMonitor] Started")

    def stop(self):
        self.psutil_mon.stop()
        if self.watchdog_mon:
            self.watchdog_mon.stop()
        print("[CombinedFileMonitor] Stopped")

    def get_log(self):
        return self.file_log.recent(100)


if __name__ == "__main__":
    print("Filesystem Watcher — standalone test")
    print(f"psutil available:   {HAS_PSUTIL}")
    print(f"watchdog available: {HAS_WATCHDOG}")
    if not HAS_WATCHDOG:
        print("  Install with: pip install watchdog")

    def fake_perm(path, access_type):
        print(f"  PERMISSION NEEDED: {access_type} → {path}")
        return True

    log = FileAccessLog()
    mon = PsutilFileMonitor(os.getpid(), fake_perm, os.getcwd(), file_log=log)
    mon.start()
    print("Watching this process for 3 seconds...")
    time.sleep(3)
    mon.stop()
    print("Recent file access log:", log.recent(5))
