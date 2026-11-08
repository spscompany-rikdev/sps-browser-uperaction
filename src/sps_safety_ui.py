"""Safety Check window (opens as a drop-down). The checks run in a worker thread; the UI is updated through signals only."""
import threading
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QFrame, QProgressBar
import sps_safety

ICON = {"ok": "✅", "warn": "⚠️", "bad": "⛔", "info": "ℹ️"}


class _Sig(QObject):
    progress = pyqtSignal(str)
    done = pyqtSignal(list)


class SafetyDialog(QDialog):
    def __init__(self, mw, version="0"):
        super().__init__(mw)
        self.mw = mw; self.version = version
        self.setWindowTitle("Safety Check")
        self.setMinimumWidth(420)
        self.sig = _Sig(); self.sig.progress.connect(self._progress); self.sig.done.connect(self._done)
        lay = QVBoxLayout(self); lay.setSpacing(8)
        self.head = QLabel("Check passwords, extensions, version and protection in one go."); self.head.setWordWrap(True)
        self.head.setStyleSheet("font-size:14px;font-weight:600;")
        lay.addWidget(self.head)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); self.bar.setVisible(False); self.bar.setFixedHeight(6); self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame); self.scroll.setMinimumHeight(260)
        self.box = QWidget(); self.bl = QVBoxLayout(self.box); self.bl.setSpacing(6); self.bl.addStretch(1)
        self.scroll.setWidget(self.box); lay.addWidget(self.scroll, 1)
        row = QHBoxLayout()
        self.go = QPushButton("Check now"); self.go.clicked.connect(self.start); row.addWidget(self.go)
        self.extb = QPushButton("Open extensions"); self.extb.clicked.connect(self._open_ext); row.addWidget(self.extb)
        self.pwb = QPushButton("Open passwords"); self.pwb.clicked.connect(self._open_pw); row.addWidget(self.pwb)
        lay.addLayout(row)
        self.running = False

    def _open_ext(self):
        self.accept()
        try: self.mw._safe_call(self.mw.show_extensions) if hasattr(self.mw, "show_extensions") else None
        except Exception: pass

    def _open_pw(self):
        self.accept()
        try: self.mw._safe_call(self.mw.show_password_manager) if hasattr(self.mw, "show_password_manager") else None
        except Exception: pass

    def _clear(self):
        while self.bl.count() > 1:
            it = self.bl.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def start(self):
        if self.running:
            return
        self.running = True; self.go.setEnabled(False); self.bar.setVisible(True); self._clear()
        mw = self.mw
        try:
            import sps_updater
            pw = [dict(e) for e in mw.password_manager.get_all()]
            exts = mw.extension_manager.get_all_extensions(); scripts = mw.extension_manager.get_all_scripts()
            settings = dict(mw.settings_data)
            ver = self.version
        except Exception as e:
            pw, exts, scripts, settings, ver = [], [], [], dict(getattr(mw, "settings_data", {})), "0"
            sps_updater = None

        def work():
            try:
                res = sps_safety.run_all(passwords=pw, extensions=exts, scripts=scripts, settings=settings, current_version=ver,
                                         fetch_page=sps_updater.fetch_page if sps_updater else (lambda: ""),
                                         best_valid_update=sps_updater.best_valid_update if sps_updater else (lambda p, v: None),
                                         progress=self.sig.progress.emit)
            except Exception as e:
                res = [("warn", "Safety Check", "Something went wrong: %s" % e)]
            self.sig.done.emit(res)
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, text):
        self.head.setText(text)

    def _done(self, results):
        self.running = False; self.go.setEnabled(True); self.go.setText("Check again"); self.bar.setVisible(False)
        bad, warn = sps_safety.summary(results)
        self.head.setText("⛔ %d serious problem(s), %d warning(s)" % (bad, warn) if bad else "⚠️ %d warning(s)" % warn if warn else "✅ Everything looks fine")
        order = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
        self._clear()
        for lvl, title, detail in sorted(results, key=lambda r: order.get(r[0], 9)):
            lab = QLabel("%s  <b>%s</b><br><span style='opacity:0.75'>%s</span>" % (ICON.get(lvl, ""), _esc(title), _esc(detail)))
            lab.setWordWrap(True); lab.setTextFormat(Qt.TextFormat.RichText)
            lab.setStyleSheet("padding:8px 10px;border-radius:12px;background:rgba(128,128,128,35);")
            self.bl.insertWidget(self.bl.count() - 1, lab)


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def show_safety_check(mw, version="0"):
    d = SafetyDialog(mw, version)
    d.exec()
