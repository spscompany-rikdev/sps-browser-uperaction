"""A browser that is closed on purpose must never make the sandbox show an error, even if Qt's shutdown ends with a crash code."""
import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class CleanExitTests(unittest.TestCase):
    def setUp(self):
        import sandbox_launcher as L
        self.L = L
        self.home = tempfile.mkdtemp()
        self._old = os.environ.get("HOME"), os.environ.get("USERPROFILE")
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home

    def tearDown(self):
        for k, v in zip(("HOME", "USERPROFILE"), self._old):
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def ctl(self, pid):
        c = self.L.SandboxController.__new__(self.L.SandboxController)
        c.proc = type("P", (), {"pid": pid})()
        return c

    def test_marker_is_taken_once(self):
        d = Path(self.home) / ".sps_sandbox"; d.mkdir(parents=True)
        (d / "clean_exit_4242").write_text("1")
        c = self.ctl(4242)
        self.assertTrue(self.L.SandboxController._take_clean_exit_marker(c))
        self.assertFalse(self.L.SandboxController._take_clean_exit_marker(c))     # gone after use
        self.assertFalse((d / "clean_exit_4242").exists())

    def test_no_marker_means_not_clean(self):
        self.assertFalse(self.L.SandboxController._take_clean_exit_marker(self.ctl(1)))

    def test_browser_writes_the_marker(self):
        import SPS_BROWSER as S
        S._sps_mark_clean_exit()
        self.assertTrue((Path(self.home) / ".sps_sandbox" / ("clean_exit_%d" % os.getpid())).exists())


if __name__ == "__main__":
    unittest.main()
