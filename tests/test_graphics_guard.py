"""V37: the graphics crash-guard must never force GPU flags and must fall back to software after a crash."""
import os, re, unittest
SRC = os.path.join(os.path.dirname(__file__), "..", "src", "SPS_BROWSER.py")

class GraphicsGuard(unittest.TestCase):
    def setUp(self):
        self.s = open(SRC, encoding="utf-8").read()

    def test_no_forced_gpu_flags(self):
        main = self.s[self.s.index("def sps_main"):]
        for bad in ("--ignore-gpu-blocklist", "--enable-accelerated-video-decode", "--enable-gpu-rasterization"):
            code="\n".join(l for l in main[:3000].splitlines() if not l.strip().startswith("#"))
            self.assertNotIn(bad, code)

    def test_logic(self):
        a = self.s.index("_SPS_GFX_FILE = ")
        b = self.s.index("#  ENTRY POINT")
        import json, sys, tempfile, time
        d = tempfile.mkdtemp()
        ns = {"os": os, "json": json, "sys": sys, "time": time, "APP_ROOT_DIR": d}
        exec(self.s[a:b].rsplit("# ═", 1)[0], ns)
        sys.argv = ["x"]; os.environ.pop("SPS_GRAPHICS", None)
        self.assertEqual(ns["_sps_gfx_prepare"](), "auto")
        # simulate a crashed earlier run (pid that does not exist)
        ns["_sps_gfx_save"]({"mode": "auto", "pending": [{"pid": 2**22 - 3, "t": 1.0}]})
        self.assertEqual(ns["_sps_gfx_prepare"](), "software")
        ns["_sps_gfx_clear"]()
        self.assertEqual(ns["_sps_gfx_load"]()["mode"], "software")   # sticks until the user switches back
        ns["_sps_gfx_set_mode"]("auto")
        self.assertEqual(ns["_sps_gfx_prepare"](), "auto")

if __name__ == "__main__":
    unittest.main()


class JobObjectNoUiLimits(unittest.TestCase):
    def test_job_has_no_ui_restrictions(self):
        s = open(os.path.join(os.path.dirname(__file__), "..", "src", "os_sandbox_windows.py"), encoding="utf-8").read()
        code = "\n".join(l for l in s.splitlines() if not l.strip().startswith("#"))
        self.assertNotIn("JobObjectBasicUIRestrictions,", code.split("def assign_process")[0].split("_configure")[-1])
        self.assertNotIn("UIRestrictionsClass", code)


class UpdateDialogIsCloseable(unittest.TestCase):
    def test_no_buttonless_box_and_cancel_exists(self):
        s = open(os.path.join(os.path.dirname(__file__), "..", "src", "_v36_patch.py"), encoding="utf-8").read()
        self.assertNotIn("StandardButton.NoButton", s)            # the old un-closeable 'Checking...' box
        self.assertIn("class SpsUpdateCheckDialog", s)
        self.assertIn("WindowCloseButtonHint", s)
        u = open(os.path.join(os.path.dirname(__file__), "..", "src", "sps_updater.py"), encoding="utf-8").read()
        self.assertIn("def check_and_stage(self, progress=None, cancel=None)", u)


class HttpErrorsAreShownAsSent(unittest.TestCase):
    def test_google_429_is_not_replaced(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        import sps_pages
        for dom, code in (("HttpStatusCodeDomain", 429), ("HttpErrorDomain", 404), ("HttpStatusCodeDomain", 503)):
            self.assertIsNone(sps_pages.error_category(code, dom))
        self.assertEqual(sps_pages.error_category(-105, "DnsErrorDomain"), "dns")


class AndroidAndKeyFiles(unittest.TestCase):
    ROOT = os.path.join(os.path.dirname(__file__), "..")

    def test_android_project_is_complete(self):
        for f in ("android/settings.gradle", "android/build.gradle", "android/app/build.gradle",
                  "android/app/src/main/AndroidManifest.xml",
                  "android/app/src/main/java/com/spscompany/spsbrowser/MainActivity.java",
                  "android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png"):
            self.assertTrue(os.path.isfile(os.path.join(self.ROOT, f)), f)
        import xml.dom.minidom as m
        m.parse(os.path.join(self.ROOT, "android/app/src/main/AndroidManifest.xml"))
        self.assertIn('usesCleartextTraffic="false"', open(os.path.join(self.ROOT, "android/app/src/main/AndroidManifest.xml")).read())

    def test_support_form_is_set(self):
        t = open(os.path.join(self.ROOT, "extras", "support_form.txt"), encoding="utf-8").read()
        self.assertIn("docs.google.com/forms/", t)
        self.assertNotIn("PASTE_YOUR", t)

    def test_no_private_key_in_project(self):
        for dp, dn, fn in os.walk(self.ROOT):
            for f in fn:
                self.assertNotIn("private_key", f.lower(), os.path.join(dp, f))


class PrintAndApkFeatures(unittest.TestCase):
    ROOT = os.path.join(os.path.dirname(__file__), "..")

    def test_print_helpers(self):
        import sys
        sys.path.insert(0, os.path.join(self.ROOT, "src"))
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        import sps_print
        self.assertEqual(sps_print.parse_ranges("1-3, 5, 8-")[:2], [(1, 3), (5, 5)])
        self.assertIsNone(sps_print.parse_ranges("abc"))
        self.assertIsNone(sps_print.parse_ranges("5-2"))
        css = sps_print.print_css(80, True, 'T"itle', "https://x.test/")
        self.assertIn("zoom: 0.8", css)
        self.assertIn('"T\\"itle"', css)
        self.assertNotIn("@page", sps_print.print_css(100, False, "t", "u"))

    def test_window_uses_new_print_dialog(self):
        s = open(os.path.join(self.ROOT, "src", "_v36_patch.py"), encoding="utf-8").read()
        self.assertIn("MainWindow.print_page = _v38_print_page", s)
        self.assertIn("MainWindow.export_pdf = _v38_export_pdf", s)
        spec = open(os.path.join(self.ROOT, "SPS_Browser.spec"), encoding="utf-8").read()
        self.assertIn('"sps_print"', spec)

    def test_apk_permissions_and_features(self):
        m = open(os.path.join(self.ROOT, "android/app/src/main/AndroidManifest.xml"), encoding="utf-8").read()
        for perm in ("CAMERA", "RECORD_AUDIO", "ACCESS_FINE_LOCATION"):
            self.assertIn("android.permission." + perm, m)
        self.assertIn("networkSecurityConfig", m)
        j = open(os.path.join(self.ROOT, "android/app/src/main/java/com/spscompany/spsbrowser/MainActivity.java"), encoding="utf-8").read()
        for needle in ("onPermissionRequest", "onGeolocationPermissionsShowPrompt", "RecognizerIntent", "showDownloads",
                       "showSettings", "printSelectedArea", "FLAG_SECURE"):
            self.assertIn(needle, j)
