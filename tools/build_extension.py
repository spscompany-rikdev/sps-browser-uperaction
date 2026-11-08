"""Zip the SPS Shield extension:  python tools/build_extension.py [version]
  -> dist_ext/SPS_Shield_Extension_v<version>.zip   Chrome / Edge / Brave (load unpacked after unzipping, or the Chrome Web Store)
  -> dist_ext/SPS_Shield_Firefox_v<version>.zip     Firefox (addons.mozilla.org / about:debugging)
The Firefox zip differs only in its manifest: Firefox needs an add-on ID, the data-collection declaration and a
background 'scripts' fallback (Mozilla's validator reports these as errors/warnings for the Chrome manifest)."""
import copy, json, os, sys, zipfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXT = os.path.join(ROOT, "extension")
mf = os.path.join(EXT, "manifest.json")
m = json.load(open(mf, encoding="utf-8"))
if len(sys.argv) > 1:
    parts = sys.argv[1].split(".")
    m["version"] = ".".join(parts[:4])
    json.dump(m, open(mf, "w", encoding="utf-8"), indent=2)
out = os.path.join(ROOT, "dist_ext"); os.makedirs(out, exist_ok=True)


def firefox_manifest(chrome):
    f = copy.deepcopy(chrome)
    f.pop("minimum_chrome_version", None)
    pass
    bg = f.get("background", {})
    f["background"] = {"scripts": [bg.get("service_worker", "background.js")]}      # Firefox runs MV3 background as an event page
    f["browser_specific_settings"] = {"gecko": {
        "id": "sps-shield@spsbrowser",
        "strict_min_version": "140.0",
        "data_collection_permissions": {"required": ["none"]},                       # nothing leaves the computer
    }, "gecko_android": {"strict_min_version": "142.0"}}
    return f


def build(name, manifest):
    path = os.path.join(out, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for d, dirs, files in os.walk(EXT):
            dirs[:] = sorted(x for x in dirs if not x.startswith("_"))                # '_metadata' etc. are not allowed by the stores
            for f in sorted(files):
                full = os.path.join(d, f)
                rel = os.path.relpath(full, EXT)
                if rel == "manifest.json":
                    z.writestr(rel, json.dumps(manifest, indent=2))
                else:
                    z.write(full, rel)
    print("created", path)


build("SPS_Shield_Extension_v%s.zip" % m["version"], m)
build("SPS_Shield_Firefox_v%s.zip" % m["version"], firefox_manifest(m))
