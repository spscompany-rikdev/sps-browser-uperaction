"""The QR pictures must really be scannable: draw with the desktop code, decode with jsQR (the same decoder the Android app bundles)."""
import base64, os, sys, tempfile, unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSQR = os.path.join(ROOT, "android", "app", "src", "main", "assets", "jsQR.js")


class QrTests(unittest.TestCase):
    def test_roundtrip_with_jsqr(self):
        try:
            from playwright.sync_api import sync_playwright
            from PyQt6.QtWidgets import QApplication
            import sps_qr
        except Exception as e:
            self.skipTest(str(e))
        app = QApplication.instance() or QApplication(["x"])
        texts = ["https://example.com/", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "https://বাংলা.example/পথ?q=১২৩"]
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(); pg.set_content("<canvas id=c></canvas>"); pg.add_script_tag(path=JSQR)
            for t in texts:
                f = os.path.join(tempfile.mkdtemp(), "q.png"); self.assertTrue(sps_qr.qr_pixmap(t, 300).save(f))
                data = base64.b64encode(open(f, "rb").read()).decode()
                got = pg.evaluate("""async (d) => { const img = new Image(); img.src = 'data:image/png;base64,' + d; await img.decode();
                    const c = document.getElementById('c'); c.width = img.width; c.height = img.height; const x = c.getContext('2d'); x.drawImage(img, 0, 0);
                    const r = jsQR(x.getImageData(0, 0, c.width, c.height).data, c.width, c.height); return r ? r.data : null; }""", data)
                self.assertEqual(got, t)
            b.close()

    def test_split_urls(self):
        import sps_qr
        self.assertEqual(sps_qr.split_urls("a\nhttps://x.y/1, http://z\njavascript:alert(1)\nftp://q"), ["https://x.y/1", "http://z"])


if __name__ == "__main__":
    unittest.main()
