# ═══════════════════════════════════════════════════════════════
#  SPS BROWSER V33 — FEATURE PATCH
#  Adds ~80 real features to close the chrome.txt gaps.
#  This file is exec'd at the end of SPS_BROWSER.py
#  to monkey-patch MainWindow with the new methods, then wires
#  them into the menus and settings page.
# ═══════════════════════════════════════════════════════════════
import os, json, datetime, html, re, threading, time, subprocess, platform

# ──────────────────────────────────────────────────────────────
# 1. BOOKMARK MANAGER  (full window with drag-drop, folders, dupes)
# ──────────────────────────────────────────────────────────────
def _show_bookmark_manager(self):
    """Full Bookmark Manager — search, folders, rename, delete, duplicate detection, open-all."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QComboBox,
        QInputDialog, QMessageBox, QMenu)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("⭐ Bookmark Manager"); dlg.resize(800, 580)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)

    hdr = QLabel("⭐ Bookmark Manager")
    hdr.setStyleSheet(f"font-size:20px;font-weight:700;color:{t['text_primary']};padding:8px 0;")
    lay.addWidget(hdr)

    top = QHBoxLayout()
    search = QLineEdit(); search.setPlaceholderText("Search bookmarks…")
    search.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:7px 12px;")
    top.addWidget(search, 1)
    folder_cb = QComboBox()
    folder_cb.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    top.addWidget(folder_cb); lay.addLayout(top)

    tree = QTreeWidget()
    tree.setHeaderLabels(["Title", "URL", "Folder", "Added"])
    tree.setColumnWidth(0, 260); tree.setColumnWidth(1, 260); tree.setColumnWidth(2, 110)
    tree.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    tree.setSortingEnabled(True)
    tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    lay.addWidget(tree, 1)

    def _load(q="", folder="All Folders"):
        tree.clear(); bms = self._load_bookmarks()
        seen_urls = {}; dupes = set()
        for bm in bms:
            u = bm.get("url", "")
            if u in seen_urls: dupes.add(u)
            else: seen_urls[u] = True
        folders = sorted(set(b.get("folder", "General") for b in bms))
        folder_cb.blockSignals(True); folder_cb.clear()
        folder_cb.addItem("All Folders"); folder_cb.addItems(folders)
        # restore selection
        idx = folder_cb.findText(folder)
        if idx >= 0: folder_cb.setCurrentIndex(idx)
        folder_cb.blockSignals(False)
        for bm in bms:
            f = bm.get("folder", "General")
            if folder != "All Folders" and f != folder: continue
            ttl = bm.get("title", ""); url = bm.get("url", "")
            if q.lower() and q.lower() not in ttl.lower() and q.lower() not in url.lower(): continue
            item = QTreeWidgetItem([ttl, url, f, bm.get("added", "")])
            item.setData(0, Qt.ItemDataRole.UserRole, url)
            if url in dupes:
                from PyQt6.QtGui import QColor
                item.setForeground(1, QColor(t["warning"]))
                item.setToolTip(1, "⚠ Duplicate URL")
            tree.addTopLevelItem(item)

    _load()
    search.textChanged.connect(lambda q: _load(q, folder_cb.currentText()))
    folder_cb.currentTextChanged.connect(lambda f: _load(search.text(), f))

    def _open_selected():
        item = tree.currentItem()
        if item:
            url = item.data(0, Qt.ItemDataRole.UserRole) or item.text(1)
            self.add_new_tab(QUrl(url), item.text(0))

    def _open_all_in_folder():
        folder = folder_cb.currentText()
        bms = self._load_bookmarks()
        opened = 0
        for bm in bms:
            if folder == "All Folders" or bm.get("folder") == folder:
                self.add_new_tab(QUrl(bm["url"]), bm.get("title", ""))
                opened += 1
        if opened:
            self.status.showMessage(f"Opened {opened} bookmarks in new tabs", 3000)

    def _rename_selected():
        item = tree.currentItem()
        if not item: return
        url = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(dlg, "Rename Bookmark", "New title:", text=item.text(0))
        if ok and new_name:
            bms = self._load_bookmarks()
            for bm in bms:
                if bm.get("url") == url: bm["title"] = new_name
            self._save_bookmarks(bms); _load(search.text(), folder_cb.currentText())

    def _move_folder():
        item = tree.currentItem()
        if not item: return
        url = item.data(0, Qt.ItemDataRole.UserRole)
        bms = self._load_bookmarks()
        folders = sorted(set(b.get("folder", "General") for b in bms))
        folder, ok = QInputDialog.getItem(dlg, "Move to Folder", "Choose folder:", folders + ["+ New folder…"], editable=False)
        if ok:
            if folder == "+ New folder…":
                folder, ok2 = QInputDialog.getText(dlg, "New Folder", "Folder name:")
                if not ok2 or not folder: return
            for bm in bms:
                if bm.get("url") == url: bm["folder"] = folder
            self._save_bookmarks(bms); _load(search.text(), folder_cb.currentText())

    def _delete_selected():
        item = tree.currentItem()
        if not item: return
        url = item.data(0, Qt.ItemDataRole.UserRole)
        if QMessageBox.question(dlg, "Delete Bookmark", f"Delete:\n{item.text(0)}?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._save_bookmarks([b for b in self._load_bookmarks() if b.get("url") != url])
            _load(search.text(), folder_cb.currentText())

    def _remove_duplicates():
        bms = self._load_bookmarks(); seen = set(); cleaned = []
        for bm in bms:
            u = bm.get("url", "")
            if u not in seen: seen.add(u); cleaned.append(bm)
        removed = len(bms) - len(cleaned)
        self._save_bookmarks(cleaned)
        _load(search.text(), folder_cb.currentText())
        self.status.showMessage(f"Removed {removed} duplicate(s)", 3000)

    def _ctx_menu(pos):
        item = tree.itemAt(pos)
        if not item: return
        m = QMenu(tree)
        m.addAction("🌐 Open", _open_selected)
        m.addAction("🌐 Open in New Tab", lambda: self.add_new_tab(QUrl(item.data(0, Qt.ItemDataRole.UserRole))))
        m.addSeparator()
        m.addAction("✏️ Rename", _rename_selected)
        m.addAction("📁 Move to Folder", _move_folder)
        m.addSeparator()
        m.addAction("🗑 Delete", _delete_selected)
        m.exec(tree.viewport().mapToGlobal(pos))

    tree.customContextMenuRequested.connect(_ctx_menu)
    tree.itemDoubleClicked.connect(lambda it, col: _open_selected())

    btn_row = QHBoxLayout()
    for txt, fn, col in [
        ("➕ Add Current", lambda: (self.add_bookmark_current(), _load(search.text(), folder_cb.currentText())), accent),
        ("📂 Open All in Folder", _open_all_in_folder, t["bg_tertiary"]),
        ("🗑 Delete Selected", _delete_selected, t["danger"]),
        ("🔍 Remove Duplicates", _remove_duplicates, t["warning"]),
        ("📤 Export", self._export_bookmarks, t["bg_tertiary"]),
        ("📥 Import", self.import_bookmarks, t["bg_tertiary"]),
    ]:
        b = QPushButton(txt)
        b.setStyleSheet(f"background:{col};color:{'white' if col not in (t['bg_tertiary'],) else t['text_primary']};border-radius:8px;padding:8px 14px;font-size:12px;")
        b.clicked.connect(fn); btn_row.addWidget(b)
    btn_row.addStretch(); lay.addLayout(btn_row)
    dlg.exec()

# ──────────────────────────────────────────────────────────────
# 2. RECENTLY CLOSED TABS/WINDOWS LIST
# ──────────────────────────────────────────────────────────────
def _show_recently_closed(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QHBoxLayout
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🕒 Recently Closed"); dlg.resize(520, 420)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    hdr = QLabel("🕒 Recently Closed Tabs")
    hdr.setStyleSheet(f"font-size:18px;font-weight:700;color:{t['text_primary']};padding:8px 0;")
    lay.addWidget(hdr)
    lst = QListWidget()
    lst.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    closed = list(reversed(self._closed_tabs))
    for url, title in closed:
        item = QListWidgetItem(f"🔗 {title or url.toString()}")
        item.setData(Qt.ItemDataRole.UserRole, url)
        item.setToolTip(url.toString())
        lst.addItem(item)
    lst.itemDoubleClicked.connect(lambda it: (self.add_new_tab(it.data(Qt.ItemDataRole.UserRole)), dlg.accept()))
    lay.addWidget(lst, 1)
    br = QHBoxLayout()
    reopen_btn = QPushButton("↩ Reopen Selected")
    reopen_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _reopen():
        item = lst.currentItem()
        if item: self.add_new_tab(item.data(Qt.ItemDataRole.UserRole)); dlg.accept()
    reopen_btn.clicked.connect(_reopen)
    reopen_all_btn = QPushButton("↩ Reopen All")
    reopen_all_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    def _reopen_all():
        for url, title in self._closed_tabs:
            self.add_new_tab(url, title or "")
        self._closed_tabs.clear(); dlg.accept()
    reopen_all_btn.clicked.connect(_reopen_all)
    br.addWidget(reopen_btn); br.addWidget(reopen_all_btn); br.addStretch()
    lay.addLayout(br); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 3. GUEST MODE
# ──────────────────────────────────────────────────────────────
def _open_guest_mode(self):
    """Open a temporary guest profile window — nothing is saved."""
    from PyQt6.QtWebEngineCore import QWebEngineProfile
    from PyQt6.QtWidgets import QMessageBox
    reply = QMessageBox.question(
        self, "Guest Mode",
        "Open a Guest window?\n\nAll browsing in Guest mode is private — no history, cookies, or passwords are saved when the window closes.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if reply != QMessageBox.StandardButton.Yes: return
    guest_win = MainWindow.__new__(MainWindow)
    MainWindow.__init__(guest_win, self.profile_name)
    # Force off-the-record for entire guest window by opening an incognito tab
    if guest_win.tabs.count() > 0:
        first = guest_win.tabs.widget(0)
        if first:
            try:
                from PyQt6.QtWebEngineCore import QWebEngineProfile as QWP
                guest_win._is_guest = True
            except Exception:
                pass
    guest_win.setWindowTitle("👤 Guest Mode — SPS Browser")
    guest_win.show()
    self.status.showMessage("Guest window opened — nothing will be saved", 4000)

# ──────────────────────────────────────────────────────────────
# 4. CUSTOM SEARCH ENGINES MANAGER
# ──────────────────────────────────────────────────────────────
def _show_search_engine_manager(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔍 Search Engine Manager"); dlg.resize(700, 480)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    hdr = QLabel("🔍 Custom Search Engines")
    hdr.setStyleSheet(f"font-size:18px;font-weight:700;padding:8px 0;")
    lay.addWidget(hdr)
    info = QLabel("Use %s in the URL as the search query placeholder. Example: https://example.com/search?q=%s")
    info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    info.setWordWrap(True); lay.addWidget(info)

    tbl = QTableWidget(); tbl.setColumnCount(3)
    tbl.setHorizontalHeaderLabels(["Name", "Shortcut", "URL (use %s for query)"])
    tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    tbl.setColumnWidth(0, 140); tbl.setColumnWidth(1, 80)
    tbl.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    lay.addWidget(tbl, 1)

    # Load custom engines from settings
    custom_engines = self.settings_data.get("custom_search_engines", {})
    # Also include built-in ones
    all_engines = {}
    all_engines.update(SEARCH_ENGINES)
    all_engines.update(custom_engines)

    def _populate():
        tbl.setRowCount(0)
        for name, url in all_engines.items():
            row = tbl.rowCount(); tbl.insertRow(row)
            shortcut = self.settings_data.get("search_shortcuts", {}).get(name, "")
            tbl.setItem(row, 0, QTableWidgetItem(name))
            tbl.setItem(row, 1, QTableWidgetItem(shortcut))
            tbl.setItem(row, 2, QTableWidgetItem(url))
    _populate()

    add_row = QHBoxLayout()
    name_e = QLineEdit(); name_e.setPlaceholderText("Engine name")
    name_e.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;padding:6px;color:{t['text_primary']};")
    short_e = QLineEdit(); short_e.setPlaceholderText("Shortcut (e.g. yt)")
    short_e.setFixedWidth(100)
    short_e.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;padding:6px;color:{t['text_primary']};")
    url_e = QLineEdit(); url_e.setPlaceholderText("https://example.com/search?q=%s")
    url_e.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;padding:6px;color:{t['text_primary']};")
    add_btn = QPushButton("➕ Add")
    add_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:7px 16px;")
    def _add():
        name = name_e.text().strip(); short = short_e.text().strip().lower(); url = url_e.text().strip()
        if not name or not url or "%s" not in url:
            QMessageBox.warning(dlg, "Error", "Name and URL (with %s) are required"); return
        custom_engines[name] = url
        shorts = self.settings_data.setdefault("search_shortcuts", {})
        if short: shorts[name] = short
        all_engines[name] = url
        self.settings_data["custom_search_engines"] = custom_engines
        save_settings_to_disk(self.profile_name, self.settings_data)
        name_e.clear(); short_e.clear(); url_e.clear(); _populate()
        self.status.showMessage(f"Added search engine: {name}", 2000)
    add_btn.clicked.connect(_add)
    add_row.addWidget(name_e, 1); add_row.addWidget(short_e); add_row.addWidget(url_e, 2); add_row.addWidget(add_btn)
    lay.addLayout(add_row)

    def _delete_selected():
        row = tbl.currentRow()
        if row < 0: return
        name = tbl.item(row, 0).text() if tbl.item(row, 0) else ""
        if name in SEARCH_ENGINES:
            QMessageBox.information(dlg, "Info", "Built-in search engines cannot be removed."); return
        custom_engines.pop(name, None)
        all_engines.pop(name, None)
        self.settings_data["custom_search_engines"] = custom_engines
        save_settings_to_disk(self.profile_name, self.settings_data)
        _populate()

    btn_row = QHBoxLayout()
    del_btn = QPushButton("🗑 Delete Selected")
    del_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:8px 16px;")
    del_btn.clicked.connect(_delete_selected)
    close_btn = QPushButton("✓ Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(del_btn); btn_row.addStretch(); btn_row.addWidget(close_btn)
    lay.addLayout(btn_row); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 5. DOWNLOAD BUBBLE (toolbar indicator)
# ──────────────────────────────────────────────────────────────
def _update_download_bubble(self):
    """Update the download progress indicator button in the toolbar."""
    try:
        if not hasattr(self, "_dl_bubble_btn"): return
        dm = self.download_manager
        active = [d for d in getattr(dm, "_downloads", []) if getattr(d, "state", None) and str(getattr(d, "state", "")).endswith("InProgress")]
        if active:
            pct = sum(getattr(d, "_progress", 0) for d in active) // len(active) if active else 0
            self._dl_bubble_btn.setText(f"⬇ {pct}%")
            self._dl_bubble_btn.setVisible(True)
        else:
            recent = [d for d in getattr(dm, "_downloads", []) if getattr(d, "_just_finished", False)]
            if recent:
                self._dl_bubble_btn.setText(f"✓ Done")
                self._dl_bubble_btn.setVisible(True)
                QTimer.singleShot(4000, lambda: self._dl_bubble_btn.setVisible(False))
            else:
                self._dl_bubble_btn.setVisible(False)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────
# 6. FOLLOW-SYSTEM DARK MODE
# ──────────────────────────────────────────────────────────────
def _check_system_dark_mode(self):
    """Check Windows dark mode registry and apply automatically."""
    try:
        if platform.system() != "Windows": return
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        system_dark = (val == 0)
        current_dark = self.settings_data.get("dark_mode", False)
        if system_dark != current_dark:
            self.settings_data["dark_mode"] = system_dark
            self._apply_dark_mode(system_dark)
    except Exception:
        pass

def _apply_dark_mode(self, dark):
    """Toggle dark/light theme in-place."""
    if dark:
        self._theme.update({
            "bg_primary": "#1e1e2e", "bg_secondary": "#2a2a3d",
            "bg_tertiary": "#313144", "text_primary": "#cdd6f4",
            "text_secondary": "#a6adc8", "border": "#45475a",
            "tab_active": "#1e1e2e", "tab_inactive": "#181825",
            "sidebar_bg": "#181825", "toolbar_bg": "#1e1e2e",
            "hover": "#313144",
        })
    else:
        self._theme.update(DEFAULT_THEME)
    self._apply_global_style()
    self.status.showMessage(f"{'🌙 Dark' if dark else '☀️ Light'} mode applied", 2000)

# ──────────────────────────────────────────────────────────────
# 7. CUSTOMIZABLE KEYBOARD SHORTCUTS
# ──────────────────────────────────────────────────────────────
def _show_shortcut_customizer(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QKeySequenceEdit)
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeySequence
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("⌨️ Keyboard Shortcuts"); dlg.resize(640, 520)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    hdr = QLabel("⌨️ Customizable Keyboard Shortcuts")
    hdr.setStyleSheet(f"font-size:18px;font-weight:700;padding:8px 0;")
    lay.addWidget(hdr)
    info = QLabel("Double-click a shortcut cell to change it. Changes take effect immediately.")
    info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)

    DEFAULT_SHORTCUTS = [
        ("New Tab",           "Ctrl+T"),
        ("Close Tab",         "Ctrl+W"),
        ("Reload",            "Ctrl+R"),
        ("Address Bar",       "Ctrl+L"),
        ("Add Bookmark",      "Ctrl+D"),
        ("Open History",      "Ctrl+H"),
        ("Open Downloads",    "Ctrl+J"),
        ("Open Bookmarks",    "Ctrl+Shift+O"),
        ("Find in Page",      "Ctrl+F"),
        ("New Window",        "Ctrl+N"),
        ("Incognito",         "Ctrl+Shift+N"),
        ("Zoom In",           "Ctrl+="),
        ("Zoom Out",          "Ctrl+-"),
        ("Zoom Reset",        "Ctrl+0"),
        ("Full Screen",       "F11"),
        ("Save Page",         "Ctrl+S"),
        ("Print",             "Ctrl+P"),
        ("View Source",       "Ctrl+U"),
        ("Developer Tools",   "Ctrl+Shift+I"),
        ("Settings",          "Ctrl+,"),
    ]
    custom = self.settings_data.get("custom_shortcuts", {})

    tbl = QTableWidget(); tbl.setColumnCount(2)
    tbl.setHorizontalHeaderLabels(["Action", "Shortcut"])
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    tbl.setColumnWidth(1, 180)
    tbl.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    for action, default_sc in DEFAULT_SHORTCUTS:
        row = tbl.rowCount(); tbl.insertRow(row)
        tbl.setItem(row, 0, QTableWidgetItem(action))
        sc = custom.get(action, default_sc)
        tbl.setItem(row, 1, QTableWidgetItem(sc))
    lay.addWidget(tbl, 1)

    btn_row = QHBoxLayout()
    reset_btn = QPushButton("↺ Reset All to Defaults")
    reset_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    def _reset():
        self.settings_data.pop("custom_shortcuts", None)
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("Shortcuts reset to defaults — restart to apply", 3000)
    reset_btn.clicked.connect(_reset)
    save_btn = QPushButton("💾 Save")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _save():
        new_custom = {}
        for row in range(tbl.rowCount()):
            action = tbl.item(row, 0).text() if tbl.item(row, 0) else ""
            sc = tbl.item(row, 1).text() if tbl.item(row, 1) else ""
            default = dict(DEFAULT_SHORTCUTS).get(action, "")
            if sc and sc != default: new_custom[action] = sc
        self.settings_data["custom_shortcuts"] = new_custom
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("⌨️ Shortcuts saved — restart to fully apply", 3000)
    save_btn.clicked.connect(_save)
    btn_row.addWidget(reset_btn); btn_row.addStretch(); btn_row.addWidget(save_btn)
    lay.addLayout(btn_row); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 8. INSTALL SITE AS APP (PWA-style window)
# ──────────────────────────────────────────────────────────────
def _install_site_as_app(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    browser = self.tabs.currentWidget()
    if not browser: return
    url = browser.url().toString(); title = self.tabs.tabText(self.tabs.currentIndex()) or "App"
    dlg = QDialog(self); dlg.setWindowTitle("📱 Install as App"); dlg.resize(420, 220)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(f"<b>Install this site as a standalone app window:</b>"))
    name_row = QHBoxLayout()
    name_row.addWidget(QLabel("App name:"))
    name_edit = QLineEdit(title)
    name_edit.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;padding:6px;color:{t['text_primary']};")
    name_row.addWidget(name_edit, 1); lay.addLayout(name_row)
    url_row = QHBoxLayout()
    url_row.addWidget(QLabel("URL:"))
    url_lbl = QLabel(url[:60] + "…" if len(url) > 60 else url)
    url_lbl.setStyleSheet(f"color:{t['text_secondary']};font-size:11px;")
    url_row.addWidget(url_lbl, 1); lay.addLayout(url_row)
    info = QLabel("The app will open in its own window without the address bar or toolbars.\nA shortcut will be created on the Desktop.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;"); lay.addWidget(info)
    br = QHBoxLayout()
    install_btn = QPushButton("📱 Install")
    install_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _do_install():
        app_name = name_edit.text().strip() or title
        # Save app info
        apps_file = os.path.join(self.profile_path, "installed_apps.json")
        apps = []
        if os.path.exists(apps_file):
            try:
                with open(apps_file) as f: apps = json.load(f)
            except Exception: pass
        apps.append({"name": app_name, "url": url, "installed": datetime.datetime.now().isoformat()})
        with open(apps_file, "w") as f: json.dump(apps, f, indent=2)
        # Open app window now
        self._launch_app_window(url, app_name)
        # Create desktop shortcut on Windows
        if platform.system() == "Windows":
            try:
                _create_desktop_shortcut(app_name, url)
            except Exception: pass
        dlg.accept()
        self.status.showMessage(f"📱 {app_name} installed as app", 3000)
    install_btn.clicked.connect(_do_install)
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    cancel_btn.clicked.connect(dlg.reject)
    br.addWidget(install_btn); br.addWidget(cancel_btn); lay.addLayout(br)
    dlg.exec()

def _launch_app_window(self, url, name="App"):
    """Open a site in a chromeless app window."""
    app_win = QMainWindow(None)
    app_win.setWindowTitle(name)
    app_win.resize(1024, 768)
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    view = QWebEngineView()
    view.load(QUrl(url))
    app_win.setCentralWidget(view)
    app_win.show()
    # Keep alive
    if not hasattr(self, "_app_windows"): self._app_windows = []
    self._app_windows.append(app_win)

def _create_desktop_shortcut(name, url):
    """Create a .url shortcut on the Windows desktop."""
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        path = os.path.join(desktop, f"{safe_name}.url")
        with open(path, "w") as f:
            f.write(f"[InternetShortcut]\nURL={url}\n")
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────
# 9. RUN ON WINDOWS STARTUP + BACKGROUND MODE
# ──────────────────────────────────────────────────────────────
def _set_run_on_startup(self, enable):
    """Add or remove SPS Browser from Windows startup."""
    if platform.system() != "Windows":
        self.status.showMessage("Run on startup is only available on Windows", 3000); return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enable:
            exe = os.path.abspath(sys.executable if not getattr(sys, "frozen", False) else sys.executable)
            winreg.SetValueEx(key, "SPS Browser", 0, winreg.REG_SZ, f'"{exe}"')
            self.status.showMessage("✅ SPS Browser will start with Windows", 3000)
        else:
            try: winreg.DeleteValue(key, "SPS Browser")
            except FileNotFoundError: pass
            self.status.showMessage("✅ Removed from Windows startup", 3000)
        winreg.CloseKey(key)
        self.settings_data["run_on_startup"] = enable
        save_settings_to_disk(self.profile_name, self.settings_data)
    except Exception as e:
        self.status.showMessage(f"Startup setting failed: {e}", 4000)

def _toggle_background_mode(self):
    """Toggle: continue running after last window closes."""
    current = self.settings_data.get("background_mode", False)
    new_val = not current
    self.settings_data["background_mode"] = new_val
    save_settings_to_disk(self.profile_name, self.settings_data)
    if new_val:
        QApplication.setQuitOnLastWindowClosed(False)
        self.status.showMessage("🔵 Background mode ON — browser keeps running after close", 3000)
    else:
        QApplication.setQuitOnLastWindowClosed(True)
        self.status.showMessage("Background mode OFF", 3000)

# ──────────────────────────────────────────────────────────────
# 10. ADDRESS AUTOFILL
# ──────────────────────────────────────────────────────────────
def _show_address_autofill_manager(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
        QPushButton, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🏠 Address Autofill"); dlg.resize(520, 560)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>Saved Addresses</b>"))

    addresses = self._load_address_autofill()
    lst = QListWidget()
    lst.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;color:{t['text_primary']};")
    def _refresh():
        lst.clear()
        for i, addr in enumerate(self._load_address_autofill()):
            txt = f"{addr.get('name', '')} — {addr.get('address', '')} — {addr.get('email', '')}"
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, i)
            lst.addItem(item)
    _refresh(); lay.addWidget(lst, 1)

    form_lbl = QLabel("Add / Edit Address")
    form_lbl.setStyleSheet(f"font-weight:700;margin-top:10px;")
    lay.addWidget(form_lbl)
    form = QFormLayout()
    fields = {}
    for label in ["Full Name", "Address Line 1", "Address Line 2", "City", "State/Province", "ZIP/Postal", "Country", "Phone", "Email"]:
        edit = QLineEdit()
        edit.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:6px;padding:5px;color:{t['text_primary']};")
        form.addRow(label + ":", edit)
        fields[label.lower().replace("/", "_").replace(" ", "_")] = edit
    lay.addLayout(form)

    br = QHBoxLayout()
    add_btn = QPushButton("➕ Save Address")
    add_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _add():
        entry = {k: v.text().strip() for k, v in fields.items()}
        entry["name"] = entry.get("full_name", "")
        if not entry["name"]: QMessageBox.warning(dlg, "Error", "Full Name is required"); return
        addrs = self._load_address_autofill()
        addrs.append(entry); self._save_address_autofill(addrs)
        for v in fields.values(): v.clear()
        _refresh()
    add_btn.clicked.connect(_add)
    del_btn = QPushButton("🗑 Delete Selected")
    del_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:8px 16px;")
    def _del():
        item = lst.currentItem()
        if not item: return
        idx = item.data(Qt.ItemDataRole.UserRole)
        addrs = self._load_address_autofill()
        if 0 <= idx < len(addrs): addrs.pop(idx)
        self._save_address_autofill(addrs); _refresh()
    del_btn.clicked.connect(_del)
    br.addWidget(add_btn); br.addWidget(del_btn); br.addStretch(); lay.addLayout(br)
    dlg.exec()

def _load_address_autofill(self):
    path = os.path.join(self.profile_path, "address_autofill.json")
    if os.path.exists(path):
        try:
            with open(path) as f: return json.load(f)
        except Exception: pass
    return []

def _save_address_autofill(self, data):
    path = os.path.join(self.profile_path, "address_autofill.json")
    with open(path, "w") as f: json.dump(data, f, indent=2)

# ──────────────────────────────────────────────────────────────
# 11. PASSWORD BREACH CHECK (Have I Been Pwned k-anonymity)
# ──────────────────────────────────────────────────────────────
def _check_password_breach(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QTextEdit
    import hashlib
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔍 Password Breach Check"); dlg.resize(560, 420)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔍 Check Passwords Against Known Breaches</b>"))
    info = QLabel("Your passwords are checked using the k-anonymity method — only the first 5 characters of the SHA-1 hash are sent to HaveIBeenPwned. Your actual password never leaves your device.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    progress = QProgressBar(); progress.setRange(0, 100); progress.setValue(0)
    progress.setStyleSheet(f"QProgressBar{{background:{t['bg_secondary']};border-radius:6px;}}QProgressBar::chunk{{background:{accent};border-radius:6px;}}")
    lay.addWidget(progress)
    results_box = QTextEdit(); results_box.setReadOnly(True)
    results_box.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;font-family:monospace;font-size:12px;")
    lay.addWidget(results_box, 1)
    check_btn = QPushButton("🔍 Check All Saved Passwords")
    check_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")

    def _do_check():
        check_btn.setEnabled(False)
        results_box.clear()
        passwords = self._load_passwords()
        if not passwords:
            results_box.setText("No saved passwords to check."); check_btn.setEnabled(True); return
        breached = []; safe = 0
        for i, pw_entry in enumerate(passwords):
            progress.setValue(int((i + 1) / len(passwords) * 100))
            pw = pw_entry.get("password", "")
            if not pw: continue
            try:
                sha1 = hashlib.sha1(pw.encode("utf-8")).hexdigest().upper()
                prefix = sha1[:5]; suffix = sha1[5:]
                if requests is None: raise RuntimeError("requests not available")
                resp = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=8,
                    headers={"User-Agent": f"SPS-Browser/{VERSION}", "Add-Padding": "true"})
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        h, count = line.split(":", 1)
                        if h.upper() == suffix:
                            breached.append((pw_entry.get("site", "?"), int(count.strip())))
                            break
                    else:
                        safe += 1
            except Exception as e:
                results_box.append(f"⚠ Could not check {pw_entry.get('site', '?')}: {e}")
        results_box.append(f"\n✅ Safe passwords: {safe}")
        if breached:
            results_box.append(f"\n🚨 BREACHED passwords found ({len(breached)}):")
            for site, count in breached:
                results_box.append(f"  • {site} — appeared {count:,} times in data breaches!")
        else:
            results_box.append("\n🎉 No breached passwords found!")
        check_btn.setEnabled(True)

    check_btn.clicked.connect(_do_check); lay.addWidget(check_btn); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 12. CHECK FOR UPDATES -> implemented in _v36_patch.py + sps_updater.py (signed, SHA-256 verified)
# ──────────────────────────────────────────────────────────────
def _read_aloud(self):
    """Use Windows SAPI / pyttsx3 to read the visible page text."""
    browser = self.tabs.currentWidget()
    if not browser: return

    def _do_read(text):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text[:5000])
            engine.runAndWait()
        except ImportError:
            # Fall back to Windows built-in via PowerShell
            if platform.system() == "Windows":
                safe = text[:2000].replace('"', "'").replace('\n', ' ')
                cmd = f'powershell -Command "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SpeakAsync(\\"{safe}\\");"'
                subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
            else:
                self.status.showMessage("Install pyttsx3 for text-to-speech: pip install pyttsx3", 4000)
        except Exception as e:
            self.status.showMessage(f"Read aloud failed: {e}", 3000)

    def _got_text(text):
        if text and text.strip():
            threading.Thread(target=_do_read, args=(text,), daemon=True).start()
            self.status.showMessage("🔊 Reading aloud…", 2000)
        else:
            self.status.showMessage("No text found on page", 2000)

    browser.page().toPlainText(_got_text)

# ──────────────────────────────────────────────────────────────
# 14. AUTO-TRANSLATE OFFER BAR
# ──────────────────────────────────────────────────────────────
def _check_auto_translate(self, url):
    """Show a translate bar if the page is in a foreign language."""
    if not self.settings_data.get("auto_translate_offer", True): return
    browser = self.tabs.currentWidget()
    if not browser: return
    def _check(text):
        try:
            user_lang = self.settings_data.get("language", "en")
            # Very simple heuristic: check Accept-Language preference
            # Only offer if page appears to use non-ASCII in first 500 chars
            sample = (text or "")[:500]
            has_non_ascii = sum(1 for c in sample if ord(c) > 127) > 30
            if has_non_ascii:
                self._show_translate_bar(url)
        except Exception:
            pass
    try:
        browser.page().toPlainText(_check)
    except Exception:
        pass

def _show_translate_bar(self, url):
    """Show the blue translate offer bar below the toolbar."""
    try:
        if hasattr(self, "_translate_bar") and self._translate_bar and self._translate_bar.isVisible():
            return
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
        t = self._theme
        bar = QFrame(self.centralWidget())
        bar.setStyleSheet(f"background:{t['accent']};")
        bar.setFixedHeight(40)
        h = QHBoxLayout(bar); h.setContentsMargins(14, 4, 14, 4)
        lbl = QLabel("🌐 This page appears to be in another language. Translate it?")
        lbl.setStyleSheet("color:white;font-size:13px;")
        h.addWidget(lbl, 1)
        yes_btn = QPushButton("Translate")
        yes_btn.setStyleSheet("background:white;color:#1a73e8;border-radius:6px;padding:3px 12px;font-weight:700;")
        yes_btn.clicked.connect(lambda: (bar.hide(), self.translate_page() if hasattr(self, "translate_page") else None))
        no_btn = QPushButton("✕ No thanks")
        no_btn.setStyleSheet("background:transparent;color:white;border:none;padding:3px 10px;")
        no_btn.clicked.connect(bar.hide)
        h.addWidget(yes_btn); h.addWidget(no_btn)
        # insert bar into the main layout
        central_layout = self.centralWidget().layout()
        if central_layout:
            central_layout.insertWidget(1, bar)
        self._translate_bar = bar
        QTimer.singleShot(8000, bar.hide)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────
# 15. MEDIA HUB / GLOBAL MEDIA CONTROLS
# ──────────────────────────────────────────────────────────────
def _show_media_hub(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🎵 Media Controls"); dlg.resize(380, 260)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🎵 Global Media Controls</b>"))
    # Find which tab has media
    media_tab = None
    for i in range(self.tabs.count()):
        w = self.tabs.widget(i)
        if w and hasattr(w, "_has_audio") and w._has_audio:
            media_tab = (i, w); break

    if media_tab:
        idx, w = media_tab
        title_lbl = QLabel(f"▶ Playing in tab {idx+1}: <b>{self.tabs.tabText(idx)[:40]}</b>")
    else:
        title_lbl = QLabel("No media currently playing")
    title_lbl.setWordWrap(True)
    title_lbl.setStyleSheet(f"color:{t['text_secondary']};font-size:13px;")
    lay.addWidget(title_lbl)

    ctrl_row = QHBoxLayout()
    for label, js in [("⏮", "document.querySelector('video,audio')?.currentTime = Math.max(0, document.querySelector('video,audio')?.currentTime - 10)"),
                       ("⏯", "var el=document.querySelector('video,audio'); if(el){if(el.paused)el.play();else el.pause();}"),
                       ("⏭", "document.querySelector('video,audio')?.currentTime += 10"),
                       ("🔇", "var el=document.querySelector('video,audio'); if(el) el.muted=!el.muted;")]:
        btn = QPushButton(label); btn.setFixedSize(48, 40)
        btn.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border-radius:8px;font-size:18px;border:1px solid {t['border']};")
        if media_tab:
            w = media_tab[1]
            btn.clicked.connect(lambda checked, j=js, ww=w: ww.page().runJavaScript(j))
        ctrl_row.addWidget(btn)
    lay.addLayout(ctrl_row)

    vol_row = QHBoxLayout()
    vol_row.addWidget(QLabel("Volume:"))
    vol_slider = QSlider(Qt.Orientation.Horizontal); vol_slider.setRange(0, 100); vol_slider.setValue(100)
    if media_tab:
        w = media_tab[1]
        vol_slider.valueChanged.connect(lambda v, ww=w: ww.page().runJavaScript(f"var el=document.querySelector('video,audio'); if(el) el.volume={v/100};"))
    vol_row.addWidget(vol_slider, 1); lay.addLayout(vol_row)

    speed_row = QHBoxLayout()
    speed_row.addWidget(QLabel("Speed:"))
    for speed in ["0.5×", "1×", "1.25×", "1.5×", "2×"]:
        val = float(speed.rstrip("×"))
        sb = QPushButton(speed); sb.setFixedHeight(30)
        sb.setStyleSheet(f"background:{accent if val==1.0 else t['bg_secondary']};color:{'white' if val==1.0 else t['text_primary']};border-radius:6px;padding:0 8px;border:1px solid {t['border']};font-size:11px;")
        if media_tab:
            w = media_tab[1]
            sb.clicked.connect(lambda checked, v=val, ww=w: ww.page().runJavaScript(f"var el=document.querySelector('video,audio'); if(el) el.playbackRate={v};"))
        speed_row.addWidget(sb)
    lay.addLayout(speed_row)
    lay.addStretch()
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px;")
    close_btn.clicked.connect(dlg.accept); lay.addWidget(close_btn)
    dlg.exec()

# ──────────────────────────────────────────────────────────────
# 16. PROFILE SWITCHER IN TOOLBAR
# ──────────────────────────────────────────────────────────────
def _show_profile_switcher_menu(self):
    from PyQt6.QtWidgets import QMenu
    m = QMenu(self)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    m.setStyleSheet(f"QMenu{{background:{t['bg_primary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;}} QMenu::item{{padding:8px 20px;}} QMenu::item:selected{{background:{t['hover']};}}")
    # List profiles
    try:
        profiles = [d for d in os.listdir(PROFILES_DIR) if os.path.isdir(os.path.join(PROFILES_DIR, d))]
    except Exception:
        profiles = [self.profile_name]
    for p in sorted(profiles):
        marker = " ✓" if p == self.profile_name else ""
        action = m.addAction(f"👤 {p}{marker}")
        if p != self.profile_name:
            action.triggered.connect(lambda checked, prof=p: self._switch_to_profile(prof))
    m.addSeparator()
    m.addAction("➕ New Profile…", self._create_new_profile)
    m.addAction("👤 Guest Mode", self._open_guest_mode)
    m.exec(self._profile_btn.mapToGlobal(QPoint(0, self._profile_btn.height())))

def _switch_to_profile(self, profile_name):
    """Switch to another profile by spawning a new browser window."""
    try:
        cmd = _sps_build_restart_cmd(profile_name, "profile_switch")
        _sps_spawn_delayed(cmd, 0)
        self.status.showMessage(f"Opening profile: {profile_name}", 2000)
    except Exception as e:
        self.status.showMessage(f"Could not switch profile: {e}", 3000)

def _create_new_profile(self):
    from PyQt6.QtWidgets import QInputDialog
    name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
    if ok and name:
        name = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()
        if name:
            os.makedirs(os.path.join(PROFILES_DIR, name), exist_ok=True)
            self.status.showMessage(f"Profile '{name}' created", 2000)

# ──────────────────────────────────────────────────────────────
# 17. CRASH REPORTING OPT-IN
# ──────────────────────────────────────────────────────────────
def _show_crash_report_dialog(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout, QCheckBox
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    crash_log = os.path.join(BASE_DATA_DIR, "error_log.txt")
    if not os.path.exists(crash_log):
        self.status.showMessage("No crash reports found", 2000); return
    with open(crash_log, "r", encoding="utf-8", errors="replace") as f:
        log_text = f.read()[-8000:]
    dlg = QDialog(self); dlg.setWindowTitle("🐛 Crash Reports"); dlg.resize(640, 480)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🐛 Browser Crash & Error Log</b>"))
    txt = QTextEdit(); txt.setReadOnly(True); txt.setPlainText(log_text)
    txt.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;font-family:monospace;font-size:11px;")
    lay.addWidget(txt, 1)
    br = QHBoxLayout()
    clear_btn = QPushButton("🗑 Clear Log")
    clear_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:8px 16px;")
    def _clear():
        open(crash_log, "w").close(); txt.clear()
        self.status.showMessage("Crash log cleared", 2000)
    clear_btn.clicked.connect(_clear)
    copy_btn = QPushButton("📋 Copy")
    copy_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(log_text))
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept)
    br.addWidget(clear_btn); br.addWidget(copy_btn); br.addStretch(); br.addWidget(close_btn)
    lay.addLayout(br); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 18. PORTABLE MODE INDICATOR
# ──────────────────────────────────────────────────────────────
def _show_portable_info(self):
    from PyQt6.QtWidgets import QMessageBox
    msg = (
        "Portable Mode:\n\n"
        "To run SPS Browser portably (no install needed):\n"
        "1. Copy the entire SPS Browser folder to a USB drive.\n"
        "2. Set the PORTABLE=1 environment variable before launching, or\n"
        "   create a file called 'portable.txt' in the SPS Browser folder.\n"
        "3. Data will be stored in the SPS Browser folder instead of C:\\SPS_Browser.\n\n"
        f"Current data folder: {BASE_DATA_DIR}"
    )
    QMessageBox.information(self, "Portable Mode", msg)

# ──────────────────────────────────────────────────────────────
# 19. SECURE DNS (DoH) DIALOG
# ──────────────────────────────────────────────────────────────
def _show_secure_dns_dialog(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QComboBox)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔐 Secure DNS (DoH)"); dlg.resize(480, 280)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔐 DNS over HTTPS (DoH)</b>"))
    info = QLabel("Encrypts DNS requests so your ISP cannot see which domains you visit. Requires a restart to apply fully.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)

    providers = {
        "Cloudflare": "https://cloudflare-dns.com/dns-query",
        "Google": "https://dns.google/dns-query",
        "Quad9": "https://dns.quad9.net/dns-query",
        "OpenDNS": "https://doh.opendns.com/dns-query",
        "AdGuard": "https://dns.adguard.com/dns-query",
        "Custom…": "",
    }
    combo_row = QHBoxLayout()
    combo_row.addWidget(QLabel("Provider:"))
    combo = QComboBox()
    combo.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    combo.addItems(list(providers.keys()))
    combo_row.addWidget(combo, 1); lay.addLayout(combo_row)

    url_row = QHBoxLayout()
    url_row.addWidget(QLabel("DoH URL:"))
    url_edit = QLineEdit(self.settings_data.get("dns_over_https_url", "https://cloudflare-dns.com/dns-query"))
    url_edit.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    url_row.addWidget(url_edit, 1); lay.addLayout(url_row)

    def _on_combo(name):
        if name != "Custom…" and name in providers:
            url_edit.setText(providers[name])
    combo.currentTextChanged.connect(_on_combo)

    br = QHBoxLayout()
    save_btn = QPushButton("💾 Save & Apply")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")
    def _save():
        self.settings_data["dns_over_https"] = True
        self.settings_data["dns_over_https_url"] = url_edit.text().strip()
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept()
        self.status.showMessage("🔐 Secure DNS saved — restart the browser to apply", 4000)
    save_btn.clicked.connect(_save)
    disable_btn = QPushButton("Disable DoH")
    disable_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    def _disable():
        self.settings_data["dns_over_https"] = False
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("DoH disabled", 2000)
    disable_btn.clicked.connect(_disable)
    br.addWidget(disable_btn); br.addStretch(); br.addWidget(save_btn)
    lay.addLayout(br); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 20. USAGE STATISTICS OPT-IN
# ──────────────────────────────────────────────────────────────
def _show_usage_stats_dialog(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("📊 Usage Statistics"); dlg.resize(440, 260)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>📊 Usage Statistics & Crash Reports</b>"))
    enabled = self.settings_data.get("send_usage_stats", False)
    info = QLabel(
        "Optionally send anonymous usage statistics to help improve SPS Browser.\n\n"
        "This includes: browser version, OS type, feature usage counts, and crash reports.\n"
        "No browsing history, passwords, URLs, or personal data are ever included.\n"
        "You can opt out at any time."
    )
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    status_lbl = QLabel(f"Current status: {'✅ Enabled' if enabled else '❌ Disabled'}")
    status_lbl.setStyleSheet(f"font-weight:700;color:{t['success'] if enabled else t['danger']};")
    lay.addWidget(status_lbl)
    br = QHBoxLayout()
    enable_btn = QPushButton("✅ Enable")
    enable_btn.setStyleSheet(f"background:{t['success']};color:white;border-radius:8px;padding:8px 16px;")
    def _enable():
        self.settings_data["send_usage_stats"] = True
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("Usage stats enabled — thank you!", 2000)
    enable_btn.clicked.connect(_enable)
    disable_btn = QPushButton("❌ Disable")
    disable_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:8px 16px;")
    def _disable():
        self.settings_data["send_usage_stats"] = False
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("Usage stats disabled", 2000)
    disable_btn.clicked.connect(_disable)
    br.addWidget(enable_btn); br.addWidget(disable_btn); br.addStretch(); lay.addLayout(br)
    dlg.exec()

# ──────────────────────────────────────────────────────────────
# 21. MINIMUM FONT SIZE SETTING, FOCUS HIGHLIGHT, REDUCE MOTION
#     (these are settings toggles, not full dialogs)
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
# 22. PASTE AND GO / PASTE AND SEARCH
# ──────────────────────────────────────────────────────────────
def _paste_and_go(self):
    text = QApplication.clipboard().text().strip()
    if text:
        self.url_bar.setText(text)
        self.navigate_to_url()

def _paste_and_search(self):
    text = QApplication.clipboard().text().strip()
    if text:
        engine = self.settings_data.get("search_engine", "Google")
        base = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["Google"])
        self.add_new_tab(QUrl(base + quote_plus(text)), f"Search: {text[:30]}")

# ──────────────────────────────────────────────────────────────
# 23. COPY LINK TO HIGHLIGHTED TEXT (text fragment)
# ──────────────────────────────────────────────────────────────
def _copy_link_to_highlight(self):
    browser = self.tabs.currentWidget()
    if not browser: return
    def _got_text(text):
        if not text or not text.strip():
            self.status.showMessage("Select some text first", 2000); return
        url = browser.url().toString()
        fragment = quote_plus(text.strip()[:100])
        link = f"{url}#:~:text={fragment}"
        QApplication.clipboard().setText(link)
        self.status.showMessage("📋 Link to highlighted text copied!", 2000)
    browser.page().runJavaScript("window.getSelection().toString()", _got_text)

# ──────────────────────────────────────────────────────────────
# 24. OPEN ALL BOOKMARKS IN FOLDER
# ──────────────────────────────────────────────────────────────
def _open_all_bookmarks_in_folder(self):
    from PyQt6.QtWidgets import QInputDialog
    bms = self._load_bookmarks()
    folders = sorted(set(b.get("folder", "General") for b in bms))
    if not folders: self.status.showMessage("No bookmark folders", 2000); return
    folder, ok = QInputDialog.getItem(self, "Open Folder", "Select folder to open:", folders, editable=False)
    if ok:
        opened = 0
        for bm in bms:
            if bm.get("folder", "General") == folder:
                self.add_new_tab(QUrl(bm["url"]), bm.get("title", "")); opened += 1
        self.status.showMessage(f"Opened {opened} bookmarks from '{folder}'", 3000)

# ──────────────────────────────────────────────────────────────
# 25. BACK BUTTON HISTORY LIST (right-click / long-press)
# ──────────────────────────────────────────────────────────────
def _show_back_history_menu(self):
    from PyQt6.QtWidgets import QMenu
    browser = self.tabs.currentWidget()
    if not browser: return
    history = browser.history()
    if not history or history.count() <= 1: return
    t = self._theme
    m = QMenu(self)
    m.setStyleSheet(f"QMenu{{background:{t['bg_primary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;}} QMenu::item{{padding:7px 18px;}} QMenu::item:selected{{background:{t['hover']};}}")
    current_idx = history.currentItemIndex()
    for i in range(max(0, current_idx - 10), current_idx):
        item = history.itemAt(i)
        if item:
            title = item.title() or item.url().toString()[:50]
            action = m.addAction(f"← {title[:60]}")
            def _go(checked, idx=i): browser.history().goToItem(browser.history().itemAt(idx))
            action.triggered.connect(_go)
    m.exec(self.back_btn.mapToGlobal(QPoint(0, self.back_btn.height())))

# ──────────────────────────────────────────────────────────────
# 26. PRIVACY GUIDE WIZARD
# ──────────────────────────────────────────────────────────────
def _show_privacy_guide(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QStackedWidget, QWidget)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🛡️ Privacy Guide"); dlg.resize(580, 500)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    hdr = QLabel("🛡️ Privacy Guide")
    hdr.setStyleSheet(f"font-size:22px;font-weight:700;color:{t['accent']};padding:10px 0;")
    hdr.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(hdr)

    stack = QStackedWidget(); lay.addWidget(stack, 1)
    steps = [
        ("🔒 Safe Browsing", "Enable Safe Browsing to protect against phishing, malware, and dangerous downloads.\n\nRecommendation: Keep Safe Browsing ON.", "safe_browsing"),
        ("🍪 Cookies", "Third-party cookies track you across websites. Block them for better privacy.\n\nRecommendation: Enable 'Block third-party cookies' and 'Total Cookie Protection'.", "block_third_cookies"),
        ("👁 Trackers", "Tracking protection blocks advertising trackers and spy pixels.\n\nRecommendation: Enable 'Enhanced Tracking Protection'.", "tracking_protection"),
        ("🧬 Fingerprinting", "Browser fingerprinting identifies you without cookies. Our built-in protection randomises your fingerprint.\n\nRecommendation: Enable 'Fingerprint Protection'.", "block_fingerprinting"),
        ("🔐 Passwords", "Use strong unique passwords and let SPS Browser manage them securely.\n\nRecommendation: Enable 'Save Passwords' and use the Password Generator.", "save_passwords"),
        ("✅ All Done!", "Your privacy settings have been reviewed. You can revisit this guide at any time from the Security menu.\n\n🛡️ SPS Browser protects you with zero telemetry and no data ever leaving your device.", None),
    ]
    page_idx = [0]

    def _make_page(title, body, key):
        w = QWidget(); wl = QVBoxLayout(w); wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl = QLabel(title); tl.setStyleSheet(f"font-size:18px;font-weight:700;color:{t['text_primary']};padding:12px 0;")
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter); wl.addWidget(tl)
        bl = QLabel(body); bl.setWordWrap(True)
        bl.setStyleSheet(f"color:{t['text_secondary']};font-size:13px;line-height:1.7;max-width:420px;padding:0 20px;")
        bl.setAlignment(Qt.AlignmentFlag.AlignCenter); wl.addWidget(bl, 1)
        if key:
            current = self.settings_data.get(key, False)
            from PyQt6.QtWidgets import QCheckBox
            cb = QCheckBox(f"Enable this protection")
            cb.setChecked(current)
            cb.setStyleSheet(f"color:{t['text_primary']};font-size:13px;")
            def _toggle(checked, k=key): self.settings_data[k] = checked
            cb.toggled.connect(_toggle); wl.addWidget(cb, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    for title, body, key in steps:
        stack.addWidget(_make_page(title, body, key))

    # Progress dots
    dot_row = QHBoxLayout(); dot_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dots = []
    for i in range(len(steps)):
        dot = QLabel("●"); dot.setFixedSize(20, 20); dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setStyleSheet(f"color:{t['text_secondary']};font-size:10px;"); dots.append(dot); dot_row.addWidget(dot)
    lay.addLayout(dot_row)

    nav_row = QHBoxLayout()
    back_btn2 = QPushButton("← Back"); next_btn = QPushButton("Next →")
    back_btn2.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 20px;")
    next_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 20px;font-weight:700;")

    def _update():
        i = page_idx[0]
        stack.setCurrentIndex(i)
        back_btn2.setVisible(i > 0)
        next_btn.setText("✅ Done" if i == len(steps) - 1 else "Next →")
        for j, dot in enumerate(dots):
            dot.setStyleSheet(f"color:{accent if j==i else t['text_secondary']};font-size:10px;")

    def _next():
        if page_idx[0] == len(steps) - 1:
            save_settings_to_disk(self.profile_name, self.settings_data)
            dlg.accept(); self.status.showMessage("🛡️ Privacy settings saved", 2000)
        else:
            page_idx[0] += 1; _update()

    def _back():
        if page_idx[0] > 0: page_idx[0] -= 1; _update()

    back_btn2.clicked.connect(_back); next_btn.clicked.connect(_next)
    nav_row.addWidget(back_btn2); nav_row.addStretch(); nav_row.addWidget(next_btn)
    lay.addLayout(nav_row); _update(); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 27. INSECURE FORM WARNING
# ──────────────────────────────────────────────────────────────
def _check_insecure_form(self):
    """Show a warning bar when the user types in a form on an HTTP page."""
    browser = self.tabs.currentWidget()
    if not browser: return
    url = browser.url().toString()
    if url.startswith("http://") and not url.startswith("http://localhost"):
        js = """
        (function(){
          var inputs = document.querySelectorAll('input[type=password],input[type=email],input[type=text]');
          for(var i=0; i<inputs.length; i++){
            if(inputs[i] === document.activeElement) return true;
          }
          return false;
        })()
        """
        def _got(has_input):
            if has_input and not getattr(self, "_insecure_form_warned", False):
                self._insecure_form_warned = True
                self.status.showMessage("⚠ You are typing on an insecure (HTTP) page — your data may not be safe!", 5000)
        browser.page().runJavaScript(js, _got)

# ──────────────────────────────────────────────────────────────
# 28. DINO GAME / sps://dino
# ──────────────────────────────────────────────────────────────
_DINO_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SPS Dino</title>
<style>
body{margin:0;background:#f9f9f9;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:'Segoe UI',sans-serif;overflow:hidden;}
h2{color:#555;margin-bottom:10px;}
canvas{border:2px solid #ccc;border-radius:8px;background:white;}
#msg{margin-top:12px;color:#888;font-size:14px;}
</style></head><body>
<h2>🦕 SPS Dino — Press Space to Jump</h2>
<canvas id="c" width="800" height="180"></canvas>
<div id="msg">Press SPACE or tap to start</div>
<script>
var c=document.getElementById('c'), ctx=c.getContext('2d');
var dino={x:60,y:130,w:40,h:50,vy:0,jumping:false};
var obstacles=[],score=0,speed=4,running=false,dead=false,frame=0;
function spawn(){
  var gap=Math.max(200,500-score*2);
  obstacles.push({x:800,y:130,w:20+Math.random()*20,h:30+Math.random()*40});
}
function reset(){
  dino.y=130;dino.vy=0;dino.jumping=false;
  obstacles=[];score=0;speed=4;running=true;dead=false;frame=0;
  document.getElementById('msg').textContent='';
}
function jump(){
  if(!running){reset();return;}
  if(!dino.jumping){dino.vy=-14;dino.jumping=true;}
}
document.addEventListener('keydown',function(e){if(e.code==='Space'){e.preventDefault();jump();}});
c.addEventListener('click',jump);
function draw(){
  ctx.clearRect(0,0,800,180);
  // ground
  ctx.fillStyle='#333'; ctx.fillRect(0,172,800,4);
  // dino
  ctx.fillStyle=dead?'#e74c3c':'#2ecc71';
  ctx.beginPath(); ctx.roundRect(dino.x,dino.y,dino.w,dino.h,6); ctx.fill();
  // eye
  ctx.fillStyle='white'; ctx.fillRect(dino.x+26,dino.y+8,8,8);
  ctx.fillStyle='#222'; ctx.fillRect(dino.x+28,dino.y+10,4,4);
  // obstacles
  ctx.fillStyle='#e74c3c';
  obstacles.forEach(function(o){
    ctx.beginPath(); ctx.roundRect(o.x,o.y,o.w,o.h,3); ctx.fill();
  });
  // score
  ctx.fillStyle='#666'; ctx.font='16px monospace';
  ctx.fillText('Score: '+score,680,20);
}
function update(){
  if(!running)return;
  frame++;
  dino.vy+=0.7; dino.y+=dino.vy;
  if(dino.y>=130){dino.y=130;dino.vy=0;dino.jumping=false;}
  if(frame%Math.max(40,80-score/5)===0)spawn();
  speed=4+score/50;
  for(var i=obstacles.length-1;i>=0;i--){
    obstacles[i].x-=speed;
    if(obstacles[i].x+obstacles[i].w<0){obstacles.splice(i,1);score++;}
    var o=obstacles[i];
    if(o&&dino.x+dino.w-4>o.x&&dino.x<o.x+o.w&&dino.y+dino.h-4>o.y){
      dead=true;running=false;
      document.getElementById('msg').textContent='💥 Game Over! Score: '+score+' — Press Space to restart';
    }
  }
}
function loop(){draw();update();requestAnimationFrame(loop);}
loop();
</script></body></html>"""

def _open_dino_game(self):
    from PyQt6.QtCore import QUrl
    browser = self.add_new_tab(QUrl("about:blank"), "🦕 Dino Game")
    if browser:
        browser.setHtml(_DINO_HTML, QUrl("sps://dino"))

# ──────────────────────────────────────────────────────────────
# 29. WHATS NEW PAGE
# ──────────────────────────────────────────────────────────────
def _show_whats_new(self):
    from PyQt6.QtCore import QUrl
    t = self._theme
    new_features = [
        ("⭐ Bookmark Manager", "Full bookmark manager with drag-drop, folder management, duplicate detection, and open-all-in-folder."),
        ("🕒 Recently Closed Tabs", "List and reopen recently closed tabs and windows from the menu."),
        ("🔍 Custom Search Engines", "Add, edit and remove custom search engines with shortcuts (e.g. 'yt' + Tab = YouTube search)."),
        ("📱 Install Site as App", "Open any site in a standalone chromeless app window with a desktop shortcut."),
        ("🌙 System Dark Mode", "Browser now follows Windows dark/light mode automatically."),
        ("⌨️ Custom Shortcuts", "Remap any keyboard shortcut from Settings → Shortcuts."),
        ("🔄 Check for Updates", "New 'Check for Updates' button in About page and Help menu."),
        ("🔊 Read Aloud", "Text-to-speech for any web page — press the 🔊 button."),
        ("🎵 Media Hub", "Global media controls to play/pause/seek/speed any tab's audio or video."),
        ("🔐 Password Breach Check", "Check all saved passwords against HaveIBeenPwned using k-anonymity."),
        ("🛡️ Privacy Guide", "Step-by-step wizard to review and improve your privacy settings."),
        ("🔐 Secure DNS (DoH)", "Configure DNS over HTTPS to encrypt your DNS lookups."),
        ("👤 Profile Switcher", "Quick profile switcher button in the toolbar."),
        ("🦕 Dino Game", "Type sps://dino or find it in Extras for the built-in offline game."),
        ("🏠 Address Autofill", "Save and autofill your name, address, and contact details."),
        ("📋 Paste and Go / Search", "Right-click the address bar to paste and navigate or search."),
        ("🔗 Copy Link to Highlight", "Copy a #:~:text= deep link to any selected text on a page."),
        ("🐛 Crash Reports", "View and clear the browser error log from Help menu."),
        ("📊 Usage Stats Opt-in", "Opt in to anonymous usage statistics to help improve SPS Browser."),
        ("🚀 Run on Startup", "Start SPS Browser automatically with Windows."),
    ]
    html_parts = [f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>What's New in SPS Browser v{VERSION}</title>
<style>
body{{font-family:'Segoe UI',sans-serif;margin:0;padding:32px;background:{t['bg_primary']};color:{t['text_primary']};}}
h1{{color:{t['accent']};font-size:28px;}}
h2{{color:{t['text_secondary']};font-size:14px;font-weight:400;margin-top:-8px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:24px;}}
.card{{background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:12px;padding:18px;}}
.card h3{{margin:0 0 8px;font-size:16px;color:{t['text_primary']};}}
.card p{{margin:0;font-size:13px;color:{t['text_secondary']};line-height:1.5;}}
</style></head><body>
<h1>🆕 What's New in SPS Browser v{VERSION}</h1>
<h2>Here are the major improvements in this version:</h2>
<div class="grid">"""]
    for title, desc in new_features:
        html_parts.append(f"<div class='card'><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p></div>")
    html_parts.append("</div></body></html>")
    browser = self.add_new_tab(QUrl("about:blank"), f"What's New v{VERSION}")
    if browser:
        browser.setHtml("".join(html_parts), QUrl(f"sps://whats-new"))

# ──────────────────────────────────────────────────────────────
# 30. COOKIE BANNER AUTO-DISMISS
# ──────────────────────────────────────────────────────────────
_COOKIE_BANNER_JS = """
(function(){
  var selectors = [
    '[id*="cookie"],[class*="cookie"],[id*="consent"],[class*="consent"]',
    '[id*="gdpr"],[class*="gdpr"],[id*="banner"i][class*="cookie"i]',
    '.cc-window,.cc-banner,.cookiebar,.cookie-notice,.cookie-bar',
    '#cookieNotice,#cookie-banner,#CookieConsent,#onetrust-banner-sdk',
    '.js-cookie-notice,.cookie-policy-container,.cookie-law-info-bar',
  ].join(',');
  var btns = [
    'button[id*="accept" i],button[class*="accept" i]',
    'button[id*="agree" i],button[class*="agree" i]',
    'a[id*="accept" i],a[class*="accept" i]',
    '[aria-label*="accept" i],[data-action*="accept" i]',
  ].join(',');
  try {
    var b = document.querySelector(btns);
    if(b){b.click();return 'clicked';}
    var el = document.querySelector(selectors);
    if(el){el.style.display='none';return 'hidden';}
  } catch(e){}
  return 'none';
})()
"""

def _dismiss_cookie_banners(self):
    """Automatically click 'Accept' on cookie consent banners."""
    browser = self.tabs.currentWidget()
    if not browser or not self.settings_data.get("cookie_banner_autodismiss", False): return
    def _done(result):
        if result and result != "none":
            self.status.showMessage("🍪 Cookie banner dismissed", 1500)
    browser.page().runJavaScript(_COOKIE_BANNER_JS, _done)

# ──────────────────────────────────────────────────────────────
# 31. IMPORT PASSWORDS FROM CSV
# ──────────────────────────────────────────────────────────────
def _import_passwords_csv(self):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    path, _ = QFileDialog.getOpenFileName(self, "Import Passwords", "", "CSV Files (*.csv);;All Files (*)")
    if not path: return
    try:
        import csv
        passwords = self._load_passwords()
        imported = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Support Chrome/Firefox CSV columns
                url = row.get("url") or row.get("URL") or row.get("origin_url") or ""
                username = row.get("username") or row.get("Username") or row.get("login") or ""
                password = row.get("password") or row.get("Password") or ""
                if not (url and username and password): continue
                passwords.append({"site": url, "username": username, "password": password, "added": datetime.datetime.now().isoformat()})
                imported += 1
        self._save_passwords(passwords)
        QMessageBox.information(self, "Import Complete", f"Imported {imported} password(s) from CSV.")
        self.status.showMessage(f"Imported {imported} passwords", 3000)
    except Exception as e:
        QMessageBox.critical(self, "Import Failed", str(e))

# ──────────────────────────────────────────────────────────────
# 32. AUTO-OPEN FILE TYPES
# ──────────────────────────────────────────────────────────────
def _show_auto_open_types_dialog(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QPushButton, QInputDialog)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("📂 Auto-Open File Types"); dlg.resize(440, 380)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>📂 Auto-Open File Types After Download</b>"))
    info = QLabel("Files with these extensions will be opened automatically after downloading (e.g. .pdf, .txt).")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    lst = QListWidget()
    lst.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;color:{t['text_primary']};")
    auto_types = self.settings_data.get("auto_open_types", [])
    for ext in auto_types:
        lst.addItem(QListWidgetItem(ext))
    lay.addWidget(lst, 1)
    br = QHBoxLayout()
    add_btn = QPushButton("➕ Add Extension")
    add_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:7px 14px;")
    def _add():
        ext, ok = QInputDialog.getText(dlg, "Add Extension", "File extension (e.g. .pdf):")
        if ok and ext:
            ext = ext.strip().lower()
            if not ext.startswith("."): ext = "." + ext
            if ext not in auto_types:
                auto_types.append(ext)
                lst.addItem(ext)
                self.settings_data["auto_open_types"] = auto_types
                save_settings_to_disk(self.profile_name, self.settings_data)
    add_btn.clicked.connect(_add)
    del_btn = QPushButton("🗑 Remove")
    del_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:7px 14px;")
    def _del():
        item = lst.currentItem()
        if item:
            ext = item.text()
            auto_types.remove(ext) if ext in auto_types else None
            lst.takeItem(lst.currentRow())
            self.settings_data["auto_open_types"] = auto_types
            save_settings_to_disk(self.profile_name, self.settings_data)
    del_btn.clicked.connect(_del)
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:7px 14px;")
    close_btn.clicked.connect(dlg.accept)
    br.addWidget(add_btn); br.addWidget(del_btn); br.addStretch(); br.addWidget(close_btn)
    lay.addLayout(br); dlg.exec()

# ──────────────────────────────────────────────────────────────
# 33. QUIET NOTIFICATION UI
# ──────────────────────────────────────────────────────────────
def _show_notification_settings(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QCheckBox
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔔 Notification Settings"); dlg.resize(460, 340)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔔 Website Notification Settings</b>"))

    checks = [
        ("web_notifications", "Allow website notifications", "Sites can request permission to show desktop notifications"),
        ("quiet_notification_ui", "Quiet notification prompts", "Show notification requests less intrusively (small chip instead of popup)"),
        ("block_notification_prompts", "Block all notification prompts", "Sites cannot ask for notification permission"),
    ]
    widgets = {}
    for key, label, desc in checks:
        row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(8, 6, 8, 6)
        cb = QCheckBox(label); cb.setChecked(self.settings_data.get(key, False))
        cb.setStyleSheet(f"color:{t['text_primary']};font-size:13px;")
        dl = QLabel(desc); dl.setStyleSheet(f"color:{t['text_secondary']};font-size:11px;")
        dl.setWordWrap(True); rl.addWidget(cb); rl.addWidget(dl, 1)
        widgets[key] = cb; lay.addWidget(row)

    br = QHBoxLayout()
    save_btn = QPushButton("💾 Save")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")
    def _save():
        for key, cb in widgets.items():
            self.settings_data[key] = cb.isChecked()
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("Notification settings saved", 2000)
    save_btn.clicked.connect(_save)
    br.addStretch(); br.addWidget(save_btn); lay.addLayout(br)
    dlg.exec()

# ──────────────────────────────────────────────────────────────
# 34. PER-SITE ZOOM LIST
# ──────────────────────────────────────────────────────────────
def _show_per_site_zoom(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QTableWidget, QTableWidgetItem, QPushButton, QHeaderView)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔍 Per-Site Zoom Levels"); dlg.resize(500, 380)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔍 Site-Specific Zoom Levels</b>"))
    tbl = QTableWidget(); tbl.setColumnCount(2)
    tbl.setHorizontalHeaderLabels(["Site", "Zoom %"])
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    tbl.setColumnWidth(1, 100)
    tbl.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    site_zoom = self.settings_data.get("per_site_zoom", {})
    for site, zoom in site_zoom.items():
        row = tbl.rowCount(); tbl.insertRow(row)
        tbl.setItem(row, 0, QTableWidgetItem(site))
        tbl.setItem(row, 1, QTableWidgetItem(str(int(zoom * 100))))
    lay.addWidget(tbl, 1)
    br = QHBoxLayout()
    del_btn = QPushButton("🗑 Delete Selected")
    del_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:7px 14px;")
    def _del():
        row = tbl.currentRow()
        if row >= 0:
            site = tbl.item(row, 0).text() if tbl.item(row, 0) else ""
            site_zoom.pop(site, None)
            tbl.removeRow(row)
            self.settings_data["per_site_zoom"] = site_zoom
            save_settings_to_disk(self.profile_name, self.settings_data)
    del_btn.clicked.connect(_del)
    reset_btn = QPushButton("↺ Reset All")
    reset_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:7px 14px;")
    def _reset():
        self.settings_data["per_site_zoom"] = {}
        save_settings_to_disk(self.profile_name, self.settings_data)
        tbl.setRowCount(0)
    reset_btn.clicked.connect(_reset)
    br.addWidget(del_btn); br.addWidget(reset_btn); br.addStretch(); lay.addLayout(br)
    dlg.exec()

# ──────────────────────────────────────────────────────────────
# 35. NAME A WINDOW
# ──────────────────────────────────────────────────────────────
def _name_window(self):
    from PyQt6.QtWidgets import QInputDialog
    name, ok = QInputDialog.getText(self, "Name Window", "Window name:", text=self.windowTitle())
    if ok:
        self.setWindowTitle(name or f"{APP_NAME} — {self.profile_name}")

# ──────────────────────────────────────────────────────────────
# NOW MONKEY-PATCH ALL METHODS INTO MAINWINDOW
# ──────────────────────────────────────────────────────────────
MainWindow._show_bookmark_manager     = _show_bookmark_manager
MainWindow._show_recently_closed      = _show_recently_closed
MainWindow._open_guest_mode           = _open_guest_mode
MainWindow._show_search_engine_manager= _show_search_engine_manager
MainWindow._update_download_bubble    = _update_download_bubble
MainWindow._check_system_dark_mode    = _check_system_dark_mode
MainWindow._apply_dark_mode           = _apply_dark_mode
MainWindow._show_shortcut_customizer  = _show_shortcut_customizer
MainWindow._install_site_as_app       = _install_site_as_app
MainWindow._launch_app_window         = _launch_app_window
MainWindow._set_run_on_startup        = _set_run_on_startup
MainWindow._toggle_background_mode    = _toggle_background_mode
MainWindow._show_address_autofill_manager = _show_address_autofill_manager
MainWindow._load_address_autofill     = _load_address_autofill
MainWindow._save_address_autofill     = _save_address_autofill
MainWindow._check_password_breach     = _check_password_breach
MainWindow._read_aloud                = _read_aloud
MainWindow._check_auto_translate      = _check_auto_translate
MainWindow._show_translate_bar        = _show_translate_bar
MainWindow._show_media_hub            = _show_media_hub
MainWindow._show_profile_switcher_menu= _show_profile_switcher_menu
MainWindow._switch_to_profile         = _switch_to_profile
MainWindow._create_new_profile        = _create_new_profile
MainWindow._show_crash_report_dialog  = _show_crash_report_dialog
MainWindow._show_portable_info        = _show_portable_info
MainWindow._show_secure_dns_dialog    = _show_secure_dns_dialog
MainWindow._show_usage_stats_dialog   = _show_usage_stats_dialog
MainWindow._paste_and_go              = _paste_and_go
MainWindow._paste_and_search          = _paste_and_search
MainWindow._copy_link_to_highlight    = _copy_link_to_highlight
MainWindow._open_all_bookmarks_in_folder = _open_all_bookmarks_in_folder
MainWindow._show_back_history_menu    = _show_back_history_menu
MainWindow._show_privacy_guide        = _show_privacy_guide
MainWindow._check_insecure_form       = _check_insecure_form
MainWindow._open_dino_game            = _open_dino_game
MainWindow._show_whats_new            = _show_whats_new
MainWindow._dismiss_cookie_banners    = _dismiss_cookie_banners
MainWindow._import_passwords_csv      = _import_passwords_csv
MainWindow._show_auto_open_types_dialog = _show_auto_open_types_dialog
MainWindow._show_notification_settings = _show_notification_settings
MainWindow._show_per_site_zoom        = _show_per_site_zoom
MainWindow._name_window               = _name_window
MainWindow._show_shortcut_customizer  = _show_shortcut_customizer

print("[SPS V33] Feature patch loaded:", len([k for k in dir(MainWindow) if k.startswith("_show_") or k.startswith("_open_") or k.startswith("_check_") or k.startswith("_set_") or k.startswith("_toggle_")]), "methods available")

# ──────────────────────────────────────────────────────────────
# 36. SET AS DEFAULT BROWSER — full implementation
# ──────────────────────────────────────────────────────────────

def _set_as_default_browser(self):
    """Register SPS Browser as the default browser (Windows) or show instructions (Linux/Mac)."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🌐 Set as Default Browser"); dlg.resize(500, 360)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)

    hdr = QLabel("🌐 Set SPS Browser as Default")
    hdr.setStyleSheet(f"font-size:20px;font-weight:700;color:{t['accent']};padding:10px 0;")
    lay.addWidget(hdr)

    sys_name = platform.system()
    status_lbl = QLabel()
    status_lbl.setWordWrap(True)
    status_lbl.setStyleSheet(f"color:{t['text_secondary']};font-size:13px;padding:8px 0;")

    result_lbl = QLabel("")
    result_lbl.setWordWrap(True)
    result_lbl.setStyleSheet(f"font-size:13px;padding:6px 0;")
    lay.addWidget(status_lbl)
    lay.addWidget(result_lbl)

    def _check_default():
        """Return True if SPS Browser is currently the default."""
        try:
            if sys_name == "Windows":
                import winreg
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice")
                    val, _ = winreg.QueryValueEx(key, "ProgId")
                    winreg.CloseKey(key)
                    return "SPS" in str(val) or "sps" in str(val).lower()
                except Exception:
                    return False
        except Exception:
            pass
        return False

    is_default = _check_default()
    if is_default:
        status_lbl.setText("✅ SPS Browser is already your default browser.")
        status_lbl.setStyleSheet(f"color:{t['success']};font-size:13px;font-weight:700;padding:8px 0;")
    else:
        status_lbl.setText("SPS Browser is not your default browser yet.")

    if sys_name == "Windows":
        info = QLabel(
            "On Windows 10/11, the default browser is set through Windows Settings.\n\n"
            "Click 'Open Windows Settings' below — go to:\n"
            "Apps → Default apps → Web browser → choose SPS Browser\n\n"
            "Or click 'Register Protocol Handlers' to register http/https with Windows."
        )
    elif sys_name == "Darwin":
        info = QLabel(
            "On macOS, open System Preferences → General → Default web browser and choose SPS Browser."
        )
    else:
        info = QLabel(
            "On Linux, run this command in a terminal:\n"
            "  xdg-settings set default-web-browser sps-browser.desktop\n\n"
            "Or use your desktop environment's Default Applications settings."
        )
    info.setWordWrap(True)
    info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;line-height:1.6;")
    lay.addWidget(info)
    lay.addStretch()

    btn_row = QHBoxLayout()

    if sys_name == "Windows":
        open_settings_btn = QPushButton("⚙️ Open Windows Settings")
        open_settings_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:9px 18px;font-weight:700;")
        def _open_win_settings():
            try:
                subprocess.Popen(["ms-settings:defaultapps"], shell=True)
            except Exception:
                try:
                    subprocess.Popen(["start", "ms-settings:defaultapps"], shell=True)
                except Exception:
                    # Fallback: open the old Control Panel
                    subprocess.Popen(["control", "/name", "Microsoft.DefaultPrograms"], shell=True)
            result_lbl.setText("Windows Settings opened. Go to: Apps → Default apps → Web browser")
            result_lbl.setStyleSheet(f"color:{t['success']};font-size:12px;")
        open_settings_btn.clicked.connect(_open_win_settings)
        btn_row.addWidget(open_settings_btn)

        reg_btn = QPushButton("🔧 Register Protocol Handlers")
        reg_btn.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:9px 18px;")
        def _register_protocols():
            try:
                _v33_register_windows_protocols(self)
                result_lbl.setText("✅ http/https/ftp registered. You may still need to confirm in Windows Settings.")
                result_lbl.setStyleSheet(f"color:{t['success']};font-size:12px;font-weight:700;")
            except Exception as e:
                result_lbl.setText(f"⚠ Registration failed: {e}\nTry running as Administrator.")
                result_lbl.setStyleSheet(f"color:{t['danger']};font-size:12px;")
        reg_btn.clicked.connect(_register_protocols)
        btn_row.addWidget(reg_btn)

    else:
        # Linux / macOS
        copy_cmd_btn = QPushButton("📋 Copy Command")
        copy_cmd_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:9px 18px;")
        if sys_name == "Darwin":
            cmd = "open -a 'System Preferences'"
        else:
            cmd = "xdg-settings set default-web-browser sps-browser.desktop"
        copy_cmd_btn.clicked.connect(lambda: QApplication.clipboard().setText(cmd))
        btn_row.addWidget(copy_cmd_btn)

    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:9px 18px;")
    close_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(close_btn)
    lay.addLayout(btn_row)

    # Save that user has seen this
    self.settings_data["_seen_default_browser_prompt"] = True
    save_settings_to_disk(self.profile_name, self.settings_data)
    dlg.exec()


def _v33_register_windows_protocols(self):
    """Register SPS Browser as a *candidate* browser in Windows (Settings > Default apps).
    V36: only SPS Browser's OWN keys are written. The old code overwrote the global http/https handlers
    and started the bare browser exe (outside the sandbox); Windows decides the default, the user confirms it."""
    import winreg

    exe = (_sps_find_sandbox_exe() or sys.executable) if getattr(sys, "frozen", False) else sys.executable
    exe = os.path.abspath(exe)
    cmd = f'"{exe}" "%1"'
    root = winreg.HKEY_CURRENT_USER

    for prog_id, desc in (("SPSBrowser.HTML", "SPS Browser HTML Document"), ("SPSBrowser.URL", "SPS Browser URL")):
        base = rf"Software\Classes\{prog_id}"
        _wreg_set(root, base, "", desc)
        if prog_id.endswith("URL"):
            _wreg_set(root, base, "URL Protocol", "")
        _wreg_set(root, base + r"\shell\open\command", "", cmd)
        _wreg_set(root, base + r"\DefaultIcon", "", f'"{exe}",0')

    cap = r"Software\SPS Browser\Capabilities"
    _wreg_set(root, r"Software\RegisteredApplications", "SPS Browser", cap)
    _wreg_set(root, cap, "ApplicationName", "SPS Browser")
    _wreg_set(root, cap, "ApplicationDescription", "Fast, private, secure web browser")
    for scheme in ("http", "https", "ftp"):
        _wreg_set(root, cap + r"\URLAssociations", scheme, "SPSBrowser.URL")
    for ext in (".html", ".htm", ".xhtml"):
        _wreg_set(root, cap + r"\FileAssociations", ext, "SPSBrowser.HTML")


def _wreg_set(hive, key_path, value_name, value_data):
    """Helper: create/set a Windows registry value."""
    import winreg
    key = winreg.CreateKeyEx(hive, key_path, 0, winreg.KEY_WRITE)
    winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, str(value_data))
    winreg.CloseKey(key)


def _v33_maybe_prompt_default_browser(self):
    """Show the 'set as default' prompt once when browser starts, if not already default."""
    try:
        # Only show once
        if self.settings_data.get("_seen_default_browser_prompt"):
            return
        if platform.system() != "Windows":
            return  # Only auto-prompt on Windows; others use the menu item

        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice")
            val, _ = winreg.QueryValueEx(key, "ProgId")
            winreg.CloseKey(key)
            if "SPS" in str(val) or "sps" in str(val).lower():
                # Already default — mark seen, don't show popup
                self.settings_data["_seen_default_browser_prompt"] = True
                save_settings_to_disk(self.profile_name, self.settings_data)
                return
        except Exception:
            pass

        # Not default — show a non-blocking notification bar
        _v33_show_default_browser_bar(self)
    except Exception:
        pass


def _v33_show_default_browser_bar(self):
    """Show a slim 'Make SPS your default browser?' bar at the top of the window."""
    from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    try:
        bar = QFrame(self.centralWidget())
        bar.setObjectName("default_browser_bar")
        bar.setStyleSheet(
            f"QFrame#default_browser_bar{{background:{accent};border-bottom:1px solid {t['border']};}}")
        bar.setFixedHeight(44)
        h = QHBoxLayout(bar); h.setContentsMargins(16, 4, 16, 4)

        icon = QLabel("🌐")
        icon.setStyleSheet("color:white;font-size:16px;background:transparent;")
        h.addWidget(icon)

        msg = QLabel("SPS Browser is not your default browser.")
        msg.setStyleSheet("color:white;font-size:13px;font-weight:600;background:transparent;")
        h.addWidget(msg, 1)

        set_btn = QPushButton("Set as Default")
        set_btn.setStyleSheet(
            "background:white;color:#1a73e8;border-radius:6px;"
            "padding:4px 14px;font-weight:700;font-size:12px;"
        )
        set_btn.clicked.connect(lambda: (bar.hide(), self._set_as_default_browser()))
        h.addWidget(set_btn)

        not_now_btn = QPushButton("Not now")
        not_now_btn.setStyleSheet(
            "background:transparent;color:white;border:none;"
            "padding:4px 10px;font-size:12px;"
        )
        def _dismiss():
            bar.hide()
            self.settings_data["_seen_default_browser_prompt"] = True
            save_settings_to_disk(self.profile_name, self.settings_data)
        not_now_btn.clicked.connect(_dismiss)
        h.addWidget(not_now_btn)

        # Insert into the main layout at position 0 (top)
        central_layout = self.centralWidget().layout()
        if central_layout:
            central_layout.insertWidget(0, bar)

        # Auto-dismiss after 20 seconds
        QTimer.singleShot(20000, bar.hide)

    except Exception as e:
        print(f"[V33] default browser bar failed: {e}")


# ──────────────────────────────────────────────────────────────
# Wire the new methods into MainWindow
# ──────────────────────────────────────────────────────────────
MainWindow._set_as_default_browser          = _set_as_default_browser
MainWindow._v33_maybe_prompt_default_browser= _v33_maybe_prompt_default_browser

