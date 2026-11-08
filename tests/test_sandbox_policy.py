import os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sandbox_policy as sp

class T(unittest.TestCase):
    def test_existing_desktop_file_never_asks(self):
        d = os.path.join(os.path.expanduser("~"), "Desktop"); 
        self.assertIsNone(sp.classify(os.path.join(d, "notes.txt"), "/opt/sps"))
        self.assertIsNone(sp.classify(os.path.join(d, "old.exe"), "/opt/sps"))      # does not exist -> not fresh
    def test_new_program_file_asks(self):
        # use a dir that is not a 'safe prefix'
        d = os.path.join(os.path.expanduser("~"), "sps_policy_test"); os.makedirs(d, exist_ok=True)
        f = os.path.join(d, "dropper.exe"); open(f, "w").write("x")
        try:
            self.assertEqual(sp.classify(f, "/opt/sps"), "file_write")
            old = time.time() - 600; os.utime(f, (old, old))     # old mtime
            # ctime can't be faked on Linux, but mtime old -> still not 'fresh'
            self.assertIsNone(sp.classify(f, "/opt/sps"))
        finally:
            os.remove(f); os.rmdir(d)
    def test_lnk_never_asks(self):
        self.assertIsNone(sp.classify(os.path.join(os.path.expanduser("~"), "Desktop", "Site.lnk"), "/opt/sps"))
if __name__ == "__main__": unittest.main()
