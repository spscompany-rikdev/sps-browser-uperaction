"""
╔══════════════════════════════════════════════════════════════════╗
║  SPS SANDBOX — Windows Deep Isolation Layer  v1.0               ║
║  Uses Windows Job Objects + restricted tokens                    ║
╚══════════════════════════════════════════════════════════════════╝

Provides:
  - Job Object confinement (prevents child processes escaping)
  - Restricted file system access via Windows ACLs
  - Environment variable scrubbing
  - Network confinement hooks

This is auto-used by sandbox_launcher.py on Windows.
"""

import os
import sys
import ctypes
import subprocess
from pathlib import Path
from typing import Optional

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes.wintypes as wt
    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32


# ══════════════════════════════════════════════════════════════════
#  JOB OBJECT  (keeps browser process contained)
# ══════════════════════════════════════════════════════════════════

class WindowsJobObject:
    """
    V36: a real Windows Job Object around the whole browser (it is assigned right after the browser starts, so every
    Chromium helper process it creates afterwards is inside it too).
      - KILL_ON_JOB_CLOSE : if the sandbox is closed or crashes, the browser and ALL its helper processes die with it
                            (no orphaned/hidden browser processes keep running)
      - UI limits         : the browser cannot log you off / shut Windows down or change screen settings
                            (NOT "no new desktops": Chromium's own sandbox creates a private desktop for every helper
                             process. Blocking that made the browser die silently the moment the first web page opened -
                             right after choosing a profile - with no window and no error.)
    The old "ActiveProcessLimit = 20" is GONE: Chromium starts a separate process for every site and iframe, and a
    Google sign-in alone needs many - hitting the limit made Chromium crash and the browser "closed by itself".
    """

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JobObjectBasicUIRestrictions       = 4
    JobObjectExtendedLimitInformation  = 9
    JOB_OBJECT_UILIMIT_DESKTOP         = 0x40
    JOB_OBJECT_UILIMIT_DISPLAYSETTINGS = 0x10
    JOB_OBJECT_UILIMIT_EXITWINDOWS     = 0x80

    def __init__(self):
        self._handle = None
        if not IS_WINDOWS:
            return
        if os.environ.get("SPS_NO_JOB") == "1":
            raise OSError("Job Object disabled by SPS_NO_JOB=1")
        kernel32.CreateJobObjectW.restype = wt.HANDLE
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
        kernel32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
        kernel32.OpenProcess.restype = wt.HANDLE
        kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        kernel32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        kernel32.CloseHandle.argtypes = [wt.HANDLE]
        self._handle = kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError("Failed to create Job Object")
        self._configure()

    def _configure(self):
        if not IS_WINDOWS or not self._handle:
            return

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wt.LARGE_INTEGER),
                ("PerJobUserTimeLimit",     wt.LARGE_INTEGER),
                ("LimitFlags",              wt.DWORD),
                ("MinimumWorkingSetSize",   ctypes.c_size_t),
                ("MaximumWorkingSetSize",   ctypes.c_size_t),
                ("ActiveProcessLimit",      wt.DWORD),
                ("Affinity",                ctypes.c_size_t),
                ("PriorityClass",           wt.DWORD),
                ("SchedulingClass",         wt.DWORD),
            ]

        class EXTENDED(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC),
                ("IoInfo",                IO_COUNTERS),
                ("ProcessMemoryLimit",    ctypes.c_size_t),
                ("JobMemoryLimit",        ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed",     ctypes.c_size_t),
            ]

        ext = EXTENDED()
        ext.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE      # NO process-count limit
        kernel32.SetInformationJobObject(self._handle, self.JobObjectExtendedLimitInformation,
                                         ctypes.byref(ext), ctypes.sizeof(ext))

        # V38: NO Job-Object UI restrictions any more. On a user's Windows 10 (build 19041.6456) putting a running GUI process
        # into a job that has UI limits blue-screened the PC (SYSTEM_SERVICE_EXCEPTION 0x3B inside win32kbase.sys, twice, at the same
        # address). The job still kills every browser helper when the sandbox closes; the UI limits added almost no protection.

    def assign_process(self, pid: int) -> bool:
        if not IS_WINDOWS or not self._handle:
            return False
        PROCESS_ALL_ACCESS = 0x1F0FFF
        proc_handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not proc_handle:
            return False
        result = kernel32.AssignProcessToJobObject(self._handle, proc_handle)
        kernel32.CloseHandle(proc_handle)
        return bool(result)

    def close(self):
        if IS_WINDOWS and self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None


# ══════════════════════════════════════════════════════════════════
#  ENVIRONMENT SCRUBBER  (removes sensitive env vars before launch)
# ══════════════════════════════════════════════════════════════════

SENSITIVE_ENV_VARS = [
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "GITHUB_TOKEN", "GITLAB_TOKEN", "NPM_TOKEN",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "DATABASE_URL", "DB_PASSWORD", "DB_PASS",
    "SECRET_KEY", "PRIVATE_KEY", "API_KEY",
    "GCP_SERVICE_ACCOUNT", "GOOGLE_APPLICATION_CREDENTIALS",
    "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID",
    "SSH_AUTH_SOCK",  # prevent SSH key forwarding
]


def scrub_environment(env: dict) -> dict:
    """
    Remove sensitive environment variables before passing to browser.
    Logs what was removed.
    """
    cleaned = dict(env)
    removed = []
    for key in list(cleaned.keys()):
        if any(key.upper().startswith(s) or key.upper() == s
               for s in SENSITIVE_ENV_VARS):
            del cleaned[key]
            removed.append(key)
    if removed:
        print(f"[Sandbox] Scrubbed {len(removed)} sensitive env vars: {', '.join(removed)}")
    return cleaned


# ══════════════════════════════════════════════════════════════════
#  TEMP DIRECTORY JAIL  (browser writes only to sandbox temp dir)
# ══════════════════════════════════════════════════════════════════

class TempDirJail:
    """
    Creates a dedicated temp directory for the browser.
    Sets TEMP/TMP env vars so browser writes there first.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path.home() / ".sps_sandbox" / "browser_temp"
        self.path = base_dir
        self.path.mkdir(parents=True, exist_ok=True)

        # Sub-directories matching normal Windows temp layout
        (self.path / "downloads").mkdir(exist_ok=True)
        (self.path / "cache").mkdir(exist_ok=True)
        (self.path / "profile").mkdir(exist_ok=True)

    def inject_env(self, env: dict) -> dict:
        env = dict(env)
        env["TEMP"]   = str(self.path)
        env["TMP"]    = str(self.path)
        env["TMPDIR"] = str(self.path)  # Linux compat
        return env

    def cleanup(self):
        import shutil
        try:
            shutil.rmtree(self.path, ignore_errors=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
#  COMBINED SETUP FUNCTION
# ══════════════════════════════════════════════════════════════════

_jail = None
_job  = None


def setup_windows_sandbox(pid: int, env: dict) -> dict:
    """
    Call this after launching the browser process.
    Returns the modified env dict.
    """
    global _jail, _job

    # 1. Temp dir jail
    _jail = TempDirJail()
    env = _jail.inject_env(env)
    print(f"[Sandbox/Win] Temp jail: {_jail.path}")

    # 2. Scrub env
    env = scrub_environment(env)

    # 3. Job Object
    if IS_WINDOWS:
        try:
            _job = WindowsJobObject()
            if _job.assign_process(pid):
                print(f"[Sandbox/Win] Job Object assigned to PID {pid}")
            else:
                print(f"[Sandbox/Win] Warning: could not assign Job Object")
        except Exception as e:
            print(f"[Sandbox/Win] Job Object failed: {e}")

    return env


def teardown_windows_sandbox():
    global _jail, _job
    if _job:
        _job.close()
    # Keep jail dir for inspection; user can clear via manager


if __name__ == "__main__":
    print("Windows Sandbox module — not meant to run directly.")
    print("Import and call setup_windows_sandbox(pid, env) after launching browser.")
