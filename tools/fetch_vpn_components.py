"""Put the FREE helper programs SPS VPN needs into <folder>/vpn/ :  wireproxy, Tor, (Windows) the WireGuard installer.

Usage:  python tools/fetch_vpn_components.py <target SPS_Browser folder> [--only wireproxy|tor|wireguard] [--strict]

--strict  : exit with an error when a REQUIRED part (wireproxy; on Windows also the WireGuard MSI) is missing.
            ci_build.py uses it, so a release can never be published without a working VPN.
Without --strict a failure only prints a warning (the program can still download wireproxy by itself the first time you connect).
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import sps_vpn_fetch as F


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__); return 2
    vpn = os.path.join(argv[0], "vpn")
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    strict = "--strict" in argv
    required = {"wireproxy"} | ({"wireguard"} if sys.platform.startswith("win") else set())
    steps = (("wireproxy", F.fetch_wireproxy), ("tor", F.fetch_tor), ("wireguard", F.fetch_wireguard_msi))
    ok, missing = [], []
    for name, fn in steps:
        if only and only != name:
            continue
        if name == "wireguard" and not sys.platform.startswith("win"):
            continue
        try:
            fn(vpn); ok.append(name); print("[vpn] installed", name)
        except Exception as e:
            print("::warning::SPS VPN component '%s' was not included: %s" % (name, e))
            if name in required:
                missing.append(name)
    if ok:
        with open(os.path.join(vpn, "NOTICE.txt"), "w", encoding="utf-8") as f:
            f.write("Third-party programs used by SPS VPN (unchanged, from their official releases):\n"
                    "- wireproxy (ISC licence) https://github.com/windtf/wireproxy\n"
                    "- Tor (BSD 3-clause licence) https://www.torproject.org\n"
                    "- WireGuard for Windows installer (MIT/GPL, signed by WireGuard LLC) https://www.wireguard.com\n")
    if strict and missing:
        print("ERROR: required VPN component(s) missing: " + ", ".join(missing)); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
