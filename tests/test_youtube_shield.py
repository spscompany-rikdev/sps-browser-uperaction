"""YouTube ad shield: the SAME script runs on desktop and Android. Executed in real Chromium on a fake YouTube page."""
import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(ROOT, "android", "app", "src", "main", "assets", "yt_shield.js")
PAGE = """<html><head></head><body><div class="html5-video-player ad-showing"><video class="html5-main-video" id="v"></video>
<button class="ytp-ad-skip-button" onclick="window.skipped=1">skip</button></div><ytd-ad-slot-renderer id="ad">AD</ytd-ad-slot-renderer></body></html>"""


class YoutubeShieldTests(unittest.TestCase):
    def test_desktop_and_android_use_identical_script(self):
        js = open(ASSET, encoding="utf-8").read()
        py = open(os.path.join(ROOT, "src", "SPS_BROWSER.py"), encoding="utf-8").read()
        m = re.search(r'SPS_YT_SKIP_JS = r"""\n(.*?)"""', py, re.S)
        self.assertEqual(m.group(1), js)

    def test_no_heavy_polling(self):
        js = open(ASSET, encoding="utf-8").read()
        self.assertEqual(len(re.findall(r"setInterval", js)), 1)
        self.assertGreaterEqual(int(re.search(r"\}, (\d+)\);\n\}\)\(\);", js).group(1)), 500)   # at most twice a second
        self.assertNotIn("querySelectorAll('*')", js)

    def test_android_wiring(self):
        j = open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "spscompany", "spsbrowser", "MainActivity.java"), encoding="utf-8").read()
        for needle in ("yt_shield.js", "injectYoutubeShield(view, url)", "isYoutubeAdRequest(request.getUrl())", '"ytshield"', "onPageCommitVisible"):
            self.assertIn(needle, j)

    def test_android_capture_never_uses_webview_draw(self):
        j = open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "spscompany", "spsbrowser", "MainActivity.java"), encoding="utf-8").read()
        self.assertIn("PixelCopy.request", j)
        self.assertEqual(j.count("web.draw("), 1)   # only the tiny tab-manager thumbnail (guarded); area print + screenshot use PixelCopy
        self.assertGreaterEqual(j.count("captureArea("), 3)
        self.assertIn("webHolder.post(", j)         # the overlay is removed outside its own touch callback

    def test_cookie_banner_script_in_chromium(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("playwright missing")
        j = open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "spscompany", "spsbrowser", "MainActivity.java"), encoding="utf-8").read()
        m = re.search(r"BANNER_JS =(.*?);\n", j, re.S)
        parts = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
        js = "".join(parts).encode().decode("unicode_escape")
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.set_content("<div id='onetrust-banner-sdk'>cookies</div><p id='keep'>x</p>")
            pg.evaluate(js); pg.evaluate(js)
            self.assertEqual(pg.evaluate("getComputedStyle(document.getElementById('onetrust-banner-sdk')).display"), "none")
            self.assertNotEqual(pg.evaluate("getComputedStyle(document.getElementById('keep')).display"), "none")
            self.assertEqual(pg.evaluate("document.querySelectorAll('#sps-banner-css').length"), 1)
            self.assertEqual(errs, []); b.close()

    def test_script_in_real_chromium(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("playwright missing")
        js = open(ASSET, encoding="utf-8").read()
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route("https://www.youtube.com/**", lambda r: r.fulfill(body=PAGE, content_type="text/html"))
            pg.add_init_script(js)
            pg.goto("https://www.youtube.com/watch?v=x")
            pg.evaluate("window.ytInitialPlayerResponse={adPlacements:[1],playerAds:[2],adSlots:[3],streamingData:{ok:1}}")
            self.assertEqual(pg.evaluate("JSON.stringify(window.ytInitialPlayerResponse)"), '{"streamingData":{"ok":1}}')
            self.assertEqual(pg.evaluate("JSON.stringify(JSON.parse('{\"adPlacements\":[1],\"x\":2,\"playerResponse\":{\"adSlots\":[1],\"y\":1}}'))"),
                             '{"x":2,"playerResponse":{"y":1}}')
            self.assertEqual(pg.evaluate("JSON.parse('[1,2,{\"a\":1}]').length"), 3)             # normal JSON untouched
            self.assertEqual(pg.evaluate("getComputedStyle(document.getElementById('ad')).display"), "none")
            pg.wait_for_timeout(900)
            self.assertTrue(pg.evaluate("window.skipped"))
            self.assertTrue(pg.evaluate("document.getElementById('v').muted"))
            # injecting twice (Android injects on several page events) must be harmless
            pg.evaluate(js); pg.evaluate(js)
            self.assertEqual(pg.evaluate("document.querySelectorAll('#sps-yt-shield-css').length"), 1)
            self.assertEqual(errs, [])
            b.close()


if __name__ == "__main__":
    unittest.main()
