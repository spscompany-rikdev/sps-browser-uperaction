"""Chrome extensions for SPS Browser (Qt 6.10+ QWebEngineExtensionManager).

Add several extensions at once (a .zip / .crx file, a folder, or a download link); they are downloaded, checked and installed ONE
AFTER THE OTHER, then switched on. Rules that come from Qt itself:
  * only Manifest V3 extensions work (older ones are refused with a clear message),
  * a private / guest window has no extensions,
  * Qt does not publish a list of supported Chrome APIs, so some extensions may install but not fully work - that is why every
    installed extension has a "Check" that shows whether it is loaded and enabled.
The pure helpers (prepare_package, crx_to_zip_bytes, safe_name) need no Qt and are covered by tests/test_chrome_ext.py.
"""
import io, json, os, re, shutil, struct, tempfile, threading, zipfile

MAX_BYTES = 80 * 1024 * 1024


class ExtError(Exception):
    pass


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:60] or "extension"


def crx_to_zip_bytes(data):
    """A .crx is a zip with a header in front. Returns the zip bytes (CRX2 and CRX3)."""
    if data[:4] != b"Cr24":
        return data
    ver = struct.unpack("<I", data[4:8])[0]
    if ver == 2:
        pub, sig = struct.unpack("<II", data[8:16]); start = 16 + pub + sig
    elif ver == 3:
        hdr = struct.unpack("<I", data[8:12])[0]; start = 12 + hdr
    else:
        raise ExtError("unknown .crx version %s" % ver)
    return data[start:]


def _check_zip(zbytes_or_path):
    try:
        z = zipfile.ZipFile(zbytes_or_path if isinstance(zbytes_or_path, str) else io.BytesIO(zbytes_or_path))
    except zipfile.BadZipFile:
        raise ExtError("this is not a valid zip / crx file")
    names = z.namelist()
    for n in names:                                         # zip-slip: no absolute or '..' paths
        if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
            raise ExtError("the package contains an unsafe path: " + n)
    if sum(i.file_size for i in z.infolist()) > 400 * 1024 * 1024:
        raise ExtError("the package unpacks to more than 400 MB")
    if "manifest.json" not in names:
        inner = sorted(n for n in names if n.endswith("/manifest.json") and n.count("/") == 1)
        if inner:
            raise ExtError("manifest.json is inside the folder '%s' - zip the CONTENT of that folder, not the folder itself" % inner[0].split("/")[0])
        raise ExtError("manifest.json was not found at the top of the package")
    try:
        m = json.loads(z.read("manifest.json").decode("utf-8-sig"))
    except Exception:
        raise ExtError("manifest.json cannot be read")
    if m.get("manifest_version") != 3:
        raise ExtError("this extension uses Manifest V%s - SPS Browser (Chromium engine) only runs Manifest V3 extensions" % m.get("manifest_version"))
    return m


def prepare_package(src, workdir):
    """src = path of .zip / .crx / folder. Returns (zip_path, manifest). Raises ExtError with a plain-language reason."""
    os.makedirs(workdir, exist_ok=True)
    if os.path.isdir(src):
        out = os.path.join(workdir, safe_name(os.path.basename(src.rstrip("/\\"))) + ".zip")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for d, dirs, files in os.walk(src):
                dirs[:] = [x for x in dirs if not x.startswith("_")]
                for f in files:
                    full = os.path.join(d, f); z.write(full, os.path.relpath(full, src))
        return out, _check_zip(out)
    if not os.path.isfile(src):
        raise ExtError("file not found: " + src)
    if os.path.getsize(src) > MAX_BYTES:
        raise ExtError("the file is larger than %d MB" % (MAX_BYTES // 1048576))
    data = open(src, "rb").read()
    zb = crx_to_zip_bytes(data)
    m = _check_zip(zb)
    out = os.path.join(workdir, safe_name(os.path.splitext(os.path.basename(src))[0]) + ".zip")
    with open(out, "wb") as f:
        f.write(zb)
    return out, m


def download(url, workdir, cancel=None):
    """Download an https link (a .zip/.crx, e.g. a GitHub release asset) into workdir. Returns the file path."""
    import requests
    if not url.lower().startswith("https://"):
        raise ExtError("only https:// links are accepted")
    if "chromewebstore.google.com" in url.lower() or "chrome.google.com/webstore" in url.lower():
        raise ExtError("this is a Chrome Web Store page, not a package. Download the extension's .zip/.crx from its developer "
                       "(for example GitHub Releases) and add that link or file")
    os.makedirs(workdir, exist_ok=True)
    name = safe_name(os.path.basename(url.split("?")[0]) or "extension.zip")
    out = os.path.join(workdir, name if name.lower().endswith((".zip", ".crx")) else name + ".zip")
    try:
        with requests.get(url, stream=True, timeout=(10, 30), headers={"User-Agent": "SPS-Browser"}) as r:
            r.raise_for_status()
            total = 0
            with open(out, "wb") as f:
                for chunk in r.iter_content(65536):
                    if cancel is not None and cancel.is_set():
                        raise ExtError("cancelled")
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ExtError("the download is larger than %d MB" % (MAX_BYTES // 1048576))
                    f.write(chunk)
    except ExtError:
        raise
    except Exception as e:
        raise ExtError("download failed: %s" % str(e)[:120])
    return out


# ───────────────────────────── Qt part (window) ─────────────────────────────
def manager_for(profile):
    """The profile's extension manager, or (None, reason)."""
    try:
        if profile.isOffTheRecord():
            return None, "A private / guest window cannot use extensions (Qt does not allow it). Use a normal window."
        mgr = profile.extensionManager()
    except AttributeError:
        return None, "This build of the web engine is older than Qt 6.10 and has no Chrome extension support."
    return mgr, ""


def show_dialog(window, modal=True):
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                                 QFileDialog, QMessageBox, QAbstractItemView)
    mgr, why = manager_for(window.browser_profile)
    if mgr is None:
        QMessageBox.information(window, "Chrome extensions", why)
        return None
    t = getattr(window, "_theme", {}) or {}
    bg = t.get("bg_primary", "#ffffff"); fg = t.get("text_primary", "#202124"); fg2 = t.get("text_secondary", "#5f6368")
    card = t.get("bg_secondary", "#f1f3f4"); acc = t.get("accent", "#1a73e8")
    dlg = QDialog(window); dlg.setWindowTitle("Chrome extensions"); dlg.resize(640, 640)
    dlg.setStyleSheet(f"QDialog{{background:{bg};}} QLabel{{color:{fg};}} QLineEdit,QListWidget{{background:{card};color:{fg};"
                      f"border:1px solid {fg2};border-radius:8px;padding:6px;}} QPushButton{{background:{card};color:{fg};"
                      f"border:1px solid {fg2};border-radius:8px;padding:7px 12px;}} QPushButton:hover{{border-color:{acc};}}"
                      f"QPushButton#go{{background:{acc};color:#fff;border:none;font-weight:600;}}")
    lay = QVBoxLayout(dlg); lay.setContentsMargins(18, 16, 18, 14); lay.setSpacing(8)
    title = QLabel("Add Chrome extensions"); title.setStyleSheet("font-size:18px;font-weight:600;"); lay.addWidget(title)
    info = QLabel("Add one or many: a download link (https, a .zip or .crx, for example from GitHub Releases) or files / folders from your "
                  "computer. They are installed one after the other and switched on. Only Manifest V3 extensions work.")
    info.setWordWrap(True); info.setStyleSheet(f"color:{fg2};"); lay.addWidget(info)
    row = QHBoxLayout(); url = QLineEdit(); url.setPlaceholderText("https://github.com/.../releases/download/.../extension.zip")
    b_url = QPushButton("Add link"); b_files = QPushButton("Add files…"); b_dir = QPushButton("Add folder…")
    for w in (url, b_url, b_files, b_dir): row.addWidget(w)
    row.setStretch(0, 1); lay.addLayout(row)
    queue = QListWidget(); queue.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); lay.addWidget(queue, 1)
    row2 = QHBoxLayout(); b_rm = QPushButton("Remove from list"); b_go = QPushButton("Install all, in order"); b_go.setObjectName("go")
    row2.addWidget(b_rm); row2.addStretch(); row2.addWidget(b_go); lay.addLayout(row2)
    status = QLabel(""); status.setWordWrap(True); status.setStyleSheet(f"color:{fg2};"); lay.addWidget(status)
    lay.addWidget(QLabel("<b>Installed extensions</b>"))
    inst = QListWidget(); lay.addWidget(inst, 1)
    row3 = QHBoxLayout(); b_chk = QPushButton("Check"); b_del = QPushButton("Uninstall"); b_close = QPushButton("Close")
    for w in (b_chk, b_del): row3.addWidget(w)
    row3.addStretch(); row3.addWidget(b_close); lay.addLayout(row3)

    work = tempfile.mkdtemp(prefix="sps_ext_")
    st = {"running": False, "current": None, "box": None, "cancel": threading.Event(), "ok": 0, "bad": 0}

    def add_item(kind, value):
        for i in range(queue.count()):
            if queue.item(i).data(Qt.ItemDataRole.UserRole) == (kind, value):
                return
        it = QListWidgetItem("⏳  " + value); it.setData(Qt.ItemDataRole.UserRole, (kind, value)); queue.addItem(it)

    def refresh():
        inst.clear()
        for e in mgr.extensions():
            if e.name() in ("chromium-pdf", "Google Hangouts"):
                continue
            state = "ON" if e.isLoaded() else "off"
            it = QListWidgetItem("%s  [%s]  %s" % (e.name(), state, ("" if e.isLoaded() else "(not loaded)")))
            it.setData(Qt.ItemDataRole.UserRole, e.id()); inst.addItem(it)

    def toolbar_sync():
        try: window._rebuild_extension_toolbar_buttons()
        except Exception: pass

    def ext_by_id(i):
        return next((e for e in mgr.extensions() if e.id() == i), None)

    def mark(item, icon, text):
        kind, value = item.data(Qt.ItemDataRole.UserRole); item.setText("%s  %s%s" % (icon, value, ("  —  " + text) if text else ""))

    def next_item():
        for i in range(queue.count()):
            if queue.item(i).text().startswith("⏳"):
                return queue.item(i)
        return None

    def finish():
        st["running"] = False; b_go.setEnabled(True)
        status.setText("Done: %d installed, %d failed.%s" % (st["ok"], st["bad"], "  Reload open pages to see the extension work." if st["ok"] else ""))
        refresh()

    def step():
        it = next_item()
        if it is None:
            finish(); return
        kind, value = it.data(Qt.ItemDataRole.UserRole); st["current"] = it; mark(it, "⬇", "preparing…")
        status.setText("Installing %d of %d…" % (st["ok"] + st["bad"] + 1, st["ok"] + st["bad"] + sum(1 for i in range(queue.count()) if queue.item(i).text().startswith(("⏳", "⬇")))))
        box = {}; st["box"] = box
        def work_fn():
            try:
                src = download(value, work, st["cancel"]) if kind == "url" else value
                box["zip"], box["manifest"] = prepare_package(src, work)
            except ExtError as e:
                box["err"] = str(e)
            except Exception as e:
                box["err"] = "unexpected: %s" % str(e)[:120]
            box["done"] = True
        threading.Thread(target=work_fn, daemon=True).start()
        tm = QTimer(dlg); tm.setInterval(200)
        def poll():
            if not box.get("done"):
                return
            tm.stop(); tm.deleteLater()
            if "err" in box:
                mark(it, "❌", box["err"]); st["bad"] += 1; QTimer.singleShot(0, step); return
            mark(it, "⬇", "installing…")
            try:
                mgr.installExtension(box["zip"])
            except Exception as e:
                mark(it, "❌", str(e)[:100]); st["bad"] += 1; QTimer.singleShot(0, step); return
            guard = QTimer(dlg); guard.setSingleShot(True); guard.setInterval(30000)      # never wait forever for Qt
            box["guard"] = guard
            def timeout():
                if st["current"] is it and it.text().startswith("⬇"):
                    mark(it, "❌", "Qt did not answer within 30 s"); st["bad"] += 1; st["current"] = None; QTimer.singleShot(0, step)
            guard.timeout.connect(timeout); guard.start()
        tm.timeout.connect(poll); tm.start()

    def on_installed(info):
        it = st["current"]
        if it is None or not it.text().startswith("⬇"):
            refresh(); return
        g = (st["box"] or {}).get("guard")
        if g is not None: g.stop()
        err, ext_id, ext_name = info.error(), info.id(), info.name()      # copy now: 'info' must not be used after this call (Qt crash)
        if err:
            mark(it, "❌", err); st["bad"] += 1
            st["current"] = None
            QTimer.singleShot(300, step)
            return
        st["current"] = None
        # Qt loads a freshly installed extension straight away, so it is already running.
        # (Qt's setExtensionEnabled() crashes on some builds, so it is deliberately never called.)
        def finish():
            mark(it, "✅", "%s installed and running" % ext_name); st["ok"] += 1
            toolbar_sync()
            QTimer.singleShot(400, step)
        QTimer.singleShot(200, finish)
    mgr.installFinished.connect(on_installed)

    def go():
        if st["running"]: return
        if next_item() is None:
            status.setText("The list is empty or already done - add a link or file first."); return
        st["running"] = True; st["ok"] = st["bad"] = 0; b_go.setEnabled(False); step()

    def pick_files():
        fs, _ = QFileDialog.getOpenFileNames(dlg, "Chrome extension packages", "", "Extension (*.zip *.crx);;All files (*.*)")
        for f in fs: add_item("file", f)
    def pick_dir():
        d = QFileDialog.getExistingDirectory(dlg, "Unpacked extension folder")
        if d: add_item("file", d)
    def add_link():
        u = url.text().strip()
        if u: add_item("url", u); url.clear()
    def remove_sel():
        for it in queue.selectedItems():
            if it is not st["current"]: queue.takeItem(queue.row(it))
    def selected_ext():
        it = inst.currentItem()
        return ext_by_id(it.data(Qt.ItemDataRole.UserRole)) if it else None
    def check():
        e = selected_ext()
        if e is None: status.setText("Select an installed extension first."); return
        problems = []
        if not e.isLoaded(): problems.append("it is not loaded")
        if e.error(): problems.append("error: " + e.error())
        status.setText("%s: %s" % (e.name(), "working - loaded and running. Reload the page you want to use it on." if not problems
                                   else "NOT working - " + "; ".join(problems) + "."))
    def uninstall():
        e = selected_ext()
        if e is None: status.setText("Select an installed extension first."); return
        if QMessageBox.question(dlg, "Uninstall", "Remove %s?" % e.name()) == QMessageBox.StandardButton.Yes:
            remove(mgr, e); QTimer.singleShot(600, refresh); QTimer.singleShot(700, toolbar_sync)

    b_url.clicked.connect(add_link); url.returnPressed.connect(add_link); b_files.clicked.connect(pick_files); b_dir.clicked.connect(pick_dir)
    b_rm.clicked.connect(remove_sel); b_go.clicked.connect(go); b_chk.clicked.connect(check)
    b_del.clicked.connect(uninstall); b_close.clicked.connect(dlg.accept)
    mgr.uninstallFinished.connect(lambda *a: refresh())
    dlg.finished.connect(lambda *_: (st["cancel"].set(), shutil.rmtree(work, True)))
    refresh()
    dlg.test_hooks = {"add": add_item, "go": go, "queue": queue, "inst": inst, "status": status, "state": st, "refresh": refresh, "check": check}
    if modal:
        dlg.exec()
    else:
        dlg.show()
    return dlg


# ── toolbar support (V40) ───────────────────────────────────────────────────────────────────
BUILTIN = ("chromium-pdf", "Google Hangouts")


def autoload(profile):
    """Qt does NOT reload installed extensions after a restart - load every installed folder again. Safe to call often."""
    mgr, _why = manager_for(profile)
    if mgr is None:
        return 0
    n = 0
    try:
        root = mgr.installPath()
        have = {os.path.normcase(os.path.abspath(e.path())) for e in mgr.extensions() if e.path()}
        for d in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            full = os.path.join(root, d)
            if os.path.isfile(os.path.join(full, "manifest.json")) and os.path.normcase(os.path.abspath(full)) not in have:
                mgr.loadExtension(full); n += 1
    except Exception:
        pass
    return n


def icon_file(ext_dir):
    """The extension's real logo: the biggest sensible PNG named in manifest.json (icons, then action.default_icon)."""
    try:
        with open(os.path.join(ext_dir, "manifest.json"), encoding="utf-8-sig") as f:
            m = json.load(f)
    except Exception:
        return ""
    cands = []
    for src in (m.get("icons"), (m.get("action") or m.get("browser_action") or {}).get("default_icon")):
        if isinstance(src, str):
            cands.append((32, src))
        elif isinstance(src, dict):
            for k, v in src.items():
                try: cands.append((int(k), v))
                except Exception: pass
    good = sorted((c for c in cands if c[0] >= 32), key=lambda c: c[0]) or sorted(cands, key=lambda c: -c[0])
    for _sz, rel in good:
        fp = os.path.normpath(os.path.join(ext_dir, str(rel).lstrip("/\\")))
        if os.path.isfile(fp) and fp.startswith(os.path.normpath(ext_dir)):
            return fp
    return ""


def toolbar_entries(profile):
    """[(name, id, icon_path, popup_url)] for every running extension that is not Qt's own."""
    mgr, _why = manager_for(profile)
    out = []
    if mgr is None:
        return out
    for e in mgr.extensions():
        if e.name() in BUILTIN or not e.isLoaded():
            continue
        try: pop = e.actionPopupUrl().toString()
        except Exception: pop = ""
        out.append((e.name(), e.id(), icon_file(e.path()) if e.path() else "", pop))
    return out


def open_popup(window, name, url, anchor=None, size=(400, 560)):
    """Show the extension's own popup page (what Chrome shows when you click its icon) under the toolbar button."""
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtWidgets import QDialog, QVBoxLayout
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage
    dlg = QDialog(window, Qt.WindowType.Popup)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dlg.resize(*size)
    lay = QVBoxLayout(dlg); lay.setContentsMargins(0, 0, 0, 0)
    view = QWebEngineView(dlg)
    view.setPage(QWebEnginePage(window.browser_profile, view))
    lay.addWidget(view)
    view.setUrl(QUrl(url))
    if anchor is not None:
        pt = anchor.mapToGlobal(anchor.rect().bottomRight())
        dlg.move(max(0, pt.x() - size[0]), pt.y() + 4)
    dlg.show()
    window._sps_ext_popup = dlg
    return dlg


def remove(mgr, ext):
    """Uninstall. An extension that was only loaded from its folder (not 'installed') is unloaded and its folder deleted."""
    import shutil
    path = ext.path()
    try:
        if ext.isInstalled():
            mgr.uninstallExtension(ext); return
    except Exception:
        pass
    mgr.unloadExtension(ext)
    try:
        if path and os.path.abspath(path).startswith(os.path.abspath(mgr.installPath())):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass
