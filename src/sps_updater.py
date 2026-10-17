"""
SPS Browser updater  -  secure, silent download; forced install on next start.

How it works (no UI code in this file - the browser window shows the dialogs):

  1. In the background the browser reads the owner's update page (plain text on a Google Site) and looks for
         SPS-UPDATE-BEGIN  ...  SPS-UPDATE-END
     (format: UPDATE_PAGE_FORMAT.md).
  2. The announcement carries an Ed25519 SIGNATURE made with the owner's private key.  It is checked with the public
     key built into the browser, so nobody who merely edits the web page (or hijacks the Google account) can push a
     file to users.  The announcement also carries the SHA-256 of the installer.
  3. A newer, correctly signed version is downloaded silently (HTTPS only, size-capped) into the browser's data folder,
     verified against its SHA-256, and recorded in  updates/staged.json.
  4. The next time the browser starts it re-verifies file + signature and, if everything is still valid, asks the user to
     update (the window cannot be dismissed when the update is mandatory).
  5. "Update now" runs the installer silently:  Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /RELAUNCH
     The installer removes the old version first (user data is kept) and starts the new browser again.

Nothing here is ever executed unless the SHA-256 AND the signature are valid.
"""
import hashlib
import hmac
import html
import json
import os
import re
import sys
import threading
import time

import sps_ed25519

# ───────────────────────────── configuration ─────────────────────────────
SPS_UPDATE_PAGE = "https://sites.google.com/view/spsbrowserpro/updates"

# Public half of the owner's update-signing key (64 hex characters).  The matching private key is NEVER shipped.
# tools/make_update_keys.py writes a fresh pair and puts the public half here.
UPDATE_PUBLIC_KEY_HEX = "3ccd8bb3a32d1718c9023bb213dfa4a724d205cab27ed23bc21084e7e56d7a9f"

CHECK_INTERVAL_SECONDS = 6 * 3600       # how often a running browser looks for news
FIRST_CHECK_DELAY_SECONDS = 25          # wait a little after start-up so the browser stays fast
MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_INSTALLER_BYTES = 1500 * 1024 * 1024
LOCK_STALE_SECONDS = 45 * 60
USER_AGENT = "SPS-Browser-Updater/1"
SILENT_ARGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS", "/RELAUNCH"]

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX128 = re.compile(r"^[0-9a-fA-F]{128}$")


# ───────────────────────────── small helpers ─────────────────────────────
def parse_version(text):
    """'36.1.0' -> (36, 1, 0).  Returns None when the text is not a plain dotted version number."""
    m = re.fullmatch(r"\s*v?(\d{1,4}(?:\.\d{1,4}){1,3})\s*", str(text or ""))
    if not m:
        return None
    parts = tuple(int(p) for p in m.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def is_newer(candidate, current):
    a, b = parse_version(candidate), parse_version(current)
    return a is not None and b is not None and a > b


def canonical_message(info):
    """The exact bytes the owner signs. Changing ANY of these fields invalidates the signature."""
    return ("SPS-UPDATE-V1\n"
            f"version={info['version']}\n"
            f"url={info['url']}\n"
            f"sha256={info['sha256'].lower()}\n"
            f"size={int(info['size'])}\n"
            f"mandatory={'yes' if info['mandatory'] else 'no'}\n").encode("utf-8")


def verify_signature(info, public_key_hex=None):
    key = (public_key_hex or UPDATE_PUBLIC_KEY_HEX).strip()
    if not _HEX64.match(key) or set(key) == {"0"}:
        return False                              # no key configured -> nothing is ever accepted
    sig = str(info.get("signature", "")).strip()
    if not _HEX128.match(sig):
        return False
    return sps_ed25519.verify(bytes.fromhex(key), canonical_message(info), bytes.fromhex(sig))


def https_only(url):
    return bool(re.match(r"^https://[A-Za-z0-9.\-]+(:\d+)?(/|$)", str(url or "")))


# ───────────────────────────── reading the update page ─────────────────────────────
def page_to_text(raw):
    """Google Sites sends the page as HTML plus JSON-escaped copies of the text. Turn it into plain lines."""
    t = raw or ""
    t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)
    t = t.replace("\\n", "\n").replace("\\r", "\n").replace("\\/", "/").replace('\\"', '"')
    t = html.unescape(html.unescape(t))
    t = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", lambda m: m.group(0) if "SPS-UPDATE" in m.group(0) else " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace(" ", " ").replace("​", "")
    return t


_FIELD = {
    "version":   r"version\s*[:=]\s*v?(\d{1,4}(?:\.\d{1,4}){1,3})",
    "url":       r"url\s*[:=]\s*(https://[^\s\"'<>\\]+)",
    "sha256":    r"sha-?256\s*[:=]\s*([0-9a-fA-F]{64})\b",
    "size":      r"size\s*[:=]\s*(\d{4,10})\b",
    "signature": r"signature\s*[:=]\s*([0-9a-fA-F]{128})\b",
    "mandatory": r"mandatory\s*[:=]\s*(yes|no|true|false)\b",
}


def parse_blocks(page_text):
    """All SPS-UPDATE blocks found on the page, as dicts (not yet trusted!)."""
    text = page_to_text(page_text)
    out = []
    for m in re.finditer(r"SPS-UPDATE-BEGIN(.*?)SPS-UPDATE-END", text, re.S | re.I):
        body = m.group(1)
        info = {}
        for key, rx in _FIELD.items():
            f = re.search(rx, body, re.I)
            if f:
                info[key] = f.group(1).strip().rstrip(".,;)")
        if not all(k in info for k in ("version", "url", "sha256", "size", "signature")):
            continue
        info["mandatory"] = info.get("mandatory", "yes").lower() in ("yes", "true")      # default: force the update
        info["size"] = int(info["size"])
        n = re.search(r"notes\s*[:=]\s*(.+)", body, re.I | re.S)
        info["notes"] = re.sub(r"[ \t]+", " ", n.group(1)).strip()[:1500] if n else ""
        out.append(info)
    return out


def best_valid_update(page_text, current_version, public_key_hex=None):
    """The newest announcement that is signed correctly and is newer than the running browser (or None)."""
    best = None
    for info in parse_blocks(page_text):
        if not (https_only(info["url"]) and _HEX64.match(info["sha256"]) and 0 < info["size"] <= MAX_INSTALLER_BYTES):
            continue
        if not is_newer(info["version"], current_version):
            continue
        if not verify_signature(info, public_key_hex):
            continue
        if best is None or parse_version(info["version"]) > parse_version(best["version"]):
            best = info
    return best


# ───────────────────────────── network ─────────────────────────────
def _session():
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def fetch_page(url=SPS_UPDATE_PAGE, timeout=20):
    if not https_only(url):
        raise ValueError("the update page must be an https address")
    with _session().get(url, timeout=timeout, stream=True) as r:
        r.raise_for_status()
        data = bytearray()
        for chunk in r.iter_content(65536):
            data += chunk
            if len(data) > MAX_PAGE_BYTES:
                raise ValueError("update page is too large")
        return bytes(data).decode("utf-8", "replace")


def download_verified(info, dest_path, progress=None, timeout=30):
    """Download info['url'] to dest_path. The file only appears under its final name when size AND SHA-256 match."""
    if not https_only(info["url"]):
        raise ValueError("the installer address must be https")
    part = dest_path + ".part"
    sha = hashlib.sha256()
    total = 0
    try:
        with _session().get(info["url"], timeout=timeout, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            for hop in list(r.history) + [r]:
                if not https_only(hop.url):
                    raise ValueError("a redirect left https")
            with open(part, "wb") as f:
                for chunk in r.iter_content(256 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > info["size"]:
                        raise ValueError("the file is larger than announced")
                    sha.update(chunk)
                    f.write(chunk)
                    if progress:
                        progress(total, info["size"])
        if total != info["size"]:
            raise ValueError("the file size does not match the announcement")
        if not hmac.compare_digest(sha.hexdigest(), info["sha256"].lower()):
            raise ValueError("SHA-256 does not match - the download is discarded")
        os.replace(part, dest_path)
    finally:
        try:
            if os.path.exists(part):
                os.remove(part)
        except OSError:
            pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ───────────────────────────── the updater ─────────────────────────────
class SpsUpdater:
    def __init__(self, current_version, data_dir, page_url=SPS_UPDATE_PAGE, public_key_hex=None, log=None):
        self.current = current_version
        self.dir = os.path.join(data_dir, "updates")
        self.page_url = page_url
        self.key = public_key_hex
        self._log = log or (lambda msg: None)
        self._thread = None
        self._stop = threading.Event()
        os.makedirs(self.dir, exist_ok=True)

    # ---- paths ----
    @property
    def _state_path(self):
        return os.path.join(self.dir, "staged.json")

    @property
    def _lock_path(self):
        return os.path.join(self.dir, "download.lock")

    def _installer_path(self, version):
        return os.path.join(self.dir, f"SPS_Browser_Setup_{version}.exe")

    # ---- cross-process lock (several browser windows must not download the same file) ----
    def _take_lock(self):
        try:
            if os.path.exists(self._lock_path) and time.time() - os.path.getmtime(self._lock_path) > LOCK_STALE_SECONDS:
                os.remove(self._lock_path)
            fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except OSError:
            return False

    def _release_lock(self):
        try:
            os.remove(self._lock_path)
        except OSError:
            pass

    # ---- staged update ----
    def staged_update(self):
        """The downloaded update, re-verified RIGHT NOW (file hash, signature, newer than the running version) - or None."""
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            path = self._installer_path(info["version"])
            if not (is_newer(info["version"], self.current) and https_only(info["url"]) and os.path.isfile(path)):
                return None
            info["size"] = int(info["size"])
            if os.path.getsize(path) != info["size"] or not verify_signature(info, self.key):
                return None
            if not hmac.compare_digest(sha256_file(path), info["sha256"].lower()):
                return None
            info["path"] = path
            return info
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def cleanup(self):
        """Delete installers of versions that are already installed (or that no longer verify)."""
        try:
            keep = None
            st = self.staged_update()
            if st:
                keep = os.path.basename(st["path"])
            for name in os.listdir(self.dir):
                if name.endswith((".exe", ".part")) and name != keep:
                    os.remove(os.path.join(self.dir, name))
            if not st and os.path.exists(self._state_path):
                os.remove(self._state_path)
        except OSError:
            pass

    # ---- the check ----
    def check_and_stage(self, progress=None, cancel=None):
        """Blocking. Returns ('uptodate'|'staged'|'ready'|'busy'|'error', info_or_message)."""
        ready = self.staged_update()
        if ready:
            return "ready", ready
        if not self._take_lock():
            return "busy", None
        try:
            if cancel is not None and cancel.is_set():
                return "error", "cancelled by the user"
            page = fetch_page(self.page_url)
            if cancel is not None and cancel.is_set():
                return "error", "cancelled by the user"
            info = best_valid_update(page, self.current, self.key)
            if info is None:
                self.cleanup()
                return "uptodate", None
            dest = self._installer_path(info["version"])
            self._log(f"update {info['version']} found - downloading in the background")
            def _prog(done, total):
                if cancel is not None and cancel.is_set():
                    raise InterruptedError("cancelled by the user")
                if progress:
                    progress(done, total)
            download_verified(info, dest, _prog)
            tmp = self._state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({**info, "downloaded_at": time.time()}, f)
            os.replace(tmp, self._state_path)
            self.cleanup()
            self._log(f"update {info['version']} downloaded and verified")
            ready = self.staged_update()
            return ("staged", ready) if ready else ("error", "the downloaded file did not verify")
        except Exception as exc:                                  # network down, page changed, hash mismatch ...
            self._log(f"update check failed: {type(exc).__name__}: {exc}")
            return "error", str(exc)
        finally:
            self._release_lock()

    # ---- background thread ----
    def start_background(self):
        if self._thread and self._thread.is_alive():
            return

        def loop():
            if self._stop.wait(FIRST_CHECK_DELAY_SECONDS):
                return
            while not self._stop.is_set():
                self.check_and_stage()
                if self._stop.wait(CHECK_INTERVAL_SECONDS):
                    return

        self._thread = threading.Thread(target=loop, name="sps-updater", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    # ---- installing ----
    def launch_installer(self, info):
        """Start the verified installer silently (Windows asks for administrator permission once). True on success."""
        path = info.get("path") or ""
        if sys.platform != "win32" or not os.path.isfile(path):
            return False
        # re-check at the last possible moment
        if not hmac.compare_digest(sha256_file(path), info["sha256"].lower()) or not verify_signature(info, self.key):
            return False
        import ctypes
        params = " ".join(SILENT_ARGS)
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, params, os.path.dirname(path), 0)
        return rc > 32                                            # <= 32 means the user refused the permission or it failed
