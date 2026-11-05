"""Animations + scrolling + Chrome-style icons for SPS Browser (desktop).

* every menu / popup / window fades + slides in (app-wide event filter, 140-180 ms, can be switched off with setting `animations`)
* the toolbar buttons get crisp vector icons and a small press "pulse"
* the 3-dot menu button spins while the menu is open and morphs into the SPS Browser logo (and back when it closes)
* long menus scroll, dialogs that are taller than the screen (or have no scroll of their own) get a scroll area
Everything is wrapped in try/except: a failure here can never break the browser."""
import math
from PyQt6.QtCore import Qt, QEvent, QObject, QPoint, QPropertyAnimation, QEasingCurve, QVariantAnimation, QTimer, QSize, QRectF, QByteArray
from PyQt6.QtGui import QPainter, QColor, QPixmap
from PyQt6.QtWidgets import (QApplication, QMenu, QDialog, QPushButton, QToolButton, QScrollArea, QWidget, QFrame, QAbstractScrollArea,
                             QTabWidget, QLabel, QMessageBox, QFileDialog, QColorDialog, QInputDialog, QFontDialog, QToolBar)

import sps_icons

_state = {"on": True, "filter": None}
ICON_MAP = {"☰": "menu", "←": "back", "→": "forward", "↻": "reload", "✕": "close", "🏠": "home", "⭐": "star", "−": "minus",
            "＋": "plus", "⋮": "more", "⚡": "bolt", "🔒": "lock", "⬇": "download"}


def enabled():
    return _state["on"]


def set_enabled(on):
    _state["on"] = bool(on)


# ───────────────────────── fade / slide in ─────────────────────────
def animate_in(w, dy=8, ms=150):
    """Fade (+ slide a few px) a top-level widget that was just shown."""
    if not _state["on"] or getattr(w, "_sps_anim_busy", False):
        return
    try:
        w._sps_anim_busy = True
        end = w.pos()
        w.setWindowOpacity(0.0)
        a = QPropertyAnimation(w, QByteArray(b"windowOpacity"), w); a.setDuration(ms); a.setStartValue(0.0); a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        g = None
        if dy:
            w.move(end.x(), end.y() - dy)
            g = QPropertyAnimation(w, QByteArray(b"pos"), w); g.setDuration(ms + 40); g.setStartValue(QPoint(end.x(), end.y() - dy))
            g.setEndValue(end); g.setEasingCurve(QEasingCurve.Type.OutCubic)
        def done():
            try:
                w.setWindowOpacity(1.0); w._sps_anim_busy = False
            except Exception:
                pass
        a.finished.connect(done)
        w._sps_anims = (a, g)
        a.start()
        if g: g.start()
    except Exception:
        try: w._sps_anim_busy = False; w.setWindowOpacity(1.0)
        except Exception: pass


def _wrap_scroll(dlg):
    """Give a dialog a scroll area when it has none of its own (only when its content could not fit)."""
    try:
        if getattr(dlg, "_sps_scroll_done", False):
            return
        dlg._sps_scroll_done = True
        lay = dlg.layout()
        if lay is None:
            return
        for c in dlg.findChildren(QAbstractScrollArea):
            if c.isVisibleTo(dlg) and c.height() > 120:
                return                                               # already scrolls by itself
        if dlg.findChild(QTabWidget) is not None:
            return
        scr = QApplication.screenAt(dlg.pos()) or QApplication.primaryScreen()
        avail = scr.availableGeometry() if scr else None
        need_h = lay.sizeHint().height() + 8
        if avail is not None and need_h <= avail.height() * 0.86 and dlg.minimumHeight() <= avail.height() * 0.86:
            # fits: still make it scrollable (for small screens / zoom), but without changing the look
            pass
        holder = QWidget(); holder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        tmp = QWidget(); tmp.setLayout(lay)                          # detach the old layout from the dialog
        holder.setLayout(lay); tmp.deleteLater()
        sa = QScrollArea(dlg); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setStyleSheet("QScrollArea{background:transparent;border:none;}QScrollArea>QWidget>QWidget{background:transparent;}"
                         "QScrollBar:vertical{width:8px;background:transparent;margin:2px;}"
                         "QScrollBar::handle:vertical{background:rgba(128,128,128,110);border-radius:4px;min-height:30px;}"
                         "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        sa.setWidget(holder)
        from PyQt6.QtWidgets import QVBoxLayout
        outer = QVBoxLayout(dlg); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(sa)
        if avail is not None and need_h > avail.height() * 0.9:
            dlg.setMinimumHeight(0)
            h = int(avail.height() * 0.88)
            dlg.resize(dlg.width(), h)
            QTimer.singleShot(0, lambda: dlg.resize(dlg.width(), h))     # after the pending layout pass
    except Exception as e:
        print('[SPS V40] scroll wrap:', e)


MENU_SCROLL_QSS = "QMenu{menu-scrollable:1;}"


class _Global(QObject):
    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow() and _state["on"]:
                if isinstance(obj, QMenu):
                    if not obj.property("_sps_scroll"):
                        obj.setProperty("_sps_scroll", True)
                        sc = QApplication.screenAt(obj.pos()) or QApplication.primaryScreen()
                        if sc: obj.setMaximumHeight(int(sc.availableGeometry().height() * 0.92))
                        obj.setStyleSheet((obj.styleSheet() or "") + MENU_SCROLL_QSS)
                    animate_in(obj, 6, 130)
                elif isinstance(obj, (QMessageBox, QFileDialog, QColorDialog, QInputDialog, QFontDialog)):
                    animate_in(obj, 0, 140)
                elif isinstance(obj, QDialog):
                    if type(obj).__name__ != "DropdownHost":
                        _wrap_scroll(obj)
                    animate_in(obj, 10, 170)
                elif type(obj).__name__ == "EasyPanel":
                    animate_in(obj, 8, 150)
            elif t == QEvent.Type.MouseButtonPress and isinstance(obj, (QPushButton, QToolButton)) and _state["on"]:
                if not obj.icon().isNull() and not getattr(obj, "_sps_pulse_busy", False):
                    _pulse(obj)
        except Exception:
            pass
        return False


def _pulse(btn):
    try:
        base = btn.iconSize()
        btn._sps_pulse_busy = True
        a = QVariantAnimation(btn); a.setDuration(220); a.setStartValue(1.0); a.setKeyValueAt(0.35, 0.78); a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutQuad)
        a.valueChanged.connect(lambda v: btn.setIconSize(QSize(max(4, int(base.width() * v)), max(4, int(base.height() * v)))))
        def fin():
            btn.setIconSize(base); btn._sps_pulse_busy = False
        a.finished.connect(fin); a.start(); btn._sps_pulse = a
    except Exception:
        btn._sps_pulse_busy = False


def install_global():
    app = QApplication.instance()
    if app is None or _state["filter"] is not None:
        return
    f = _Global(app); app.installEventFilter(f); _state["filter"] = f


# ───────────────────────── icons on the toolbar ─────────────────────────
def _color(mw):
    try:
        return mw._theme["text_primary"]
    except Exception:
        return "#5f6368"


def style_icon_button(btn, name, color, size=20):
    QPushButton.setText(btn, "")
    btn.setIcon(sps_icons.icon(name, color, size)); btn.setIconSize(QSize(size, size))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn._sps_icon_name = name


def apply_toolbar_icons(mw):
    col = _color(mw)
    for w in mw.toolbar.findChildren(QPushButton):
        try:
            txt = w.text()
            if txt in ICON_MAP:
                name = ICON_MAP[txt]
                if w is getattr(mw, "menu_btn", None):
                    continue
                if w is getattr(mw, "lock_btn", None):
                    col2 = getattr(mw, "_theme", {}).get("success", col)
                    style_icon_button(w, "lock", col2, 17); continue
                style_icon_button(w, name, col, 21 if name not in ("minus", "plus") else 18)
                w._sps_orig_text = txt
        except Exception:
            pass
    rb = getattr(mw, "reload_btn", None)
    if rb is not None:
        try:
            store = {"t": "↻"}
            def setText(t, _b=rb):
                store["t"] = t
                style_icon_button(_b, ICON_MAP.get(t, "reload"), _color(mw), 21)
            rb.setText = setText; rb.text = lambda: store["t"]
        except Exception:
            pass


# ───────────────────────── ⋮ → SPS logo ─────────────────────────
def _logo_pixmap(mw, size):
    try:
        import SPS_BROWSER as _m
        fn = getattr(_m, "_sps_load_app_icon", None)
    except Exception:
        fn = None
    if fn is None:
        fn = mw.__class__.__init__.__globals__.get("_sps_load_app_icon")
    try:
        ic = fn() if fn else None
        if ic is not None and not ic.isNull():
            return ic.pixmap(size, size)
    except Exception:
        pass
    px = QPixmap(size * 2, size * 2); px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    from PyQt6.QtGui import QLinearGradient, QBrush, QFont
    g = QLinearGradient(0, 0, px.width(), px.height()); g.setColorAt(0, QColor("#1a73e8")); g.setColorAt(1, QColor("#8ab4f8"))
    p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(2, 2, px.width() - 4, px.height() - 4)
    p.setPen(QColor("white")); f = QFont(); f.setBold(True); f.setPixelSize(int(size * 1.25)); p.setFont(f)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "S"); p.end(); px.setDevicePixelRatio(2.0)
    return px


class MenuButtonFx(QObject):
    """Paints the ⋮ button itself: dots rotate 0->180deg while cross-fading to the SPS logo; reverse when the menu closes."""
    def __init__(self, mw, btn):
        super().__init__(btn)
        self.mw, self.btn, self.p = mw, btn, 0.0
        self.anim = QVariantAnimation(self); self.anim.setDuration(320); self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.valueChanged.connect(self._tick)
        QPushButton.setText(btn, "")
        self._orig_paint = btn.paintEvent
        btn.paintEvent = self.paint
        self._logo = None

    def _tick(self, v):
        self.p = float(v); self.btn.update()

    def go(self, forward):
        if not _state["on"]:
            self.p = 1.0 if forward else 0.0; self.btn.update(); return
        self.anim.stop(); self.anim.setStartValue(self.p); self.anim.setEndValue(1.0 if forward else 0.0)
        self.anim.setDuration(int(320 * max(0.25, abs((1.0 if forward else 0.0) - self.p)))); self.anim.start()

    def paint(self, ev):
        b = self.btn
        QPushButton.paintEvent(b, ev)
        p = QPainter(b); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        s = 22; cx, cy = b.width() / 2, b.height() / 2
        col = _color(self.mw)
        if self._logo is None:
            self._logo = _logo_pixmap(self.mw, 40)
        # dots
        if self.p < 0.999:
            p.save(); p.translate(cx, cy); p.rotate(180 * self.p); p.setOpacity(1.0 - self.p)
            sc = 1.0 - 0.25 * self.p; p.scale(sc, sc)
            px = sps_icons.pixmap("more", col, s); p.drawPixmap(QRectF(-s / 2, -s / 2, s, s), px, QRectF(px.rect())); p.restore()
        if self.p > 0.001:
            p.save(); p.translate(cx, cy); p.rotate(-180 + 180 * self.p); p.setOpacity(self.p)
            sc = 0.55 + 0.45 * self.p; p.scale(sc, sc); L = 24
            p.drawPixmap(QRectF(-L / 2, -L / 2, L, L), self._logo, QRectF(self._logo.rect())); p.restore()
        p.end()


def install_menu_button(mw):
    btn = getattr(mw, "menu_btn", None)
    if btn is None or hasattr(btn, "_sps_fx"):
        return
    fx = MenuButtonFx(mw, btn); btn._sps_fx = fx
    orig = mw._show_main_menu

    def wrapped(*a, **k):
        fx.go(True)
        try:
            return orig(*a, **k)
        finally:
            fx.go(False)
    mw._show_main_menu = wrapped


def install(mw):
    """Called once per MainWindow after it is built."""
    try:
        try:
            _state["on"] = mw.settings_data.get("animations", True) is not False
        except Exception:
            pass
        install_global()
        apply_toolbar_icons(mw)
        install_menu_button(mw)
    except Exception as e:                                     # pragma: no cover
        print("[SPS V40] anim install:", e)
