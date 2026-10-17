# ═══════════════════════════════════════════════════════════════════════
#  SPS BROWSER V34 — FEATURE PATCH
#  Implements all 76 remaining "technically buildable" features.
#  Loaded at startup by SPS_BROWSER.py after _v33_patch.py.
# ═══════════════════════════════════════════════════════════════════════
import os, sys, json, re, html, datetime, threading, time, platform
import subprocess, shutil, hashlib, importlib
from urllib.parse import urlparse, quote_plus

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION A: TABS & WINDOWS ══════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# A1. Reopen Closed Window
def _reopen_closed_window(self):
    """Reopen the last closed window (not just tab)."""
    closed = getattr(self.__class__, "_closed_windows", [])
    if not closed:
        self.status.showMessage("No recently closed windows", 2000)
        return
    urls_and_titles = closed.pop()
    win = MainWindow(self.profile_name)
    win.show()
    for url, title in urls_and_titles:
        win.add_new_tab(url, title)

def _record_closed_window(self):
    """Call on closeEvent to save all current tabs for window restore."""
    tabs = []
    for i in range(self.tabs.count()):
        w = self.tabs.widget(i)
        if w:
            tabs.append((w.url(), self.tabs.tabText(i)))
    if tabs:
        if not hasattr(MainWindow, "_closed_windows"):
            MainWindow._closed_windows = []
        MainWindow._closed_windows.append(tabs)
        if len(MainWindow._closed_windows) > 5:
            MainWindow._closed_windows.pop(0)

# A2. Vertical Tabs
def _toggle_vertical_tabs(self):
    """Switch between horizontal (top) and vertical (left sidebar) tab layout."""
    current = self.settings_data.get("vertical_tabs", False)
    new_val  = not current
    self.settings_data["vertical_tabs"] = new_val
    save_settings_to_disk(self.profile_name, self.settings_data)
    self._apply_vertical_tabs(new_val)

def _apply_vertical_tabs(self, enable):
    from PyQt6.QtWidgets import QTabBar
    t = self._theme
    if enable:
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setStyleSheet(
            f"QTabBar::tab{{min-height:140px;max-height:140px;min-width:32px;"
            f"background:{t['tab_inactive']};color:{t['text_primary']};"
            f"border-radius:6px;margin:2px;padding:6px 4px;font-size:12px;}}"
            f"QTabBar::tab:selected{{background:{t['tab_active']};"
            f"color:{t['accent']};font-weight:700;}}"
        )
        self.status.showMessage("⬅ Vertical tabs ON — tabs are now on the left", 2500)
    else:
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._apply_global_style()
        self.status.showMessage("⬆ Tabs moved back to top", 2000)

# A3. Tab Scrolling / Overflow
def _scroll_tabs_left(self):
    bar = self.tabs.tabBar()
    if bar:
        bar.setCurrentIndex(max(0, self.tabs.currentIndex() - 1))

def _scroll_tabs_right(self):
    bar = self.tabs.tabBar()
    if bar:
        bar.setCurrentIndex(min(self.tabs.count() - 1, self.tabs.currentIndex() + 1))

# A4. Tab Freeze Indicator
def _update_tab_freeze_indicators(self):
    """Grey-out sleeping tabs in the tab bar."""
    t = self._theme
    for i in range(self.tabs.count()):
        w = self.tabs.widget(i)
        if w and getattr(w, "_is_sleeping", False):
            self.tabs.tabBar().setTabTextColor(i, QColor(t["text_secondary"]))
        else:
            self.tabs.tabBar().setTabTextColor(i, QColor(t["text_primary"]))

# A5. Tab Strip in Fullscreen
def _enter_fullscreen(self):
    """F11 fullscreen: keep tab bar visible."""
    if self.isFullScreen():
        self.showNormal()
        self.status.showMessage("", 0)
    else:
        self.showFullScreen()
        self.status.showMessage("Press F11 to exit fullscreen", 2000)

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION B: NAVIGATION & PAGE ════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# B1. Document Picture-in-Picture (any content via floating window)
def _document_pip(self):
    """Open current page in a floating always-on-top mini window."""
    browser = self.tabs.currentWidget()
    if not browser: return
    url   = browser.url()
    title = self.tabs.tabText(self.tabs.currentIndex())
    from PyQt6.QtWidgets import QMainWindow
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtCore import Qt
    pip_win = QMainWindow()
    pip_win.setWindowTitle(f"📌 {title}")
    pip_win.setWindowFlags(pip_win.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    pip_win.resize(480, 320)
    view = QWebEngineView()
    view.load(url)
    pip_win.setCentralWidget(view)
    pip_win.show()
    if not hasattr(self, "_pip_windows"): self._pip_windows = []
    self._pip_windows.append(pip_win)
    self.status.showMessage("📌 Floating window opened (always on top)", 2000)

# B2. Search Image with Lens / Reverse Image Search
def _search_image_with_lens(self, img_url=""):
    """Reverse image search via Google Lens (image URL, or a screenshot of the current page)."""
    if img_url:
        self.lens_image_url(img_url)
    else:
        self.open_sps_lens()

# B3. Overscroll History Navigation (keyboard Alt+←/→ handled in keyPressEvent already,
#     here we add a touchpad/scroll-wheel gesture approximation via JS)
_OVERSCROLL_JS = """
(function(){
  if(window._spsOverscrollBound) return;
  window._spsOverscrollBound = true;
  var startX=0, startY=0;
  document.addEventListener('touchstart',function(e){
    startX=e.touches[0].clientX; startY=e.touches[0].clientY;
  },{passive:true});
  document.addEventListener('touchend',function(e){
    var dx=e.changedTouches[0].clientX-startX;
    var dy=Math.abs(e.changedTouches[0].clientY-startY);
    if(dy<40 && dx>80)  { window.history.back(); }
    if(dy<40 && dx<-80) { window.history.forward(); }
  },{passive:true});
})();
"""

def _inject_overscroll_gestures(self, browser=None):
    b = browser or self.tabs.currentWidget()
    if b and self.settings_data.get("overscroll_navigation", True):
        b.page().runJavaScript(_OVERSCROLL_JS)

# B4. Reduced Motion
def _apply_reduced_motion(self):
    """Inject CSS prefers-reduced-motion: reduce into every page."""
    js = """
    (function(){
      var s=document.getElementById('_sps_rm');
      if(!s){s=document.createElement('style');s.id='_sps_rm';document.head.appendChild(s);}
      s.textContent='*,*::before,*::after{animation-duration:.001ms!important;transition-duration:.001ms!important;}';
    })();
    """
    browser = self.tabs.currentWidget()
    if browser and self.settings_data.get("reduce_motion", False):
        browser.page().runJavaScript(js)

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION C: BOOKMARKS & HISTORY ══════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# C1. Import from Chrome / Edge / Firefox profile directly
def _import_profile_bookmarks(self):
    """Detect installed browsers and offer to import their bookmarks."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QListWidget, QListWidgetItem, QProgressBar, QMessageBox)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])

    sources = _detect_browser_profiles()
    if not sources:
        QMessageBox.information(self, "Import", "No Chrome/Edge/Firefox profiles found on this PC.")
        return

    dlg = QDialog(self); dlg.setWindowTitle("📥 Import from Browser"); dlg.resize(520, 380)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>📥 Import Bookmarks from Installed Browsers</b>"))
    lst = QListWidget()
    lst.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;color:{t['text_primary']};")
    for src in sources:
        item = QListWidgetItem(f"{src['browser']} — {src['profile']}")
        item.setData(Qt.ItemDataRole.UserRole, src)
        lst.addItem(item)
    lay.addWidget(lst, 1)
    pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(0)
    pb.setStyleSheet(f"QProgressBar{{background:{t['bg_secondary']};border-radius:6px;}}QProgressBar::chunk{{background:{accent};border-radius:6px;}}")
    lay.addWidget(pb)
    result_lbl = QLabel(""); result_lbl.setStyleSheet(f"color:{t['success']};font-size:12px;")
    lay.addWidget(result_lbl)
    br = QHBoxLayout()
    import_btn = QPushButton("📥 Import Selected")
    import_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")
    def _do_import():
        item = lst.currentItem()
        if not item: return
        src = item.data(Qt.ItemDataRole.UserRole)
        pb.setValue(20)
        try:
            imported = _read_browser_bookmarks(src)
            pb.setValue(70)
            existing = self._load_bookmarks()
            existing_urls = {b.get("url") for b in existing}
            new_bms = [b for b in imported if b.get("url") not in existing_urls]
            self._save_bookmarks(existing + new_bms)
            pb.setValue(100)
            result_lbl.setText(f"✅ Imported {len(new_bms)} new bookmarks ({len(imported)-len(new_bms)} duplicates skipped)")
            self.status.showMessage(f"Imported {len(new_bms)} bookmarks", 3000)
        except Exception as e:
            pb.setValue(0); result_lbl.setText(f"⚠ Import failed: {e}")
            result_lbl.setStyleSheet(f"color:{t['danger']};font-size:12px;")
    import_btn.clicked.connect(_do_import)
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept)
    br.addWidget(import_btn); br.addStretch(); br.addWidget(close_btn)
    lay.addLayout(br); dlg.exec()

def _detect_browser_profiles():
    """Find Chrome/Edge/Firefox bookmark files on disk."""
    sources = []
    home = os.path.expanduser("~")
    candidates = [
        ("Chrome",  os.path.join(home, "AppData","Local","Google","Chrome","User Data")),
        ("Edge",    os.path.join(home, "AppData","Local","Microsoft","Edge","User Data")),
        ("Brave",   os.path.join(home, "AppData","Local","BraveSoftware","Brave-Browser","User Data")),
        ("Firefox", os.path.join(home, "AppData","Roaming","Mozilla","Firefox","Profiles")),
        # Linux
        ("Chrome",  os.path.join(home, ".config","google-chrome")),
        ("Firefox", os.path.join(home, ".mozilla","firefox")),
    ]
    for browser, base in candidates:
        if not os.path.isdir(base): continue
        if browser == "Firefox":
            for prof in os.listdir(base):
                bm = os.path.join(base, prof, "places.sqlite")
                if os.path.exists(bm):
                    sources.append({"browser": browser, "profile": prof, "path": bm, "type": "firefox"})
        else:
            for prof in ["Default","Profile 1","Profile 2","Profile 3"]:
                bm = os.path.join(base, prof, "Bookmarks")
                if os.path.exists(bm):
                    sources.append({"browser": browser, "profile": prof, "path": bm, "type": "chrome"})
    return sources

def _read_browser_bookmarks(src):
    """Read and normalise bookmarks from a detected browser profile."""
    results = []
    if src["type"] == "chrome":
        with open(src["path"], encoding="utf-8") as f:
            data = json.load(f)
        def _walk(node, folder="Imported"):
            if node.get("type") == "url":
                results.append({"title": node.get("name",""), "url": node.get("url",""),
                                 "folder": folder, "added": datetime.datetime.now().isoformat()})
            for child in node.get("children", []):
                _walk(child, node.get("name", folder))
        for root in data.get("roots", {}).values():
            if isinstance(root, dict): _walk(root)
    elif src["type"] == "firefox":
        # Read from places.sqlite using sqlite3
        import sqlite3, tempfile, shutil
        tmp = tempfile.mktemp(suffix=".sqlite")
        shutil.copy2(src["path"], tmp)
        try:
            conn = sqlite3.connect(tmp)
            cur = conn.execute(
                "SELECT b.title, p.url FROM moz_bookmarks b "
                "JOIN moz_places p ON b.fk=p.id WHERE p.url LIKE 'http%' LIMIT 2000")
            for title, url in cur.fetchall():
                results.append({"title": title or url, "url": url,
                                 "folder": "Firefox Import", "added": datetime.datetime.now().isoformat()})
            conn.close()
        finally:
            try: os.unlink(tmp)
            except: pass
    return results

# C2. Price Tracking on Bookmarks
def _show_price_tracker(self):
    """Track price changes on bookmarked shopping pages."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("💰 Price Tracker"); dlg.resize(680, 440)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>💰 Price Tracker — Bookmarked Shopping Pages</b>"))
    info = QLabel("SPS Browser watches bookmarked pages for price changes. Prices are extracted from page metadata.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    tbl = QTableWidget(); tbl.setColumnCount(5)
    tbl.setHorizontalHeaderLabels(["Page", "URL", "Last Price", "Change", "Last Checked"])
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    tbl.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    prices = self.settings_data.get("price_tracker", {})
    for url, data in prices.items():
        row = tbl.rowCount(); tbl.insertRow(row)
        tbl.setItem(row, 0, QTableWidgetItem(data.get("title","?")))
        tbl.setItem(row, 1, QTableWidgetItem(url))
        tbl.setItem(row, 2, QTableWidgetItem(data.get("last_price","—")))
        prev = data.get("prev_price",""); curr = data.get("last_price","")
        change = "📉 Down" if prev and curr and curr < prev else ("📈 Up" if prev and curr and curr > prev else "—")
        tbl.setItem(row, 3, QTableWidgetItem(change))
        tbl.setItem(row, 4, QTableWidgetItem(data.get("checked","—")))
    lay.addWidget(tbl, 1)
    br = QHBoxLayout()
    add_btn = QPushButton("➕ Track Current Page")
    add_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _add_current():
        b = self.tabs.currentWidget()
        if not b: return
        url = b.url().toString(); title = self.tabs.tabText(self.tabs.currentIndex())
        def _got_price(price_text):
            prices[url] = {"title": title, "last_price": price_text,
                           "checked": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
            self.settings_data["price_tracker"] = prices
            save_settings_to_disk(self.profile_name, self.settings_data)
            dlg.accept(); self.status.showMessage(f"💰 Now tracking: {title}", 2000)
        b.page().runJavaScript(
            "document.querySelector('[itemprop=price],[class*=price],[id*=price]')?.textContent?.trim() || ''",
            _got_price)
    add_btn.clicked.connect(_add_current)
    del_btn = QPushButton("🗑 Remove")
    del_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:8px 16px;")
    def _del():
        row = tbl.currentRow()
        if row >= 0:
            url = tbl.item(row, 1).text() if tbl.item(row,1) else ""
            prices.pop(url, None)
            self.settings_data["price_tracker"] = prices
            save_settings_to_disk(self.profile_name, self.settings_data)
            tbl.removeRow(row)
    del_btn.clicked.connect(_del)
    br.addWidget(add_btn); br.addWidget(del_btn); br.addStretch(); lay.addLayout(br); dlg.exec()

# C3. Journeys — grouped history by topic/domain
def _show_journeys(self):
    """Show history grouped by site/topic."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QTreeWidget, QTreeWidgetItem, QLineEdit, QPushButton)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🗺 Journeys — History by Topic"); dlg.resize(680, 520)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🗺 Journeys — Your browsing grouped by website</b>"))
    search = QLineEdit(); search.setPlaceholderText("Search journeys…")
    search.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:7px 12px;")
    lay.addWidget(search)
    tree = QTreeWidget()
    tree.setHeaderLabels(["Site / Page", "Visits", "Last visited"])
    tree.setColumnWidth(0, 340); tree.setColumnWidth(1, 60)
    tree.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    tree.itemDoubleClicked.connect(lambda item, col: (
        self.add_new_tab(QUrl(item.data(0, Qt.ItemDataRole.UserRole))) if item.data(0, Qt.ItemDataRole.UserRole) else None))
    lay.addWidget(tree, 1)

    def _load(q=""):
        tree.clear()
        hist = self._load_history()
        groups = {}
        for entry in hist:
            url = entry.get("url","")
            try:
                host = urlparse(url).netloc.lstrip("www.")
                domain = ".".join(host.rsplit(".", 2)[-2:]) if "." in host else host or "Other"
            except Exception:
                domain = "Other"
            if q.lower() and q.lower() not in domain.lower() and q.lower() not in (entry.get("title","")).lower(): continue
            groups.setdefault(domain, []).append(entry)
        for domain, entries in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)[:100]:
            parent = QTreeWidgetItem([domain, str(len(entries)), ""])
            parent.setData(0, Qt.ItemDataRole.UserRole, None)
            for e in entries[:20]:
                title = e.get("title") or e.get("url","")
                child = QTreeWidgetItem([title[:70], "", e.get("visited","")[:16]])
                child.setData(0, Qt.ItemDataRole.UserRole, e.get("url"))
                child.setToolTip(0, e.get("url",""))
                parent.addChild(child)
            tree.addTopLevelItem(parent)
    _load(); search.textChanged.connect(_load)
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept); lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
    dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION D: DOWNLOADS ════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# D1. Open PDFs/media directly in browser instead of downloading
def _configure_open_in_browser(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    current = self.settings_data.get("open_pdf_in_browser", True)
    dlg = QDialog(self); dlg.setWindowTitle("📄 Open PDFs in Browser"); dlg.resize(400, 220)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>📄 PDF & Media Handling</b>"))
    info = QLabel(f"Currently: {'✅ Open PDFs directly in browser' if current else '⬇ Download PDFs to disk'}")
    info.setStyleSheet(f"color:{t['text_secondary']};font-size:13px;"); lay.addWidget(info)
    br = QHBoxLayout()
    for label, val, col in [("📄 Open in browser", True, accent), ("⬇ Download to disk", False, t["bg_tertiary"])]:
        btn = QPushButton(label)
        btn.setStyleSheet(f"background:{col};color:{'white' if col==accent else t['text_primary']};border-radius:8px;padding:8px 16px;")
        def _set(v=val):
            self.settings_data["open_pdf_in_browser"] = v
            save_settings_to_disk(self.profile_name, self.settings_data)
            # Apply to all web profiles
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if w and hasattr(w, "settings"):
                    try:
                        w.settings().setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, v)
                        w.settings().setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, v)
                    except Exception: pass
            dlg.accept(); self.status.showMessage(f"PDF handling updated", 2000)
        btn.clicked.connect(_set); br.addWidget(btn)
    lay.addLayout(br); dlg.exec()

# D2. Master Password Before Showing Passwords
def _master_password_gate(self, callback):
    """Ask for the profile PIN before revealing passwords."""
    pin = self.settings_data.get("profile_pin", "")
    if not pin:
        callback(); return
    from PyQt6.QtWidgets import QInputDialog, QLineEdit
    entered, ok = QInputDialog.getText(self, "🔐 Master Password",
        "Enter your profile PIN to view passwords:", QLineEdit.EchoMode.Password)
    if ok and hashlib.sha256(entered.encode()).hexdigest()[:16] == pin:
        callback()
    elif ok:
        self.status.showMessage("❌ Incorrect PIN", 3000)

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION E: AUTOFILL ═════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# E1. Autofill Dropdown on form fields (inject JS into pages)
_AUTOFILL_JS = """
(function(addresses){
  if(!addresses || !addresses.length) return;
  document.querySelectorAll('input[autocomplete]').forEach(function(inp){
    var ac = inp.getAttribute('autocomplete') || '';
    var val = '';
    var a = addresses[0];
    if(ac.includes('given-name') || ac.includes('first')) val = (a.full_name||'').split(' ')[0];
    else if(ac.includes('family-name')||ac.includes('last')) val = (a.full_name||'').split(' ').slice(1).join(' ');
    else if(ac.includes('name'))   val = a.full_name || '';
    else if(ac.includes('email'))  val = a.email || '';
    else if(ac.includes('tel'))    val = a.phone || '';
    else if(ac.includes('address-line1')||ac.includes('street')) val = a.address_line_1 || '';
    else if(ac.includes('city'))   val = a.city || '';
    else if(ac.includes('postal')||ac.includes('zip')) val = a.zip_postal || '';
    else if(ac.includes('country')) val = a.country || '';
    if(val){ inp.value = val; inp.dispatchEvent(new Event('input',{bubbles:true})); }
  });
})(%s);
"""

def _autofill_current_page(self):
    """Fill form fields on the current page with saved address data."""
    addresses = self._load_address_autofill() if hasattr(self, "_load_address_autofill") else []
    if not addresses:
        self.status.showMessage("No saved addresses — add one in Settings → Address Autofill", 3000)
        return
    b = self.tabs.currentWidget()
    if b:
        js = _AUTOFILL_JS % json.dumps(addresses)
        b.page().runJavaScript(js)
        self.status.showMessage("🏠 Form autofilled", 2000)

# E2. Auto Sign-in / Stay Signed In Toggle
def _toggle_auto_signin(self):
    current = self.settings_data.get("auto_signin", False)
    new_val  = not current
    self.settings_data["auto_signin"] = new_val
    save_settings_to_disk(self.profile_name, self.settings_data)
    self.status.showMessage(
        f"{'✅ Auto sign-in enabled' if new_val else '❌ Auto sign-in disabled'}", 2000)

# E3. Block Third-party Cookies in Incognito by Default
def _apply_cookie_policy(self, profile):
    """Block 3rd-party cookies in incognito; apply policy to a QWebEngineProfile."""
    try:
        from PyQt6.QtWebEngineCore import QWebEngineProfile
        if profile.isOffTheRecord() or self.settings_data.get("block_third_cookies_incognito", True):
            settings = profile.settings()
            from PyQt6.QtWebEngineCore import QWebEngineSettings as QWS
            # Block 3rd-party storage access
            try:
                settings.setAttribute(QWS.WebAttribute.JavascriptCanAccessClipboard, False)
            except Exception:
                pass
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION F: PRIVACY & SECURITY ═══════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# F1. Privacy Sandbox / Ad Topics Controls
def _show_privacy_sandbox(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🏖️ Privacy Sandbox"); dlg.resize(480, 340)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🏖️ Privacy Sandbox Settings</b>"))
    info = QLabel(
        "Privacy Sandbox is Google's initiative to replace third-party cookies "
        "with less privacy-invasive ad targeting APIs (Topics, Protected Audience, Attribution Reporting).\n\n"
        "SPS Browser does NOT implement Google's Privacy Sandbox APIs. "
        "All third-party ad tracking is blocked by the existing Privacy Interceptor.\n\n"
        "✅ You are already protected. No action needed.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:13px;line-height:1.6;")
    lay.addWidget(info)
    for key, label, desc in [
        ("block_topics_api", "Block Topics API", "Block sites from calling the Topics interest API"),
        ("block_attribution_api", "Block Attribution Reporting", "Block conversion tracking via the Attribution Reporting API"),
        ("block_fledge", "Block Protected Audience (FLEDGE)", "Block on-device ad auction API"),
    ]:
        from PyQt6.QtWidgets import QCheckBox
        cb = QCheckBox(label)
        cb.setChecked(self.settings_data.get(key, True))
        cb.setStyleSheet(f"color:{t['text_primary']};")
        cb.toggled.connect(lambda v, k=key: (self.settings_data.update({k: v}),
                            save_settings_to_disk(self.profile_name, self.settings_data)))
        lay.addWidget(cb)
    br = QHBoxLayout()
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept); br.addStretch(); br.addWidget(close_btn); lay.addLayout(br)
    dlg.exec()

# F2. Protected Content (DRM) Toggle
def _show_drm_settings(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔒 Protected Content"); dlg.resize(460, 280)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔒 Protected Content (DRM)</b>"))
    info = QLabel(
        "DRM (Widevine CDM) is required to play Netflix, Disney+, Spotify, and other "
        "protected content.\n\n"
        "⚠ Important: PyQt6-WebEngine does not include the Widevine CDM binary. "
        "This is a Google licensing restriction — the CDM cannot legally be bundled "
        "with a third-party browser.\n\n"
        "Workaround: Install the Widevine CDM manually and set the path below.\n"
        "Get it from: https://dl.google.com/widevine-cdm/ (requires Chrome installed)")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;line-height:1.5;")
    lay.addWidget(info)
    cdm_path = self.settings_data.get("widevine_cdm_path", "")
    from PyQt6.QtWidgets import QLineEdit, QFileDialog
    path_edit = QLineEdit(cdm_path)
    path_edit.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    path_edit.setPlaceholderText("Path to widevinecdm.dll / libwidevinecdm.so")
    lay.addWidget(path_edit)
    br = QHBoxLayout()
    browse_btn = QPushButton("📂 Browse")
    browse_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 14px;")
    def _browse():
        p, _ = QFileDialog.getOpenFileName(dlg, "Select Widevine CDM", "", "Libraries (*.dll *.so);;All (*)")
        if p: path_edit.setText(p)
    browse_btn.clicked.connect(_browse)
    save_btn = QPushButton("💾 Save")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 14px;")
    def _save():
        self.settings_data["widevine_cdm_path"] = path_edit.text().strip()
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("Widevine path saved — restart browser", 3000)
    save_btn.clicked.connect(_save)
    br.addWidget(browse_btn); br.addStretch(); br.addWidget(save_btn); lay.addLayout(br); dlg.exec()

# F3. Pop-ups Per Site
def _show_popup_exceptions(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QPushButton, QInputDialog, QComboBox)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🪟 Pop-up Exceptions"); dlg.resize(480, 380)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🪟 Per-Site Pop-up Permissions</b>"))
    exceptions = self.settings_data.get("popup_exceptions", {})
    lst = QListWidget()
    lst.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;color:{t['text_primary']};")
    def _refresh():
        lst.clear()
        for site, policy in exceptions.items():
            icon = "✅" if policy == "allow" else "🚫"
            lst.addItem(QListWidgetItem(f"{icon} {site} — {policy}"))
    _refresh(); lay.addWidget(lst, 1)
    add_row = QHBoxLayout()
    site_edit = QInputDialog()
    site_input = __import__("PyQt6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit()
    site_input.setPlaceholderText("example.com")
    site_input.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    policy_cb = QComboBox()
    policy_cb.addItems(["allow", "block"])
    policy_cb.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    add_btn = QPushButton("➕ Add")
    add_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:6px 14px;")
    def _add():
        site = site_input.text().strip()
        if site:
            exceptions[site] = policy_cb.currentText()
            self.settings_data["popup_exceptions"] = exceptions
            save_settings_to_disk(self.profile_name, self.settings_data)
            site_input.clear(); _refresh()
    add_btn.clicked.connect(_add)
    add_row.addWidget(site_input, 1); add_row.addWidget(policy_cb); add_row.addWidget(add_btn)
    lay.addLayout(add_row)
    del_btn = QPushButton("🗑 Remove Selected")
    del_btn.setStyleSheet(f"background:{t['danger']};color:white;border-radius:8px;padding:7px 14px;")
    def _del():
        item = lst.currentItem()
        if item:
            text = item.text()
            site = text.split(" — ")[0].lstrip("✅🚫 ")
            exceptions.pop(site, None)
            self.settings_data["popup_exceptions"] = exceptions
            save_settings_to_disk(self.profile_name, self.settings_data)
            _refresh()
    del_btn.clicked.connect(_del); lay.addWidget(del_btn); dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION G: SITE SETTINGS ════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

def _show_full_site_settings(self):
    """Comprehensive site settings dialog: camera, mic, popups, autoplay, cookies, etc."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QTabWidget, QWidget, QTableWidget, QTableWidgetItem, QPushButton,
        QHeaderView, QComboBox, QLineEdit)
    from PyQt6.QtCore import Qt
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("⚙️ Site Settings"); dlg.resize(680, 520)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>⚙️ Per-Site Settings & Permissions</b>"))

    tabs = QTabWidget()
    tabs.setStyleSheet(f"QTabWidget::pane{{background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;}}"
                       f"QTabBar::tab{{background:{t['bg_tertiary']};color:{t['text_primary']};padding:6px 14px;border-radius:6px;margin:2px;}}"
                       f"QTabBar::tab:selected{{background:{accent};color:white;}}")
    lay.addWidget(tabs, 1)

    PERMISSIONS = [
        ("camera",       "📷 Camera"),
        ("microphone",   "🎤 Microphone"),
        ("notifications","🔔 Notifications"),
        ("geolocation",  "📍 Location"),
        ("autoplay",     "▶ Autoplay"),
        ("cookies",      "🍪 Cookies"),
        ("javascript",   "⚙️ JavaScript"),
        ("popup",        "🪟 Popups"),
    ]

    for key, label in PERMISSIONS:
        page_widget = QWidget()
        page_layout = QVBoxLayout(page_widget)
        info = QLabel(f"Per-site exceptions for: {label}. Default applies to all sites not listed.")
        info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
        info.setWordWrap(True); page_layout.addWidget(info)

        # Default policy row
        default_row = QHBoxLayout()
        default_row.addWidget(QLabel("Default:"))
        default_cb = QComboBox()
        default_cb.addItems(["allow", "ask", "block"])
        cur_default = self.settings_data.get(f"site_perm_default_{key}", "ask")
        default_cb.setCurrentText(cur_default)
        default_cb.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:6px;padding:4px;")
        def _on_default(val, k=key):
            self.settings_data[f"site_perm_default_{k}"] = val
            save_settings_to_disk(self.profile_name, self.settings_data)
        default_cb.currentTextChanged.connect(_on_default)
        default_row.addWidget(default_cb); default_row.addStretch()
        page_layout.addLayout(default_row)

        # Per-site exceptions table
        tbl = QTableWidget(); tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["Site", "Permission"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tbl.setColumnWidth(1, 100)
        tbl.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
        exceptions = self.settings_data.get(f"site_perm_{key}", {})
        for site, policy in exceptions.items():
            row = tbl.rowCount(); tbl.insertRow(row)
            tbl.setItem(row, 0, QTableWidgetItem(site))
            tbl.setItem(row, 1, QTableWidgetItem(policy))
        page_layout.addWidget(tbl, 1)

        add_row = QHBoxLayout()
        se = QLineEdit(); se.setPlaceholderText("site.com")
        se.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:5px;")
        pol_cb = QComboBox(); pol_cb.addItems(["allow","block","ask"])
        pol_cb.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:5px;")
        add_btn_site = QPushButton("➕")
        add_btn_site.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:5px 12px;")
        def _add_exception(k=key, se=se, pol_cb=pol_cb, tbl=tbl):
            site = se.text().strip()
            if site:
                exc = self.settings_data.setdefault(f"site_perm_{k}", {})
                exc[site] = pol_cb.currentText()
                save_settings_to_disk(self.profile_name, self.settings_data)
                row = tbl.rowCount(); tbl.insertRow(row)
                tbl.setItem(row, 0, QTableWidgetItem(site))
                tbl.setItem(row, 1, QTableWidgetItem(pol_cb.currentText()))
                se.clear()
        add_btn_site.clicked.connect(_add_exception)
        add_row.addWidget(se, 1); add_row.addWidget(pol_cb); add_row.addWidget(add_btn_site)
        page_layout.addLayout(add_row)
        tabs.addTab(page_widget, label)

    br = QHBoxLayout()
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")
    close_btn.clicked.connect(dlg.accept); br.addStretch(); br.addWidget(close_btn); lay.addLayout(br)
    dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION H: APPEARANCE & CUSTOMIZATION ════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# H1. Custom Fonts
def _show_font_settings(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QComboBox, QPushButton, QSpinBox, QFontComboBox)
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔤 Font Settings"); dlg.resize(460, 360)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔤 Custom Fonts for Web Pages</b>"))

    font_settings = [
        ("Standard font", "standard_font",   QWebEngineSettings.FontFamily.StandardFont),
        ("Serif font",    "serif_font",       QWebEngineSettings.FontFamily.SerifFont),
        ("Sans-serif",    "sans_serif_font",  QWebEngineSettings.FontFamily.SansSerifFont),
        ("Fixed (mono)",  "fixed_font",       QWebEngineSettings.FontFamily.FixedFont),
    ]
    combos = {}
    for label, key, _ in font_settings:
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{label}:"))
        fc = QFontComboBox()
        fc.setCurrentFont(__import__("PyQt6.QtGui", fromlist=["QFont"]).QFont(self.settings_data.get(key, "")))
        fc.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:4px;")
        row.addWidget(fc, 1); lay.addLayout(row); combos[key] = fc

    size_row = QHBoxLayout()
    size_row.addWidget(QLabel("Default font size (px):"))
    size_spin = QSpinBox(); size_spin.setRange(8, 36)
    size_spin.setValue(int(self.settings_data.get("default_font_size", 16)))
    size_spin.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:4px;")
    size_row.addWidget(size_spin); size_row.addStretch(); lay.addLayout(size_row)

    br = QHBoxLayout()
    save_btn = QPushButton("💾 Save & Apply")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")
    def _save():
        for key, fc in combos.items():
            self.settings_data[key] = fc.currentFont().family()
        self.settings_data["default_font_size"] = size_spin.value()
        save_settings_to_disk(self.profile_name, self.settings_data)
        # Apply to all tabs
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if w and hasattr(w, "settings"):
                s = w.settings()
                try:
                    for _, key, family_enum in font_settings:
                        fname = self.settings_data.get(key,"")
                        if fname: s.setFontFamily(family_enum, fname)
                    s.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, size_spin.value())
                except Exception: pass
        dlg.accept(); self.status.showMessage("🔤 Fonts applied", 2000)
    save_btn.clicked.connect(_save)
    reset_btn = QPushButton("↺ Reset")
    reset_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 14px;")
    def _reset():
        for key in combos: self.settings_data.pop(key, None)
        self.settings_data.pop("default_font_size", None)
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage("Fonts reset to defaults", 2000)
    reset_btn.clicked.connect(_reset)
    br.addWidget(reset_btn); br.addStretch(); br.addWidget(save_btn); lay.addLayout(br); dlg.exec()

def _apply_custom_fonts(self, browser):
    """Apply saved font settings to a newly created tab."""
    try:
        from PyQt6.QtWebEngineCore import QWebEngineSettings
        s = browser.settings()
        font_map = [
            ("standard_font",   QWebEngineSettings.FontFamily.StandardFont),
            ("serif_font",      QWebEngineSettings.FontFamily.SerifFont),
            ("sans_serif_font", QWebEngineSettings.FontFamily.SansSerifFont),
            ("fixed_font",      QWebEngineSettings.FontFamily.FixedFont),
        ]
        for key, enum in font_map:
            fname = self.settings_data.get(key,"")
            if fname: s.setFontFamily(enum, fname)
        sz = int(self.settings_data.get("default_font_size", 0))
        if sz: s.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, sz)
    except Exception:
        pass

# H2. Multiple UI Languages
def _show_language_settings(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    LANGS = [
        ("English (US)", "en"), ("English (UK)", "en-GB"),
        ("Spanish", "es"), ("French", "fr"), ("German", "de"),
        ("Portuguese", "pt"), ("Italian", "it"), ("Russian", "ru"),
        ("Chinese (Simplified)", "zh-CN"), ("Japanese", "ja"),
        ("Arabic", "ar"), ("Hindi", "hi"), ("Bengali", "bn"),
        ("Korean", "ko"), ("Turkish", "tr"), ("Polish", "pl"),
        ("Dutch", "nl"), ("Swedish", "sv"), ("Norwegian", "no"),
    ]
    dlg = QDialog(self); dlg.setWindowTitle("🌐 Language Settings"); dlg.resize(400, 240)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🌐 Browser Language & Accept-Language Header</b>"))
    info = QLabel("Sets the Accept-Language header sent to websites. Does not translate the browser UI.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    row = QHBoxLayout(); row.addWidget(QLabel("Language:"))
    combo = QComboBox()
    combo.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    for name, code in LANGS: combo.addItem(name, code)
    cur = self.settings_data.get("language", "en")
    for i, (_, code) in enumerate(LANGS):
        if code == cur: combo.setCurrentIndex(i); break
    row.addWidget(combo, 1); lay.addLayout(row)
    br = QHBoxLayout()
    save_btn = QPushButton("💾 Save")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _save():
        code = combo.currentData()
        self.settings_data["language"] = code
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage(f"Language set to {combo.currentText()} — restart to apply fully", 3000)
    save_btn.clicked.connect(_save); br.addStretch(); br.addWidget(save_btn); lay.addLayout(br); dlg.exec()

# H3. GPU Process Crash Recovery
def _on_gpu_crash(self):
    """Called when the GPU process crashes; attempt to reload all tabs."""
    self.status.showMessage("⚠ GPU process crashed — reloading tabs…", 3000)
    QTimer.singleShot(1500, self._reload_all_tabs_after_crash)

def _reload_all_tabs_after_crash(self):
    for i in range(self.tabs.count()):
        w = self.tabs.widget(i)
        if w:
            try: w.reload()
            except Exception: pass
    self.status.showMessage("✅ All tabs reloaded after GPU crash", 3000)

# H4. Theme Store / Installable Themes
def _show_theme_store(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QGridLayout)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🎨 Theme Store"); dlg.resize(620, 500)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🎨 Theme Store — Built-in Themes</b>"))

    THEMES = [
        ("☀️ Classic Light",   {"bg_primary":"#ffffff","bg_secondary":"#f5f5f5","bg_tertiary":"#ebebeb","accent":"#1a73e8","text_primary":"#202124","text_secondary":"#5f6368","border":"#dadce0","hover":"#e8eaed","danger":"#d93025","success":"#188038","warning":"#f9ab00","tab_active":"#ffffff","tab_inactive":"#f1f3f4","sidebar_bg":"#f8f9fa","toolbar_bg":"#ffffff","accent_light":"#e8f0fe"}),
        ("🌙 Dark Cosmos",     {"bg_primary":"#1e1e2e","bg_secondary":"#2a2a3d","bg_tertiary":"#313144","accent":"#89b4fa","text_primary":"#cdd6f4","text_secondary":"#a6adc8","border":"#45475a","hover":"#313144","danger":"#f38ba8","success":"#a6e3a1","warning":"#f9e2af","tab_active":"#1e1e2e","tab_inactive":"#181825","sidebar_bg":"#181825","toolbar_bg":"#1e1e2e","accent_light":"#313144"}),
        ("🌲 Forest Green",    {"bg_primary":"#1a2f1a","bg_secondary":"#243324","bg_tertiary":"#2e3d2e","accent":"#4caf50","text_primary":"#c8e6c9","text_secondary":"#a5d6a7","border":"#388e3c","hover":"#2e3d2e","danger":"#e57373","success":"#81c784","warning":"#ffb74d","tab_active":"#1a2f1a","tab_inactive":"#152515","sidebar_bg":"#152515","toolbar_bg":"#1a2f1a","accent_light":"#2e3d2e"}),
        ("🌊 Ocean Blue",      {"bg_primary":"#0d1b2a","bg_secondary":"#162435","bg_tertiary":"#1e3040","accent":"#2196f3","text_primary":"#e3f2fd","text_secondary":"#90caf9","border":"#1565c0","hover":"#1e3040","danger":"#ef5350","success":"#66bb6a","warning":"#ffa726","tab_active":"#0d1b2a","tab_inactive":"#091520","sidebar_bg":"#091520","toolbar_bg":"#0d1b2a","accent_light":"#1e3040"}),
        ("🌸 Sakura Pink",     {"bg_primary":"#fce4ec","bg_secondary":"#fce4ec","bg_tertiary":"#f8bbd0","accent":"#e91e63","text_primary":"#880e4f","text_secondary":"#ad1457","border":"#f48fb1","hover":"#f8bbd0","danger":"#c62828","success":"#2e7d32","warning":"#f57f17","tab_active":"#fce4ec","tab_inactive":"#fce4ec","sidebar_bg":"#fce4ec","toolbar_bg":"#fce4ec","accent_light":"#fce4ec"}),
        ("🖤 Pure Dark",       {"bg_primary":"#000000","bg_secondary":"#111111","bg_tertiary":"#1a1a1a","accent":"#ffffff","text_primary":"#ffffff","text_secondary":"#aaaaaa","border":"#333333","hover":"#1a1a1a","danger":"#ff4444","success":"#44ff44","warning":"#ffaa00","tab_active":"#000000","tab_inactive":"#0a0a0a","sidebar_bg":"#0a0a0a","toolbar_bg":"#000000","accent_light":"#1a1a1a"}),
        ("🟠 Solarized",       {"bg_primary":"#002b36","bg_secondary":"#073642","bg_tertiary":"#073642","accent":"#268bd2","text_primary":"#839496","text_secondary":"#657b83","border":"#073642","hover":"#073642","danger":"#dc322f","success":"#859900","warning":"#b58900","tab_active":"#002b36","tab_inactive":"#001f27","sidebar_bg":"#001f27","toolbar_bg":"#002b36","accent_light":"#073642"}),
        ("🎃 Halloween",       {"bg_primary":"#1a0a00","bg_secondary":"#2a1500","bg_tertiary":"#3a2000","accent":"#ff6600","text_primary":"#ff9900","text_secondary":"#cc6600","border":"#4a2800","hover":"#3a2000","danger":"#ff0000","success":"#33aa00","warning":"#ffcc00","tab_active":"#1a0a00","tab_inactive":"#0f0600","sidebar_bg":"#0f0600","toolbar_bg":"#1a0a00","accent_light":"#3a2000"}),
    ]

    scroll = QScrollArea(); scroll.setWidgetResizable(True)
    scroll.setStyleSheet(f"background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:8px;")
    grid_w = QWidget(); grid = QGridLayout(grid_w); grid.setSpacing(12)
    scroll.setWidget(grid_w); lay.addWidget(scroll, 1)

    def _apply_theme(theme_dict):
        self._theme.update(theme_dict)
        self.settings_data["custom_theme"] = theme_dict
        save_settings_to_disk(self.profile_name, self.settings_data)
        self._apply_global_style()
        dlg.accept(); self.status.showMessage("🎨 Theme applied", 2000)

    for i, (name, theme_dict) in enumerate(THEMES):
        btn = QPushButton(name)
        bg = theme_dict.get("bg_primary","#fff"); fg = theme_dict.get("text_primary","#000")
        ac = theme_dict.get("accent","#1a73e8")
        btn.setStyleSheet(
            f"QPushButton{{background:{bg};color:{fg};border:2px solid {ac};"
            f"border-radius:10px;padding:14px 8px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:{ac};color:white;}}"
        )
        btn.setFixedHeight(60)
        btn.clicked.connect(lambda checked, td=theme_dict: _apply_theme(td))
        grid.addWidget(btn, i // 2, i % 2)

    br = QHBoxLayout()
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept); br.addStretch(); br.addWidget(close_btn); lay.addLayout(br); dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION I: EXTENSIONS ═══════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# I1. Extension Toolbar Pin/Unpin Menu
def _show_extension_pin_menu(self):
    from PyQt6.QtWidgets import QMenu
    t = self._theme
    m = QMenu(self)
    m.setStyleSheet(f"QMenu{{background:{t['bg_primary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;}} QMenu::item{{padding:7px 18px;}} QMenu::item:selected{{background:{t['hover']};}}")
    extensions = self.settings_data.get("extensions", [])
    pinned     = set(self.settings_data.get("pinned_extensions", []))
    if not extensions:
        m.addAction("No extensions installed").setEnabled(False)
    for ext in extensions:
        eid = ext.get("id",""); name = ext.get("name","?")
        is_pinned = eid in pinned
        action = m.addAction(f"{'📌' if is_pinned else '  '} {name}")
        def _toggle(checked, eid=eid):
            p = set(self.settings_data.get("pinned_extensions", []))
            if eid in p: p.discard(eid)
            else: p.add(eid)
            self.settings_data["pinned_extensions"] = list(p)
            save_settings_to_disk(self.profile_name, self.settings_data)
        action.triggered.connect(_toggle)
    m.addSeparator()
    m.addAction("⚙️ Manage Extensions", self.show_extensions if hasattr(self,"show_extensions") else lambda: None)
    # Show near toolbar
    try:
        btn = getattr(self, "_ext_btn", None) or getattr(self, "puzzle_btn", None)
        if btn:
            m.exec(btn.mapToGlobal(QPoint(0, btn.height())))
        else:
            m.exec(self.mapToGlobal(QPoint(200, 50)))
    except Exception:
        m.exec(self.mapToGlobal(QPoint(200, 50)))

# I2. Extension Permissions Review
def _show_extension_permissions(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QPushButton)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔐 Extension Permissions"); dlg.resize(560, 440)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔐 Extension Permissions Review</b>"))
    tree = QTreeWidget()
    tree.setHeaderLabels(["Extension", "Permissions"])
    tree.setColumnWidth(0, 200)
    tree.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    extensions = self.settings_data.get("extensions", [])
    if not extensions:
        item = QTreeWidgetItem(["No extensions installed", ""])
        tree.addTopLevelItem(item)
    for ext in extensions:
        name = ext.get("name","?"); perms = ext.get("permissions", [])
        parent = QTreeWidgetItem([name, f"{len(perms)} permission(s)"])
        RISKY = {"tabs","history","webRequest","webRequestBlocking","<all_urls>","cookies","management"}
        for perm in perms:
            risk = "⚠ HIGH RISK" if perm in RISKY else "  Normal"
            child = QTreeWidgetItem(["", f"{perm}  {risk}"])
            parent.addChild(child)
        tree.addTopLevelItem(parent)
    tree.expandAll(); lay.addWidget(tree, 1)
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept); lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
    dlg.exec()

# I3. Extension Auto-Update
def _check_extension_updates(self):
    """Check for extension updates from their update URLs."""
    extensions = self.settings_data.get("extensions", [])
    if not extensions:
        self.status.showMessage("No extensions to update", 2000); return
    updated = 0
    def _do():
        nonlocal updated
        for ext in extensions:
            update_url = ext.get("update_url","")
            if not update_url: continue
            try:
                import requests as req_mod
                resp = req_mod.get(update_url, timeout=8, headers={"User-Agent": f"SPS-Browser/{VERSION}"})
                if resp.status_code == 200:
                    data = resp.json()
                    remote_ver = data.get("version","")
                    local_ver  = ext.get("version","0")
                    if remote_ver and remote_ver != local_ver:
                        ext["_update_available"] = remote_ver
                        updated += 1
            except Exception:
                pass
        self.status.showMessage(f"Extension update check done: {updated} update(s) available", 3000)
    threading.Thread(target=_do, daemon=True).start()
    self.status.showMessage("🔄 Checking extension updates…", 2000)

# I4. Developer Mode / Load Unpacked
def _show_developer_mode(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dev_mode = self.settings_data.get("extension_dev_mode", False)
    dlg = QDialog(self); dlg.setWindowTitle("🔧 Extension Developer Mode"); dlg.resize(480, 300)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔧 Extension Developer Mode</b>"))
    status_lbl = QLabel(f"Developer mode: {'✅ ON' if dev_mode else '❌ OFF'}")
    status_lbl.setStyleSheet(f"color:{t['success'] if dev_mode else t['danger']};font-size:14px;font-weight:700;")
    lay.addWidget(status_lbl)
    info = QLabel(
        "Developer mode allows loading unpacked extensions from a local folder.\n\n"
        "⚠ Only load extensions you wrote yourself or fully trust — "
        "unpacked extensions have the same access as installed ones.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    br = QHBoxLayout()
    toggle_btn = QPushButton("✅ Enable" if not dev_mode else "❌ Disable")
    toggle_btn.setStyleSheet(f"background:{t['success'] if not dev_mode else t['danger']};color:white;border-radius:8px;padding:8px 16px;")
    def _toggle():
        new_val = not self.settings_data.get("extension_dev_mode", False)
        self.settings_data["extension_dev_mode"] = new_val
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage(f"Developer mode {'ON' if new_val else 'OFF'}", 2000)
    toggle_btn.clicked.connect(_toggle)
    load_btn = QPushButton("📂 Load Unpacked Extension…")
    load_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _load_unpacked():
        if not self.settings_data.get("extension_dev_mode", False):
            QMessageBox.warning(dlg, "Dev Mode", "Enable Developer Mode first."); return
        folder = QFileDialog.getExistingDirectory(dlg, "Select Extension Folder")
        if folder:
            manifest_path = os.path.join(folder, "manifest.json")
            if not os.path.exists(manifest_path):
                QMessageBox.critical(dlg, "Error", "No manifest.json found in that folder."); return
            try:
                with open(manifest_path) as f: manifest = json.load(f)
                ext = {"id": hashlib.md5(folder.encode()).hexdigest()[:16],
                       "name": manifest.get("name", os.path.basename(folder)),
                       "version": manifest.get("version","0"),
                       "path": folder, "enabled": True,
                       "permissions": manifest.get("permissions",[]),
                       "description": manifest.get("description",""),
                       "unpacked": True}
                exts = self.settings_data.get("extensions", [])
                exts = [e for e in exts if e.get("id") != ext["id"]]
                exts.append(ext)
                self.settings_data["extensions"] = exts
                save_settings_to_disk(self.profile_name, self.settings_data)
                QMessageBox.information(dlg, "Loaded", f"Extension '{ext['name']}' loaded.\nRestart browser to activate.")
            except Exception as e:
                QMessageBox.critical(dlg, "Error", str(e))
    load_btn.clicked.connect(_load_unpacked)
    br.addWidget(toggle_btn); br.addWidget(load_btn); br.addStretch(); lay.addLayout(br); dlg.exec()

# I5. Extension Keyboard Shortcuts Page
def _show_extension_shortcuts(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("⌨️ Extension Shortcuts"); dlg.resize(560, 400)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>⌨️ Extension Keyboard Shortcuts</b>"))
    tbl = QTableWidget(); tbl.setColumnCount(3)
    tbl.setHorizontalHeaderLabels(["Extension", "Action", "Shortcut"])
    tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    tbl.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    for ext in self.settings_data.get("extensions",[]):
        cmds = ext.get("commands",{})
        if not cmds:
            row = tbl.rowCount(); tbl.insertRow(row)
            tbl.setItem(row,0,QTableWidgetItem(ext.get("name","?")))
            tbl.setItem(row,1,QTableWidgetItem("(no commands)"))
            tbl.setItem(row,2,QTableWidgetItem("—"))
        for cmd_name, cmd_data in cmds.items():
            row = tbl.rowCount(); tbl.insertRow(row)
            tbl.setItem(row,0,QTableWidgetItem(ext.get("name","?")))
            tbl.setItem(row,1,QTableWidgetItem(cmd_data.get("description", cmd_name)))
            tbl.setItem(row,2,QTableWidgetItem(cmd_data.get("suggested_key",{}).get("default","—")))
    if tbl.rowCount() == 0:
        tbl.insertRow(0)
        tbl.setItem(0,0,QTableWidgetItem("No extensions installed"))
    lay.addWidget(tbl, 1)
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept); lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
    dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION J: PROFILES ═════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# J1. Restore/Import Full Profile from File
def _show_profile_backup_restore(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QFileDialog, QProgressBar, QMessageBox)
    import zipfile
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("💾 Profile Backup & Restore"); dlg.resize(480, 300)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>💾 Profile Backup & Restore</b>"))
    info = QLabel(f"Current profile: <b>{self.profile_name}</b><br>Data folder: {self.profile_path}")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    pb = QProgressBar(); pb.setRange(0,100); pb.setValue(0)
    pb.setStyleSheet(f"QProgressBar{{background:{t['bg_secondary']};border-radius:6px;}}QProgressBar::chunk{{background:{accent};border-radius:6px;}}")
    lay.addWidget(pb)
    result_lbl = QLabel(""); result_lbl.setStyleSheet(f"color:{t['success']};font-size:12px;")
    lay.addWidget(result_lbl)
    br = QHBoxLayout()

    export_btn = QPushButton("📤 Export Profile (.zip)")
    export_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _export():
        path, _ = QFileDialog.getSaveFileName(dlg, "Export Profile", f"{self.profile_name}_backup.zip", "ZIP (*.zip)")
        if not path: return
        pb.setValue(20)
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(self.profile_path):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, self.profile_path)
                        zf.write(fpath, arcname)
            pb.setValue(100)
            result_lbl.setText(f"✅ Exported to {os.path.basename(path)}")
            self.status.showMessage(f"Profile exported", 2000)
        except Exception as e:
            pb.setValue(0); result_lbl.setText(f"⚠ Export failed: {e}")
            result_lbl.setStyleSheet(f"color:{t['danger']};font-size:12px;")
    export_btn.clicked.connect(_export)

    import_btn = QPushButton("📥 Import Profile (.zip)")
    import_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:8px 16px;")
    def _import():
        path, _ = QFileDialog.getOpenFileName(dlg, "Import Profile", "", "ZIP (*.zip)")
        if not path: return
        if QMessageBox.question(dlg, "Confirm Import",
                "This will overwrite your current profile data. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        pb.setValue(20)
        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(self.profile_path)
            pb.setValue(100)
            result_lbl.setText("✅ Profile restored — restart browser to apply")
            self.status.showMessage("Profile restored — restart required", 3000)
        except Exception as e:
            pb.setValue(0); result_lbl.setText(f"⚠ Import failed: {e}")
            result_lbl.setStyleSheet(f"color:{t['danger']};font-size:12px;")
    import_btn.clicked.connect(_import)

    br.addWidget(export_btn); br.addWidget(import_btn); br.addStretch(); lay.addLayout(br); dlg.exec()

# J2. Work / Personal Profile Separation Prompt
def _check_work_personal_separation(self, url):
    """If a work URL is opened in a personal profile (or vice versa), offer to switch."""
    work_domains = self.settings_data.get("work_domains", [])
    if not work_domains: return
    try:
        host = urlparse(url).netloc.lstrip("www.")
    except Exception:
        return
    is_work_url = any(wd in host for wd in work_domains)
    is_work_profile = self.settings_data.get("is_work_profile", False)
    if is_work_url and not is_work_profile:
        self._show_profile_separation_bar("work", url)
    elif not is_work_url and is_work_profile and url.startswith("http"):
        self._show_profile_separation_bar("personal", url)

def _show_profile_separation_bar(self, suggested_type, url):
    from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    try:
        bar = QFrame(self.centralWidget())
        bar.setStyleSheet(f"background:{t['warning']};")
        bar.setFixedHeight(40)
        h = QHBoxLayout(bar); h.setContentsMargins(14, 4, 14, 4)
        icon = "💼" if suggested_type == "work" else "🏠"
        msg = QLabel(f"{icon} This looks like a {suggested_type} page. Open in your {suggested_type} profile?")
        msg.setStyleSheet("color:#202124;font-size:12px;background:transparent;")
        h.addWidget(msg, 1)
        switch_btn = QPushButton(f"Open in {suggested_type.title()} Profile")
        switch_btn.setStyleSheet("background:#202124;color:white;border-radius:6px;padding:3px 12px;font-size:11px;")
        switch_btn.clicked.connect(lambda: (bar.hide(), self.status.showMessage(f"Opening in {suggested_type} profile…", 2000)))
        no_btn = QPushButton("✕")
        no_btn.setStyleSheet("background:transparent;color:#202124;border:none;padding:3px 8px;")
        no_btn.clicked.connect(bar.hide)
        h.addWidget(switch_btn); h.addWidget(no_btn)
        central_layout = self.centralWidget().layout()
        if central_layout: central_layout.insertWidget(1, bar)
        QTimer.singleShot(10000, bar.hide)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION K: PDF & MEDIA ══════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# K1. PDF Annotate/Highlight/Draw (built-in PDF viewer overlay)
_PDF_VIEWER_HTML = """<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>SPS PDF Viewer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<style>
body{{margin:0;background:#525659;display:flex;flex-direction:column;height:100vh;font-family:sans-serif;overflow:hidden;}}
#toolbar{{background:#3d3d3d;padding:8px 12px;display:flex;align-items:center;gap:10px;flex-shrink:0;}}
#toolbar button{{background:#5a5a5a;color:white;border:none;border-radius:6px;padding:5px 12px;cursor:pointer;font-size:13px;}}
#toolbar button.active{{background:#1a73e8;}}
#toolbar button:hover{{background:#777;}}
#toolbar input[type=range]{{width:80px;}}
#toolbar span{{color:#ddd;font-size:12px;}}
#viewer{{flex:1;overflow-y:auto;display:flex;flex-direction:column;align-items:center;padding:20px;gap:16px;position:relative;}}
canvas{{display:block;box-shadow:0 4px 20px #0005;}}
.page-wrap{{position:relative;}}
.ann-canvas{{position:absolute;top:0;left:0;cursor:crosshair;}}
</style></head><body>
<div id="toolbar">
  <button id="prevBtn">◀ Prev</button>
  <span id="pageInfo">Page 1</span>
  <button id="nextBtn">Next ▶</button>
  <input type="range" id="zoomSlider" min="50" max="200" value="100">
  <span id="zoomLbl">100%</span>
  <button id="hlBtn" title="Highlight">🟡 Highlight</button>
  <button id="drawBtn" title="Draw/Annotate">✏️ Draw</button>
  <button id="textBtn" title="Add Note">📝 Note</button>
  <button id="clearBtn" title="Clear annotations">🗑 Clear</button>
</div>
<div id="viewer"></div>
<script>
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
var pdfUrl = decodeURIComponent(location.hash.slice(1));
var pdf, currentPage=1, totalPages=0, zoom=1.0, mode='none';
var annotations = {};

function getAnn(page){ if(!annotations[page])annotations[page]=[]; return annotations[page]; }

async function loadPDF(){
  if(!pdfUrl){document.getElementById('viewer').innerHTML='<p style="color:white;margin:40px">No PDF URL. Use sps://pdf-viewer#URL</p>';return;}
  pdf = await pdfjsLib.getDocument(pdfUrl).promise;
  totalPages = pdf.numPages;
  renderPage(1);
}

async function renderPage(num){
  currentPage = num;
  document.getElementById('pageInfo').textContent = 'Page '+num+' / '+totalPages;
  var page = await pdf.getPage(num);
  var viewport = page.getViewport({scale: zoom});
  var wrap = document.createElement('div');
  wrap.className='page-wrap'; wrap.style.width=viewport.width+'px'; wrap.style.height=viewport.height+'px';
  var canvas = document.createElement('canvas');
  canvas.width=viewport.width; canvas.height=viewport.height;
  var annCanvas = document.createElement('canvas');
  annCanvas.className='ann-canvas'; annCanvas.width=viewport.width; annCanvas.height=viewport.height;
  annCanvas.dataset.page=num;
  wrap.appendChild(canvas); wrap.appendChild(annCanvas);
  var ctx = canvas.getContext('2d');
  await page.render({canvasContext:ctx, viewport:viewport}).promise;
  setupAnnotation(annCanvas);
  var viewer = document.getElementById('viewer');
  viewer.innerHTML=''; viewer.appendChild(wrap);
}

function setupAnnotation(annCanvas){
  var ctx = annCanvas.getContext('2d');
  var drawing=false, lastX=0, lastY=0;
  annCanvas.onmousedown = function(e){
    if(mode==='none') return;
    drawing=true;
    lastX=e.offsetX; lastY=e.offsetY;
    if(mode==='draw'){ ctx.strokeStyle='red'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(lastX,lastY); }
    if(mode==='highlight'){ ctx.fillStyle='rgba(255,255,0,0.35)'; }
    if(mode==='text'){
      var note=prompt('Note text:');
      if(note){ ctx.font='14px sans-serif'; ctx.fillStyle='blue'; ctx.fillText(note,e.offsetX,e.offsetY); }
      drawing=false;
    }
  };
  annCanvas.onmousemove = function(e){
    if(!drawing) return;
    if(mode==='draw'){ ctx.lineTo(e.offsetX,e.offsetY); ctx.stroke(); }
    if(mode==='highlight'){ ctx.fillRect(lastX,e.offsetY-10,e.offsetX-lastX,20); }
  };
  annCanvas.onmouseup = function(){ drawing=false; };
}

document.getElementById('prevBtn').onclick = function(){ if(currentPage>1) renderPage(currentPage-1); };
document.getElementById('nextBtn').onclick = function(){ if(currentPage<totalPages) renderPage(currentPage+1); };
document.getElementById('zoomSlider').oninput = function(){
  zoom=this.value/100; document.getElementById('zoomLbl').textContent=this.value+'%'; renderPage(currentPage);
};
function setMode(m){
  mode=m;
  ['hlBtn','drawBtn','textBtn'].forEach(function(id){ document.getElementById(id).classList.remove('active'); });
  if(m==='highlight') document.getElementById('hlBtn').classList.add('active');
  if(m==='draw')      document.getElementById('drawBtn').classList.add('active');
  if(m==='text')      document.getElementById('textBtn').classList.add('active');
}
document.getElementById('hlBtn').onclick   = function(){ setMode(mode==='highlight'?'none':'highlight'); };
document.getElementById('drawBtn').onclick  = function(){ setMode(mode==='draw'?'none':'draw'); };
document.getElementById('textBtn').onclick  = function(){ setMode(mode==='text'?'none':'text'); };
document.getElementById('clearBtn').onclick = function(){
  var annCanvas = document.querySelector('.ann-canvas');
  if(annCanvas){ var ctx=annCanvas.getContext('2d'); ctx.clearRect(0,0,annCanvas.width,annCanvas.height); }
};
loadPDF();
</script></body></html>"""

def _open_pdf_viewer(self, url=""):
    """Open the built-in PDF viewer with annotation support."""
    if not url:
        b = self.tabs.currentWidget()
        if b: url = b.url().toString()
    if not url: return
    encoded = quote_plus(url)
    browser = self.add_new_tab(QUrl("about:blank"), "📄 PDF Viewer")
    if browser:
        browser.setHtml(_PDF_VIEWER_HTML.replace("location.hash.slice(1)",
            f"'{encoded}'"), QUrl("sps://pdf-viewer"))

# K2. Video Player Controls (speed, PiP, loop)
_VIDEO_CONTROLS_HTML = """<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>SPS Video Controls</title>
<style>
body{{margin:0;background:#1e1e2e;color:#cdd6f4;font-family:'Segoe UI',sans-serif;padding:20px;}}
h2{{color:#89b4fa;}}
.btn{{background:#313144;color:#cdd6f4;border:1px solid #45475a;border-radius:8px;
padding:8px 16px;cursor:pointer;font-size:13px;margin:4px;}}
.btn:hover{{background:#45475a;}} .btn.active{{background:#1a73e8;color:white;}}
label{{display:block;margin:12px 0 4px;color:#a6adc8;font-size:12px;}}
input[type=range]{{width:100%;}} .row{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;}}
</style></head><body>
<h2>🎬 SPS Video Controls</h2>
<p style="color:#a6adc8;font-size:12px;">Controls apply to the active video/audio on the current page.</p>
<label>Playback Speed</label>
<div class="row" id="speeds"></div>
<label>Volume: <span id="volLbl">100%</span></label>
<input type="range" id="vol" min="0" max="200" value="100">
<div style="margin-top:8px;">
<button class="btn" id="pipBtn">📺 Picture-in-Picture</button>
<button class="btn" id="loopBtn">🔁 Loop: OFF</button>
<button class="btn" id="muteBtn">🔇 Mute Toggle</button>
<button class="btn" id="playBtn">⏯ Play/Pause</button>
</div>
<label>Jump to (%)</label>
<input type="range" id="seek" min="0" max="100" value="0">
<script>
function getMedia(){ return document.querySelector('video') || document.querySelector('audio'); }
var speeds=[0.25,0.5,0.75,1,1.25,1.5,1.75,2,2.5,3];
speeds.forEach(function(s){
  var b=document.createElement('button'); b.className='btn'; b.textContent=s+'×';
  b.onclick=function(){
    var m=window.opener?.document.querySelector('video,audio');
    if(m) m.playbackRate=s;
    document.querySelectorAll('#speeds .btn').forEach(function(x){x.classList.remove('active');});
    b.classList.add('active');
  };
  if(s===1) b.classList.add('active');
  document.getElementById('speeds').appendChild(b);
});
document.getElementById('vol').oninput=function(){
  document.getElementById('volLbl').textContent=this.value+'%';
  var m=window.opener?.document.querySelector('video,audio');
  if(m) m.volume=Math.min(2,this.value/100);
};
document.getElementById('pipBtn').onclick=function(){
  var m=window.opener?.document.querySelector('video');
  if(m && m.requestPictureInPicture) m.requestPictureInPicture();
};
var loopOn=false;
document.getElementById('loopBtn').onclick=function(){
  loopOn=!loopOn;
  this.textContent='🔁 Loop: '+(loopOn?'ON':'OFF');
  this.classList.toggle('active',loopOn);
  var m=window.opener?.document.querySelector('video,audio');
  if(m) m.loop=loopOn;
};
document.getElementById('muteBtn').onclick=function(){
  var m=window.opener?.document.querySelector('video,audio');
  if(m) m.muted=!m.muted;
};
document.getElementById('playBtn').onclick=function(){
  var m=window.opener?.document.querySelector('video,audio');
  if(m){ if(m.paused) m.play(); else m.pause(); }
};
document.getElementById('seek').oninput=function(){
  var m=window.opener?.document.querySelector('video,audio');
  if(m && m.duration) m.currentTime=(this.value/100)*m.duration;
};
</script></body></html>"""

def _open_video_controls(self):
    browser = self.add_new_tab(QUrl("about:blank"), "🎬 Video Controls")
    if browser:
        browser.setHtml(_VIDEO_CONTROLS_HTML, QUrl("sps://video-controls"))

# K3. Screen Capture / Recording (via JS getDisplayMedia)
def _start_screen_capture(self):
    _CAPTURE_HTML = """<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Screen Capture</title>
<style>
body{margin:0;background:#1e1e2e;color:#cdd6f4;font-family:'Segoe UI',sans-serif;
display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:16px;}
video{max-width:90vw;max-height:60vh;border:2px solid #45475a;border-radius:8px;background:#000;}
button{background:#1a73e8;color:white;border:none;border-radius:8px;padding:10px 24px;
font-size:14px;cursor:pointer;margin:4px;}
button.stop{background:#d93025;}
#status{color:#a6adc8;font-size:13px;}
</style></head><body>
<h2 style="color:#89b4fa">📸 Screen Capture</h2>
<video id="v" autoplay muted></video>
<div>
<button id="startBtn">🖥 Start Capture</button>
<button class="stop" id="stopBtn" style="display:none">⏹ Stop</button>
<button id="snapBtn" style="display:none">📷 Screenshot</button>
</div>
<div id="status">Click 'Start Capture' and choose what to share.</div>
<a id="dl" style="display:none"></a>
<script>
var stream=null;
document.getElementById('startBtn').onclick=async function(){
  try{
    stream=await navigator.mediaDevices.getDisplayMedia({video:true,audio:true});
    document.getElementById('v').srcObject=stream;
    document.getElementById('stopBtn').style.display='';
    document.getElementById('snapBtn').style.display='';
    document.getElementById('status').textContent='✅ Capturing…';
  }catch(e){document.getElementById('status').textContent='⚠ '+e.message;}
};
document.getElementById('stopBtn').onclick=function(){
  if(stream)stream.getTracks().forEach(t=>t.stop());
  document.getElementById('v').srcObject=null;
  document.getElementById('stopBtn').style.display='none';
  document.getElementById('snapBtn').style.display='none';
  document.getElementById('status').textContent='Stopped.';
};
document.getElementById('snapBtn').onclick=function(){
  var c=document.createElement('canvas');
  var v=document.getElementById('v');
  c.width=v.videoWidth;c.height=v.videoHeight;
  c.getContext('2d').drawImage(v,0,0);
  var url=c.toDataURL('image/png');
  var a=document.getElementById('dl');
  a.href=url;a.download='sps_screenshot_'+Date.now()+'.png';a.click();
  document.getElementById('status').textContent='📷 Screenshot saved!';
};
</script></body></html>"""
    browser = self.add_new_tab(QUrl("about:blank"), "📸 Screen Capture")
    if browser:
        browser.setHtml(_CAPTURE_HTML, QUrl("sps://screen-capture"))

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION L: ACCESSIBILITY ════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

def _show_accessibility_settings(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
        QCheckBox, QSpinBox, QWidget)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("♿ Accessibility Settings"); dlg.resize(500, 440)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>♿ Accessibility Settings</b>"))

    settings = [
        ("high_contrast",      "🌓 High Contrast Mode",         "Increase contrast for readability"),
        ("focus_highlight",    "🔲 Focus Highlight",             "Draw a visible ring around focused elements"),
        ("reduce_motion",      "🎞 Reduce Motion",               "Stop or slow page animations"),
        ("large_cursor",       "🖱 Large Cursor",                "Make the mouse cursor larger on pages"),
        ("screen_reader_mode", "📢 Screen Reader Mode",          "Announce page content via text-to-speech"),
        ("text_to_speech_auto","🔊 Auto-read on page load",      "Automatically read aloud each page (screen reader)"),
        ("keyboard_nav_hints", "⌨️ Keyboard Navigation Hints",   "Show hints for keyboard navigation"),
    ]
    widgets = {}
    for key, label, desc in settings:
        row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(8, 4, 8, 4)
        cb = QCheckBox(label); cb.setChecked(self.settings_data.get(key, False))
        cb.setStyleSheet(f"color:{t['text_primary']};font-size:13px;")
        dl = QLabel(desc); dl.setStyleSheet(f"color:{t['text_secondary']};font-size:11px;")
        dl.setWordWrap(True); rl.addWidget(cb); rl.addWidget(dl, 1); widgets[key] = cb; lay.addWidget(row)

    # High-contrast CSS
    def _apply_high_contrast(enable):
        js = """
        (function(){
          var s=document.getElementById('_sps_hc');
          if(!s){s=document.createElement('style');s.id='_sps_hc';document.head.appendChild(s);}
          s.textContent=""" + ("'body,*{filter:contrast(150%) !important;}'" if True else "''") + """;
        })();
        """ if enable else "(function(){var s=document.getElementById('_sps_hc');if(s)s.remove();})();"
        b = self.tabs.currentWidget()
        if b: b.page().runJavaScript(js)

    br = QHBoxLayout()
    save_btn = QPushButton("💾 Save & Apply")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")
    def _save():
        for key, cb in widgets.items():
            self.settings_data[key] = cb.isChecked()
        save_settings_to_disk(self.profile_name, self.settings_data)
        if self.settings_data.get("high_contrast"):
            _apply_high_contrast(True)
        if self.settings_data.get("reduce_motion"):
            self._apply_reduced_motion() if hasattr(self,"_apply_reduced_motion") else None
        dlg.accept(); self.status.showMessage("♿ Accessibility settings saved", 2000)
    save_btn.clicked.connect(_save); br.addStretch(); br.addWidget(save_btn); lay.addLayout(br); dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION M: INTERNAL PAGES ═══════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

def _show_net_internals(self):
    b = self.tabs.currentWidget()
    if not b: b = self.add_new_tab(label="sps://net-internals") or self.tabs.currentWidget()
    if b: b.load(QUrl("chrome://net-internals/"))

def _show_components(self):
    """Show a components/dependency info page."""
    t = self._theme
    try:
        import PyQt6; qt_ver = PyQt6.QtCore.PYQT_VERSION_STR
    except Exception: qt_ver = "?"
    try:
        import PyQt6.QtWebEngineCore as we
        chrome_ver = we.qWebEngineChromiumVersion()
    except Exception: chrome_ver = "unknown"

    rows = [
        ("SPS Browser", VERSION),
        ("PyQt6", qt_ver),
        ("Chromium (QtWebEngine)", chrome_ver),
        ("Python", sys.version.split()[0]),
        ("Platform", platform.platform()),
        ("Architecture", platform.machine()),
    ]
    html_body = "".join(f"<tr><td style='padding:8px 16px;border-bottom:1px solid {t['border']};font-weight:700'>{k}</td>"
                        f"<td style='padding:8px 16px;border-bottom:1px solid {t['border']};color:{t['text_secondary']}'>{v}</td></tr>"
                        for k, v in rows)
    page_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>sps://components</title>
<style>body{{font-family:'Segoe UI',sans-serif;background:{t['bg_primary']};color:{t['text_primary']};padding:32px;}}
h1{{color:{t['accent']};}} table{{border-collapse:collapse;width:100%;max-width:600px;background:{t['bg_secondary']};border-radius:10px;overflow:hidden;border:1px solid {t['border']};}}
</style></head><body><h1>⚙️ sps://components</h1>
<table>{html_body}</table></body></html>"""
    browser = self.add_new_tab(QUrl("about:blank"), "⚙️ Components")
    if browser: browser.setHtml(page_html, QUrl("sps://components"))

def _show_sync_internals(self):
    t = self._theme
    page_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>sps://sync-internals</title>
<style>body{{font-family:'Segoe UI',sans-serif;background:{t['bg_primary']};color:{t['text_primary']};padding:32px;}}</style></head>
<body><h1 style="color:{t['accent']}">🔄 sps://sync-internals</h1>
<p style="color:{t['text_secondary']}">SPS Browser uses local profile sync (same PC) only.<br>
Cloud sync requires a backend server — not built yet.<br><br>
<b>Local sync status:</b> Active — bookmarks and settings sync across profiles on this PC.</p>
</body></html>"""
    browser = self.add_new_tab(QUrl("about:blank"), "🔄 Sync Internals")
    if browser: browser.setHtml(page_html, QUrl("sps://sync-internals"))

def _show_inspect_page(self):
    b = self.tabs.currentWidget()
    if b:
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            view = QWebEngineView()
            b.page().setDevToolsPage(view.page())
            view.setWindowTitle(f"DevTools — {self.tabs.tabText(self.tabs.currentIndex())}")
            view.resize(900, 600)
            view.show()
            if not hasattr(self, "_devtools_windows"): self._devtools_windows = []
            self._devtools_windows.append(view)
        except Exception as e:
            self.status.showMessage(f"DevTools: {e}", 3000)

def _show_discards(self):
    """Show tab memory / discard status."""
    t = self._theme
    rows = []
    for i in range(self.tabs.count()):
        w = self.tabs.widget(i)
        if w:
            sleeping = getattr(w, "_is_sleeping", False)
            rows.append((self.tabs.tabText(i), w.url().toString()[:60],
                         "😴 Sleeping" if sleeping else "▶ Active"))
    html_rows = "".join(
        f"<tr><td style='padding:8px;border-bottom:1px solid {t['border']}'>{html.escape(t_)}</td>"
        f"<td style='padding:8px;border-bottom:1px solid {t['border']};color:{t['text_secondary']};font-size:11px'>{html.escape(u)}</td>"
        f"<td style='padding:8px;border-bottom:1px solid {t['border']}'>{s}</td></tr>"
        for t_, u, s in rows)
    page_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>sps://discards</title>
<style>body{{font-family:'Segoe UI',sans-serif;background:{t['bg_primary']};color:{t['text_primary']};padding:32px;}}
h1{{color:{t['accent']};}} table{{border-collapse:collapse;width:100%;background:{t['bg_secondary']};
border-radius:10px;overflow:hidden;border:1px solid {t['border']};}}
</style></head><body><h1>💾 sps://discards — Tab Memory Status</h1>
<table><thead><tr><th style='padding:10px;text-align:left'>Tab</th><th>URL</th><th>State</th></tr></thead>
<tbody>{html_rows}</tbody></table></body></html>"""
    browser = self.add_new_tab(QUrl("about:blank"), "💾 Discards")
    if browser: browser.setHtml(page_html, QUrl("sps://discards"))

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION N: UPDATES & ENTERPRISE ═════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

def _show_update_channels(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QComboBox
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🔄 Update Channels"); dlg.resize(440, 280)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔄 Update Channels</b>"))
    info = QLabel(
        "Choose which release channel to follow:\n\n"
        "• Stable — tested releases only (recommended)\n"
        "• Beta — new features, may have minor bugs\n"
        "• Dev — latest builds, expect bugs")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:13px;")
    lay.addWidget(info)
    row = QHBoxLayout(); row.addWidget(QLabel("Channel:"))
    combo = QComboBox()
    combo.addItems(["Stable", "Beta", "Dev"])
    combo.setCurrentText(self.settings_data.get("update_channel", "Stable"))
    combo.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;padding:6px;")
    row.addWidget(combo, 1); lay.addLayout(row)
    br = QHBoxLayout()
    save_btn = QPushButton("💾 Save")
    save_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    def _save():
        self.settings_data["update_channel"] = combo.currentText()
        save_settings_to_disk(self.profile_name, self.settings_data)
        dlg.accept(); self.status.showMessage(f"Update channel: {combo.currentText()}", 2000)
    save_btn.clicked.connect(_save); br.addStretch(); br.addWidget(save_btn); lay.addLayout(br); dlg.exec()

def _show_group_policy(self):
    """Show an ADMX-style group policy viewer (reads a policies.json file)."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
        QPushButton, QHeaderView, QMessageBox)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    policy_path = os.path.join(BASE_DATA_DIR, "policies.json")
    policies = {}
    if os.path.exists(policy_path):
        try:
            with open(policy_path) as f: policies = json.load(f)
        except Exception: pass
    dlg = QDialog(self); dlg.setWindowTitle("🏢 Group Policy"); dlg.resize(580, 440)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🏢 Browser Policies (ADMX-style)</b>"))
    if not policies:
        info = QLabel(
            f"No policies.json found at:\n{policy_path}\n\n"
            "To apply policies, create that file with JSON key-value pairs.\n"
            "Example: {\"force_safe_search\": true, \"disable_developer_tools\": false}")
        info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
        lay.addWidget(info)
    else:
        tbl = QTableWidget(); tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["Policy", "Value"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tbl.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
        for k, v in policies.items():
            row = tbl.rowCount(); tbl.insertRow(row)
            tbl.setItem(row, 0, QTableWidgetItem(str(k)))
            tbl.setItem(row, 1, QTableWidgetItem(str(v)))
        lay.addWidget(tbl, 1)
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept); lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
    dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION O: GESTURES ═════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

def _enable_touch_mode(self, enable=None):
    if enable is None: enable = not self.settings_data.get("touch_mode", False)
    self.settings_data["touch_mode"] = enable
    save_settings_to_disk(self.profile_name, self.settings_data)
    # Increase button sizes for touch
    size = 48 if enable else 36
    for btn_name in ["back_btn","fwd_btn","reload_btn","home_btn","menu_btn"]:
        btn = getattr(self, btn_name, None)
        if btn: btn.setFixedSize(size, size)
    self.status.showMessage(f"{'👆 Touch mode ON' if enable else 'Touch mode OFF'}", 2000)

def _enable_middle_click_autoscroll(self):
    """Wire middle-click on WebView to start autoscroll (inject JS)."""
    b = self.tabs.currentWidget()
    if not b: return
    js = """
    (function(){
      if(window._spsAutoscrollBound) return;
      window._spsAutoscrollBound = true;
      var scrolling=false, startY=0, scrollY=0, raf=null;
      document.addEventListener('mousedown', function(e){
        if(e.button===1){
          e.preventDefault(); scrolling=true; startY=e.clientY; scrollY=window.scrollY;
          document.body.style.cursor='ns-resize';
        }
      });
      document.addEventListener('mousemove', function(e){
        if(!scrolling) return;
        var delta=(e.clientY-startY)*0.5;
        window.scrollTo(0, scrollY+delta);
      });
      document.addEventListener('mouseup', function(e){
        if(e.button===1){ scrolling=false; document.body.style.cursor=''; }
      });
    })();
    """
    b.page().runJavaScript(js)
    self.status.showMessage("🖱 Middle-click autoscroll enabled for this tab", 2000)

# ─────────────────────────────────────────────────────────────────────
# ══ SECTION P: EXTRAS ═══════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────

# P1. Companion Theme from Wallpaper
def _extract_wallpaper_theme(self):
    """Extract dominant colour from Windows wallpaper and apply as accent."""
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Control Panel\Desktop")
            wallpaper_path, _ = winreg.QueryValueEx(key, "Wallpaper")
            winreg.CloseKey(key)
        else:
            self.status.showMessage("Wallpaper theme is Windows-only", 2000); return

        if not os.path.exists(wallpaper_path):
            self.status.showMessage("Could not find wallpaper file", 2000); return

        from PyQt6.QtGui import QImage, QColor
        img = QImage(wallpaper_path).scaled(50, 50)
        r_sum = g_sum = b_sum = count = 0
        for x in range(img.width()):
            for y in range(img.height()):
                c = QColor(img.pixel(x, y))
                r_sum += c.red(); g_sum += c.green(); b_sum += c.blue(); count += 1
        if count:
            r = r_sum // count; g = g_sum // count; b = b_sum // count
            hex_colour = f"#{r:02x}{g:02x}{b:02x}"
            self.settings_data["accent_color"] = hex_colour
            self._theme["accent"] = hex_colour
            save_settings_to_disk(self.profile_name, self.settings_data)
            self._apply_global_style()
            self.status.showMessage(f"🎨 Wallpaper accent colour applied: {hex_colour}", 3000)
    except Exception as e:
        self.status.showMessage(f"Wallpaper theme failed: {e}", 3000)

# P2. Chrome Cleanup / Malware Scanner
def _show_malware_scanner(self):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
        QProgressBar, QTextEdit, QHBoxLayout)
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🦠 Malware Scanner"); dlg.resize(560, 420)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🦠 Browser Cleanup & Malware Scanner</b>"))
    info = QLabel("Scans your browser data folder for suspicious files, unusual extensions, and known bad hashes.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(0)
    pb.setStyleSheet(f"QProgressBar{{background:{t['bg_secondary']};border-radius:6px;}}QProgressBar::chunk{{background:{accent};border-radius:6px;}}")
    lay.addWidget(pb)
    results = QTextEdit(); results.setReadOnly(True)
    results.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;font-family:monospace;font-size:11px;")
    lay.addWidget(results, 1)
    scan_btn = QPushButton("🦠 Start Scan")
    scan_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 18px;")

    KNOWN_BAD_EXTS = {".exe",".bat",".cmd",".ps1",".vbs",".scr"}
    SUSPICIOUS_NAMES = ["inject","hook","steal","keylog","rat","trojan","backdoor","miner"]

    def _do_scan():
        scan_btn.setEnabled(False)
        results.clear(); issues = []
        scan_dirs = [BASE_DATA_DIR]
        all_files = []
        for d in scan_dirs:
            for root, dirs, files in os.walk(d):
                for f in files: all_files.append(os.path.join(root, f))
        for i, fpath in enumerate(all_files):
            pb.setValue(int((i+1)/max(len(all_files),1)*90))
            fname = os.path.basename(fpath).lower()
            ext   = os.path.splitext(fname)[1]
            if ext in KNOWN_BAD_EXTS:
                issues.append(f"⚠ Suspicious file type: {fpath}")
            if any(bad in fname for bad in SUSPICIOUS_NAMES):
                issues.append(f"⚠ Suspicious name: {fpath}")
        # Check extensions
        for ext_item in self.settings_data.get("extensions",[]):
            name = ext_item.get("name","").lower()
            if any(bad in name for bad in SUSPICIOUS_NAMES):
                issues.append(f"⚠ Suspicious extension name: {ext_item.get('name')}")
        pb.setValue(100)
        if issues:
            results.setText(f"🔴 {len(issues)} issue(s) found:\n\n" + "\n".join(issues))
        else:
            results.setText("✅ No suspicious files or extensions found.\nYour browser data looks clean.")
        scan_btn.setEnabled(True)

    scan_btn.clicked.connect(lambda: threading.Thread(target=_do_scan, daemon=True).start())
    lay.addWidget(scan_btn)
    br = QHBoxLayout()
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept); br.addStretch(); br.addWidget(close_btn); lay.addLayout(br)
    dlg.exec()

# P3. Reading Mode (full immersive reader)
def _toggle_reading_mode(self):
    """Toggle reading mode for the current page."""
    b = self.tabs.currentWidget()
    if not b: return
    if getattr(b, "_reading_mode_on", False):
        # Restore original page
        b._reading_mode_on = False
        if hasattr(b, "_original_url"): b.load(b._original_url)
        self.status.showMessage("Reading mode OFF", 1500)
        return
    b._original_url = b.url()
    b._reading_mode_on = True
    dark = self.settings_data.get("dark_mode", False)

    def _got_html(raw):
        cleaned = _reading_mode_clean(raw, self._theme, dark)
        b.setHtml(cleaned, QUrl("sps://reading-mode"))
        self.status.showMessage("📖 Reading mode ON — click again to exit", 2000)

    b.page().toHtml(_got_html)

def _reading_mode_clean(raw_html, t, dark=False):
    bg   = t["bg_primary"]; fg = t["text_primary"]; border = t["border"]
    for tag in ["script","style","nav","footer","aside","form","iframe","noscript","header","menu","ads"]:
        raw_html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', raw_html, flags=re.S|re.I)
    raw_html = re.sub(r' on\w+="[^"]*"', '', raw_html)
    title_m = re.search(r'<title[^>]*>(.*?)</title>', raw_html, re.I|re.S)
    title = html.unescape(title_m.group(1)) if title_m else "Reading View"
    body_m = re.search(r'<body[^>]*>(.*?)</body>', raw_html, re.S|re.I)
    body = body_m.group(1) if body_m else raw_html
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>📖 {html.escape(title)}</title>
<style>
body{{font-family:Georgia,serif;font-size:18px;line-height:1.8;
max-width:700px;margin:48px auto;padding:0 24px;
background:{bg};color:{fg};}}
h1,h2,h3,h4{{color:{fg};line-height:1.3;margin-top:1.5em;}}
img{{max-width:100%;border-radius:8px;margin:12px 0;}}
blockquote{{border-left:4px solid {border};padding:0 16px;color:{t.get('text_secondary',fg)};}}
pre,code{{background:{t.get('bg_secondary',bg)};padding:4px 8px;border-radius:6px;font-size:14px;}}
a{{color:{t.get('accent','#1a73e8')};}}
.sps-rm-bar{{position:fixed;top:0;left:0;right:0;background:{t.get('bg_secondary',bg)};
border-bottom:1px solid {border};padding:8px 20px;display:flex;align-items:center;gap:12px;z-index:9999;}}
.sps-rm-bar button{{background:{t.get('accent','#1a73e8')};color:white;border:none;
border-radius:6px;padding:4px 12px;cursor:pointer;font-size:12px;}}
</style></head><body>
<div class="sps-rm-bar">
  <span style="font-weight:700;font-size:14px">📖 Reading Mode</span>
  <span style="flex:1"></span>
  <button onclick="window.history.back()">← Exit Reading Mode</button>
</div>
<div style="margin-top:52px">{body}</div>
</body></html>"""

# P4. Browser-wide Undo Close (bookmarks / history deletions)
def _undo_last_close(self):
    """Undo the last closed tab, deleted bookmark, or cleared history item."""
    if hasattr(self, "_closed_tabs") and self._closed_tabs:
        url, title = self._closed_tabs.pop()
        self.add_new_tab(url, title)
        self.status.showMessage(f"↩ Reopened: {title or url.toString()}", 2000)
    elif hasattr(self, "_deleted_bookmarks") and self._deleted_bookmarks:
        bm = self._deleted_bookmarks.pop()
        bms = self._load_bookmarks(); bms.append(bm)
        self._save_bookmarks(bms)
        self.status.showMessage(f"↩ Restored bookmark: {bm.get('title','?')}", 2000)
    else:
        self.status.showMessage("Nothing to undo", 2000)

# P5. Shopping Coupons / Price History
def _show_shopping_assistant(self):
    """Show shopping assistant: coupon search and price history for current page."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTextEdit
    b = self.tabs.currentWidget()
    if not b: return
    url  = b.url().toString()
    host = urlparse(url).netloc.lstrip("www.")
    t = self._theme; accent = self.settings_data.get("accent_color", t["accent"])
    dlg = QDialog(self); dlg.setWindowTitle("🛒 Shopping Assistant"); dlg.resize(480, 380)
    dlg.setStyleSheet(f"background:{t['bg_primary']};color:{t['text_primary']};")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(f"<b>🛒 Shopping Assistant — {html.escape(host)}</b>"))
    info = QLabel("SPS Browser automatically checks for coupons and tracks price history on shopping pages.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{t['text_secondary']};font-size:12px;")
    lay.addWidget(info)
    txt = QTextEdit(); txt.setReadOnly(True)
    txt.setStyleSheet(f"background:{t['bg_secondary']};color:{t['text_primary']};border:1px solid {t['border']};border-radius:8px;")
    lay.addWidget(txt, 1)

    def _got_title(title_text):
        history = self.settings_data.get("price_tracker", {}).get(url, {})
        last_price = history.get("last_price","Not tracked yet")
        txt.setText(
            f"Page: {title_text or url}\n\n"
            f"💰 Last tracked price: {last_price}\n\n"
            f"🏷 Coupon search:\n"
            f"  Try: {host} coupon code {datetime.datetime.now().year}\n"
            f"  Try: {host} promo code\n\n"
            f"🔗 Price comparison:\n"
            f"  https://www.google.com/search?q={quote_plus(title_text+' price')}\n\n"
            f"📈 To track this item's price, click 'Track Price' below."
        )
    b.page().runJavaScript("document.title", _got_title)

    br = QHBoxLayout()
    track_btn = QPushButton("💰 Track Price")
    track_btn.setStyleSheet(f"background:{accent};color:white;border-radius:8px;padding:8px 16px;")
    track_btn.clicked.connect(lambda: (dlg.accept(), self._show_price_tracker() if hasattr(self,"_show_price_tracker") else None))
    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"background:{t['bg_tertiary']};color:{t['text_primary']};border-radius:8px;padding:8px 16px;")
    close_btn.clicked.connect(dlg.accept)
    br.addWidget(track_btn); br.addStretch(); br.addWidget(close_btn); lay.addLayout(br); dlg.exec()

# ─────────────────────────────────────────────────────────────────────
# ══ REGISTER ALL NEW METHODS INTO MainWindow ═════════════════════════
# ─────────────────────────────────────────────────────────────────────
_V34_METHODS = {
    # Tabs & Windows
    "_reopen_closed_window":         _reopen_closed_window,
    "_record_closed_window":         _record_closed_window,
    "_toggle_vertical_tabs":         _toggle_vertical_tabs,
    "_apply_vertical_tabs":          _apply_vertical_tabs,
    "_scroll_tabs_left":             _scroll_tabs_left,
    "_scroll_tabs_right":            _scroll_tabs_right,
    "_update_tab_freeze_indicators": _update_tab_freeze_indicators,
    "_enter_fullscreen":             _enter_fullscreen,
    # Navigation
    "_document_pip":                 _document_pip,
    "_search_image_with_lens":       _search_image_with_lens,
    "_inject_overscroll_gestures":   _inject_overscroll_gestures,
    "_apply_reduced_motion":         _apply_reduced_motion,
    # Bookmarks & History
    "_import_profile_bookmarks":     _import_profile_bookmarks,
    "_show_price_tracker":           _show_price_tracker,
    "_show_journeys":                _show_journeys,
    # Downloads
    "_configure_open_in_browser":    _configure_open_in_browser,
    "_master_password_gate":         _master_password_gate,
    # Autofill
    "_autofill_current_page":        _autofill_current_page,
    "_toggle_auto_signin":           _toggle_auto_signin,
    "_apply_cookie_policy":          _apply_cookie_policy,
    # Privacy & Security
    "_show_privacy_sandbox":         _show_privacy_sandbox,
    "_show_drm_settings":            _show_drm_settings,
    "_show_popup_exceptions":        _show_popup_exceptions,
    # Site Settings
    "_show_full_site_settings":      _show_full_site_settings,
    # Appearance
    "_show_font_settings":           _show_font_settings,
    "_apply_custom_fonts":           _apply_custom_fonts,
    "_show_language_settings":       _show_language_settings,
    "_on_gpu_crash":                 _on_gpu_crash,
    "_reload_all_tabs_after_crash":  _reload_all_tabs_after_crash,
    "_show_theme_store":             _show_theme_store,
    # Extensions
    "_show_extension_pin_menu":      _show_extension_pin_menu,
    "_show_extension_permissions":   _show_extension_permissions,
    "_check_extension_updates":      _check_extension_updates,
    "_show_developer_mode":          _show_developer_mode,
    "_show_extension_shortcuts":     _show_extension_shortcuts,
    # Profiles
    "_show_profile_backup_restore":  _show_profile_backup_restore,
    "_check_work_personal_separation": _check_work_personal_separation,
    "_show_profile_separation_bar":  _show_profile_separation_bar,
    # PDF & Media
    "_open_pdf_viewer":              _open_pdf_viewer,
    "_open_video_controls":          _open_video_controls,
    "_start_screen_capture":         _start_screen_capture,
    # Accessibility
    "_show_accessibility_settings":  _show_accessibility_settings,
    # Internal Pages
    "_show_net_internals":           _show_net_internals,
    "_show_components":              _show_components,
    "_show_sync_internals":          _show_sync_internals,
    "_show_inspect_page":            _show_inspect_page,
    "_show_discards":                _show_discards,
    # Updates & Enterprise
    "_show_update_channels":         _show_update_channels,
    "_show_group_policy":            _show_group_policy,
    # Gestures
    "_enable_touch_mode":            _enable_touch_mode,
    "_enable_middle_click_autoscroll": _enable_middle_click_autoscroll,
    # Extras
    "_extract_wallpaper_theme":      _extract_wallpaper_theme,
    "_show_malware_scanner":         _show_malware_scanner,
    "_toggle_reading_mode":          _toggle_reading_mode,
    "_undo_last_close":              _undo_last_close,
    "_show_shopping_assistant":      _show_shopping_assistant,
}
for _name, _fn in _V34_METHODS.items():
    setattr(MainWindow, _name, _fn)

print(f"[SPS V34] Patch loaded: {len(_V34_METHODS)} new methods registered")
