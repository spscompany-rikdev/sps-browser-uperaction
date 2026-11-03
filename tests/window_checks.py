"""Builds the REAL main window (offscreen) and checks: extension toolbar icons, extra windows staying alive, guest window."""
import gc, os, sys, tempfile, unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC)
os.environ["HOME"] = tempfile.mkdtemp(prefix="spshome_")
os.environ["USERPROFILE"] = os.environ["HOME"]
os.environ["SPS_DISABLE_UPDATER"] = "1"
try:
    sys.argv = ["sps"]
    import SPS_BROWSER as S
    from PyQt6.QtWidgets import QApplication, QPushButton, QMessageBox
    from PyQt6.QtCore import QTimer, QEventLoop, QUrl
    HAVE = True
except Exception as e:  # pragma: no cover
    HAVE = False
    print("window tests skipped:", e)


def wait(ms):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()


@unittest.skipUnless(HAVE, "browser module could not be imported here")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        S.MainWindow._ask_username_once = lambda self, *a, **k: None
        cls.app = QApplication.instance() or QApplication(["sps"])
        cls.w = S.MainWindow("Default")
        cls.w.show(); wait(400)

    def puzzle_buttons(self):
        return [b for b in self.w.toolbar.findChildren(QPushButton) if b.text() and b.isVisibleTo(self.w) is not None and b in getattr(self.w, "_ext_toolbar_widgets", [])]

    def set_exts(self, n):
        em = self.w.extension_manager
        em._extensions = [{"id": "x%d" % i, "name": "Ext %d" % i, "icon": "E%d" % i, "enabled": True, "show_in_toolbar": True, "description": ""} for i in range(n)]
        em._scripts = []

    def test_toolbar_icons_do_not_pile_up(self):
        for n, expected in ((0, 0), (1, 1), (2, 2), (3, 1), (5, 1)):
            self.set_exts(n)
            for _ in range(4):                       # rebuilding again and again must never add icons
                self.w._rebuild_extension_toolbar_buttons()
            wait(50)
            live = [b for b in self.w.toolbar.findChildren(QPushButton) if b.text() in ("\U0001F9E9",) or b.text().startswith("E")]
            self.assertEqual(len(live), expected, "extensions=%d" % n)
            if n > 2:
                self.assertEqual(live[0].text(), "\U0001F9E9")        # one puzzle button with the drop-down

    def test_extra_window_survives_garbage_collection(self):
        before = len(S._SPS_WINDOW_REFS)
        self.w.open_new_window()
        gc.collect(); wait(200); gc.collect()
        self.assertGreater(len(S._SPS_WINDOW_REFS), before)
        win = S._SPS_WINDOW_REFS[-1]
        self.assertTrue(win.isVisible())
        win.hide()

    def test_guest_window_is_private_and_stays(self):
        q = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        try:
            self.w._open_guest_mode()
        finally:
            QMessageBox.question = q
        gc.collect(); wait(300); gc.collect()
        g = S._SPS_WINDOW_REFS[-1]
        self.assertTrue(g.isVisible()); self.assertTrue(getattr(g, "_is_guest", False))
        self.assertTrue(g.browser_profile.isOffTheRecord())
        self.assertEqual(g._load_bookmarks(), [])
        n = len(g._load_history()); g._save_history("https://example.com/", "x")
        self.assertEqual(len(g._load_history()), n)                    # nothing written for a guest
        self.assertGreaterEqual(g.tabs.count(), 1)
        g.hide()


if __name__ == "__main__":
    unittest.main()
