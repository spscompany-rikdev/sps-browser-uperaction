"""Zip the SPS Shield extension:  python tools/build_extension.py [version]  ->  dist_ext/SPS_Shield_Extension_v<version>.zip
The same zip can be (a) loaded unpacked after unzipping (free) or (b) uploaded to the Chrome Web Store."""
import json, os, sys, zipfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXT = os.path.join(ROOT, "extension")
mf = os.path.join(EXT, "manifest.json")
m = json.load(open(mf, encoding="utf-8"))
if len(sys.argv) > 1:
    parts = sys.argv[1].split(".")
    m["version"] = ".".join(parts[:4])
    json.dump(m, open(mf, "w", encoding="utf-8"), indent=2)
out = os.path.join(ROOT, "dist_ext"); os.makedirs(out, exist_ok=True)
name = os.path.join(out, "SPS_Shield_Extension_v%s.zip" % m["version"])
with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, files in os.walk(EXT):
        for f in sorted(files):
            full = os.path.join(d, f)
            z.write(full, os.path.relpath(full, EXT))
print("created", name)
