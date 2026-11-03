"""Clicks EVERY item of the real main menu (and all sub-menus) and every toolbar button of the real window, offscreen.
Modal windows are replaced by instant answers so nothing blocks. Anything that raises is reported."""
import os, sys, tempfile, traceback, unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)
os.environ["HOME"] = tempfile.mkdtemp(prefix="spshome_"); os.environ["USERPROFILE"] = os.environ["HOME"]
os.environ["SPS_DISABLE_UPDATER"] = "1"
sys.argv = ["sps"]
import SPS_BROWSER as S
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QApplication, QMenu, QDialog, QMessageBox, QFileDialog, QInputDialog, QPushButton, QToolButton

SKIP = ("⋮", "vpn", "👤", "exit", "quit", "restart", "close window", "clear", "delete", "reset", "erase", "wipe", "remove all", "uninstall", "shutdown",
        "set as default", "install", "update", "factory", "sign out", "logout", "lock")
errors, ran = [], []

def no_block():
    Y = QMessageBox.StandardButton.Yes
    for n in ("question", "information", "warning", "critical", "about", "aboutQt"):
        setattr(QMessageBox, n, staticmethod(lambda *a, **k: Y))
    QMessageBox.exec = lambda self, *a: 0
    QDialog.exec = lambda self, *a: 0
    QMenu.exec = lambda self, *a, **k: None
    QMenu.popup = lambda self, *a, **k: None
    for n in ("getOpenFileName", "getSaveFileName", "getExistingDirectory", "getOpenFileNames"):
        setattr(QFileDialog, n, staticmethod(lambda *a, **k: ("", "")))
    for n in ("getText", "getMultiLineText", "getItem"):
        setattr(QInputDialog, n, staticmethod(lambda *a, **k: ("", False)))
    QtWidgets.QColorDialog.getColor = staticmethod(lambda *a, **k: __import__('PyQt6.QtGui', fromlist=['QColor']).QColor())
    QtWidgets.QFontDialog.getFont = staticmethod(lambda *a, **k: (__import__('PyQt6.QtGui', fromlist=['QFont']).QFont(), False))
    QInputDialog.getInt = staticmethod(lambda *a, **k: (0, False))
    QInputDialog.getDouble = staticmethod(lambda *a, **k: (0.0, False))

def walk(menu, path=""):
    for a in menu.actions():
        if a.isSeparator():
            continue
        label = path + a.text().replace("&", "")
        sub = a.menu()
        if sub is not None:
            yield from walk(sub, label + " > ")
        else:
            yield label, a

def run_all():
    no_block()
    S.MainWindow._ask_username_once = lambda self, *a, **k: None
    app = QApplication.instance() or QApplication(["sps"])
    logged = []
    orig = S._sps_log_exception
    def rec(t, e, tb):
        logged.append("".join(traceback.format_exception(t, e, tb))[-600:]); return orig(t, e, tb)
    S._sps_log_exception = rec
    w = S.MainWindow("Default"); w.show()
    def wait(ms):
        l = QtCore.QEventLoop(); QtCore.QTimer.singleShot(ms, l.quit); l.exec()
    wait(500)
    captured = []
    QMenu.exec = lambda self, *a, **k: captured.append(self)
    w._show_main_menu()
    menu = captured[-1]
    items = list(walk(menu))
    print("menu items:", len(items), flush=True)
    for label, act in items:
        low = label.lower()
        if any(s in low for s in SKIP) or not act.isEnabled():
            continue
        del logged[:]
        print('>>', label, flush=True)
        try:
            act.trigger(); wait(30)
            ran.append(label)
        except Exception:
            errors.append((label, traceback.format_exc()[-500:])); print('PROBLEM:', label, traceback.format_exc()[-300:], flush=True)
        if logged:
            errors.append((label, logged[-1])); print('PROBLEM:', label, logged[-1][-300:], flush=True)
    print('MENU DONE', flush=True)
    # toolbar buttons
    for b in w.toolbar.findChildren((QPushButton, QToolButton)):
        txt = (b.text() or b.toolTip() or "?").strip()
        if any(s in txt.lower() for s in SKIP) or not b.isEnabled():
            continue
        del logged[:]
        print('>> toolbar', txt, flush=True)
        try:
            b.click(); wait(30); ran.append("toolbar: " + txt)
        except Exception:
            errors.append(("toolbar: " + txt, traceback.format_exc()[-500:]))
        if logged:
            errors.append(("toolbar: " + txt, logged[-1]))
    return errors, ran

if __name__ == "__main__":
    import faulthandler; faulthandler.dump_traceback_later(480, exit=True)
    e, r = run_all()
    print("CLICKED", len(r), "items;", len(e), "problems")
    seen = set()
    for label, tb in e:
        if label in seen: continue
        seen.add(label); print("PROBLEM:", label, "\n", tb, flush=True)
    os._exit(1 if e else 0)
