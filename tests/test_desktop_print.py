"""Runs print_checks.py (the real main window, offscreen) in a separate process with a time limit, so a hang can never block the build."""
import os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class PrintAreaRealTests(unittest.TestCase):
    def test_real_print_checks(self):
        code = ("import faulthandler,sys,unittest,os;faulthandler.dump_traceback_later(150, exit=True);"
                "sys.path.insert(0, %r);"
                "r=unittest.main(module='print_checks', argv=['x'], exit=False).result;"
                "os._exit(0 if r.wasSuccessful() else 1)" % HERE)
        try:
            r = subprocess.run([sys.executable, "-W", "ignore", "-c", code], capture_output=True, text=True, timeout=170)
        except subprocess.TimeoutExpired:
            self.fail("print checks hung")
        out = (r.stdout or "") + (r.stderr or "")
        if "window tests skipped" in out and r.returncode == 0:
            self.skipTest("browser module cannot be imported in this environment")
        self.assertEqual(r.returncode, 0, out[-3000:])


if __name__ == "__main__":
    unittest.main()
