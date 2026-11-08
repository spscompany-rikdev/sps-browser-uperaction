"""Create the update-signing key pair.  Run ONCE, on your own PC:   python tools/make_update_keys.py

 * update_private_key.txt   -> SECRET. Keep it offline (USB stick / password manager). Never upload it, never put it in the
                              build folder or on GitHub. Whoever has it can push updates to every user.
 * the PUBLIC key is written into src/sps_updater.py (UPDATE_PUBLIC_KEY_HEX) - it ships inside the browser.

If you ever lose the private key you must ship one new installer by hand with a new public key.
"""
import os, re, sys, secrets
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import sps_ed25519

out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "update_private_key.txt")
if os.path.exists(out):
    sys.exit(f"{out} already exists - refusing to overwrite your private key.")
sk = secrets.token_bytes(32)
pk = sps_ed25519.public_key(sk)
if not sps_ed25519.verify(pk, b"t", sps_ed25519.sign(sk, b"t")):
    sys.exit("self-check failed")
with open(out, "w") as f:
    f.write(sk.hex() + "\n")
try: os.chmod(out, 0o600)
except OSError: pass
target = os.path.join(HERE, "..", "src", "sps_updater.py")
src = open(target, encoding="utf-8").read()
src2 = re.sub(r'(UPDATE_PUBLIC_KEY_HEX\s*=\s*")[0-9a-fA-F]{64}(")', lambda m: m.group(1) + pk.hex() + m.group(2), src, count=1)
open(target, "w", encoding="utf-8").write(src2)
print("Private key saved to:", out, "  (KEEP SECRET, back it up)")
print("Public key written into src/sps_updater.py:", pk.hex())
print("Now rebuild the browser so the new public key is inside it.")
