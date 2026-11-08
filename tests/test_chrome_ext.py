import io, json, os, struct, sys, tempfile, unittest, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sps_chrome_ext as C


def mkzip(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    return b.getvalue()


MV3 = json.dumps({"manifest_version": 3, "name": "x", "version": "1"})


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def w(self, name, data):
        p = os.path.join(self.d, name); open(p, "wb").write(data); return p

    def test_zip_ok(self):
        z, m = C.prepare_package(self.w("a.zip", mkzip({"manifest.json": MV3, "b.js": "1"})), os.path.join(self.d, "o"))
        self.assertTrue(os.path.isfile(z)); self.assertEqual(m["name"], "x")

    def test_crx3_and_crx2(self):
        zb = mkzip({"manifest.json": MV3})
        crx3 = b"Cr24" + struct.pack("<II", 3, 5) + b"12345" + zb
        crx2 = b"Cr24" + struct.pack("<IIII", 2, 3, 2, 0)[0:0] + struct.pack("<I", 2) + struct.pack("<II", 3, 2) + b"abcde" + zb
        for n, data in (("c3.crx", crx3), ("c2.crx", crx2)):
            z, m = C.prepare_package(self.w(n, data), os.path.join(self.d, "o")); self.assertEqual(m["manifest_version"], 3)

    def test_refusals(self):
        o = os.path.join(self.d, "o")
        for data, word in ((mkzip({"manifest.json": json.dumps({"manifest_version": 2})}), "Manifest V2"),
                           (mkzip({"folder/manifest.json": MV3}), "inside the folder"),
                           (mkzip({"a.js": "1"}), "not found"),
                           (mkzip({"manifest.json": MV3, "../evil.js": "1"}), "unsafe"),
                           (b"not a zip", "not a valid")):
            with self.assertRaises(C.ExtError) as cm:
                C.prepare_package(self.w("t.zip", data), o)
            self.assertIn(word, str(cm.exception))

    def test_folder(self):
        f = os.path.join(self.d, "ext"); os.makedirs(f); open(os.path.join(f, "manifest.json"), "w").write(MV3)
        z, m = C.prepare_package(f, os.path.join(self.d, "o")); self.assertEqual(m["version"], "1")

    def test_download_refuses_http_and_store_pages(self):
        for u in ("http://x.example/a.zip", "https://chromewebstore.google.com/detail/abc"):
            with self.assertRaises(C.ExtError):
                C.download(u, self.d)

    def test_shipped_extension_is_valid(self):
        root = os.path.join(os.path.dirname(__file__), "..", "extension")
        z, m = C.prepare_package(root, os.path.join(self.d, "o")); self.assertEqual(m["manifest_version"], 3)


if __name__ == "__main__":
    unittest.main()
