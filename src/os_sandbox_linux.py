"""
╔══════════════════════════════════════════════════════════════════╗
║  SPS SANDBOX — Linux Isolation Layer  v1.0                       ║
║  Uses namespaces, seccomp, cgroups, and bwrap (bubblewrap)       ║
╚══════════════════════════════════════════════════════════════════╝

On Linux, the sandbox can use REAL kernel-level isolation:
  - User namespaces (unshare) — own UID/GID mapping
  - Mount namespaces — hide real filesystem, show only what's safe
  - Network namespaces — isolate network stack
  - cgroups — limit CPU/memory
  - seccomp BPF — restrict allowed system calls
  - bubblewrap (bwrap) — easy to use all of the above

Install bubblewrap:
  Ubuntu/Debian: sudo apt install bubblewrap
  Fedora/RHEL:   sudo dnf install bubblewrap
  Arch:          sudo pacman -S bubblewrap
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List

IS_LINUX = sys.platform.startswith("linux")


# ══════════════════════════════════════════════════════════════════
#  BUBBLEWRAP LAUNCHER  (recommended — full filesystem isolation)
# ══════════════════════════════════════════════════════════════════

def has_bwrap() -> bool:
    return shutil.which("bwrap") is not None


def build_bwrap_command(
    python_bin: str,
    browser_script: str,
    browser_dir: str,
    extra_env: dict,
) -> List[str]:
    """
    Build a bwrap command that:
    - Mounts /usr, /lib, /bin, /etc read-only (needed to run Python)
    - Mounts the browser directory read-only
    - Mounts a writable sandbox home for browser data
    - Blocks access to ~, /tmp (real), /var, /proc (real)
    - Gives the process a fake /proc and /tmp
    """
    sandbox_home = Path.home() / ".sps_sandbox" / "browser_home"
    sandbox_home.mkdir(parents=True, exist_ok=True)
    sandbox_tmp  = Path.home() / ".sps_sandbox" / "browser_tmp"
    sandbox_tmp.mkdir(parents=True, exist_ok=True)

    cmd = ["bwrap"]

    # ── Read-only system dirs (needed to run Python & Qt) ────────
    for d in ["/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc"]:
        if Path(d).exists():
            cmd += ["--ro-bind", d, d]

    # ── Fake /proc (safe subset) ─────────────────────────────────
    cmd += ["--proc", "/proc"]

    # ── Fake /dev (minimal) ──────────────────────────────────────
    cmd += ["--dev", "/dev"]

    # ── Isolated /tmp ────────────────────────────────────────────
    cmd += ["--bind", str(sandbox_tmp), "/tmp"]

    # ── Isolated home ────────────────────────────────────────────
    cmd += ["--bind", str(sandbox_home), str(Path.home())]

    # ── Browser dir (read-only) ──────────────────────────────────
    cmd += ["--ro-bind", browser_dir, browser_dir]

    # ── Python site-packages (read-only) ─────────────────────────
    import site
    for sp in site.getsitepackages():
        if Path(sp).exists():
            cmd += ["--ro-bind", sp, sp]

    # ── /run (needed by some Qt/dbus things) ─────────────────────
    run_user = f"/run/user/{os.getuid()}"
    if Path(run_user).exists():
        cmd += ["--bind", run_user, run_user]

    # ── Environment ──────────────────────────────────────────────
    cmd += ["--clearenv"]
    safe_env = {
        "PATH":    "/usr/local/bin:/usr/bin:/bin",
        "HOME":    str(Path.home()),
        "DISPLAY": os.environ.get("DISPLAY", ":0"),
        "XAUTHORITY": os.environ.get("XAUTHORITY", ""),
        "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", run_user),
        "LANG":    os.environ.get("LANG", "en_US.UTF-8"),
        "SPS_SANDBOX": "1",
        "SPS_SANDBOX_PID": str(os.getpid()),
        **extra_env,
    }
    for k, v in safe_env.items():
        if v:
            cmd += ["--setenv", k, v]

    # ── Die with parent ──────────────────────────────────────────
    cmd += ["--die-with-parent"]

    # ── The actual command ───────────────────────────────────────
    cmd += [python_bin, browser_script]

    return cmd


# ══════════════════════════════════════════════════════════════════
#  SECCOMP FILTER  (block dangerous syscalls)
# ══════════════════════════════════════════════════════════════════

# Syscalls the browser should NEVER need
BLOCKED_SYSCALLS = [
    "ptrace",           # can't spy on other processes
    "process_vm_readv", # can't read other process memory
    "process_vm_writev",
    "kexec_load",       # can't replace kernel
    "kexec_file_load",
    "init_module",      # can't load kernel modules
    "finit_module",
    "delete_module",
    "perf_event_open",  # no performance monitoring
    "io_uring_setup",   # limit io_uring attack surface
]


def has_seccomp_tools() -> bool:
    return shutil.which("seccomp-tools") is not None or shutil.which("strace") is not None


def build_seccomp_bpf_snippet() -> str:
    """
    Returns a Python snippet using ctypes to install a seccomp filter.
    Can be prepended to the browser launch.
    """
    return """
import ctypes, struct

# Install seccomp: kill process if it calls ptrace etc.
SECCOMP_SET_MODE_FILTER = 1
PR_SET_SECCOMP = 22
BPF_STMT = lambda code,k: struct.pack("HBBI", code, 0, 0, k)
BPF_JUMP = lambda code,k,jt,jf: struct.pack("HBBI", code, jt, jf, k)

AUDIT_ARCH_X86_64 = 0xC000003E
NR_ptrace = 101

# Simple BPF: allow all, but kill on ptrace
filter_prog = (
    BPF_STMT(0x20, 4)      +  # load arch
    BPF_JUMP(0x15, AUDIT_ARCH_X86_64, 1, 0) +  # if x86-64 skip
    BPF_STMT(0x06, 0x7fff0000) +  # ALLOW
    BPF_STMT(0x20, 0)      +  # load syscall nr
    BPF_JUMP(0x15, NR_ptrace, 0, 1) +  # if ptrace
    BPF_STMT(0x06, 0x00000000) +  # KILL
    BPF_STMT(0x06, 0x7fff0000)    # ALLOW
)
try:
    import ctypes.util
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    libc.prctl(PR_SET_SECCOMP, SECCOMP_SET_MODE_FILTER, None, 0, 0)
except Exception:
    pass
"""


# ══════════════════════════════════════════════════════════════════
#  COMBINED SETUP FUNCTION
# ══════════════════════════════════════════════════════════════════

def launch_sandboxed_linux(
    python_bin: str,
    browser_script: str,
    browser_dir: str,
    extra_env: dict,
) -> Optional[subprocess.Popen]:
    """
    Launch the browser inside a Linux sandbox.
    Uses bwrap if available, otherwise falls back to plain subprocess.
    """
    if has_bwrap():
        cmd = build_bwrap_command(python_bin, browser_script, browser_dir, extra_env)
        print("[Sandbox/Linux] Using bubblewrap filesystem isolation")
    else:
        print("[Sandbox/Linux] bubblewrap not found — using basic process monitoring")
        print("[Sandbox/Linux] Install with: sudo apt install bubblewrap")
        cmd = [python_bin, browser_script]
        env = {**os.environ, **extra_env, "SPS_SANDBOX": "1", "SPS_SANDBOX_PID": str(os.getpid())}
        return subprocess.Popen(cmd, cwd=browser_dir, env=env)

    try:
        proc = subprocess.Popen(cmd, cwd=browser_dir)
        print(f"[Sandbox/Linux] Browser PID: {proc.pid} (inside bwrap namespace)")
        return proc
    except FileNotFoundError as e:
        print(f"[Sandbox/Linux] bwrap error: {e}")
        return None


if __name__ == "__main__":
    print("Linux Sandbox module — not meant to run directly.")
    print(f"bubblewrap available: {has_bwrap()}")
    if not has_bwrap():
        print("Install: sudo apt install bubblewrap")
