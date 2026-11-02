"""SYSTEM-WIDE protection (whole computer) using the official, free WireGuard programs - no own driver, nothing hidden.

  Windows : WireGuard for Windows (https://www.wireguard.com/install/) - tunnel service installed with administrator approval
  Linux   : wg-quick (package 'wireguard-tools') through pkexec (asks for the password)
  macOS   : wg-quick (brew install wireguard-tools) through an administrator prompt

SPS only writes the config and asks the OS to start/stop the tunnel. It needs a WireGuard config from a server you have
(your own server, or a provider that gives you a WireGuard file).  UNTESTED on real Windows/macOS in this build - see README.
"""
import os, re, shutil, subprocess, sys

IS_WIN, IS_MAC = sys.platform.startswith("win"), sys.platform == "darwin"
TUNNEL = "spsvpn"


def _wireguard_exe():
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        p = os.path.join(base, "WireGuard", "wireguard.exe")
        if os.path.isfile(p):
            return p
    return None


def bundled_msi(base_dirs):
    """The official WireGuard MSI shipped next to the app (fetched at build time), or None."""
    for d in base_dirs:
        try:
            for n in sorted(os.listdir(d)):
                if n.lower().startswith("wireguard") and n.lower().endswith(".msi"):
                    return os.path.join(d, n)
        except OSError:
            pass
    return None


def verify_signature(path):
    """Windows only: the installer must be signed by WireGuard LLC and the signature must be valid."""
    ps = ("$s=Get-AuthenticodeSignature -LiteralPath '%s'; if($s.Status -eq 'Valid' -and $s.SignerCertificate.Subject -like '*WireGuard LLC*'){exit 0}else{exit 1}"
          % path.replace("'", "''"))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def install_wireguard(base_dirs):
    """Windows: install the bundled official WireGuard (asks for administrator approval). Returns a message."""
    if not IS_WIN:
        return "Linux: sudo apt install wireguard-tools   |   macOS: brew install wireguard-tools"
    msi = bundled_msi(base_dirs)
    if not msi:
        return "The WireGuard installer is not bundled in this build. Download it from https://www.wireguard.com/install/"
    if not verify_signature(msi):
        raise RuntimeError("The bundled WireGuard installer failed the signature check (WireGuard LLC). Not installing.")
    _run_win_elevated(["msiexec.exe", "/i", msi, "/qb"])
    return "WireGuard is being installed - approve the Windows prompt, wait a few seconds, then press 'Protect WHOLE computer'."


def available():
    """(ok, message)"""
    if IS_WIN:
        return (True, "") if _wireguard_exe() else (False, "Install the free 'WireGuard for Windows' from wireguard.com/install first.")
    if shutil.which("wg-quick"):
        return True, ""
    return False, "Install 'wireguard-tools' (provides wg-quick) first."


def conf_path(workdir):
    return os.path.join(workdir, TUNNEL + ".conf")           # the tunnel NAME comes from this file name


def write_conf(workdir, conf_text):
    if not re.match(r"^\s*\[Interface\]", conf_text, re.I):
        raise ValueError("not a WireGuard config")
    p = conf_path(workdir)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(conf_text)
    return p


def commands(action, path):
    """The exact OS command for 'up' or 'down' (separate so it can be unit-tested)."""
    if IS_WIN:
        exe = _wireguard_exe() or "wireguard.exe"
        return [exe, "/installtunnelservice", path] if action == "up" else [exe, "/uninstalltunnelservice", TUNNEL]
    wg = ["wg-quick", action, path]
    if IS_MAC:
        return wg
    return ["pkexec"] + wg


def _run_win_elevated(cmd):
    import ctypes
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", cmd[0], subprocess.list2cmdline(cmd[1:]), None, 0)
    if r <= 32:
        raise RuntimeError("Administrator approval was refused or failed (code %d)." % r)


def run(action, path):
    cmd = commands(action, path)
    if IS_WIN:
        _run_win_elevated(cmd)
        return
    if IS_MAC:
        script = 'do shell script "%s" with administrator privileges' % " ".join(c.replace('"', '') for c in cmd)
        cmd = ["osascript", "-e", script]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "failed").strip()[-300:])


def start(workdir, conf_text):
    ok, msg = available()
    if not ok:
        raise RuntimeError(msg)
    run("up", write_conf(workdir, conf_text))


def stop(workdir):
    run("down", conf_path(workdir))
    try:
        os.remove(conf_path(workdir))                         # the config holds a private key: do not leave it lying around
    except OSError:
        pass
