"""SPS Quick panel - a rounded drop-down under the toolbar (no separate window).

Everything that used to need a whole window for a quick action lives here: protection switches, tools, recent history, bookmarks.
Big tools (Settings, the History/Bookmark manager ...) still open their own window, because they need the space.
The panel only talks to the main window through small, individually guarded calls, so one failing action never closes the browser.
"""
import json, os
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QScrollArea, QWidget, QGridLayout,
                             QGraphicsDropShadowEffect, QApplication)

TOGGLES = [("ad_blocker", "🛡 Ads"), ("youtube_ad_skip", "▶ YouTube ads"), ("tracking_protection", "👁 Trackers"),
           ("https_only", "🔒 HTTPS only"), ("block_popups", "🚫 Pop-ups"), ("tab_sleep_enabled", "😴 Memory saver"),
           ("energy_saver", "🔋 Energy saver")]

TOOLS = [("➕", "New tab", "add_new_tab", ()), ("🕵", "Private", "add_new_tab", {"incognito": True}),
         ("🖨", "Print", "print_page", ()), ("✂", "Print area", "print_selected_area", ()),
         ("📸", "Screenshot", "take_screenshot", ()), ("🔎", "SPS Lens", "open_sps_lens", ()),
         ("🕒", "History", "show_history", ()), ("⭐", "Bookmarks", "show_bookmarks", ()),
         ("🍪", "Cookies", "show_cookie_manager", ()), ("🗂", "Tabs", "show_tab_organizer", ()),
         ("🛰", "VPN", "_v39_open_vpn", ()), ("⚙", "Settings", "show_settings", ()),
         ("✅", "Safety Check", "show_safety_check", ()), ("📲", "Send tab", "show_send_tab", ())]


def _read_list(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return [e for e in d if isinstance(e, dict) and e.get("url")] if isinstance(d, list) else []
    except Exception:
        return []


class QuickPanel(QFrame):
    def __init__(self, mw):
        super().__init__(mw, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.mw = mw
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        t = dict(getattr(mw, "_theme", {}) or {})
        bg, fg, sub = t.get("bg_primary", "#ffffff"), t.get("text_primary", "#202124"), t.get("text_secondary", "#5f6368")
        card, hov, acc = t.get("bg_secondary", "#f1f3f4"), t.get("hover", "#e8eaed"), (mw.settings_data.get("accent_color") or t.get("accent", "#1a73e8"))
        self._acc = acc
        outer = QVBoxLayout(self); outer.setContentsMargins(14, 14, 14, 18)
        self.box = QFrame(); self.box.setObjectName("qp")
        outer.addWidget(self.box)
        sh = QGraphicsDropShadowEffect(self); sh.setBlurRadius(28); sh.setOffset(0, 6); sh.setColor(QColor(0, 0, 0, 90)); self.box.setGraphicsEffect(sh)
        self.setStyleSheet(
            "#qp{background:%s;border:1px solid %s;border-radius:18px;}"
            "QLabel{color:%s;background:transparent;} QLabel#h{font-size:15px;font-weight:700;} QLabel#s{color:%s;font-size:11px;font-weight:600;padding-top:4px;}"
            "QPushButton{background:%s;color:%s;border:none;border-radius:12px;padding:8px 10px;font-weight:600;}"
            "QPushButton:hover{background:%s;} QPushButton[on='true']{background:%s;color:white;}"
            "QPushButton#row{text-align:left;background:transparent;border-radius:10px;font-weight:500;padding:6px 10px;}"
            "QPushButton#row:hover{background:%s;}"
            "QLineEdit{background:%s;color:%s;border:none;border-radius:12px;padding:8px 12px;}"
            "QScrollArea{border:none;background:transparent;} QWidget#inner{background:transparent;}"
            % (bg, t.get("border", "#dadce0"), fg, sub, card, fg, hov, acc, hov, card, fg))
        lay = QVBoxLayout(self.box); lay.setContentsMargins(14, 12, 14, 12); lay.setSpacing(8)
        head = QHBoxLayout(); h = QLabel("SPS quick panel"); h.setObjectName("h"); head.addWidget(h); head.addStretch()
        x = QPushButton("✕"); x.setFixedSize(30, 30); x.clicked.connect(self.close); head.addWidget(x); lay.addLayout(head)

        s = QLabel("PROTECTION"); s.setObjectName("s"); lay.addWidget(s)
        row = QGridLayout(); row.setSpacing(6); self.toggle_btns = {}
        for i, (key, label) in enumerate(TOGGLES):
            b = QPushButton(label); b.setCheckable(False); b.setProperty("on", bool(mw.settings_data.get(key, key in ("youtube_ad_skip", "tab_sleep_enabled"))))
            b.clicked.connect(lambda _=False, k=key, bb=b: self._flip(k, bb)); self.toggle_btns[key] = b
            row.addWidget(b, i // 3, i % 3)
        lay.addLayout(row)

        self.perf = QLabel(); self.perf.setObjectName("s"); lay.addWidget(self.perf)
        prow = QHBoxLayout(); prow.setSpacing(6)
        self.sleep_btn = QPushButton("😴 Sleep other tabs now"); self.sleep_btn.clicked.connect(self._sleep_now); prow.addWidget(self.sleep_btn)
        self.mins_btn = QPushButton(); self.mins_btn.clicked.connect(self._cycle_minutes); prow.addWidget(self.mins_btn)
        lay.addLayout(prow)
        self._perf_text()

        s = QLabel("TOOLS"); s.setObjectName("s"); lay.addWidget(s)
        g = QGridLayout(); g.setSpacing(6)
        for i, (ic, label, meth, kw) in enumerate(TOOLS):
            b = QPushButton("%s  %s" % (ic, label)); b.clicked.connect(lambda _=False, m=meth, k=kw: self._call(m, k)); g.addWidget(b, i // 3, i % 3)
        lay.addLayout(g)

        self.find = QLineEdit(); self.find.setPlaceholderText("Search history and bookmarks…"); self.find.textChanged.connect(self._fill)
        lay.addWidget(self.find)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFixedHeight(190)
        self.inner = QWidget(); self.inner.setObjectName("inner"); self.il = QVBoxLayout(self.inner); self.il.setContentsMargins(0, 0, 4, 0); self.il.setSpacing(0)
        self.scroll.setWidget(self.inner); lay.addWidget(self.scroll)
        self.setFixedWidth(430)
        self._fill()

    # ---- content ----
    def _fill(self, *_):
        while self.il.count():
            it = self.il.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        q = self.find.text().strip().lower()
        try:
            bms = _read_list(self.mw._bm_path()); hist = list(reversed(_read_list(self.mw._hist_path())))
        except Exception:
            bms, hist = [], []
        if getattr(self.mw, "_is_guest", False):
            bms, hist = [], []

        def add_section(title, items, limit):
            shown = [e for e in items if not q or q in ((e.get("title") or "") + " " + e.get("url", "")).lower()][:limit]
            if not shown:
                return
            lab = QLabel(title); lab.setObjectName("s"); self.il.addWidget(lab)
            for e in shown:
                text = (e.get("title") or e.get("url"))[:54]
                b = QPushButton(text); b.setObjectName("row"); b.setToolTip(e.get("url", ""))
                b.clicked.connect(lambda _=False, u=e.get("url"): self._open(u)); self.il.addWidget(b)
        add_section("BOOKMARKS", bms, 30 if q else 6)
        add_section("RECENT HISTORY", hist, 30 if q else 8)
        if self.il.count() == 0:
            self.il.addWidget(QLabel("Nothing here yet." if not q else "No match."))
        self.il.addStretch(1)

    def _perf_text(self):
        try:
            import sps_perf
            mem = sps_perf.memory_mb()
            self.perf.setText("PERFORMANCE   ·   %d tabs   ·   %d sleeping%s" % (self.mw.tabs.count(), sps_perf.sleeping_count(self.mw),
                                                                       ("   ·   %d MB" % mem) if mem else ""))
            self.mins_btn.setText("⏱ Sleep after %d min" % int(self.mw.settings_data.get("tab_sleep_minutes", 15)))
        except Exception as e:
            self.perf.setText("PERFORMANCE")

    def _sleep_now(self):
        try:
            import sps_perf
            n = sps_perf.sleep_others_now(self.mw)
            self.mw.status.showMessage("%d tab(s) put to sleep" % n, 3000)
        except Exception as e:
            print("[SPS quick] sleep:", e)
        self._perf_text()

    def _cycle_minutes(self):
        try:
            import sps_perf
            cur = int(self.mw.settings_data.get("tab_sleep_minutes", 15))
            nxt = next((m for m in sps_perf.SLEEP_CHOICES if m > cur), sps_perf.SLEEP_CHOICES[0])
            self.mw.v32_apply_setting("tab_sleep_minutes", nxt)
        except Exception as e:
            print("[SPS quick] minutes:", e)
        self._perf_text()

    # ---- actions ----
    def _flip(self, key, btn):
        try:
            new = not bool(self.mw.settings_data.get(key, key in ("youtube_ad_skip", "tab_sleep_enabled")))
            self.mw.v32_apply_setting(key, new)
            btn.setProperty("on", new); btn.style().unpolish(btn); btn.style().polish(btn)
            try:
                self.mw.status.showMessage("%s %s" % (btn.text().split(" ", 1)[-1], "on" if new else "off") + (" - reload the page to apply" if key == "youtube_ad_skip" else ""), 3000)
            except Exception:
                pass
        except Exception as e:
            print("[SPS quick] toggle failed:", e)

    def _call(self, meth, kw):
        self.close()
        fn = getattr(self.mw, meth, None)
        if fn is None:
            return
        try:
            if meth == "show_history" or meth == "show_bookmarks":
                pass
            safe = getattr(self.mw, "_safe_call", None)
            if isinstance(kw, dict) and kw:
                fn(**kw)
            elif safe:
                safe(fn)
            else:
                fn()
        except Exception as e:
            print("[SPS quick] %s failed: %s" % (meth, e))

    def _open(self, url):
        self.close()
        try:
            self.mw.add_new_tab(QUrl(url))
        except Exception as e:
            print("[SPS quick] open failed:", e)

    # ---- show ----
    def popup_at(self, anchor):
        pos = anchor.mapToGlobal(QPoint(anchor.width() - self.width(), anchor.height() + 2))
        scr = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if scr is not None:
            pos.setX(max(scr.left() + 4, min(pos.x(), scr.right() - self.width() - 4)))
        self.move(pos)
        self.setWindowOpacity(0.0); self.show()
        self._anim = QPropertyAnimation(self, b"windowOpacity", self); self._anim.setDuration(140)
        self._anim.setStartValue(0.0); self._anim.setEndValue(1.0); self._anim.setEasingCurve(QEasingCurve.Type.OutCubic); self._anim.start()
        self.find.setFocus()


def show_quick_panel(mw, anchor=None):
    old = getattr(mw, "_sps_quick", None)
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    p = QuickPanel(mw)
    mw._sps_quick = p
    p.popup_at(anchor or getattr(mw, "menu_btn", None) or mw)
    return p
