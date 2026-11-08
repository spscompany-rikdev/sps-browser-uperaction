"""SPS Browser V40 - the little "site controls" button in the toolbar.

One click shows every permission Chrome has for the website you are on, each as an on / off switch.
Nothing is on by itself: a website can do nothing until you switch it on here or answer its request.

The choices are saved per website in the profile's SitePermissionStore (the same store the 'Site Permissions' dialog and the
"site wants to ..." prompts use), so all three always agree.
"""
from PyQt6.QtCore import Qt, QRectF, QPoint, QUrl
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QAbstractButton,
                             QApplication)

# (key, icon, title, what it does)  - ON = allowed.  Not on => the site has to ask (and you can say no).
PERMISSIONS = [
    ("geolocation",   "📍", "Location",                "Know where you are"),
    ("camera",        "📷", "Camera",                  "Use your camera"),
    ("microphone",    "🎤", "Microphone",              "Use your microphone"),
    ("notifications", "🔔", "Notifications",           "Show notifications"),
    ("screen",        "🖥️", "Screen sharing",          "See your screen (and its sound)"),
    ("clipboard",     "📋", "Clipboard",               "Read and write what you copied"),
    ("fonts",         "🔤", "Fonts on this computer",  "See your installed fonts"),
    ("mouse_lock",    "🖱️", "Hide / lock the pointer", "Games and 3D pages"),
    ("files",         "📎", "File upload",             "Open the file picker"),
    ("filesystem",    "🗂️", "Files and folders",       "Read or change files you pick"),
    ("download",      "📥", "Downloads",               "Save files to your computer"),
    ("fullscreen",    "⛶",  "Full screen",             "Cover the whole screen"),
    ("protocol",      "🔗", "Open apps",               "Open links in other programs"),
]
# (key, icon, title, what it does, default_on)  - these change how the page runs
FEATURES = [
    ("js",       "⚙️", "JavaScript",           "Run the page's programs",      True),
    ("images",   "🖼️", "Images",               "Load pictures",                True),
    ("sound",    "🔊", "Sound",                "Let the page play audio",      True),
    ("popups",   "🪟", "Pop-ups and redirects", "Open extra windows",           False),
    ("autoplay", "▶️", "Autoplay",             "Start videos by themselves",   False),
    ("insecure", "⚠️", "Insecure content",     "Load http items inside https", False),
]
NOT_AVAILABLE = ["USB devices", "Serial ports", "Bluetooth", "HID devices", "MIDI devices", "Motion sensors",
                 "Background sync", "Payment handlers"]
RELOAD_KEYS = {"js", "images", "popups", "autoplay", "insecure"}


class Switch(QAbstractButton):
    def __init__(self, on, accent, off_color, parent=None):
        super().__init__(parent)
        self.setCheckable(True); self.setChecked(on)
        self.accent = QColor(accent); self.off = QColor(off_color)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.accent if self.isChecked() else self.off)
        p.drawRoundedRect(QRectF(0, 0, 44, 24), 12, 12)
        p.setBrush(QColor("#ffffff"))
        x = 22 if self.isChecked() else 2
        p.drawEllipse(QRectF(x, 2, 20, 20))


def site_of(mw):
    """(host, page) of the current tab, or (None, None) when it is not a website."""
    try:
        br = mw.tabs.currentWidget()
        u = br.url()
        if u.scheme() in ("http", "https") and u.host():
            return u.host().lower(), br.page()
    except Exception:
        pass
    return None, None


def is_on(store, host, key, default_on=False):
    v = store.get(host, key)
    if key in ("camera", "microphone", "screen"):
        return v == "allow"
    if v == "allow":
        return True
    if v == "deny":
        return False
    return default_on


def set_value(store, host, key, on, default_on=False):
    """The one place that writes a choice. Perms: on -> allow, off -> ask again. Features: stored only when different from the default."""
    if key in dict((k, 0) for k, *_ in PERMISSIONS):
        if on:
            store.set(host, key, "allow")
        else:
            store.remove(host, key)
        if key == "screen":                                  # screen sharing with sound is the same switch
            (store.set(host, "screen_audio", "allow") if on else store.remove(host, "screen_audio"))
        if key in ("camera", "microphone"):                  # camera+microphone together are allowed only when both are
            both = store.get(host, "camera") == "allow" and store.get(host, "microphone") == "allow"
            (store.set(host, "camera_mic", "allow") if both else store.remove(host, "camera_mic"))
    else:
        store.remove(host, key)
        if on != default_on:
            store.set(host, key, "allow" if on else "deny")


def block_all(store, host):
    for key, *_ in PERMISSIONS:
        store.set(host, key, "deny")
    for k in ("camera_mic", "screen_audio"):
        store.set(host, k, "deny")


def reset_site(store, host):
    for key in list(store.data.get(host, {}).keys()):
        store.remove(host, key)


class SitePanel(QFrame):
    def __init__(self, mw, host, page):
        super().__init__(mw, Qt.WindowType.Popup)
        self.mw = mw; self.host = host; self.page = page
        self.store = mw.permission_store
        t = mw._theme
        self.accent = mw.settings_data.get("accent_color", t["accent"])
        self.t = t
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedWidth(420)
        self.setObjectName("spsSitePanel")
        self.setStyleSheet(
            f"QFrame#spsSitePanel{{background:{t['bg_primary']};border:1px solid {t['border']};border-radius:16px;}}"
            f"QLabel{{color:{t['text_primary']};background:transparent;}}"
            f"QPushButton{{background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};"
            f"border-radius:14px;padding:7px 14px;font-weight:600;}}QPushButton:hover{{background:{t['hover']};}}"
            f"QScrollArea{{border:none;background:transparent;}}")
        self.changed = False
        outer = QVBoxLayout(self); outer.setContentsMargins(16, 14, 16, 14); outer.setSpacing(8)
        h = QLabel("🛡️  " + host); h.setStyleSheet(f"font-size:16px;font-weight:700;color:{t['text_primary']};")
        outer.addWidget(h)
        sub = QLabel("Everything is off until you allow it. A site can do nothing here without your say-so.")
        sub.setWordWrap(True); sub.setStyleSheet(f"font-size:12px;color:{t['text_secondary']};")
        outer.addWidget(sub)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        body = QWidget(); self.bl = QVBoxLayout(body); self.bl.setContentsMargins(0, 4, 6, 4); self.bl.setSpacing(2)
        sc.setWidget(body); outer.addWidget(sc, 1)
        self._section("Permissions")
        for key, icon, title, tip in PERMISSIONS:
            self._row(key, icon, title, tip, False, perm=True)
        self._section("Site settings")
        for key, icon, title, tip, dflt in FEATURES:
            self._row(key, icon, title, tip, dflt, perm=False)
        self._section("Not available in SPS Browser - always blocked")
        na = QLabel("  ·  ".join(NOT_AVAILABLE)); na.setWordWrap(True)
        na.setStyleSheet(f"font-size:12px;color:{t['text_secondary']};padding:2px 4px;")
        self.bl.addWidget(na)
        self.bl.addStretch(1)
        self.note = QLabel("Reload the page to apply the change."); self.note.setStyleSheet(f"color:{self.accent};font-weight:600;font-size:12px;")
        self.note.hide(); outer.addWidget(self.note)
        row = QHBoxLayout(); row.setSpacing(6)
        for text, fn in (("Block all", self._block_all), ("Reset", self._reset), ("Reload", self._reload), ("All sites…", self._all_sites)):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        outer.addLayout(row)
        self.setMinimumHeight(300)
        self.resize(420, min(640, max(420, int(self.mw.height() * 0.8))))

    def _section(self, text):
        l = QLabel(text.upper()); l.setStyleSheet(f"font-size:11px;font-weight:700;letter-spacing:1px;color:{self.t['text_secondary']};padding:10px 4px 4px 4px;")
        self.bl.addWidget(l)

    def _row(self, key, icon, title, tip, default_on, perm):
        w = QWidget(); hl = QHBoxLayout(w); hl.setContentsMargins(4, 5, 4, 5); hl.setSpacing(10)
        ic = QLabel(icon); ic.setFixedWidth(26); ic.setStyleSheet("font-size:17px;"); hl.addWidget(ic)
        col = QVBoxLayout(); col.setSpacing(0)
        a = QLabel(title); a.setStyleSheet("font-size:14px;font-weight:600;")
        st = QLabel(); st.setStyleSheet(f"font-size:11px;color:{self.t['text_secondary']};")
        col.addWidget(a); col.addWidget(st); hl.addLayout(col, 1)
        sw = Switch(is_on(self.store, self.host, key, default_on), self.accent, self.t["border"])
        sw.setToolTip(tip)
        hl.addWidget(sw)
        self._rows = getattr(self, "_rows", {}); self._rows[key] = (sw, st, perm, default_on)
        self._paint_state(key)
        sw.clicked.connect(lambda checked, k=key, d=default_on: self._toggle(k, checked, d))
        self.bl.addWidget(w)

    def _paint_state(self, key):
        sw, st, perm, default_on = self._rows[key]
        v = self.store.get(self.host, key)
        if perm:
            st.setText({"allow": "Allowed", "deny": "Blocked"}.get(v, "Ask first"))
        else:
            st.setText("On" if is_on(self.store, self.host, key, default_on) else "Off")
        sw.blockSignals(True); sw.setChecked(is_on(self.store, self.host, key, default_on)); sw.blockSignals(False); sw.update()

    def _toggle(self, key, checked, default_on):
        set_value(self.store, self.host, key, checked, default_on)
        for k in self._rows:
            self._paint_state(k)
        try:
            apply_to_page(self.mw, self.page, self.host)
        except Exception:
            pass
        if key in RELOAD_KEYS:
            self.note.show()

    def _block_all(self):
        block_all(self.store, self.host)
        for k in self._rows: self._paint_state(k)

    def _reset(self):
        reset_site(self.store, self.host)
        for k in self._rows: self._paint_state(k)
        try: apply_to_page(self.mw, self.page, self.host)
        except Exception: pass
        self.note.show()

    def _reload(self):
        try: self.page.triggerAction(self.page.WebAction.Reload)
        except Exception: pass
        self.close()

    def _all_sites(self):
        self.close()
        try: self.mw.show_site_permissions()
        except Exception: pass


def apply_to_page(mw, page, host):
    """Make the page follow the saved per-site settings (called on every navigation and after every switch)."""
    from PyQt6.QtWebEngineCore import QWebEngineSettings as QS
    store = getattr(mw, "permission_store", None)
    if store is None or page is None or not host:
        return
    base = mw.settings_data or {}
    st = page.settings(); A = QS.WebAttribute

    def feat(key, base_value):
        v = store.get(host, key)
        return True if v == "allow" else (False if v == "deny" else bool(base_value))
    st.setAttribute(A.JavascriptEnabled, feat("js", base.get("js_enabled", True)))
    st.setAttribute(A.AutoLoadImages, feat("images", base.get("load_images", True)))
    st.setAttribute(A.JavascriptCanOpenWindows, feat("popups", base.get("js_popups", False)))
    st.setAttribute(A.AllowRunningInsecureContent, feat("insecure", base.get("insecure_content", False)))
    pr = getattr(A, "PlaybackRequiresUserGesture", None)
    if pr is not None:
        st.setAttribute(pr, store.get(host, "autoplay") != "allow")
    if store.get(host, "sound") == "deny":
        page.setAudioMuted(True)
    elif store.get(host, "sound") is None and getattr(page, "_sps_site_muted", False):
        page.setAudioMuted(False)
    page._sps_site_muted = store.get(host, "sound") == "deny"


def show_panel(mw, anchor=None):
    host, page = site_of(mw)
    if host is None:
        try: mw.status.showMessage("Open a website first - site controls are for web pages.", 3500)
        except Exception: pass
        return None
    panel = SitePanel(mw, host, page)
    if anchor is not None:
        pt = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height()))
        x = max(8, pt.x() - panel.width()); y = pt.y() + 6
        scr = QApplication.screenAt(pt)
        if scr is not None:
            g = scr.availableGeometry(); x = min(max(g.left() + 8, x), g.right() - panel.width() - 8)
            panel.resize(panel.width(), min(panel.height(), g.bottom() - y - 12))
        panel.move(x, y)
    panel.show()
    mw._sps_site_panel = panel
    return panel
