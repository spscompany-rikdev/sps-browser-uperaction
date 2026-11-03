"""Optional (about 5 minutes): clicks every item of the real main menu and every toolbar button. Run with  SPS_FULL_CLICK=1 ."""
import os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))


@unittest.skipUnless(os.environ.get("SPS_FULL_CLICK") == "1", "set SPS_FULL_CLICK=1 to click every menu item (slow)")
class ClickEverything(unittest.TestCase):
    def test_click_all(self):
        r = subprocess.run([sys.executable, "-W", "ignore", os.path.join(HERE, "window_clickall.py")], capture_output=True, text=True, timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        self.assertEqual(r.returncode, 0, "\n".join(l for l in out.splitlines() if l.startswith(("PROBLEM", "CLICKED")))[-3000:])


if __name__ == "__main__":
    unittest.main()
