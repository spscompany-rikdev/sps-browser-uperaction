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
