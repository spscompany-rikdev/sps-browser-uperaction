"""Real Qt (offscreen) check of the print window: choosing 'Selected area' must work end to end."""
import os, sys, tempfile, unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["SPS_DATA_DIR"] = tempfile.mkdtemp(prefix="spsprint_")
try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtCore import QTimer, QEventLoop, QPoint, QPointF, Qt, QEvent
    from PyQt6.QtGui import QMouseEvent
    import sps_print
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    _APP = QApplication(['x'])
    HAVE = True
except Exception as e:
    HAVE = False; print("window tests skipped:", e)


def wait(ms):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()


def mouse(w, kind, pt):
    ev = QMouseEvent(kind, QPointF(pt), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w, ev)


@unittest.skipUnless(HAVE, "Qt not available")
class PrintAreaTests(unittest.TestCase):
    def test_selected_area_flow(self):
        app = _APP
        win = QMainWindow(); win.tabs = QTabWidget(); win.setCentralWidget(win.tabs)
        view = QWebEngineView(); view.setHtml("<h1 style='color:red'>Hello print</h1><p>text</p>")
        win.tabs.addTab(view, "t"); win.resize(900, 700); win.show(); wait(800)
        dlg = sps_print.show_print_dialog(win)
        self.assertIsNotNone(dlg); wait(300)
        self.assertTrue(dlg.isVisible())
        dlg.area.setCurrentIndex(1); dlg._choose_area(); wait(200)
        sel = dlg._selector
        self.assertIsNotNone(sel)
        self.assertFalse(dlg.isVisible())                     # hidden while dragging ...
        mouse(sel, QEvent.Type.MouseButtonPress, QPoint(20, 20))
        mouse(sel, QEvent.Type.MouseMove, QPoint(200, 150))
        mouse(sel, QEvent.Type.MouseButtonRelease, QPoint(200, 150))
        wait(500)
        self.assertTrue(dlg.isVisible())                      # ... and back afterwards (this was the bug)
        self.assertIsNotNone(dlg._pixmap); self.assertFalse(dlg._pixmap.isNull())
        self.assertIs(win._sps_print_dlg, dlg); self.assertTrue(dlg.save_img.isEnabled())
        dlg.close(); win.close()

    def test_escape_cancels_and_returns(self):
        app = _APP
        win = QMainWindow(); win.tabs = QTabWidget(); win.setCentralWidget(win.tabs)
        view = QWebEngineView(); view.setHtml("<p>x</p>"); win.tabs.addTab(view, "t"); win.resize(600, 500); win.show(); wait(500)
        dlg = sps_print.show_print_dialog(win, start_area=True); wait(900)
        self.assertIsNotNone(dlg._selector)
        sps_print.AreaSelector.keyPressEvent(dlg._selector, type("E", (), {"key": lambda s: Qt.Key.Key_Escape})())
        wait(200)
        self.assertTrue(dlg.isVisible()); dlg.close(); win.close()


if __name__ == "__main__":
    unittest.main()
