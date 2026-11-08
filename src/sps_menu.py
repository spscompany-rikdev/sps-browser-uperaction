"""Scrollable drop-down for long menus (the three-dot menu).  Qt's own QMenu does not scroll once a style sheet is applied, so a long menu was
cut off at the bottom of the screen.  This turns a QMenu's actions into a rounded popup with a scroll bar / mouse wheel.  Sub-menus open
beside the row.  Click outside or Esc closes it."""
from PyQt6.QtCore import Qt, QPoint, QEventLoop, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QScrollArea, QPushButton, QWidget, QApplication


class ScrollPopup(QFrame):
    def __init__(self, menu, theme, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        t = theme or {}
        bg, fg, bd, hv = t.get("bg_primary", "#ffffff"), t.get("text_primary", "#202124"), t.get("border", "#dadce0"), t.get("bg_tertiary", "#e8eaed")
        self.setObjectName("spsScrollMenu")
        self.setStyleSheet(
            "QFrame#spsScrollMenu{background:%s;border:1px solid %s;border-radius:12px;}"
            "QScrollArea{background:transparent;border:none;} QWidget#spsMenuBody{background:transparent;}"
            "QPushButton{background:transparent;color:%s;border:none;border-radius:8px;text-align:left;padding:7px 14px;font-size:13px;}"
            "QPushButton:hover{background:%s;} QPushButton:disabled{color:#9aa0a6;}"
            "QFrame#spsSep{background:%s;max-height:1px;min-height:1px;border:none;margin:4px 10px;}"
            "QScrollBar:vertical{background:transparent;width:10px;margin:4px 2px;} QScrollBar::handle:vertical{background:%s;border-radius:4px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}" % (bg, bd, fg, hv, bd, bd))
        outer = QVBoxLayout(self); outer.setContentsMargins(4, 6, 4, 6)
        self.scroll = QScrollArea(self); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget(); body.setObjectName("spsMenuBody"); self.col = QVBoxLayout(body); self.col.setContentsMargins(2, 0, 2, 0); self.col.setSpacing(0)
        self.scroll.setWidget(body); outer.addWidget(self.scroll)
        self.buttons = []; self.chosen = None; self._on_close = []
        self._fill(menu)
        self.col.addStretch(1)

    def _fill(self, menu):
        for act in menu.actions():
            if act.isSeparator():
                s = QFrame(); s.setObjectName("spsSep"); self.col.addWidget(s); continue
            sub = act.menu()
            b = QPushButton(act.text().replace("&", "") + ("      ▸" if sub else ""))
            b.setEnabled(act.isEnabled()); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(32)
            if sub is not None:
                b.clicked.connect(lambda _=False, bb=b, m=sub: self._open_sub(bb, m))
            else:
                b.clicked.connect(lambda _=False, a=act: self._run(a))
            self.col.addWidget(b); self.buttons.append((act, b))

    def _run(self, act):
        self.chosen = act
        cb = getattr(self, "chosen_cb", None)
        self.close()
        if cb is not None:
            cb(act)
        QTimer.singleShot(0, act.trigger)                 # run after the popup is gone so dialogs open normally

    def closeEvent(self, e):
        sub = getattr(self, "_sub", None)
        if sub is not None:
            try: sub.close()
            except RuntimeError: pass
        for cb in getattr(self, "_on_close", []):
            try: cb()
            except Exception: pass
        super().closeEvent(e)

    def _open_sub(self, btn, sub):
        """Open a sub-menu (Help, More Features ...) beside its row; it scrolls too and always stays on the screen."""
        old = getattr(self, "_sub", None)
        if old is not None:
            try: old.close()
            except RuntimeError: pass
        scr = QApplication.screenAt(btn.mapToGlobal(QPoint(0, 0))) or QApplication.primaryScreen()
        ag = scr.availableGeometry()
        sp = ScrollPopup(sub, None, None)
        sp.setStyleSheet(self.styleSheet())
        sp._fit(QPoint(0, ag.top()), scr, 12)
        row = btn.mapToGlobal(QPoint(0, 0))
        mine = self.mapToGlobal(QPoint(0, 0))
        x = mine.x() - sp.width() + 6                                     # to the left of this card (the card hangs at the right edge)
        if x < ag.left() + 4:
            x = min(mine.x() + self.width() - 6, ag.right() - sp.width() - 4)
        y = min(max(ag.top() + 4, row.y() - 6), ag.bottom() - sp.height() - 6)
        sp.move(x, y)
        sp._parent_pop = self
        sp.chosen_cb = lambda a, me=self: me._child_chose(a)
        self._sub = sp
        sp.show()

    def _child_chose(self, act):
        self.chosen = act
        self.close()

    def _fit(self, pos, screen, room):
        ag = screen.availableGeometry()
        body = self.scroll.widget(); body.adjustSize()
        w = max(260, body.sizeHint().width() + 30)
        h = min(body.sizeHint().height() + 16, max(200, ag.bottom() - pos.y() - room))
        self.setFixedSize(w, h)


def drop_menu(mw, menu, btn):
    """Open `menu` (a QMenu) under `btn` as a scrollable, animated drop-down. Returns the popup."""
    scr = QApplication.screenAt(btn.mapToGlobal(QPoint(0, 0))) or QApplication.primaryScreen()
    ag = scr.availableGeometry()
    tb = getattr(mw, "toolbar", None)
    bottom = tb.mapToGlobal(QPoint(0, tb.height())).y() if tb is not None and tb.isVisible() else btn.mapToGlobal(QPoint(0, btn.height())).y()
    y = max(ag.top(), bottom - 2)
    pop = ScrollPopup(menu, getattr(mw, "_theme", None), mw)
    pop._fit(QPoint(0, y), scr, 10)
    right = btn.mapToGlobal(QPoint(btn.width(), 0)).x()
    x = min(max(ag.left() + 4, right - pop.width()), ag.right() - pop.width() - 4)
    pop.move(x, y - 14)
    pop.show()
    try:
        pop.setWindowOpacity(0.0)
        g = QPropertyAnimation(pop, b"pos", pop); g.setDuration(170); g.setStartValue(QPoint(x, y - 14)); g.setEndValue(QPoint(x, y)); g.setEasingCurve(QEasingCurve.Type.OutCubic)
        f = QPropertyAnimation(pop, b"windowOpacity", pop); f.setDuration(150); f.setStartValue(0.0); f.setEndValue(1.0)
        pop._anims = (g, f); g.start(); f.start()
    except Exception:
        pass
    pop._menu = menu                                      # keep the QMenu (and its actions) alive while the popup is open
    pop.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    def _free(*_):
        try:
            menu.deleteLater()
        except RuntimeError:
            pass                                          # already gone (window closing)
    pop.destroyed.connect(_free)
    return pop


# ───────── every long menu of the browser (tab menu, profile menu, history menu ...) scrolls, not only the three-dot menu ─────────
_installed = {"done": False}


def install_global():
    """QMenu.exec(pos) of a menu that is too tall for the screen opens as a ScrollPopup instead (blocks and returns the chosen action like exec)."""
    if _installed["done"]:
        return
    from PyQt6.QtWidgets import QMenu
    orig = QMenu.exec

    def exec_(self, *args, **kw):
        try:
            if args and not isinstance(args[0], QPoint):
                return orig(self, *args, **kw)
            pos = args[0] if args else None
            if pos is None:
                from PyQt6.QtGui import QCursor
                pos = QCursor.pos()
            scr = QApplication.screenAt(pos) or QApplication.primaryScreen()
            ag = scr.availableGeometry()
            if self.sizeHint().height() + 12 <= ag.bottom() - max(pos.y(), ag.top()) or len(self.actions()) < 8:
                return orig(self, *args, **kw)               # fits: the normal menu
            if getattr(self, "_sps_long_open", False):
                return None
            self._sps_long_open = True
            try:
                pop = ScrollPopup(self, getattr(self.window(), "_theme", None) if hasattr(self.window(), "_theme") else None, None)
                pop._fit(pos, scr, 10)
                x = min(max(ag.left() + 4, pos.x()), ag.right() - pop.width() - 4)
                y = min(max(ag.top() + 4, pos.y()), ag.bottom() - pop.height() - 6)
                loop = QEventLoop()
                pop._on_close.append(loop.quit)
                pop.move(x, y); pop.show()
                loop.exec()
                act = pop.chosen
                return act
            finally:
                self._sps_long_open = False
        except Exception:
            return orig(self, *args, **kw)
    QMenu.exec = exec_
    _installed["done"] = True


# ───────── the ⋮ button turns into the browser logo while its menu is open ─────────
class Morph:
    """Rotates the three dots by half a turn while cross-fading them into the SPS Browser logo (and back when the menu closes)."""
    def __init__(self, btn, logo_icon, color_fn):
        from PyQt6.QtCore import QVariantAnimation, QEasingCurve
        self.btn, self.logo, self.color_fn, self.t = btn, logo_icon, color_fn, 0.0
        self.anim = QVariantAnimation(btn); self.anim.setDuration(420)
        self.anim.valueChanged.connect(self._set)
        btn.setText(""); btn.setIconSize(btn.size() * 0.72)
        self._set(0.0)

    def _set(self, v):
        from PyQt6.QtGui import QIcon
        self.t = float(v); self.btn.setIcon(QIcon(self._frame(self.t)))

    def _frame(self, t):
        from PyQt6.QtGui import QPixmap, QPainter, QColor
        from PyQt6.QtCore import Qt, QRectF
        d = 40
        dpr = max(1.0, float(self.btn.devicePixelRatioF()))
        pm = QPixmap(int(d * dpr), int(d * dpr)); pm.setDevicePixelRatio(dpr); pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm); p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(d / 2, d / 2); p.rotate(180.0 * t)
        c = QColor(self.color_fn())
        # dots (fade out, shrink a little)
        p.setOpacity(max(0.0, 1.0 - t * 1.4)); p.setPen(Qt.PenStyle.NoPen); p.setBrush(c)
        r = 2.6 * (1.0 - 0.3 * t)
        for dy in (-9, 0, 9):
            p.drawEllipse(QRectF(-r, dy - r, 2 * r, 2 * r))
        # logo (fade in, grow)
        p.setOpacity(max(0.0, min(1.0, (t - 0.25) / 0.75)))
        if self.logo is not None and not self.logo.isNull():
            s = d * (0.55 + 0.4 * t)
            p.rotate(-180.0)                                    # the logo ends upright
            self.logo.paint(p, int(-s / 2), int(-s / 2), int(s), int(s))
        p.end()
        return pm

    def go(self, opened):
        from PyQt6.QtCore import QEasingCurve
        self.anim.stop()
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack if opened else QEasingCurve.Type.InOutCubic)
        self.anim.setStartValue(self.t); self.anim.setEndValue(1.0 if opened else 0.0)
        self.anim.setDuration(420 if opened else 300)
        self.anim.start()

    def refresh(self):
        self._set(self.t)
