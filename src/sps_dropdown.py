"""Dropdown windows: almost every dialog of SPS Browser opens as a rounded drop-down under the toolbar (like Chrome) instead of a
separate window.  Special windows (Settings, updates, print, big managers, message boxes, file pickers ...) stay normal windows.

How it works (no dialog had to be rewritten):  QDialog.exec / QDialog.show are wrapped.  When the dialog belongs to the main window
and is not on the exclusion list, it is placed inside a rounded frame that hangs under the toolbar.  exec() still blocks until the
dialog is finished and still returns its result, so every caller keeps working.  Click outside / Esc = the dialog is rejected.
Any failure falls back to the normal window, so this can never make a dialog unusable.
"""
from PyQt6.QtCore import Qt, QEvent, QEventLoop, QObject, QPoint, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QApplication, QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QMessageBox, QFileDialog,
                             QColorDialog, QInputDialog, QFontDialog, QProgressDialog, QScrollArea, QPushButton, QVBoxLayout, QWidget)
try:
    from PyQt6.QtPrintSupport import QPrintDialog, QPageSetupDialog, QPrintPreviewDialog
    _PRINT = (QPrintDialog, QPageSetupDialog, QPrintPreviewDialog)
except Exception:                                            # pragma: no cover
    _PRINT = ()

NATIVE = (QMessageBox, QFileDialog, QColorDialog, QInputDialog, QFontDialog, QProgressDialog) + _PRINT
STAY_WINDOWS = {"SettingsDialog", "SpsPrintDialog", "SpsManager", "SpsForcedUpdateDialog", "SpsUpdateCheckDialog", "SplashScreen",
                "SandboxManagerWindow", "PermissionDialog", "ProfileSelector", "ProfileEditDialog", "LicenseDialog",
                "ModelDownloadDialog", "ChromeFlagsDialog", "ToolbarCustomizerDialog", "AIPermissionDialog"}
STAY_TITLES = ("settings", "update", "print", "licen", "welcome", "sign in", "first run", "profile")

_ENABLED = True
_orig_exec = QDialog.exec
_orig_show = QDialog.show
_state = {"host": None, "filter": None}


def set_enabled(on):
    global _ENABLED
    _ENABLED = bool(on)


def _main_window(dlg):
    w = dlg.parentWidget()
    while w is not None:
        if hasattr(w, "toolbar") and hasattr(w, "tabs") and hasattr(w, "settings_data"):
            return w
        w = w.parentWidget()
    return None


def eligible(dlg):
    if not _ENABLED or getattr(dlg, "_sps_dd_done", False) or isinstance(dlg, NATIVE):
        return None
    if type(dlg).__name__ in STAY_WINDOWS or getattr(dlg, "SPS_STAY_WINDOW", False):
        return None
    title = (dlg.windowTitle() or "").lower()
    if any(k in title for k in STAY_TITLES):
        return None
    mw = _main_window(dlg)
    if mw is None or not mw.isVisible() or mw.isMinimized():
        return None
    try:
        if mw.settings_data.get("dropdown_windows", True) is False:
            return None
    except Exception:
        pass
    return mw


class _Outside(QObject):
    """Click outside the drop-down = close it (ignored while a file picker / message box is open)."""
    def __init__(self, host):
        super().__init__(host); self.host = host

    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.Type.MouseButtonPress and self.host.isVisible():
                if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None:
                    return False
                w = obj if isinstance(obj, QWidget) else None
                if w is not None and w.window() is self.host:
                    return False
                if w is not None and w.window() is self.host.mw:
                    g = ev.globalPosition().toPoint()
                    if not self.host.frameGeometry().contains(g):
                        QTimer.singleShot(0, self.host.dismiss)
        except Exception:
            pass
        return False


class DropdownHost(QFrame):
    def __init__(self, mw, dlg):
        super().__init__(mw, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.mw, self.dlg = mw, dlg
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        t = dict(getattr(mw, "_theme", {}) or {})
        bg, fg = t.get("bg_primary", "#ffffff"), t.get("text_primary", "#202124")
        outer = QVBoxLayout(self); outer.setContentsMargins(14, 8, 14, 18)
        self.card = QFrame(); self.card.setObjectName("ddcard"); outer.addWidget(self.card)
        sh = QGraphicsDropShadowEffect(self); sh.setBlurRadius(30); sh.setOffset(0, 7); sh.setColor(QColor(0, 0, 0, 95)); self.card.setGraphicsEffect(sh)
        self.setStyleSheet("#ddcard{background:%s;border:1px solid %s;border-radius:18px;} #ddtitle{color:%s;font-size:14px;font-weight:700;background:transparent;}"
                           "QPushButton#ddx{background:transparent;color:%s;border:none;border-radius:14px;font-size:14px;}"
                           "QPushButton#ddx:hover{background:rgba(128,128,128,60);}" % (bg, t.get("border", "#dadce0"), fg, fg))
        lay = QVBoxLayout(self.card); lay.setContentsMargins(6, 8, 6, 8); lay.setSpacing(4)
        head = QHBoxLayout(); head.setContentsMargins(10, 0, 4, 0)
        self.title = QLabel(dlg.windowTitle() or ""); self.title.setObjectName("ddtitle"); head.addWidget(self.title); head.addStretch()
        x = QPushButton("✕"); x.setObjectName("ddx"); x.setFixedSize(28, 28); x.clicked.connect(self.dismiss); head.addWidget(x)
        lay.addLayout(head)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        lay.addWidget(self.scroll, 1)
        dlg.setWindowFlags(Qt.WindowType.Widget)           # the dialog becomes an ordinary widget inside the frame
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.setSizeGripEnabled(False) if hasattr(dlg, "setSizeGripEnabled") else None
        self.scroll.setWidget(dlg)
        dlg.finished.connect(self._finished)
        dlg._sps_dd_done = True
        w = max(380, min(dlg.sizeHint().width() if dlg.sizeHint().isValid() else 480, max(380, dlg.width()), 560))
        w = max(380, min(w, 560))
        avail = mw.height() - (mw.toolbar.geometry().bottom() if hasattr(mw, "toolbar") else 80) - 40
        h = max(260, min(max(dlg.sizeHint().height(), dlg.height(), 300) + 60, avail, 700))
        self.resize(w + 28, h)
        self._closing = False

    def place(self):
        anchor = getattr(self.mw, "menu_btn", None)
        if anchor is not None and anchor.isVisible():
            p = anchor.mapToGlobal(QPoint(anchor.width() - self.width() + 14, anchor.height() - 4))
        else:
            p = self.mw.mapToGlobal(QPoint(self.mw.width() - self.width() - 10, 70))
        scr = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if scr is not None:
            p.setX(max(scr.left() + 4, min(p.x(), scr.right() - self.width() - 4))); p.setY(max(scr.top() + 4, p.y()))
        self.move(p)
        self.setWindowOpacity(0.0); self.show(); self.dlg.show(); self.raise_(); self.activateWindow()
        self._a = QPropertyAnimation(self, b"windowOpacity", self); self._a.setDuration(150); self._a.setStartValue(0.0); self._a.setEndValue(1.0)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic); self._a.start()

    def dismiss(self):
        if self._closing:
            return
        try:
            if self.dlg.isVisible() or True:
                self.dlg.reject()
        except Exception:
            pass
        self._finished(0)

    def _finished(self, *_):
        if self._closing:
            return
        self._closing = True
        try:
            app = QApplication.instance()
            if _state["filter"] is not None:
                app.removeEventFilter(_state["filter"]); _state["filter"] = None
        except Exception:
            pass
        _state["host"] = None
        self.hide()
        self.deleteLater()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(ev)


def _open(dlg, mw):
    old = _state["host"]
    if old is not None:
        try:
            old.dismiss()
        except Exception:
            pass
    host = DropdownHost(mw, dlg)
    _state["host"] = host
    f = _Outside(host); _state["filter"] = f
    QApplication.instance().installEventFilter(f)
    host.place()
    return host


def _exec(self, *a, **k):
    mw = None
    try:
        mw = eligible(self)
        if mw is None:
            return _orig_exec(self, *a, **k)
        host = _open(self, mw)
    except Exception as e:                                   # never break a dialog because of the new look
        print("[SPS dropdown] fallback to a window:", e)
        return _orig_exec(self, *a, **k)
    loop = QEventLoop()
    self.finished.connect(loop.quit)
    host.destroyed.connect(loop.quit)
    loop.exec()
    try:
        return self.result()
    except RuntimeError:
        return 0


def _show(self, *a, **k):
    try:
        if not getattr(self, "_sps_dd_inside", False):
            mw = eligible(self)
            if mw is not None:
                host = _open(self, mw)
                self._sps_dd_inside = True
                return None
    except Exception as e:
        print("[SPS dropdown] fallback to a window:", e)
    return _orig_show(self, *a, **k)


def install():
    QDialog.exec = _exec
    QDialog.show = _show
