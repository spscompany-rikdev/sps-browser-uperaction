"""Make the text block for the update page.

    python tools/publish_update.py  SPS_Browser_Setup_36.1.0.exe  36.1.0  https://github.com/you/repo/releases/download/v36.1.0/SPS_Browser_Setup_36.1.0.exe  [--optional] [--notes "What changed"] [--key update_private_key.txt]

Upload the installer to the https address first (GitHub Releases is free), then paste the printed block into your Google Site
"updates" page as plain text. Old blocks may stay on the page; the browser picks the newest valid one.
"""
import argparse, hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import sps_ed25519, sps_updater

ap = argparse.ArgumentParser()
ap.add_argument("installer"); ap.add_argument("version"); ap.add_argument("url")
ap.add_argument("--optional", action="store_true", help="user may postpone (default: mandatory)")
ap.add_argument("--notes", default=""); ap.add_argument("--key", default="update_private_key.txt")
a = ap.parse_args()
if sps_updater.parse_version(a.version) is None: sys.exit("version must look like 36.1.0")
if not sps_updater.https_only(a.url): sys.exit("url must start with https://")
data = open(a.installer, "rb").read()
sk = bytes.fromhex(open(a.key).read().strip())
info = {"version": a.version, "url": a.url, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "mandatory": not a.optional}
if sps_ed25519.public_key(sk).hex() != sps_updater.UPDATE_PUBLIC_KEY_HEX.lower():
    sys.exit("This private key does not match the public key built into src/sps_updater.py")
info["signature"] = sps_ed25519.sign(sk, sps_updater.canonical_message(info)).hex()
print("SPS-UPDATE-BEGIN")
print(f"version: {info['version']}")
print(f"url: {info['url']}")
print(f"sha256: {info['sha256']}")
print(f"size: {info['size']}")
print(f"mandatory: {'yes' if info['mandatory'] else 'no'}")
print(f"signature: {info['signature']}")
if a.notes: print(f"notes: {a.notes}")
print("SPS-UPDATE-END")
