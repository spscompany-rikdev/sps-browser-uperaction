"""SPS Browser V40 - Chrome-style window top: round tabs sit in the title bar, left of the minimise / maximise / close buttons.

How it works (so it can be repaired without guessing):
  * SpsTabWidget is a normal QTabWidget (the whole browser keeps using .addTab/.widget/.tabText ... unchanged) whose own tab bar is
    hidden. A second QTabBar ("strip") that lives in the title bar mirrors it: tabs added/removed/renamed/moved/selected in
    either one are copied to the other.
  * TitleStrip is the row at the very top: [round tabs][+][empty draggable space][- [] x].
  * The window is frameless; moving and resizing use the operating system's own routines (startSystemMove / startSystemResize),
    so Windows snapping, Aero-shake and double-click-to-maximise keep working.
  * Anything goes wrong -> install() returns False and the normal window frame and tab bar stay as they were.
"""
from PyQt6.QtCore import Qt, QSize, QPoint, QEvent, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor
from PyQt6.QtWidgets import (QTabWidget, QTabBar, QWidget, QHBoxLayout, QToolButton, QSizePolicy, QApplication)

STRIP_HEIGHT = 46
GRIP = 6                                    # width of the invisible resize edges


class SpsTabWidget(QTabWidget):
    """QTabWidget + a mirrored round tab bar for the title bar (self.strip)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.strip = QTabBar()
        self.strip.setObjectName("spsStrip")
        self.strip.setExpanding(False)
        self.strip.setDrawBase(False)
        self.strip.setMovable(True)
        self.strip.setTabsClosable(True)
        self.strip.setUsesScrollButtons(True)
        self.strip.setElideMode(Qt.TextElideMode.ElideRight)
        self.strip.setDocumentMode(True)
        self.strip.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.strip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._mirror = False
        self._use_strip = False
        QTabWidget.tabBar(self).hide()
        self.strip.currentChanged.connect(self._strip_current)
        self.strip.tabCloseRequested.connect(lambda i: self.tabCloseRequested.emit(i))
        self.strip.tabMoved.connect(self._strip_moved)
        self.currentChanged.connect(self._widget_current)

    # ---- structure: copy into the strip ----
    def tabInserted(self, index):
        super().tabInserted(index)
        self._mirror = True
        try:
            self.strip.insertTab(index, self.tabIcon(index), self.tabText(index))
            self.strip.setTabToolTip(index, self.tabToolTip(index))
        finally:
            self._mirror = False
        self._sync_current()

    def tabRemoved(self, index):
        super().tabRemoved(index)
        self._mirror = True
        try:
            if 0 <= index < self.strip.count():
                self.strip.removeTab(index)
        finally:
            self._mirror = False
        self._sync_current()

    def setTabText(self, index, text):
        super().setTabText(index, text)
        if 0 <= index < self.strip.count():
            self.strip.setTabText(index, text)

    def setTabToolTip(self, index, tip):
        super().setTabToolTip(index, tip)
        if 0 <= index < self.strip.count():
            self.strip.setTabToolTip(index, tip)

    def setTabIcon(self, index, icon):
        super().setTabIcon(index, icon)
        if 0 <= index < self.strip.count():
            self.strip.setTabIcon(index, icon)

    def setTabTextColor(self, index, color):
        """Both bars (the browser colours sleeping tabs grey)."""
        for bar in (QTabWidget.tabBar(self), self.strip):
            if 0 <= index < bar.count():
                bar.setTabTextColor(index, color)

    def move_tab(self, src, dst):
        QTabWidget.tabBar(self).moveTab(src, dst)           # moves the page itself (QTabWidget listens to its own bar)
        self._mirror = True
        try:
            self.strip.moveTab(src, dst)
        finally:
            self._mirror = False

    def tab_at(self, pos):
        """pos is in strip coordinates."""
        return self.strip.tabAt(pos)

    # ---- selection and dragging stay in step ----
    def _sync_current(self):
        if self.strip.currentIndex() != self.currentIndex() and 0 <= self.currentIndex() < self.strip.count():
            self._mirror = True
            try:
                self.strip.setCurrentIndex(self.currentIndex())
            finally:
                self._mirror = False

    def _widget_current(self, i):
        self._sync_current()

    def _strip_current(self, i):
        if self._mirror or i < 0:
            return
        if i != self.currentIndex():
            self.setCurrentIndex(i)

    def _strip_moved(self, src, dst):
        if self._mirror:
            return
        QTabWidget.tabBar(self).moveTab(src, dst)

    # ---- which bar is visible ----
    def use_strip(self, on):
        """True: the round bar in the title bar. False: Qt's own bar inside the page area (vertical-tabs mode, safe fallback)."""
        self._use_strip = bool(on)
        QTabWidget.tabBar(self).setVisible(not on)

    def setTabPosition(self, pos):
        super().setTabPosition(pos)
        if self._use_strip:                                   # vertical tabs need Qt's own bar
            vertical = pos in (QTabWidget.TabPosition.West, QTabWidget.TabPosition.East)
            QTabWidget.tabBar(self).setVisible(vertical)
            self.strip.setVisible(not vertical)
            if hasattr(self, "_title_strip"):
                self._title_strip.tab_host.setVisible(not vertical)


def _x_icon(color, bg=None):
    """A small round-cornered 'x' written once to the temp folder (style sheets can only point at files)."""
    import os, tempfile
    from PyQt6.QtGui import QPixmap
    name = "sps_tabx_%s_%s.png" % (color.lstrip("#"), (bg or "none").lstrip("#"))
    path = os.path.join(tempfile.gettempdir(), name)
    if not os.path.exists(path):
        pm = QPixmap(36, 36); pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if bg:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(bg)); p.drawEllipse(2, 2, 32, 32)
        pen = QPen(QColor(color), 3.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
        p.drawLine(12, 12, 24, 24); p.drawLine(24, 12, 12, 24); p.end()
        pm.save(path)
    return path.replace("\\", "/")


def pill_style(t, accent):
    """Round tabs. t = theme dict."""
    try:
        x1 = _x_icon(t["text_secondary"]); x2 = _x_icon(t["text_primary"], t["hover"])
    except Exception:
        x1 = x2 = ""
    return f"""
        QTabBar#spsStrip{{background:transparent;}}
        QTabBar#spsStrip::tab{{background:{t['tab_inactive']};color:{t['text_secondary']};
            min-width:96px;max-width:230px;height:32px;margin:7px 2px 7px 2px;padding:0 12px 0 16px;
            border:1px solid transparent;border-radius:16px;font-size:13px;}}
        QTabBar#spsStrip::tab:hover{{background:{t['hover']};}}
        QTabBar#spsStrip::tab:selected{{background:{t['tab_active']};color:{t['text_primary']};font-weight:600;
            border:1px solid {t['border']};}}
        QTabBar#spsStrip::close-button{{subcontrol-position:right;width:18px;height:18px;margin-right:2px;image:url({x1});}}
        QTabBar#spsStrip::close-button:hover{{image:url({x2});}}
        QTabBar#spsStrip QToolButton{{background:transparent;border:none;}}
    """


class _WinButton(QToolButton):
    def __init__(self, kind, t, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.t = t
        self.setFixedSize(46, 34)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._hover = False
        self.maximized = False

    def enterEvent(self, e):
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        fg = QColor(self.t["text_primary"])
        if self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            if self.kind == "close":
                p.setBrush(QColor("#e81123")); fg = QColor("#ffffff")
            else:
                p.setBrush(QColor(self.t["hover"]))
            p.drawRoundedRect(r, 9, 9)
        pen = QPen(fg, 1.4); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
        c = QRectF(self.rect()).center()
        if self.kind == "min":
            p.drawLine(int(c.x() - 5), int(c.y() + 2), int(c.x() + 5), int(c.y() + 2))
        elif self.kind == "max":
            if self.maximized:
                p.drawRect(QRectF(c.x() - 4, c.y() - 2, 7, 7)); p.drawLine(int(c.x() - 2), int(c.y() - 4), int(c.x() + 5), int(c.y() - 4))
                p.drawLine(int(c.x() + 5), int(c.y() - 4), int(c.x() + 5), int(c.y() + 3))
            else:
                p.drawRect(QRectF(c.x() - 5, c.y() - 5, 10, 10))
        else:
            p.drawLine(int(c.x() - 5), int(c.y() - 5), int(c.x() + 5), int(c.y() + 5))
            p.drawLine(int(c.x() - 5), int(c.y() + 5), int(c.x() + 5), int(c.y() - 5))


class TitleStrip(QWidget):
    """[round tabs][+][drag space][- [] x]"""

    def __init__(self, mw, tabs, t, accent):
        super().__init__(mw)
        self.mw = mw
        self.setObjectName("spsTitleStrip")
        self.setFixedHeight(STRIP_HEIGHT)
        self.setStyleSheet(f"QWidget#spsTitleStrip{{background:{t['bg_secondary']};border-bottom:1px solid {t['border']};}}")
        lay = QHBoxLayout(self); lay.setContentsMargins(10, 0, 4, 0); lay.setSpacing(0)
        self.tab_host = QWidget(); hl = QHBoxLayout(self.tab_host); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(2)
        tabs.strip.setStyleSheet(pill_style(t, accent))
        hl.addWidget(tabs.strip)
        self.plus = QToolButton(); self.plus.setText("＋"); self.plus.setFixedSize(32, 32)
        self.plus.setToolTip("New tab (Ctrl+T)"); self.plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plus.setStyleSheet(f"QToolButton{{background:transparent;color:{t['text_primary']};border:none;border-radius:16px;font-size:18px;}}"
                                f"QToolButton:hover{{background:{t['hover']};}}")
        self.plus.clicked.connect(lambda: mw.add_new_tab())
        hl.addWidget(self.plus)
        lay.addWidget(self.tab_host, 0)
        lay.addStretch(1)
        self.b_min = _WinButton("min", t, self); self.b_max = _WinButton("max", t, self); self.b_close = _WinButton("close", t, self)
        self.b_min.clicked.connect(mw.showMinimized)
        self.b_max.clicked.connect(self.toggle_max)
        self.b_close.clicked.connect(mw.close)
        for b, tip in ((self.b_min, "Minimise"), (self.b_max, "Maximise / restore"), (self.b_close, "Close")):
            b.setToolTip(tip); lay.addWidget(b)

    def toggle_max(self):
        mw = self.mw
        if mw.isMaximized():
            mw.showNormal()
        else:
            mw.showMaximized()

    def sync_state(self):
        self.b_max.maximized = self.mw.isMaximized()
        self.b_max.update()

    # ---- empty space moves the window; double-click maximises ----
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            h = self.mw.windowHandle()
            if h is not None and not self.mw.isFullScreen():
                try:
                    h.startSystemMove(); e.accept(); return
                except Exception:
                    pass
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.toggle_max(); e.accept()
        else:
            super().mouseDoubleClickEvent(e)


class _EdgeGrip(QWidget):
    """Invisible strip along a window edge: shows the resize cursor and starts the system resize."""
    CURSORS = {
        Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor, Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor, Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
    }

    def __init__(self, mw, edges):
        super().__init__(mw)
        self.mw = mw; self.edges = edges
        c = Qt.CursorShape.SizeFDiagCursor
        if edges == (Qt.Edge.TopEdge | Qt.Edge.RightEdge) or edges == (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
            c = Qt.CursorShape.SizeBDiagCursor
        if edges in self.CURSORS:
            c = self.CURSORS[edges]
        self.setCursor(c)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            h = self.mw.windowHandle()
            if h is not None:
                try:
                    h.startSystemResize(self.edges)
                except Exception:
                    pass


class FrameController:
    """Keeps the 8 edge grips in place and the maximise icon right."""

    def __init__(self, mw, strip):
        self.mw = mw; self.strip = strip
        E = Qt.Edge
        self.grips = {
            "l": _EdgeGrip(mw, E.LeftEdge), "r": _EdgeGrip(mw, E.RightEdge),
            "t": _EdgeGrip(mw, E.TopEdge), "b": _EdgeGrip(mw, E.BottomEdge),
            "tl": _EdgeGrip(mw, E.TopEdge | E.LeftEdge), "tr": _EdgeGrip(mw, E.TopEdge | E.RightEdge),
            "bl": _EdgeGrip(mw, E.BottomEdge | E.LeftEdge), "br": _EdgeGrip(mw, E.BottomEdge | E.RightEdge),
        }
        mw.installEventFilter(self_filter(self))
        self.place()

    def place(self):
        mw = self.mw; w, h = mw.width(), mw.height(); g = GRIP
        on = not (mw.isMaximized() or mw.isFullScreen())
        geo = {"l": (0, g, g, h - 2 * g), "r": (w - g, g, g, h - 2 * g), "t": (g, 0, w - 2 * g, g), "b": (g, h - g, w - 2 * g, g),
               "tl": (0, 0, g, g), "tr": (w - g, 0, g, g), "bl": (0, h - g, g, g), "br": (w - g, h - g, g, g)}
        for k, grip in self.grips.items():
            x, y, ww, hh = geo[k]
            grip.setGeometry(x, y, max(1, ww), max(1, hh))
            grip.setVisible(on)
            if on:
                grip.raise_()
        self.strip.sync_state()


def self_filter(ctrl):
    from PyQt6.QtCore import QObject

    class _F(QObject):
        def eventFilter(self, obj, ev):
            if obj is ctrl.mw and ev.type() in (QEvent.Type.Resize, QEvent.Type.WindowStateChange, QEvent.Type.Show):
                try:
                    ctrl.place()
                except Exception:
                    pass
            return False
    f = _F(ctrl.mw)
    ctrl._filter = f
    return f


def install(mw, tabs, t, accent):
    """Turn the window into a Chrome-style one. Returns the TitleStrip or None (nothing changed)."""
    try:
        if not isinstance(tabs, SpsTabWidget):
            return None
        mw.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        strip = TitleStrip(mw, tabs, t, accent)
        tabs._title_strip = strip
        mw.setMenuWidget(strip)
        tabs.use_strip(True)
        mw._sps_frame = FrameController(mw, strip)
        return strip
    except Exception:
        try:
            tabs.use_strip(False)
        except Exception:
            pass
        return None
