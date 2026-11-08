"""Password checkup: finds saved passwords that are leaked, reused or weak.

Leaked check = "Have I Been Pwned" range service with k-anonymity: only the FIRST 5 characters of the password's SHA-1 are sent, never the
password and never the full hash; the answer is a list of hash endings that are compared here, on this computer.
Nothing is sent unless the user presses the button.
"""
import hashlib, re, threading, urllib.request

API = "https://api.pwnedpasswords.com/range/"
COMMON = {"123456", "1234567", "12345678", "123456789", "1234567890", "password", "password1", "passw0rd", "qwerty", "qwerty123", "abc123",
          "111111", "000000", "iloveyou", "admin", "welcome", "letmein", "monkey", "dragon", "football", "login", "princess", "sunshine",
          "master", "hello", "freedom", "whatever", "trustno1", "654321", "123123", "1q2w3e4r", "qazwsx", "zaq12wsx", "password123", "admin123"}


def fetch_range(prefix, timeout=10):
    req = urllib.request.Request(API + prefix, headers={"User-Agent": "SPS-Browser-password-checkup", "Add-Padding": "true"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def pwned_count(password, fetch=None):
    fetch = fetch or fetch_range
    """How many known leaks contain this password (0 = none known). Raises on network problems."""
    h = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    pre, suf = h[:5], h[5:]
    for line in fetch(pre).splitlines():
        a, _, n = line.strip().partition(":")
        if a == suf:
            try:
                return int(n)
            except ValueError:
                return 1
    return 0


def weakness(pw):
    """Reason text if the password is weak, else ''."""
    if not pw:
        return "empty"
    low = pw.lower()
    if low in COMMON:
        return "one of the most common passwords"
    if len(pw) < 8:
        return "shorter than 8 characters"
    if len(set(pw)) <= 3:
        return "uses almost the same character everywhere"
    if re.fullmatch(r"\d+", pw):
        return "only digits"
    if re.fullmatch(r"[a-zA-Z]+", pw) and len(pw) < 12:
        return "only letters and short"
    return ""


def local_issues(entries):
    """Reused + weak, no network. entries: list of dicts with id/site/username/password."""
    out = []
    by_pw = {}
    for e in entries:
        by_pw.setdefault(e.get("password", ""), []).append(e)
    for pw, group in by_pw.items():
        if pw and len(group) > 1:
            sites = {g.get("site", "") for g in group}
            for g in group:
                out.append({"kind": "reused", "id": g.get("id"), "site": g.get("site", ""), "user": g.get("username", ""),
                            "why": "Same password on %d saved logins" % len(group)})
    for e in entries:
        w = weakness(e.get("password", ""))
        if w:
            out.append({"kind": "weak", "id": e.get("id"), "site": e.get("site", ""), "user": e.get("username", ""), "why": "Weak: " + w})
    return out


def check_all(entries, fetch=None, progress=None, stop=None):
    """Full checkup. Returns {'issues': [...], 'checked': n, 'offline': bool, 'total': n}. progress(done,total) is called after each password."""
    issues = local_issues(entries)
    uniq = sorted({e.get("password", "") for e in entries if e.get("password")})
    leaked = {}; offline = False
    for i, pw in enumerate(uniq):
        if stop is not None and stop():
            break
        try:
            n = pwned_count(pw, fetch or fetch_range)
            if n:
                leaked[pw] = n
        except Exception:
            offline = True
            break
        if progress:
            progress(i + 1, len(uniq))
    for e in entries:
        n = leaked.get(e.get("password", ""))
        if n:
            issues.append({"kind": "leaked", "id": e.get("id"), "site": e.get("site", ""), "user": e.get("username", ""),
                           "why": "Found in %s known data leaks - change it now" % format(n, ",")})
    order = {"leaked": 0, "reused": 1, "weak": 2}
    issues.sort(key=lambda x: (order[x["kind"]], x["site"]))
    return {"issues": issues, "total": len(entries), "offline": offline, "checked": len(uniq) if not offline else 0}


def run_async(entries, on_progress, on_done, fetch=None):
    """Runs check_all in a background thread. Callbacks are called from that thread (connect them to Qt signals)."""
    stop = {"v": False}
    def work():
        try:
            r = check_all(entries, fetch or fetch_range, on_progress, lambda: stop["v"])
        except Exception as ex:
            r = {"issues": [], "total": len(entries), "offline": True, "checked": 0, "error": str(ex)}
        on_done(r)
    t = threading.Thread(target=work, daemon=True); t.start()
    return lambda: stop.__setitem__("v", True)


def show_checkup(mw, pm, parent=None):
    """The Password Checkup window."""
    from PyQt6.QtCore import Qt, QObject, pyqtSignal, QUrl
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView)
    t = getattr(mw, "_theme", None) or {}
    dlg = QDialog(parent or mw); dlg.setWindowTitle("🛡️ Password Checkup"); dlg.resize(760, 520)
    dlg.setStyleSheet("QDialog{background:%s;} QLabel{color:%s;} QPushButton{background:%s;color:white;border:none;border-radius:8px;padding:8px 18px;font-weight:600;}"
                      "QTableWidget{background:%s;color:%s;border:1px solid %s;border-radius:8px;gridline-color:%s;}"
                      "QHeaderView::section{background:%s;color:%s;padding:6px;border:none;font-weight:600;}"
                      "QProgressBar{border:1px solid %s;border-radius:6px;text-align:center;color:%s;} QProgressBar::chunk{background:%s;border-radius:5px;}" % (
        t.get("bg_primary", "#fff"), t.get("text_primary", "#202124"), t.get("accent", "#1a73e8"), t.get("bg_secondary", "#f8f9fa"), t.get("text_primary", "#202124"),
        t.get("border", "#dadce0"), t.get("border", "#dadce0"), t.get("bg_tertiary", "#e8eaed"), t.get("text_primary", "#202124"), t.get("border", "#dadce0"),
        t.get("text_primary", "#202124"), t.get("accent", "#1a73e8")))
    lay = QVBoxLayout(dlg)
    head = QLabel("<span style='font-size:20px;font-weight:700'>🛡️ Password Checkup</span>"); lay.addWidget(head)
    info = QLabel("Looks for saved passwords that are <b>leaked</b> in known data breaches, <b>reused</b> on several sites, or <b>weak</b>.<br>"
                  "For the leak check only the first 5 characters of a scrambled (SHA-1) fingerprint are sent - never the password itself.")
    info.setWordWrap(True); lay.addWidget(info)
    bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(0); bar.hide(); lay.addWidget(bar)
    summary = QLabel(""); summary.setWordWrap(True); lay.addWidget(summary)
    table = QTableWidget(0, 4); table.setHorizontalHeaderLabels(["Problem", "Site", "Username", ""])
    for i, m in enumerate([QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.ResizeToContents]):
        table.horizontalHeader().setSectionResizeMode(i, m)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    lay.addWidget(table, 1)
    row = QHBoxLayout(); go = QPushButton("▶ Check now"); close = QPushButton("Close"); close.setStyleSheet("background:transparent;color:%s;text-decoration:underline;" % t.get("accent", "#1a73e8"))
    row.addWidget(go); row.addStretch(1); row.addWidget(close); lay.addLayout(row)

    class Sig(QObject):
        prog = pyqtSignal(int, int); done = pyqtSignal(dict)
    sig = Sig(dlg); dlg._sig = sig; stopper = {"f": None}
    ICON = {"leaked": "🚨", "reused": "♻️", "weak": "⚠️"}

    def open_site(site):
        try:
            mw.add_new_tab(QUrl(site if "://" in site else "https://" + site))
            dlg.close()
        except Exception:
            pass

    def show(res):
        go.setEnabled(True); go.setText("▶ Check again"); bar.hide()
        iss = res["issues"]; table.setRowCount(0)
        nl = sum(1 for i in iss if i["kind"] == "leaked"); nr = sum(1 for i in iss if i["kind"] == "reused"); nw = sum(1 for i in iss if i["kind"] == "weak")
        if res["total"] == 0:
            summary.setText("No saved passwords yet."); return
        msg = []
        if nl: msg.append("🚨 <b>%d leaked</b>" % nl)
        if nr: msg.append("♻️ <b>%d reused</b>" % nr)
        if nw: msg.append("⚠️ <b>%d weak</b>" % nw)
        txt = (" &nbsp; ".join(msg)) if msg else "✅ <b>No problems found</b> in %d saved passwords." % res["total"]
        if res.get("offline"):
            txt += "<br><span style='color:#d93025'>Could not reach the leak-check service (no internet?). Reused and weak passwords were still checked - try again when online.</span>"
        summary.setText(txt)
        for it in iss:
            r = table.rowCount(); table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem("%s %s" % (ICON[it["kind"]], it["why"])))
            table.setItem(r, 1, QTableWidgetItem(it["site"])); table.setItem(r, 2, QTableWidgetItem(it["user"]))
            b = QPushButton("Change…"); b.setToolTip("Open the website to change this password"); b.setStyleSheet("padding:4px 12px;")
            b.clicked.connect(lambda _=False, s=it["site"]: open_site(s)); table.setCellWidget(r, 3, b)

    def start():
        entries = pm.get_all()
        go.setEnabled(False); go.setText("Checking…"); summary.setText(""); table.setRowCount(0)
        bar.show(); bar.setRange(0, 0)
        stopper["f"] = run_async(entries, lambda a, b: sig.prog.emit(a, b), lambda r: sig.done.emit(r))
    def prog(a, b):
        bar.setRange(0, max(b, 1)); bar.setValue(a)
    sig.prog.connect(prog); sig.done.connect(show)
    go.clicked.connect(start); close.clicked.connect(dlg.close)
    dlg.finished.connect(lambda *_: stopper["f"] and stopper["f"]())
    dlg._go = go; dlg._table = table; dlg._summary = summary; dlg._start = start
    return dlg
