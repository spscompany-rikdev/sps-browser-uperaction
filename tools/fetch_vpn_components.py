"""Download the two FREE helper programs SPS VPN can use and put them in <folder>/vpn/ :

  * wireproxy  (ISC licence)   - WireGuard tunnel exposed as a local SOCKS5 port   https://github.com/pufferffish/wireproxy
  * Tor expert bundle (BSD)    - the Tor network                                    https://www.torproject.org

Best effort: any failure only prints a warning (the browser works without them; the VPN window then says "not found").
Usage:  python tools/fetch_vpn_components.py <target SPS_Browser folder> [--only wireproxy|tor]
"""
import hashlib, io, json, os, platform, re, shutil, sys, tarfile, urllib.request, zipfile

UA = {"User-Agent": "SPS-Browser-build"}


def _get(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _plat():
    sysname = {"Windows": "windows", "Linux": "linux", "Darwin": "darwin"}.get(platform.system(), "")
    m = platform.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "386" if m in ("i386", "i686", "x86") else "amd64"
    return sysname, arch


def fetch_wireproxy(vpn):
    osn, arch = _plat()
    rel = json.loads(_get("https://api.github.com/repos/pufferffish/wireproxy/releases/latest"))
    want = "wireproxy_%s_%s" % (osn, arch)
    asset = next((a for a in rel["assets"] if a["name"].startswith(want) and a["name"].endswith((".tar.gz", ".zip"))), None)
    if not asset:
        raise RuntimeError("no wireproxy build for %s/%s in release %s" % (osn, arch, rel.get("tag_name")))
    data = _get(asset["browser_download_url"])
    exe = "wireproxy.exe" if osn == "windows" else "wireproxy"
    os.makedirs(vpn, exist_ok=True)
    if asset["name"].endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(data))
        member = next(n for n in z.namelist() if os.path.basename(n) == exe)
        blob = z.read(member)
    else:
        t = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
        member = next(m for m in t.getmembers() if m.isfile() and os.path.basename(m.name) == exe)
        blob = t.extractfile(member).read()
    with open(os.path.join(vpn, exe), "wb") as f:
        f.write(blob)
    os.chmod(os.path.join(vpn, exe), 0o755)
    return "wireproxy " + rel.get("tag_name", "")


def fetch_tor(vpn):
    osn, arch = _plat()
    tor_os = {"windows": "windows", "linux": "linux", "darwin": "macos"}[osn]
    tor_arch = {"amd64": "x86_64", "arm64": "aarch64", "386": "i686"}[arch]
    ver = json.loads(_get("https://aus1.torproject.org/torbrowser/update_3/release/downloads.json"))["version"]
    if not re.match(r"^[0-9.]+$", ver):
        raise RuntimeError("unexpected Tor version string")
    name = "tor-expert-bundle-%s-%s-%s.tar.gz" % (tor_os, tor_arch, ver)
    base = "https://dist.torproject.org/torbrowser/%s/" % ver
    data = _get(base + name, timeout=300)
    sums = _get(base + "sha256sums-signed-build.txt").decode("utf-8", "replace")
    expect = next((l.split()[0] for l in sums.splitlines() if l.strip().endswith(name)), None)
    if not expect:
        raise RuntimeError("no checksum published for " + name)
    if hashlib.sha256(data).hexdigest() != expect.lower():
        raise RuntimeError("checksum of %s does not match - NOT installing it" % name)
    dest = os.path.join(vpn, "tor")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    t = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    for m in t.getmembers():                                    # refuse path tricks
        target = os.path.realpath(os.path.join(dest, m.name))
        if not target.startswith(os.path.realpath(dest) + os.sep) and target != os.path.realpath(dest):
            raise RuntimeError("unsafe path in archive: " + m.name)
        if m.issym() or m.islnk():
            continue
        t.extract(m, dest)
    return "tor " + ver


def fetch_wireguard_msi(vpn):
    """Official WireGuard for Windows installer (signed by WireGuard LLC; SPS verifies the signature again before installing)."""
    if not sys.platform.startswith("win"):
        raise RuntimeError("only needed on Windows")
    listing = _get("https://download.wireguard.com/windows-client/").decode("utf-8", "replace")
    names = sorted(set(re.findall(r'wireguard-amd64-(\d+(?:\.\d+)*)\.msi', listing)),
                   key=lambda v: [int(x) for x in v.split(".")])
    if not names:
        raise RuntimeError("no WireGuard MSI found in the listing")
    fn = "wireguard-amd64-%s.msi" % names[-1]
    os.makedirs(vpn, exist_ok=True)
    with open(os.path.join(vpn, fn), "wb") as f:
        f.write(_get("https://download.wireguard.com/windows-client/" + fn, 300))
    return "wireguard-msi " + names[-1]


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__); return 2
    vpn = os.path.join(argv[0], "vpn")
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    ok = []
    for name, fn in (("wireproxy", fetch_wireproxy), ("tor", fetch_tor), ("wireguard", fetch_wireguard_msi)):
        if only and only != name:
            continue
        try:
            ok.append(fn(vpn)); print("[vpn] installed", ok[-1])
        except Exception as e:
            print("::warning::SPS VPN component '%s' was not included: %s" % (name, e))
    if ok:
        notice = os.path.join(vpn, "NOTICE.txt")
        with open(notice, "w", encoding="utf-8") as f:
            f.write("Third-party programs used by SPS VPN (unchanged, from their official releases):\n"
                    "- wireproxy (ISC licence) https://github.com/pufferffish/wireproxy\n"
                    "- Tor (BSD 3-clause licence) https://www.torproject.org\n"
                    "- WireGuard for Windows installer (MIT/GPL, signed by WireGuard LLC) https://www.wireguard.com\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
