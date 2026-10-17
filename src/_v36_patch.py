# ═══════════════════════════════════════════════════════════════════════
#  SPS BROWSER V36 — PATCH
#   * What's New page (rewritten)            * Support page with Google Form
#   * Chrome-style keyboard shortcuts        * Clear browsing data (Ctrl+Shift+Del)
#   * shortcut clean-up (Ctrl+Z / F11 / duplicate Ctrl+Shift+P)
#  Loaded by SPS_BROWSER.py after _v33_patch.py and _v34_patch.py (same namespace).
# ═══════════════════════════════════════════════════════════════════════
import os, sys, re, html, json, platform, datetime

# ─────────────────────────────────────────────────────────────────────
#  Support form link:  environment variable  >  support_form.txt (next to the exe / in the bundle)  >  built-in default
# ─────────────────────────────────────────────────────────────────────
SPS_SUPPORT_FORM_DEFAULT = ""            # or paste the link of your Google Form here

def _v36_support_form_url():
    cand = os.environ.get("SPS_SUPPORT_FORM_URL", "").strip()
    if not cand:
        try:
            _exe_dir = [os.path.dirname(os.path.abspath(sys.executable))] if getattr(sys, "frozen", False) else []
            for d in _exe_dir + _sps_patch_dirs():          # the copy NEXT TO THE EXE wins, so it can be edited without a rebuild
                f = os.path.join(d, "support_form.txt")
                if os.path.isfile(f):
                    with open(f, "r", encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if line and not line.startswith("#") and "PASTE_YOUR" not in line:
                                cand = line; break
                    if cand: break
        except Exception:
            pass
    cand = cand or SPS_SUPPORT_FORM_DEFAULT
    if re.match(r"^https://(docs\.google\.com/forms/|forms\.gle/|forms\.google\.com/)", cand):
        return cand
    return ""

def _v36_embed_url(url):
    """viewform?embedded=true is the Google-supported way to show a form inside a page."""
    if "docs.google.com/forms" in url:
        base = url.split("?")[0]
        if base.endswith("/edit"):
            base = base[:-5] + "/viewform"
        return base + "?embedded=true"
    return ""          # forms.gle short links cannot be framed -> the button opens them in a tab

def _v36_diagnostics():
    lines = [f"SPS Browser {VERSION}",
             f"OS: {platform.platform()}",
             f"Python: {platform.python_version()}   Qt: {QT_VERSION_STR if 'QT_VERSION_STR' in globals() else '?'}",
             f"Profile: {CURRENT_PROFILE_NAME}", ""]
    try:
        with open(os.path.join(BASE_DATA_DIR, "error_log.txt"), "r", encoding="utf-8", errors="replace") as f:
            tail = f.read().strip().splitlines()[-14:]
        if tail:
            lines += ["Recent errors:"] + tail
    except Exception:
        lines.append("(no error log)")
    return "\n".join(lines)

def _show_support_page(self):
    t = self._theme
    form = _v36_support_form_url()
    embed = _v36_embed_url(form) if form else ""
    diag = _v36_diagnostics()
    if form and embed:
        form_html = (f'<iframe src="{html.escape(embed)}" title="SPS Browser support form" '
                     f'style="width:100%;height:1150px;border:1px solid {t["border"]};border-radius:12px;background:#fff"></iframe>')
    elif form:
        form_html = ""
    else:
        form_html = ("<div class='warn'><b>The support form is not connected yet.</b><br>"
                     "Create a Google Form, press <i>Send → link</i>, paste the link into <code>support_form.txt</code> "
                     "(next to SPS_Browser.exe) and restart the browser.</div>")
    open_btn = (f'<a class="btn" href="{html.escape(form)}">Open the form in a new tab ↗</a>' if form else "")
    page = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>SPS Browser Support</title><style>
body{{font-family:'Segoe UI',sans-serif;margin:0;padding:32px;background:{t['bg_primary']};color:{t['text_primary']};max-width:900px;margin:auto}}
h1{{color:{t['accent']};margin-bottom:4px}} p.sub{{color:{t['text_secondary']};margin-top:0}}
.card{{background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:12px;padding:16px 18px;margin:16px 0}}
.btn{{display:inline-block;background:{t['accent']};color:#fff;text-decoration:none;border:none;border-radius:8px;padding:9px 16px;font-weight:600;cursor:pointer;font-size:14px;margin:4px 6px 4px 0}}
.btn.alt{{background:{t['bg_tertiary']};color:{t['text_primary']};border:1px solid {t['border']}}}
pre{{background:{t['bg_tertiary']};border:1px solid {t['border']};border-radius:8px;padding:10px;font-size:12px;white-space:pre-wrap;max-height:200px;overflow:auto}}
.warn{{background:#fff4e5;color:#663c00;border:1px solid #ffb74d;border-radius:10px;padding:14px}} code{{background:rgba(127,127,127,.2);padding:1px 5px;border-radius:4px}}
</style></head><body>
<h1>🆘 SPS Browser Support</h1><p class="sub">Report a problem, ask a question or suggest a feature. We read every message.</p>
<div class="card"><b>Before you send:</b> press <b>Copy details</b> and paste them into the form - it tells us your version and the last errors, so we can fix things faster.
<p><button class="btn" onclick="cp()">📋 Copy details</button><a class="btn alt" href="sps:whats-new">🆕 What's New</a><a class="btn alt" href="sps:tour">🧭 Take the tour</a>{open_btn}</p>
<pre id="d">{html.escape(diag)}</pre></div>
{form_html}
<script>function cp(){{var t=document.getElementById('d').innerText;
try{{navigator.clipboard.writeText(t)}}catch(e){{var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}}
alert('Copied. Paste it into the form.')}}</script></body></html>"""
    browser = self.add_new_tab(QUrl("about:blank"), "🆘 Support")
    if browser:
        browser.setHtml(page, QUrl("sps://support"))

# ─────────────────────────────────────────────────────────────────────
#  What's New
# ─────────────────────────────────────────────────────────────────────
def _show_whats_new(self):
    t = self._theme
    groups = [
        ("🆕 New in V36", [
            ("🆘 Support page", "Menu → Help → Support. Report a problem through a real form, with your version and recent errors one click away."),
            ("🧹 Clean uninstall", "Uninstalling removes the program, all profiles, history, saved data, the sandbox folder and every registry entry."),
            ("⌨️ Chrome shortcuts", "Ctrl+1…9, Ctrl+PgUp/PgDn, Ctrl+N, Ctrl+Shift+Del, Ctrl+Shift+B/O/D/J, Shift+Esc, Alt+Home, F6, Alt+D, F3 and real full screen on F11."),
            ("🗑️ Clear browsing data", "Ctrl+Shift+Del: pick history, cookies and cache, and a time range - like Chrome."),
            ("🌐 Translate fixed", "Pages from Google, Amazon and PayPal can be translated, and if Google Translate is down the page opens in Microsoft Translator."),
            ("🔍 Lens fixed", "Search-by-image retries through Google image search when Lens answers with a \"moved\" page."),
            ("🛡️ Quieter sandbox", "No more \"the browser wants to write a file\" alerts for files that already exist. You are asked only when a new program file is created."),
            ("🏷️ One name", "The browser is now simply SPS Browser everywhere."),
        ]),
        ("🎬 V35", [
            ("▶️ Built-in video player", "Local .mp4 / .mov / .mkv / .avi files open in a player that plays them (H.264 included)."),
            ("⚡ Smoother full-screen video", "Hardware video decoding is on, YouTube full screen no longer freezes and Esc leaves it."),
            ("⬜ Classic white new tab", "New tabs open on a clean white page (change it in New Tab Background)."),
            ("🪪 Local files are not \"insecure\"", "Files on your PC show 📄 Local file instead of Not secure."),
        ]),
    ]
    body = ""
    for gtitle, feats in groups:
        body += f"<h2>{html.escape(gtitle)}</h2><div class='grid'>"
        for title, desc in feats:
            body += f"<div class='card'><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p></div>"
        body += "</div>"
    page = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>What's New in SPS Browser v{VERSION}</title><style>
body{{font-family:'Segoe UI',sans-serif;margin:0;padding:32px;background:{t['bg_primary']};color:{t['text_primary']};}}
h1{{color:{t['accent']};font-size:28px;margin-bottom:0}} h2{{color:{t['text_primary']};font-size:18px;margin:28px 0 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-top:12px}}
.card{{background:{t['bg_secondary']};border:1px solid {t['border']};border-radius:12px;padding:16px}}
.card h3{{margin:0 0 6px;font-size:15px}} .card p{{margin:0;font-size:13px;color:{t['text_secondary']};line-height:1.5}}
a.btn{{display:inline-block;margin-top:18px;background:{t['accent']};color:#fff;border-radius:8px;padding:9px 16px;text-decoration:none;font-weight:600}}
</style></head><body><h1>🆕 What's New in SPS Browser v{VERSION}</h1>{body}
<a class="btn" href="sps:support">🆘 Need help? Contact support</a></body></html>"""
    browser = self.add_new_tab(QUrl("about:blank"), f"What's New v{VERSION}")
    if browser:
        browser.setHtml(page, QUrl("sps://whats-new"))

# ─────────────────────────────────────────────────────────────────────
#  Clear browsing data  (Ctrl+Shift+Del)
# ─────────────────────────────────────────────────────────────────────
def _show_clear_browsing_data(self):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox, QPushButton, QMessageBox
    t = self._theme
    dlg = QDialog(self); dlg.setWindowTitle("Clear browsing data"); dlg.resize(420, 300)
    dlg.setStyleSheet(f"QDialog{{background:{t['bg_primary']};}}QLabel,QCheckBox{{color:{t['text_primary']};}}")
    lay = QVBoxLayout(dlg)
    h = QLabel("🗑️ Clear browsing data"); h.setStyleSheet(f"font-size:18px;font-weight:700;color:{t['accent']};"); lay.addWidget(h)
    row = QHBoxLayout(); row.addWidget(QLabel("Time range:"))
    rng = QComboBox()
    for lbl, hrs in (("Last hour", 1), ("Last 24 hours", 24), ("Last 7 days", 168), ("Last 4 weeks", 672), ("All time", 0)):
        rng.addItem(lbl, hrs)
    rng.setCurrentIndex(4); row.addWidget(rng, 1); lay.addLayout(row)
    c_hist = QCheckBox("Browsing history"); c_hist.setChecked(True)
    c_cook = QCheckBox("Cookies and site data (signs you out of sites)"); c_cook.setChecked(True)
    c_cache = QCheckBox("Cached images and files"); c_cache.setChecked(True)
    for c in (c_hist, c_cook, c_cache): lay.addWidget(c)
    note = QLabel("Cookies are always cleared for all time (the web engine cannot clear them by date).")
    note.setWordWrap(True); note.setStyleSheet(f"color:{t['text_secondary']};font-size:11px;"); lay.addWidget(note)
    lay.addStretch()
    btns = QHBoxLayout(); btns.addStretch()
    cancel = QPushButton("Cancel"); cancel.clicked.connect(dlg.reject)
    go = QPushButton("Clear data"); go.setStyleSheet(f"background:{t['accent']};color:white;border-radius:8px;padding:8px 18px;font-weight:700;")
    btns.addWidget(cancel); btns.addWidget(go); lay.addLayout(btns)
    def do():
        hrs = rng.currentData(); done = []
        try:
            if c_hist.isChecked():
                p = self._hist_path()
                if os.path.exists(p):
                    if hrs == 0:
                        hist = []
                    else:
                        cutoff = datetime.datetime.now() - datetime.timedelta(hours=hrs)
                        with open(p, encoding="utf-8") as f: old = json.load(f)
                        hist = []
                        for e in old:
                            try: keep = datetime.datetime.fromisoformat(e.get("time", "")) < cutoff
                            except Exception: keep = True
                            if keep: hist.append(e)
                    with open(p, "w", encoding="utf-8") as f: json.dump(hist, f)
                try: self.browser_profile.clearAllVisitedLinks()
                except Exception: pass
                done.append("history")
            if c_cook.isChecked():
                self.browser_profile.cookieStore().deleteAllCookies(); done.append("cookies")
            if c_cache.isChecked():
                self.browser_profile.clearHttpCache(); done.append("cache")
        except Exception as e:
            QMessageBox.warning(self, "Clear browsing data", f"Something could not be cleared:\n{e}")
        self.status.showMessage("✅ Cleared: " + (", ".join(done) or "nothing selected"), 4000)
        dlg.accept()
    go.clicked.connect(do)
    dlg.exec()

# ─────────────────────────────────────────────────────────────────────
#  Chrome-style shortcuts
# ─────────────────────────────────────────────────────────────────────
_v36_orig_setup_shortcuts = MainWindow._setup_shortcuts

def _v36_setup_shortcuts(self):
    from PyQt6.QtGui import QShortcut, QKeySequence
    _v36_orig_setup_shortcuts(self)
    # 1) clean-up of shortcuts that misbehaved
    seen_cmd_palette = False
    for sc in self.findChildren(QShortcut):
        k = sc.key().toString()
        if k == "Ctrl+Z":              # it re-opened a tab instead of undoing text in every text box
            sc.setEnabled(False); sc.deleteLater()
        elif k == "F11":               # F11 is "full screen" in every browser (focus mode stays on Ctrl+Shift+F)
            sc.setEnabled(False); sc.deleteLater()
    pdf = [sc for sc in self.findChildren(QShortcut) if sc.key().toString() == "Ctrl+Shift+P"]
    for sc in pdf[:-1]:                # two shortcuts on the same key cancel each other -> keep only the command palette
        sc.setEnabled(False); sc.deleteLater()

    def s(key, fn):
        QShortcut(QKeySequence(key), self).activated.connect(lambda f=fn: self._safe_call(f))
    s("F11", lambda: self._enter_fullscreen() if hasattr(self, "_enter_fullscreen") else self.showFullScreen())
    for i in range(1, 9):
        s(f"Ctrl+{i}", lambda i=i: self.tabs.setCurrentIndex(i - 1) if i - 1 < self.tabs.count() else None)
    s("Ctrl+9", lambda: self.tabs.setCurrentIndex(self.tabs.count() - 1))
    s("Ctrl+PgDown", self._next_tab); s("Ctrl+PgUp", self._prev_tab)
    s("Ctrl+N", self.open_new_window)
    s("Ctrl+Shift+W", self.close)
    s("Ctrl+Shift+Del", self._show_clear_browsing_data)
    s("Ctrl+Shift+Delete", self._show_clear_browsing_data)
    s("Ctrl+Shift+B", self.toggle_bookmarks_bar)
    s("Ctrl+Shift+O", lambda: self._show_bookmark_manager())
    s("Ctrl+Shift+D", self.bookmark_all_tabs)
    s("Ctrl+Shift+J", self.open_dev_tools)
    s("Shift+Esc", self._show_task_manager)
    s("Alt+Home", self.navigate_home)
    s("F6", lambda: (self.url_bar.setFocus(), self.url_bar.selectAll()))
    s("Alt+D", lambda: (self.url_bar.setFocus(), self.url_bar.selectAll()))
    s("Ctrl+E", lambda: (self.url_bar.setFocus(), self.url_bar.selectAll()))
    s("F3", lambda: (self.find_bar.show_and_focus() if not self.find_bar.isVisible() else self.find_bar._find_next()))
    s("Shift+F3", lambda: self.find_bar._find_prev())
    s("Ctrl+G", lambda: self.find_bar._find_next())


# ─────────────────────────────────────────────────────────────────────
#  UPDATER  (sps_updater.py does the work; this is only the window part)
#   background: check page -> verify signature -> download -> verify SHA-256
#   next start: forced "Update now" window -> silent install -> new browser starts
# ─────────────────────────────────────────────────────────────────────
def _v36_updater(self):
    if getattr(self, "_v36_upd", None) is None:
        import sps_updater
        def _log(msg):
            try:
                with open(os.path.join(BASE_DATA_DIR, "update_log.txt"), "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
            except Exception:
                pass
        self._v36_upd = sps_updater.SpsUpdater(VERSION, APP_ROOT_DIR, log=_log)
    return self._v36_upd

def _v36_start_updater(self):
    """Called once when the window opens: silent background checks for the whole session."""
    try:
        if os.environ.get("SPS_DISABLE_UPDATER") == "1":
            return
        self._v36_updater().start_background()
        QTimer.singleShot(8000, self._v36_check_staged_update)
    except Exception as e:
        print("[SPS V36] updater not started:", e)

def _v36_check_staged_update(self, manual=False):
    """If a verified update is waiting on disk, show the window. Returns True if one was shown."""
    try:
        info = self._v36_updater().staged_update()
    except Exception:
        info = None
    if not info:
        return False
    if getattr(self, "_v36_update_dialog_open", False):
        return True
    self._v36_update_dialog_open = True
    try:
        dlg = SpsForcedUpdateDialog(self, info)
        dlg.exec()
    finally:
        self._v36_update_dialog_open = False
    return True

class SpsForcedUpdateDialog(QDialog):
    """Mandatory updates cannot be closed, skipped or postponed (Esc / the X do nothing)."""
    def __init__(self, win, info):
        super().__init__(win)
        self.win, self.info = win, info
        self.mandatory = bool(info.get("mandatory", True))
        self.setWindowTitle("SPS Browser update")
        self.setModal(True)
        flags = Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.CustomizeWindowHint
        if not self.mandatory:
            flags |= Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        title = QLabel(f"<h2>SPS Browser {html.escape(str(info['version']))} is ready</h2>")
        lay.addWidget(title)
        why = ("This update contains important security and stability fixes, so it is required." if self.mandatory
               else "A new version of SPS Browser is ready to install.")
        lay.addWidget(QLabel(f"<p>You are using version {html.escape(VERSION)}. {why}</p>"
                             "<p>The file was already downloaded and its digital fingerprint (SHA-256) and the "
                             "publisher's signature were checked. Your bookmarks, passwords and settings are kept. "
                             "SPS Browser restarts automatically when the update is done.</p>"))
        notes = (info.get("notes") or "").strip()
        if notes:
            n = QLabel(html.escape(notes)); n.setWordWrap(True)
            n.setStyleSheet("padding:8px;background:rgba(128,128,128,0.15);border-radius:6px;")
            lay.addWidget(n)
        self.status = QLabel(""); self.status.setWordWrap(True); lay.addWidget(self.status)
        row = QHBoxLayout(); row.addStretch()
        if not self.mandatory:
            later = QPushButton("Later"); later.clicked.connect(self.reject); row.addWidget(later)
        self.btn = QPushButton("Update now"); self.btn.setDefault(True)
        self.btn.clicked.connect(self._go); row.addWidget(self.btn)
        lay.addLayout(row)

    def reject(self):
        if self.mandatory:
            return                      # Esc / close ignored
        super().reject()

    def closeEvent(self, ev):
        if self.mandatory:
            ev.ignore()
        else:
            super().closeEvent(ev)

    def _go(self):
        self.btn.setEnabled(False)
        self.status.setText("Starting the installer... (Windows may ask for permission once)")
        QApplication.processEvents()
        try:
            ok = self.win._v36_updater().launch_installer(self.info)
        except Exception as e:
            ok = False; print("[SPS V36] launch failed:", e)
        if ok:
            self.status.setText("Installing... SPS Browser will close and open again by itself.")
            QApplication.processEvents()
            # leave quickly so the installer can replace the files
            QTimer.singleShot(1500, lambda: os._exit(0))
        else:
            self.btn.setEnabled(True)
            self.status.setText("The update could not start (permission was refused or the file changed). Click Update now to try again.")

class SpsUpdateCheckDialog(QDialog):
    """Manual 'Check for Updates'. Always closeable (X, Esc or Cancel), never blocks the browser, shows what is happening,
    and gives up by itself if the network does not answer."""
    NO_ANSWER_SECONDS = 45

    def __init__(self, win):
        super().__init__(win)
        import threading, time as _t
        self.win = win
        self._t0 = _t.time()
        self._cancel = threading.Event()
        self._state = {"phase": "check", "done": 0, "total": 0, "result": None}
        self.setWindowTitle("Check for Updates")
        self.setModal(False)                                  # the browser stays usable
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowSystemMenuHint
                            | Qt.WindowType.WindowCloseButtonHint)
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        self.msg = QLabel(f"Checking for updates...\nYou are using version {html.escape(VERSION)}.")
        self.msg.setWordWrap(True); lay.addWidget(self.msg)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); lay.addWidget(self.bar)
        row = QHBoxLayout(); row.addStretch()
        self.btn = QPushButton("Cancel"); self.btn.clicked.connect(self.close); row.addWidget(self.btn)
        lay.addLayout(row)
        updater = win._v36_updater()
        def progress(done, total):
            self._state.update(phase="download", done=done, total=total)
        def work():
            try:
                self._state["result"] = updater.check_and_stage(progress, self._cancel)
            except Exception as e:                            # never let the thread die silently
                self._state["result"] = ("error", f"{type(e).__name__}: {e}")
        self._thread = threading.Thread(target=work, name="sps-update-check", daemon=True)
        self._thread.start()
        self._timer = QTimer(self); self._timer.timeout.connect(self._poll); self._timer.start(200)

    def _finish(self):
        self._timer.stop()
        self.btn.setText("Close")

    def _poll(self):
        import time as _t
        st = self._state
        res = st["result"]
        if res is None:
            if st["phase"] == "download":
                tot = max(1, st["total"])
                self.bar.setRange(0, 100); self.bar.setValue(int(st["done"] * 100 / tot))
                self.msg.setText(f"Downloading the update... {st['done']//1048576} of {tot//1048576} MB\n"
                                 "You can keep browsing; you can also cancel.")
            elif _t.time() - self._t0 > self.NO_ANSWER_SECONDS:
                self._cancel.set(); self._finish()
                self.bar.setRange(0, 1); self.bar.setValue(0)
                self.msg.setText("The update server did not answer. Please check your internet connection and try again later.")
            return
        self._finish()
        self.bar.setRange(0, 1); self.bar.setValue(1)
        kind, data = res
        if kind in ("staged", "ready") and data:
            self.close()
            if not getattr(self.win, "_v36_update_dialog_open", False):
                self.win._v36_update_dialog_open = True
                try:
                    SpsForcedUpdateDialog(self.win, data).exec()
                finally:
                    self.win._v36_update_dialog_open = False
        elif kind == "uptodate":
            self.msg.setText(f"SPS Browser {html.escape(VERSION)} is up to date.")
        elif kind == "busy":
            self.msg.setText("An update is already being downloaded in the background. Please try again in a few minutes.")
        else:
            why = str(data or "")
            self.msg.setText("Could not check for updates right now.\nPlease check your internet connection and try again."
                             + (f"\n\nDetails: {html.escape(why[:200])}" if why and "cancelled" not in why else ""))

    def closeEvent(self, ev):
        self._cancel.set(); self._timer.stop()
        super().closeEvent(ev)

def _v36_check_for_updates(self):
    """Help > Check for Updates (manual)."""
    old = getattr(self, "_v36_check_dlg", None)
    try:
        if old is not None and old.isVisible():
            old.raise_(); old.activateWindow(); return
    except RuntimeError:
        pass
    self._v36_check_dlg = SpsUpdateCheckDialog(self)
    self._v36_check_dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    self._v36_check_dlg.show()

MainWindow._v36_updater = _v36_updater
MainWindow._v36_start_updater = _v36_start_updater
MainWindow._v36_check_staged_update = _v36_check_staged_update
MainWindow._check_for_updates = _v36_check_for_updates

MainWindow._setup_shortcuts = _v36_setup_shortcuts
MainWindow._show_clear_browsing_data = _show_clear_browsing_data
MainWindow._show_support_page = _show_support_page
MainWindow._show_whats_new = _show_whats_new

print("[SPS V36] Patch loaded")


# ── V37: Help > Graphics mode (safe graphics on/off) ──
def _v36_toggle_graphics(self):
    """Switch between normal graphics and SAFE graphics (no GPU). Takes effect after restart."""
    try:
        cur = _sps_gfx_load().get("mode", "auto")
        if cur == "software":
            ask = "SAFE GRAPHICS is ON (no GPU is used).\n\nSwitch back to normal graphics? Only do this if your graphics driver is up to date.\nThe change applies after SPS Browser is restarted."
            if QMessageBox.question(self, "Graphics mode", ask) == QMessageBox.StandardButton.Yes:
                _sps_gfx_set_mode("auto")
                QMessageBox.information(self, "Graphics mode", "Normal graphics will be used the next time you start SPS Browser.")
        else:
            ask = "Normal graphics are ON.\n\nSwitch to SAFE GRAPHICS? Use this if the browser or the PC crashes, freezes or shows a blue screen.\nThe change applies after SPS Browser is restarted."
            if QMessageBox.question(self, "Graphics mode", ask) == QMessageBox.StandardButton.Yes:
                _sps_gfx_set_mode("software")
                QMessageBox.information(self, "Graphics mode", "SAFE GRAPHICS will be used the next time you start SPS Browser.")
    except Exception as e:
        QMessageBox.warning(self, "Graphics mode", f"Could not change the graphics mode: {e}")

MainWindow._v36_toggle_graphics = _v36_toggle_graphics
