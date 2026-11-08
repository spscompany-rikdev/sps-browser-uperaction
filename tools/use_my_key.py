"""Put YOUR update key into the browser code.   python tools/use_my_key.py  C:\\path\\to\\update_private_key.txt

 * reads your PRIVATE key file (it is only read, never copied or changed),
 * works out the matching PUBLIC key and writes it into src/sps_updater.py (UPDATE_PUBLIC_KEY_HEX),
 * prints the public key. The public key is not secret - it is meant to be inside the browser and on GitHub.

Run it every time you replace src/sps_updater.py with a fresh copy from a zip.
Keep the private key file OUTSIDE the project folder; never upload it.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import sps_ed25519

if len(sys.argv) != 2:
    sys.exit(__doc__)
try:
    sk = bytes.fromhex(open(sys.argv[1], encoding="utf-8").read().strip())
except Exception as e:
    sys.exit(f"Could not read the private key file: {e}")
if len(sk) != 32:
    sys.exit("The private key must be 64 hex characters (32 bytes).")
pk = sps_ed25519.public_key(sk)
if not sps_ed25519.verify(pk, b"t", sps_ed25519.sign(sk, b"t")):
    sys.exit("self-check failed")
target = os.path.join(HERE, "..", "src", "sps_updater.py")
src = open(target, encoding="utf-8").read()
new, n = re.subn(r'(UPDATE_PUBLIC_KEY_HEX\s*=\s*")[0-9a-fA-F]{64}(")', lambda m: m.group(1) + pk.hex() + m.group(2), src, count=1)
if n != 1:
    sys.exit("UPDATE_PUBLIC_KEY_HEX was not found in src/sps_updater.py")
open(target, "w", encoding="utf-8").write(new)
print("Public key written into src/sps_updater.py:")
print(pk.hex())
print("Now upload src/sps_updater.py to GitHub (it contains only the PUBLIC key) and build again.")
