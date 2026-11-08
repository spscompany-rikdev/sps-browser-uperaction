"""SPS Manager - one modern window for History, Bookmarks, Cookies and Tabs.

Every list supports multi-select (click, Ctrl+click, Shift+click, Ctrl+A, drag) with bulk actions.
Rounded cards, soft colours and a short fade-in; colours come from the browser's current theme.
The window only talks to the browser through small, documented hooks (see Hooks) so it can be tested without the full browser.
"""
import datetime, json, os
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtNetwork import QNetworkCookie
from PyQt6.QtGui import QGuiApplication, QColor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QStackedWidget,
                             QTreeWidget, QTreeWidgetItem, QAbstractItemView, QFrame, QInputDialog, QMessageBox,
                             QFileDialog, QGraphicsDropShadowEffect, QHeaderView, QWidget)

DEFAULT_THEME = {"bg_primary": "#ffffff", "bg_secondary": "#f5f6f8", "bg_tertiary": "#eceff3", "accent": "#1a73e8",
                 "accent_light": "#e8f0fe", "text_primary": "#202124", "text_secondary": "#5f6368", "border": "#dadce0",
                 "danger": "#d93025", "success": "#188038", "warning": "#f9ab00", "hover": "#e8eaed"}


def host_of(url):
    try:
        h = urlparse(url).hostname or ""
    except Exception:
        h = ""
    return h[4:] if h.startswith("www.") else h


def parse_time(s):
    try:
        return datetime.datetime.fromisoformat(str(s))
    except Exception:
        return None


def day_filter(entries, key):
    """entries: list of dicts with 'time'. key: all | today | yesterday | week | month  -> list of (original_index, entry)"""
    now = datetime.datetime.now()
    start = {"today": now.replace(hour=0, minute=0, second=0, microsecond=0),
             "yesterday": (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
             "week": now - datetime.timedelta(days=7), "month": now - datetime.timedelta(days=30)}.get(key)
    out = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            continue
        if start is not None:
            t = parse_time(e.get("time"))
            if t is None or t < start or (key == "yesterday" and t >= start + datetime.timedelta(days=1)):
                continue
        out.append((i, e))
    return out


def style(t):
    a, bg, s, s2, tx, tx2, bd = t["accent"], t["bg_primary"], t["bg_secondary"], t["bg_tertiary"], t["text_primary"], t["text_secondary"], t["border"]
    return f"""
    QDialog#spsMgr {{ background:{bg}; color:{tx}; }}
    QLabel {{ color:{tx}; background:transparent; }}
    QFrame#side {{ background:{s}; border-radius:18px; }}
    QFrame#card {{ background:{s}; border-radius:16px; }}
    QPushButton#nav {{ background:transparent; color:{tx}; text-align:left; padding:11px 16px; border-radius:14px; font-size:14px; border:none; }}
    QPushButton#nav:hover {{ background:{s2}; }}
    QPushButton#nav:checked {{ background:{a}; color:white; font-weight:600; }}
    QPushButton#chip {{ background:{s2}; color:{tx}; border:none; border-radius:15px; padding:7px 14px; font-size:12px; }}
    QPushButton#chip:hover {{ background:{bd}; }}
    QPushButton#chip:disabled {{ color:{tx2}; background:{s}; }}
    QPushButton#primary {{ background:{a}; color:white; border:none; border-radius:15px; padding:7px 16px; font-size:12px; font-weight:600; }}
    QPushButton#primary:disabled {{ background:{bd}; color:{tx2}; }}
    QPushButton#danger {{ background:{t['danger']}; color:white; border:none; border-radius:15px; padding:7px 14px; font-size:12px; font-weight:600; }}
    QPushButton#danger:disabled {{ background:{bd}; color:{tx2}; }}
    QLineEdit, QComboBox {{ background:{bg}; color:{tx}; border:1px solid {bd}; border-radius:16px; padding:8px 14px; font-size:13px; }}
    QLineEdit:focus, QComboBox:focus {{ border:1px solid {a}; }}
    QComboBox::drop-down {{ border:none; width:22px; }}
    QComboBox QAbstractItemView {{ background:{bg}; color:{tx}; border:1px solid {bd}; border-radius:10px; selection-background-color:{a}; selection-color:white; }}
    QTreeWidget {{ background:{bg}; color:{tx}; border:1px solid {bd}; border-radius:16px; padding:6px; outline:0; font-size:13px; alternate-background-color:{s}; }}
    QTreeWidget::item {{ padding:7px 6px; border-radius:10px; }}
    QTreeWidget::item:hover {{ background:{s2}; }}
    QTreeWidget::item:selected {{ background:{a}; color:white; }}
    QHeaderView::section {{ background:transparent; color:{tx2}; border:none; padding:6px; font-size:11px; font-weight:600; }}
    QScrollBar:vertical {{ background:transparent; width:10px; margin:4px; }}
    QScrollBar::handle:vertical {{ background:{bd}; border-radius:4px; min-height:30px; }}
    QScrollBar::handle:vertical:hover {{ background:{tx2}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QLabel#title {{ font-size:22px; font-weight:700; }}
    QLabel#sub {{ color:{tx2}; font-size:12px; }}
    QLabel#sel {{ color:{a}; font-size:12px; font-weight:600; }}
    """


class Hooks:
    """What SpsManager needs from the browser. The real browser fills these in (see sps_manager_hooks in _v36_patch.py)."""
    theme = DEFAULT_THEME
    history_path = None           # path of history.json
    bookmarks_path = None         # path of bookmarks.json
    cookie_store = None           # QWebEngineCookieStore or None
    cookie_tracker = None         # CookieTracker created at browser start (preferred)
    save_bookmarks = None         # callable(list)  (also refreshes the bookmarks bar)
    open_url = None               # callable(url, private=False)
    tabs = None                   # callable() -> list of dict(id,title,url,private,muted,pinned,sleeping,active)
    tab_action = None             # callable(action, [ids])   actions: goto close mute unmute sleep duplicate pin


class _Page(QWidget):
    """Shared layout: title row, search + filters, selection toolbar, tree."""
    COLUMNS = ["", ""]

    def __init__(self, mgr, title, subtitle):
        super().__init__()
        self.mgr, self.h = mgr, mgr.h
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 0, 0, 0); lay.setSpacing(10)
        head = QHBoxLayout()
        col = QVBoxLayout(); col.setSpacing(0)
        self.title = QLabel(title); self.title.setObjectName("title")
        self.sub = QLabel(subtitle); self.sub.setObjectName("sub")
        col.addWidget(self.title); col.addWidget(self.sub)
        head.addLayout(col); head.addStretch()
        self.sel = QLabel(""); self.sel.setObjectName("sel"); head.addWidget(self.sel)
        lay.addLayout(head)
        self.filters = QHBoxLayout(); self.filters.setSpacing(8)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search..."); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda *_: self.render())
        self.filters.addWidget(self.search, 1)
        lay.addLayout(self.filters)
        self.bar = QHBoxLayout(); self.bar.setSpacing(8)
        lay.addLayout(self.bar)
        self.tree = QTreeWidget(); self.tree.setColumnCount(len(self.COLUMNS)); self.tree.setHeaderLabels(self.COLUMNS)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setAlternatingRowColors(False); self.tree.setRootIsDecorated(False); self.tree.setUniformRowHeights(True)
        self.tree.itemSelectionChanged.connect(self._sel_changed)
        self.tree.itemDoubleClicked.connect(lambda *_: self.on_open())
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tree, 1)
        self.buttons = {}

    def btn(self, key, text, fn, kind="chip"):
        b = QPushButton(text); b.setObjectName(kind); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda *_: fn()); self.bar.addWidget(b); self.buttons[key] = b
        return b

    def selected(self):
        return [i for i in self.tree.selectedItems()]

    def _sel_changed(self):
        n = len(self.tree.selectedItems())
        self.sel.setText("%d selected" % n if n else "")
        for k, b in self.buttons.items():
            if getattr(b, "needs_sel", True):
                b.setEnabled(n > 0)

    def select_all(self):
        self.tree.selectAll()

    def render(self): ...
    def refresh(self): self.render()
    def on_open(self): ...

    def query(self):
        return self.search.text().strip().lower()

    def finish_render(self, shown, total, what):
        self.sub.setText("%d %s%s" % (shown, what, "" if shown == total else "  (of %d)" % total))
        self._sel_changed()

    def confirm(self, text):
        return QMessageBox.question(self, "SPS", text) == QMessageBox.StandardButton.Yes

    def copy_text(self, text):
        QGuiApplication.clipboard().setText(text)


class HistoryPage(_Page):
    COLUMNS = ["Page", "Site", "When"]

    def __init__(self, mgr):
        super().__init__(mgr, "History", "")
        self.range = QComboBox()
        for k, v in (("all", "All time"), ("today", "Today"), ("yesterday", "Yesterday"), ("week", "Last 7 days"), ("month", "Last 30 days")):
            self.range.addItem(v, k)
        self.range.currentIndexChanged.connect(lambda *_: self.render())
        self.filters.addWidget(self.range)
        self.btn("sel_all", "Select all", self.select_all).needs_sel = False
        self.btn("open", "Open", self.on_open)
        self.btn("priv", "Open private", lambda: self.on_open(True))
        self.btn("bm", "Bookmark", self.on_bookmark)
        self.btn("copy", "Copy links", self.on_copy)
        self.bar.addStretch()
        self.btn("del", "Delete selected", self.on_delete, "danger")
        self.btn("clr", "Clear shown", self.on_clear, "danger").needs_sel = False
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.data = []
        self.refresh()

    def load(self):
        try:
            with open(self.h.history_path, encoding="utf-8") as f:
                d = json.load(f)
            self.data = [e for e in d if isinstance(e, dict)] if isinstance(d, list) else []
        except Exception:
            self.data = []

    def save(self):
        tmp = self.h.history_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.h.history_path)

    def refresh(self):
        self.load(); self.render()

    def rows(self):
        q = self.query()
        out = []
        for i, e in day_filter(self.data, self.range.currentData()):
            if q and q not in (e.get("title", "") + " " + e.get("url", "")).lower():
                continue
            out.append((i, e))
        out.sort(key=lambda p: str(p[1].get("time", "")), reverse=True)
        return out

    def render(self):
        self.tree.setUpdatesEnabled(False); self.tree.clear()
        rows = self.rows()
        for i, e in rows[:3000]:
            t = parse_time(e.get("time"))
            it = QTreeWidgetItem([e.get("title") or e.get("url", ""), host_of(e.get("url", "")), t.strftime("%d %b  %H:%M") if t else ""])
            it.setData(0, Qt.ItemDataRole.UserRole, i); it.setToolTip(0, e.get("url", ""))
            self.tree.addTopLevelItem(it)
        self.tree.setUpdatesEnabled(True)
        self.finish_render(min(len(rows), 3000), len(self.data), "pages")

    def _entries(self):
        return [self.data[it.data(0, Qt.ItemDataRole.UserRole)] for it in self.selected()]

    def on_open(self, private=False):
        for e in self._entries():
            self.h.open_url(e.get("url", ""), private)

    def on_bookmark(self):
        n = self.mgr.add_bookmarks([(e.get("title", ""), e.get("url", "")) for e in self._entries()])
        self.mgr.toast("%d bookmark(s) added" % n)

    def on_copy(self):
        self.copy_text("\n".join(e.get("url", "") for e in self._entries()))
        self.mgr.toast("Links copied")

    def delete_indexes(self, idx):
        gone = set(idx)
        self.data = [e for i, e in enumerate(self.data) if i not in gone]
        self.save(); self.render()

    def on_delete(self):
        idx = [it.data(0, Qt.ItemDataRole.UserRole) for it in self.selected()]
        if idx:
            self.delete_indexes(idx); self.mgr.toast("%d deleted" % len(idx))

    def on_clear(self):
        rows = self.rows()
        if rows and self.confirm("Delete all %d shown history entries?" % len(rows)):
            self.delete_indexes([i for i, _ in rows])


class BookmarksPage(_Page):
    COLUMNS = ["Bookmark", "Folder", "Site"]

    def __init__(self, mgr):
        super().__init__(mgr, "Bookmarks", "")
        self.folder = QComboBox(); self.folder.currentIndexChanged.connect(lambda *_: self.render())
        self.filters.addWidget(self.folder)
        self.btn("sel_all", "Select all", self.select_all).needs_sel = False
        self.btn("open", "Open", self.on_open)
        self.btn("move", "Move to folder...", self.on_move)
        self.btn("rename", "Rename", self.on_rename)
        self.btn("copy", "Copy links", self.on_copy)
        self.bar.addStretch()
        self.btn("del", "Delete selected", self.on_delete, "danger")
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.data = []
        self.refresh()

    def load(self):
        try:
            with open(self.h.bookmarks_path, encoding="utf-8") as f:
                d = json.load(f)
            self.data = [b for b in d if isinstance(b, dict) and b.get("url")] if isinstance(d, list) else []
        except Exception:
            self.data = []

    def refresh(self):
        self.load()
        cur = self.folder.currentData()
        self.folder.blockSignals(True); self.folder.clear(); self.folder.addItem("All folders", None)
        for f in sorted({b.get("folder") or "General" for b in self.data}):
            self.folder.addItem(f, f)
        k = self.folder.findData(cur); self.folder.setCurrentIndex(max(0, k))
        self.folder.blockSignals(False)
        self.render()

    def render(self):
        q, fo = self.query(), self.folder.currentData()
        self.tree.clear(); shown = 0
        for i, b in enumerate(self.data):
            if fo and (b.get("folder") or "General") != fo:
                continue
            if q and q not in (b.get("title", "") + " " + b.get("url", "")).lower():
                continue
            it = QTreeWidgetItem([b.get("title") or b["url"], b.get("folder") or "General", host_of(b["url"])])
            it.setData(0, Qt.ItemDataRole.UserRole, i); it.setToolTip(0, b["url"])
            self.tree.addTopLevelItem(it); shown += 1
        self.finish_render(shown, len(self.data), "bookmarks")

    def _idx(self):
        return [it.data(0, Qt.ItemDataRole.UserRole) for it in self.selected()]

    def commit(self):
        self.h.save_bookmarks(self.data)
        self.refresh()

    def on_open(self):
        for i in self._idx():
            self.h.open_url(self.data[i]["url"], False)

    def on_move(self):
        idx = self._idx()
        folders = sorted({b.get("folder") or "General" for b in self.data})
        name, ok = QInputDialog.getItem(self, "Move to folder", "Folder (type a new name to create one):", folders, 0, True)
        if ok and name.strip():
            for i in idx:
                self.data[i]["folder"] = name.strip()
            self.commit(); self.mgr.toast("Moved %d" % len(idx))

    def on_rename(self):
        idx = self._idx()
        if not idx:
            return
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=self.data[idx[0]].get("title", ""))
        if ok and name.strip():
            self.data[idx[0]]["title"] = name.strip(); self.commit()

    def on_copy(self):
        self.copy_text("\n".join(self.data[i]["url"] for i in self._idx())); self.mgr.toast("Links copied")

    def on_delete(self):
        idx = set(self._idx())
        if idx and self.confirm("Delete %d bookmark(s)?" % len(idx)):
            self.data = [b for i, b in enumerate(self.data) if i not in idx]
            self.commit(); self.mgr.toast("%d deleted" % len(idx))


class CookieTracker(QObject):
    """Keeps a live list of the cookies of one profile. Must be created at browser start (before pages load)."""
    changed = pyqtSignal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store, self.cookies = store, {}
        store.cookieAdded.connect(self._added)
        store.cookieRemoved.connect(self._removed)
        try:
            store.loadAllCookies()                 # cookies saved by earlier sessions
        except Exception:
            pass

    @staticmethod
    def key(c):
        return (c.domain(), c.path(), bytes(c.name()).decode("utf-8", "replace"))

    def _added(self, c):
        c = QNetworkCookie(c)                      # the signal's object is a temporary: keep our own copy
        self.cookies[self.key(c)] = c; self.changed.emit()

    def _removed(self, c):
        self.cookies.pop(self.key(c), None); self.changed.emit()

    def reload(self):
        try:
            self.store.loadAllCookies()
        except Exception:
            pass


class CookiesPage(_Page):
    COLUMNS = ["Site / cookie", "Expires", "Flags"]

    def __init__(self, mgr):
        super().__init__(mgr, "Cookies", "Loading...")
        self.btn("sel_all", "Select all", self.select_all).needs_sel = False
        self.btn("expand", "Expand / collapse", self.toggle).needs_sel = False
        self.btn("copy", "Copy names", self.on_copy)
        self.bar.addStretch()
        self.btn("del", "Delete selected", self.on_delete, "danger")
        self.btn("all", "Delete ALL cookies", self.on_all, "danger").needs_sel = False
        self.tree.setRootIsDecorated(True)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._expanded = False
        self.tracker = self.h.cookie_tracker
        if self.tracker is None and self.h.cookie_store is not None:
            self.tracker = CookieTracker(self.h.cookie_store, self)       # (tests) a short-lived tracker
        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.timeout.connect(self.render)
        if self.tracker is None:
            self.cookies = {}
            self.sub.setText("Cookie store not available")
        else:
            self.cookies = self.tracker.cookies
            self.tracker.changed.connect(lambda: self._timer.start(250))
            self.tracker.reload()

    def refresh(self):
        self.render()

    def render(self):
        if self.tracker is None:
            self.sub.setText("Cookie store not available"); return
        self._render()

    def _render(self):
        q = self.query()
        groups = {}
        for (dom, path, name), c in self.cookies.items():
            d = dom.lstrip(".")
            if q and q not in d.lower() and q not in name.lower():
                continue
            groups.setdefault(d, []).append((path, name, c))
        self.tree.setUpdatesEnabled(False); self.tree.clear()
        for d in sorted(groups):
            items = sorted(groups[d], key=lambda x: x[1])
            top = QTreeWidgetItem([d, "%d cookies" % len(items), ""])
            top.setData(0, Qt.ItemDataRole.UserRole, None)
            for path, name, c in items:
                exp = c.expirationDate()
                es = "session" if c.isSessionCookie() else (exp.toString("dd MMM yyyy") if exp.isValid() else "")
                flags = " ".join(x for x, on in (("secure", c.isSecure()), ("httpOnly", c.isHttpOnly())) if on)
                ch = QTreeWidgetItem([name + ("   " + path if path != "/" else ""), es, flags])
                ch.setData(0, Qt.ItemDataRole.UserRole, c)
                top.addChild(ch)
            self.tree.addTopLevelItem(top)
        if self._expanded:
            self.tree.expandAll()
        self.tree.setUpdatesEnabled(True)
        self.finish_render(len(groups), len({(k[0].lstrip('.')) for k in self.cookies}), "sites  /  %d cookies" % len(self.cookies))

    def toggle(self):
        self._expanded = not self._expanded
        self.tree.expandAll() if self._expanded else self.tree.collapseAll()

    def _selected_cookies(self):
        out, seen = [], set()
        for it in self.selected():
            kids = [it.child(i) for i in range(it.childCount())] if it.childCount() else [it]
            for k in kids:
                c = k.data(0, Qt.ItemDataRole.UserRole)
                if c is not None and id(c) not in seen:
                    seen.add(id(c)); out.append(c)
        return out

    def on_copy(self):
        self.copy_text("\n".join("%s  %s" % (c.domain(), bytes(c.name()).decode("utf-8", "replace")) for c in self._selected_cookies()))

    def on_delete(self):
        cs = self._selected_cookies()
        if not cs:
            return
        if not self.confirm("Delete %d cookie(s)? You may be signed out of those sites." % len(cs)):
            return
        for c in cs:
            try:
                (self.tracker.store if self.tracker else self.h.cookie_store).deleteCookie(c)
            except Exception:
                pass
            self.cookies.pop(CookieTracker.key(c), None)
        self.render(); self.mgr.toast("%d cookie(s) deleted" % len(cs))

    def on_all(self):
        if self.confirm("Delete ALL cookies? You will be signed out of every website."):
            try:
                (self.tracker.store if self.tracker else self.h.cookie_store).deleteAllCookies()
            except Exception:
                pass
            self.cookies.clear(); self.render(); self.mgr.toast("All cookies deleted")


class TabsPage(_Page):
    COLUMNS = ["Tab", "Site", "State"]

    def __init__(self, mgr):
        super().__init__(mgr, "Tabs", "")
        self.btn("sel_all", "Select all", self.select_all).needs_sel = False
        self.btn("goto", "Go to tab", lambda: self.act("goto"))
        self.btn("dup", "Duplicate", lambda: self.act("duplicate"))
        self.btn("mute", "Mute", lambda: self.act("mute"))
        self.btn("unmute", "Unmute", lambda: self.act("unmute"))
        self.btn("sleep", "Sleep", lambda: self.act("sleep"))
        self.btn("bm", "Bookmark", self.on_bookmark)
        self.btn("copy", "Copy links", self.on_copy)
        self.bar.addStretch()
        self.btn("others", "Close others", self.close_others, "chip")
        self.btn("dups", "Close duplicates", self.close_dups, "chip").needs_sel = False
        self.btn("close", "Close selected", lambda: self.act("close"), "danger")
        self.group = QComboBox(); self.group.addItem("List", False); self.group.addItem("Group by site", True)
        self.group.currentIndexChanged.connect(lambda *_: self.render())
        self.filters.addWidget(self.group)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.data = []
        self.refresh()

    def refresh(self):
        try:
            self.data = list(self.h.tabs())
        except Exception:
            self.data = []
        self.render()

    @staticmethod
    def state(t):
        return "  ".join(x for x, on in (("active", t.get("active")), ("pinned", t.get("pinned")), ("private", t.get("private")),
                                         ("muted", t.get("muted")), ("sleeping", t.get("sleeping"))) if on)

    def render(self):
        q = self.query(); grouped = self.group.currentData()
        rows = [t for t in self.data if not q or q in (t.get("title", "") + " " + t.get("url", "")).lower()]
        self.tree.clear()

        def mk(t):
            it = QTreeWidgetItem([t.get("title") or t.get("url") or "New tab", host_of(t.get("url", "")), self.state(t)])
            it.setData(0, Qt.ItemDataRole.UserRole, t.get("id")); it.setToolTip(0, t.get("url", ""))
            return it
        if grouped:
            g = {}
            for t in rows:
                g.setdefault(host_of(t.get("url", "")) or "(blank)", []).append(t)
            for h in sorted(g, key=lambda k: -len(g[k])):
                top = QTreeWidgetItem([h, "%d tabs" % len(g[h]), ""]); top.setData(0, Qt.ItemDataRole.UserRole, None)
                for t in g[h]:
                    top.addChild(mk(t))
                self.tree.addTopLevelItem(top)
            self.tree.setRootIsDecorated(True); self.tree.expandAll()
        else:
            self.tree.setRootIsDecorated(False)
            for t in rows:
                self.tree.addTopLevelItem(mk(t))
        self.finish_render(len(rows), len(self.data), "tabs")

    def ids(self):
        out = []
        for it in self.selected():
            kids = [it.child(i) for i in range(it.childCount())] if it.childCount() else [it]
            for k in kids:
                v = k.data(0, Qt.ItemDataRole.UserRole)
                if v is not None and v not in out:
                    out.append(v)
        return out

    def _by_id(self, ids):
        return [t for t in self.data if t.get("id") in ids]

    def act(self, action):
        ids = self.ids()
        if not ids:
            return
        if action == "close" and len(ids) > 1 and not self.confirm("Close %d tabs?" % len(ids)):
            return
        self.h.tab_action(action, ids)
        QTimer.singleShot(150, self.refresh)
        if action in ("close", "duplicate", "sleep", "mute", "unmute"):
            self.mgr.toast("%s: %d tab(s)" % (action.capitalize(), len(ids)))

    def close_others(self):
        keep = set(self.ids())
        rest = [t["id"] for t in self.data if t["id"] not in keep and not t.get("pinned")]
        if rest and self.confirm("Close %d other tab(s)?" % len(rest)):
            self.h.tab_action("close", rest); QTimer.singleShot(150, self.refresh)

    def close_dups(self):
        seen, dups = set(), []
        for t in self.data:
            u = t.get("url", "")
            if not u or u.startswith("about:"):
                continue
            if u in seen and not t.get("active"):
                dups.append(t["id"])
            seen.add(u)
        if not dups:
            self.mgr.toast("No duplicate tabs"); return
        if self.confirm("Close %d duplicate tab(s)?" % len(dups)):
            self.h.tab_action("close", dups); QTimer.singleShot(150, self.refresh)

    def on_bookmark(self):
        n = self.mgr.add_bookmarks([(t.get("title", ""), t.get("url", "")) for t in self._by_id(self.ids())])
        self.mgr.toast("%d bookmark(s) added" % n)

    def on_copy(self):
        self.copy_text("\n".join(t.get("url", "") for t in self._by_id(self.ids()))); self.mgr.toast("Links copied")


class SpsManager(QDialog):
    PAGES = (("history", "History", HistoryPage), ("bookmarks", "Bookmarks", BookmarksPage),
             ("cookies", "Cookies", CookiesPage), ("tabs", "Tabs", TabsPage))

    def __init__(self, hooks, start="history", parent=None):
        super().__init__(parent)
        self.h = hooks
        t = {**DEFAULT_THEME, **(hooks.theme or {})}
        self.setObjectName("spsMgr"); self.setWindowTitle("SPS Manager"); self.resize(1020, 680)
        self.setStyleSheet(style(t))
        root = QHBoxLayout(self); root.setContentsMargins(16, 16, 16, 16); root.setSpacing(14)
        side = QFrame(); side.setObjectName("side"); side.setFixedWidth(190)
        sl = QVBoxLayout(side); sl.setContentsMargins(12, 16, 12, 12); sl.setSpacing(4)
        brand = QLabel("SPS Manager"); brand.setObjectName("title"); brand.setStyleSheet("font-size:17px;padding:2px 6px 12px 6px;")
        sl.addWidget(brand)
        self.stack = QStackedWidget(); self.pages = {}; self.navs = {}
        for key, label, cls in self.PAGES:
            p = cls(self); self.pages[key] = p; self.stack.addWidget(p)
            b = QPushButton(label); b.setObjectName("nav"); b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            sl.addWidget(b); self.navs[key] = b
        sl.addStretch()
        self.toast_lbl = QLabel(""); self.toast_lbl.setObjectName("sel"); self.toast_lbl.setWordWrap(True)
        sl.addWidget(self.toast_lbl)
        root.addWidget(side); root.addWidget(self.stack, 1)
        self._toast_timer = QTimer(self); self._toast_timer.setSingleShot(True); self._toast_timer.timeout.connect(lambda: self.toast_lbl.setText(""))
        self.show_page(start)
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180); self._fade.setStartValue(0.0); self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, e):
        super().showEvent(e)
        self._fade.start()

    def show_page(self, key):
        if key not in self.pages:
            key = "history"
        for k, b in self.navs.items():
            b.setChecked(k == key)
        self.stack.setCurrentWidget(self.pages[key])
        self.pages[key].refresh()

    def toast(self, text):
        self.toast_lbl.setText(text); self._toast_timer.start(2500)

    def add_bookmarks(self, items):
        """items: [(title, url)] -> number of new bookmarks"""
        try:
            with open(self.h.bookmarks_path, encoding="utf-8") as f:
                bms = json.load(f)
        except Exception:
            bms = []
        have = {b.get("url") for b in bms if isinstance(b, dict)}
        n = 0
        for title, url in items:
            if url and url not in have and not url.startswith("about:"):
                bms.append({"title": title or url, "url": url, "folder": "General", "added": str(datetime.datetime.now())})
                have.add(url); n += 1
        if n:
            self.h.save_bookmarks(bms)
            self.pages["bookmarks"].refresh()
        return n
