"""Downloads the free helper programs of SPS VPN (stdlib only, no Qt).

Used in TWO places, so the VPN works however the program was installed:
  * at BUILD time  (tools/fetch_vpn_components.py -> <program folder>/vpn/)
  * at RUN time    (sps_vpn.Tunnel.start -> <profile folder>/vpn/bin/) when the helper is still missing

wireproxy  (ISC licence)   https://github.com/windtf/wireproxy   (moved from pufferffish/wireproxy; both addresses are tried)
Tor expert bundle (BSD)    https://www.torproject.org            (SHA-256 verified against the published list)
WireGuard MSI (Windows)    https://download.wireguard.com        (Authenticode "WireGuard LLC" is verified again before install)
"""
import hashlib, io, json, os, platform, re, shutil, sys, tarfile, time, urllib.request, zipfile

UA = {"User-Agent": "SPS-Browser-helper-download"}
WIREPROXY_REPOS = ("windtf/wireproxy", "pufferffish/wireproxy")


def _get(url, timeout=120, tries=3):
    last = None
    for i in range(tries):
        try:
            headers = dict(UA)
            tok = os.environ.get("GITHUB_TOKEN")
            if tok and "api.github.com" in url:
                headers["Authorization"] = "Bearer " + tok
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.read()
        except Exception as e:                                    # network hiccup / rate limit: wait and retry
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("download failed (%s): %s" % (url.split("?")[0], last))


def platform_tag():
    osn = {"Windows": "windows", "Linux": "linux", "Darwin": "darwin"}.get(platform.system(), "")
    m = platform.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "386" if m in ("i386", "i686", "x86") else "amd64"
    return osn, arch


def _extract_member(data, asset_name, exe):
    if asset_name.endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(data))
        return z.read(next(n for n in z.namelist() if os.path.basename(n) == exe))
    t = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    m = next(m for m in t.getmembers() if m.isfile() and os.path.basename(m.name) == exe)
    return t.extractfile(m).read()


def fetch_wireproxy(dest_dir):
    """Puts wireproxy(.exe) into dest_dir and returns its path. Tries the plain download links first (no API limits)."""
    osn, arch = platform_tag()
    if not osn:
        raise RuntimeError("unsupported system")
    exe = "wireproxy.exe" if osn == "windows" else "wireproxy"
    names = ["wireproxy_%s_%s.tar.gz" % (osn, arch), "wireproxy_%s_%s.zip" % (osn, arch)]
    errors, blob = [], None
    for repo in WIREPROXY_REPOS:
        for n in names:
            try:
                blob = _extract_member(_get("https://github.com/%s/releases/latest/download/%s" % (repo, n), 180, 2), n, exe)
                break
            except Exception as e:
                errors.append(str(e))
        if blob:
            break
    if not blob:                                                    # last resort: the release list
        for repo in WIREPROXY_REPOS:
            try:
                rel = json.loads(_get("https://api.github.com/repos/%s/releases/latest" % repo))
                want = "wireproxy_%s_%s" % (osn, arch)
                a = next(a for a in rel["assets"] if a["name"].startswith(want) and a["name"].endswith((".tar.gz", ".zip")))
                blob = _extract_member(_get(a["browser_download_url"], 180), a["name"], exe)
                break
            except Exception as e:
                errors.append(str(e))
    if not blob:
        raise RuntimeError("wireproxy could not be downloaded: " + " | ".join(errors[-3:]))
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, exe)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.chmod(tmp, 0o755)
    os.replace(tmp, path)
    return path


def fetch_tor(dest_dir):
    osn, arch = platform_tag()
    tor_os = {"windows": "windows", "linux": "linux", "darwin": "macos"}[osn]
    tor_arch = {"amd64": "x86_64", "arm64": "aarch64", "386": "i686"}[arch]
    ver = json.loads(_get("https://aus1.torproject.org/torbrowser/update_3/release/downloads.json"))["version"]
    if not re.match(r"^[0-9.]+$", ver):
        raise RuntimeError("unexpected Tor version string")
    name = "tor-expert-bundle-%s-%s-%s.tar.gz" % (tor_os, tor_arch, ver)
    base = "https://dist.torproject.org/torbrowser/%s/" % ver
    data = _get(base + name, 300)
    sums = _get(base + "sha256sums-signed-build.txt").decode("utf-8", "replace")
    expect = next((l.split()[0] for l in sums.splitlines() if l.strip().endswith(name)), None)
    if not expect:
        raise RuntimeError("no checksum published for " + name)
    if hashlib.sha256(data).hexdigest() != expect.lower():
        raise RuntimeError("checksum of %s does not match - NOT installing it" % name)
    dest = os.path.join(dest_dir, "tor")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    t = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    real = os.path.realpath(dest)
    for m in t.getmembers():                                        # refuse path tricks
        target = os.path.realpath(os.path.join(dest, m.name))
        if not target.startswith(real + os.sep) and target != real:
            raise RuntimeError("unsafe path in archive: " + m.name)
        if m.issym() or m.islnk():
            continue
        t.extract(m, dest)
    return dest


def fetch_wireguard_msi(dest_dir):
    if not sys.platform.startswith("win"):
        raise RuntimeError("only needed on Windows")
    listing = _get("https://download.wireguard.com/windows-client/").decode("utf-8", "replace")
    names = sorted(set(re.findall(r'wireguard-amd64-(\d+(?:\.\d+)*)\.msi', listing)), key=lambda v: [int(x) for x in v.split(".")])
    if not names:
        raise RuntimeError("no WireGuard MSI found in the listing")
    fn = "wireguard-amd64-%s.msi" % names[-1]
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, fn), "wb") as f:
        f.write(_get("https://download.wireguard.com/windows-client/" + fn, 300))
    return os.path.join(dest_dir, fn)
