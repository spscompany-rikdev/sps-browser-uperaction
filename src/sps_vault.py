"""Password vault lock for SPS Browser.

* "Set password": the browser makes a 6-digit code, shows it as a normal Windows notification, the user types it in -> then chooses a password.
* "Forgot password": same code flow; with the right code the lock is switched OFF (saved passwords are kept) and a new password can be set.
* While a password is set, the Password Manager and auto-fill stay closed until it is entered (once per browser session).

Works the same on Windows, macOS and Linux (the code is shown with each system's own notifier).

Honest note: the saved passwords themselves are always encrypted with a key that only this Windows user can open (DPAPI).  This lock is an
extra door in front of them.  The code of "Forgot password" arrives on the same computer, so it protects against people who are NOT sitting
at your unlocked computer - it cannot protect against someone who is.
"""
import base64, hashlib, hmac, json, os, secrets, time

ITER = 200_000
OTP_LIFETIME = 300          # seconds a code stays valid
OTP_TRIES = 5
OTP_RESEND_WAIT = 20        # seconds before a new code may be requested
PW_MIN = 6


class VaultLock:
    def __init__(self, folder):
        self.path = os.path.join(folder, "vault_lock.json")
        self.unlocked = False
        self._fails = 0
        self._wait_until = 0.0
        self._d = self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and d.get("salt") and d.get("hash"):
                return d
        except Exception:
            pass
        return {}

    def is_set(self):
        return bool(self._d)

    def needs_unlock(self):
        return self.is_set() and not self.unlocked

    @staticmethod
    def _hash(pw, salt, it):
        return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, it)

    def set_password(self, pw):
        if not isinstance(pw, str) or len(pw) < PW_MIN:
            raise ValueError("The password must have at least %d characters." % PW_MIN)
        salt = secrets.token_bytes(16)
        self._d = {"v": 1, "iter": ITER, "salt": base64.b64encode(salt).decode(), "hash": base64.b64encode(self._hash(pw, salt, ITER)).decode()}
        self._write()
        self.unlocked = True; self._fails = 0

    def _write(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._d, f)
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except Exception:
            pass

    def wait_seconds(self):
        return max(0, int(self._wait_until - time.time() + 0.999))

    def verify(self, pw):
        """True if right. After 5 wrong tries in a row the next try must wait 30 s (stops guessing)."""
        if not self.is_set():
            return True
        if self.wait_seconds() > 0:
            return False
        try:
            ok = hmac.compare_digest(self._hash(pw or "", base64.b64decode(self._d["salt"]), int(self._d.get("iter", ITER))),
                                     base64.b64decode(self._d["hash"]))
        except Exception:
            ok = False
        if ok:
            self.unlocked = True; self._fails = 0
        else:
            self._fails += 1
            if self._fails >= 5:
                self._fails = 0; self._wait_until = time.time() + 30
        return ok

    def remove(self):
        """Switch the lock off (used after a correct 'forgot password' code or after the right current password)."""
        self._d = {}
        try:
            os.remove(self.path)
        except OSError:
            pass
        self.unlocked = True

    def lock(self):
        self.unlocked = False


class Otp:
    """One-time code kept only in memory (as a hash)."""
    def __init__(self):
        self._h = None; self._exp = 0.0; self._tries = 0; self._sent = 0.0; self._salt = b""

    def new(self):
        """Returns the code, or None if a new one was asked for too fast."""
        now = time.time()
        if now - self._sent < OTP_RESEND_WAIT:
            return None
        code = "%06d" % secrets.randbelow(1_000_000)
        self._salt = secrets.token_bytes(8)
        self._h = hashlib.sha256(self._salt + code.encode()).digest()
        self._exp = now + OTP_LIFETIME; self._tries = 0; self._sent = now
        return code

    def wait_seconds(self):
        return max(0, int(self._sent + OTP_RESEND_WAIT - time.time() + 0.999))

    def check(self, code):
        """'ok', 'wrong', 'expired' or 'locked' (too many wrong tries -> ask for a new code)."""
        if self._h is None or time.time() > self._exp:
            return "expired"
        if self._tries >= OTP_TRIES:
            return "locked"
        self._tries += 1
        good = hmac.compare_digest(self._h, hashlib.sha256(self._salt + (code or "").strip().encode()).digest())
        if good:
            self._h = None                       # a code works once
            return "ok"
        return "locked" if self._tries >= OTP_TRIES else "wrong"


# ───────────────────────── UI (only imported when needed) ─────────────────────────
def _os_notify(title, text):
    """Native notification without Qt: Linux notify-send, macOS osascript, Windows PowerShell toast. True if the helper ran fine."""
    import platform, shutil, subprocess
    sysname = platform.system()
    try:
        if sysname == "Linux":
            exe = shutil.which("notify-send")
            if not exe:
                return False
            return subprocess.run([exe, "-a", "SPS Browser", "-u", "critical", "-t", "20000", title, text],
                                  capture_output=True, timeout=8).returncode == 0
        if sysname == "Darwin":
            exe = shutil.which("osascript")
            if not exe:
                return False
            scr = 'display notification "%s" with title "%s"' % (text.replace('"', "'").replace("\n", " "), title.replace('"', "'"))
            return subprocess.run([exe, "-e", scr], capture_output=True, timeout=8).returncode == 0
        if sysname == "Windows":
            ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
                  "$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('ToastText02');"
                  "$t=$x.GetElementsByTagName('text');$t.Item(0).AppendChild($x.CreateTextNode('%s'))|Out-Null;"
                  "$t.Item(1).AppendChild($x.CreateTextNode('%s'))|Out-Null;"
                  "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SPS Browser').Show([Windows.UI.Notifications.ToastNotification]::new($x))"
                  ) % (title.replace("'", ""), text.replace("'", "").replace("\n", " "))
            flags = 0x08000000                         # CREATE_NO_WINDOW
            return subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=10,
                                  creationflags=flags).returncode == 0
    except Exception:
        return False
    return False


def send_code(mw, code):
    """Show the code as a normal notification: Windows toast, macOS Notification Centre, Linux desktop notification.
    The tray icon is tried first, then the operating system's own notifier. Returns False if no notification could be shown
    (the code is then NOT shown anywhere else)."""
    hook = getattr(mw, "_sps_otp_sender", None)
    if hook:
        return bool(hook(code))
    title = "SPS Browser - your code"
    text = "Your code is %s\nIt works for 5 minutes. Do not share it." % code
    try:
        from PyQt6.QtWidgets import QSystemTrayIcon
        tray = getattr(mw, "tray", None)
        if tray is not None and tray.isVisible() and QSystemTrayIcon.supportsMessages():
            tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 20000)
            # A tray that is not really shown (e.g. GNOME without a tray extension) swallows the message: also use the OS notifier.
            import platform
            if platform.system() == "Windows":
                return True
            _os_notify(title, text)
            return True
    except Exception:
        pass
    return _os_notify(title, text)


def _style(mw):
    t = getattr(mw, "_theme", None) or {}
    return ("QDialog{background:%s;} QLabel{color:%s;} QLineEdit{background:%s;color:%s;border:1px solid %s;border-radius:8px;padding:8px 12px;font-size:15px;}"
            "QPushButton{background:%s;color:white;border:none;border-radius:8px;padding:8px 18px;font-weight:600;}"
            "QPushButton[flat=\"true\"]{background:transparent;color:%s;text-decoration:underline;padding:4px;}") % (
        t.get("bg_primary", "#fff"), t.get("text_primary", "#202124"), t.get("bg_secondary", "#f1f3f4"), t.get("text_primary", "#202124"),
        t.get("border", "#dadce0"), t.get("accent", "#1a73e8"), t.get("accent", "#1a73e8"))


def verify_by_code(mw, why):
    """Send a code as a notification and ask for it. True when the user typed the right one."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
    from PyQt6.QtCore import QTimer
    otp = Otp()
    dlg = QDialog(mw); dlg.setWindowTitle("🔐 Verification code"); dlg.setStyleSheet(_style(mw)); dlg.setMinimumWidth(400)
    lay = QVBoxLayout(dlg)
    head = QLabel("<b>%s</b>" % why); head.setWordWrap(True); lay.addWidget(head)
    info = QLabel(""); info.setWordWrap(True); lay.addWidget(info)
    ed = QLineEdit(); ed.setPlaceholderText("6-digit code"); ed.setMaxLength(6); lay.addWidget(ed)
    msg = QLabel(""); msg.setStyleSheet("color:#d93025;"); msg.setWordWrap(True); lay.addWidget(msg)
    row = QHBoxLayout(); ok = QPushButton("✓ Verify"); resend = QPushButton("Send a new code"); resend.setProperty("flat", True)
    cancel = QPushButton("Cancel"); cancel.setProperty("flat", True)
    row.addWidget(ok); row.addStretch(1); row.addWidget(resend); row.addWidget(cancel); lay.addLayout(row)
    result = {"ok": False}

    def send():
        c = otp.new()
        if c is None:
            msg.setText("Please wait %d seconds before asking for a new code." % otp.wait_seconds()); return
        if send_code(mw, c):
            info.setText("📩 A code was sent as a notification on this computer.\nIf you do not see it, open the notification centre (Windows key + N).")
            msg.setText("")
        else:
            otp._h = None; otp._sent = 0.0
            info.setText("")
            msg.setText("Notifications are turned off on this computer, so no code can be sent. Turn on notifications for SPS Browser and try again.")

    def verify():
        r = otp.check(ed.text())
        if r == "ok":
            result["ok"] = True; dlg.accept(); return
        ed.clear()
        msg.setText({"wrong": "That code is not right. Try again.", "expired": "The code is too old or was not sent. Press 'Send a new code'.",
                     "locked": "Too many wrong tries. Press 'Send a new code'."}[r])
        if r == "locked":
            otp._h = None; otp._sent = 0.0

    ok.clicked.connect(verify); ed.returnPressed.connect(verify); resend.clicked.connect(send); cancel.clicked.connect(dlg.reject)
    QTimer.singleShot(0, send)
    dlg.exec()
    return result["ok"]


def ask_new_password(mw, title="Choose your password"):
    """Returns the new password (typed twice) or None."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
    dlg = QDialog(mw); dlg.setWindowTitle("🔐 " + title); dlg.setStyleSheet(_style(mw)); dlg.setMinimumWidth(400)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>%s</b><br>At least %d characters. You need it to open your saved passwords." % (title, PW_MIN)))
    a = QLineEdit(); a.setEchoMode(QLineEdit.EchoMode.Password); a.setPlaceholderText("New password")
    b = QLineEdit(); b.setEchoMode(QLineEdit.EchoMode.Password); b.setPlaceholderText("Type it again")
    lay.addWidget(a); lay.addWidget(b)
    msg = QLabel(""); msg.setStyleSheet("color:#d93025;"); lay.addWidget(msg)
    row = QHBoxLayout(); ok = QPushButton("✓ Save password"); cancel = QPushButton("Cancel"); cancel.setProperty("flat", True)
    row.addWidget(ok); row.addStretch(1); row.addWidget(cancel); lay.addLayout(row)
    res = {"pw": None}

    def go():
        if len(a.text()) < PW_MIN:
            msg.setText("Use at least %d characters." % PW_MIN); return
        if a.text() != b.text():
            msg.setText("The two passwords are not the same."); return
        res["pw"] = a.text(); dlg.accept()
    ok.clicked.connect(go); b.returnPressed.connect(go); cancel.clicked.connect(dlg.reject)
    dlg.exec()
    return res["pw"]


def set_password_flow(mw, lock):
    """'Set password' / 'Change password' button. Always asks for a notification code first."""
    if lock.is_set() and not lock.unlocked:
        return False
    if not verify_by_code(mw, "Confirm it is you - we sent a code to your notifications."):
        return False
    pw = ask_new_password(mw)
    if not pw:
        return False
    lock.set_password(pw)
    return True


def forgot_flow(mw, lock):
    """'Forgot password': a code by notification; the right code switches the lock off, then a new one can be set."""
    if not verify_by_code(mw, "Forgot your password? Enter the code we send to your notifications."):
        return False
    lock.remove()
    return True


def unlock_dialog(mw, lock):
    """Ask for the vault password. True when opened. Has a 'Forgot password?' link."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
    from PyQt6.QtCore import QTimer
    dlg = QDialog(mw); dlg.setWindowTitle("🔒 Saved passwords are locked"); dlg.setStyleSheet(_style(mw)); dlg.setMinimumWidth(400)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>🔒 Enter your password to open your saved passwords</b>"))
    ed = QLineEdit(); ed.setEchoMode(QLineEdit.EchoMode.Password); ed.setPlaceholderText("Password"); lay.addWidget(ed)
    msg = QLabel(""); msg.setStyleSheet("color:#d93025;"); msg.setWordWrap(True); lay.addWidget(msg)
    row = QHBoxLayout(); ok = QPushButton("🔓 Open"); fg = QPushButton("Forgot password?"); fg.setProperty("flat", True)
    cancel = QPushButton("Cancel"); cancel.setProperty("flat", True)
    row.addWidget(ok); row.addStretch(1); row.addWidget(fg); row.addWidget(cancel); lay.addLayout(row)
    res = {"ok": False}

    def go():
        w = lock.wait_seconds()
        if w:
            msg.setText("Too many wrong tries. Wait %d seconds." % w); return
        if lock.verify(ed.text()):
            res["ok"] = True; dlg.accept(); return
        ed.clear(); w = lock.wait_seconds()
        msg.setText("Too many wrong tries. Wait %d seconds." % w if w else "That password is not right.")

    def forgot():
        if forgot_flow(mw, lock):
            res["ok"] = True; dlg.accept()
            QTimer.singleShot(0, lambda: set_password_flow_after_reset(mw, lock))
    ok.clicked.connect(go); ed.returnPressed.connect(go); fg.clicked.connect(forgot); cancel.clicked.connect(dlg.reject)
    dlg.exec()
    return res["ok"]


def set_password_flow_after_reset(mw, lock):
    """After 'forgot': offer to choose a new password right away (no second code needed - the code was just verified)."""
    pw = ask_new_password(mw, "Choose a new password (or Cancel to leave the lock off)")
    if pw:
        lock.set_password(pw)


def ensure_unlocked(mw, ask=True):
    lock = getattr(getattr(mw, "password_manager", None), "lock", None)
    if lock is None or not lock.needs_unlock():
        return True
    return bool(ask) and unlock_dialog(mw, lock)


def show_save_popup(mw, pend, on_done):
    """'Save password?' as a small drop-down card under the toolbar (top right), not a separate window.
    on_done(choice) is called with 'save', 'never' or 'later'. Returns the card widget."""
    from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
    from PyQt6.QtCore import QPoint, QPropertyAnimation, QEasingCurve, QTimer
    t = getattr(mw, "_theme", None) or {}
    f = QFrame(mw); f.setObjectName("spsSavePop"); f.setFixedWidth(360)
    f.setStyleSheet("QFrame#spsSavePop{background:%s;border:1px solid %s;border-radius:14px;} QLabel{color:%s;background:transparent;border:none;}"
                    "QLineEdit{background:%s;color:%s;border:1px solid %s;border-radius:8px;padding:6px 10px;}"
                    "QPushButton{background:%s;color:white;border:none;border-radius:8px;padding:7px 14px;font-weight:600;}"
                    "QPushButton[flat=\"true\"]{background:transparent;color:%s;padding:7px 8px;}" % (
        t.get("bg_primary", "#fff"), t.get("border", "#dadce0"), t.get("text_primary", "#202124"), t.get("bg_secondary", "#f1f3f4"),
        t.get("text_primary", "#202124"), t.get("border", "#dadce0"), t.get("accent", "#1a73e8"), t.get("accent", "#1a73e8")))
    lay = QVBoxLayout(f); lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(8)
    update = pend.get("eid") is not None
    lay.addWidget(QLabel("<b>🔐 %s?</b>" % ("Update password" if update else "Save password")))
    lay.addWidget(QLabel("🌐 %s<br>👤 %s" % (pend["host"], pend["user"] or "(no username)")))
    pw = QLineEdit(pend["pw"]); pw.setEchoMode(QLineEdit.EchoMode.Password); pw.setReadOnly(True)
    eye = QPushButton("👁"); eye.setProperty("flat", True); eye.setFixedWidth(36)
    eye.clicked.connect(lambda: pw.setEchoMode(QLineEdit.EchoMode.Normal if pw.echoMode() == QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password))
    r1 = QHBoxLayout(); r1.addWidget(pw, 1); r1.addWidget(eye); lay.addLayout(r1)
    lay.addWidget(QLabel("Stored encrypted on this computer only."))
    r2 = QHBoxLayout()
    save = QPushButton("Update" if update else "Save"); later = QPushButton("Not now"); later.setProperty("flat", True)
    never = QPushButton("Never for this site"); never.setProperty("flat", True)
    r2.addWidget(save); r2.addWidget(later); r2.addWidget(never); lay.addLayout(r2)
    state = {"done": False}

    def finish(choice):
        if state["done"]:
            return
        state["done"] = True
        try:
            pw.clear()
            f.hide(); f.deleteLater()
        except Exception:
            pass
        on_done(choice)
    save.clicked.connect(lambda: finish("save")); later.clicked.connect(lambda: finish("later")); never.clicked.connect(lambda: finish("never"))
    f.adjustSize()
    tb = getattr(mw, "toolbar", None)
    y = tb.mapTo(mw, QPoint(0, tb.height())).y() if tb is not None else 60
    x = max(8, mw.width() - f.width() - 16)
    f.move(x, y - 16); f.show(); f.raise_()
    try:
        a = QPropertyAnimation(f, b"pos", f); a.setDuration(180); a.setStartValue(QPoint(x, y - 16)); a.setEndValue(QPoint(x, y + 2))
        a.setEasingCurve(QEasingCurve.Type.OutCubic); f._anim = a; a.start()
    except Exception:
        f.move(x, y + 2)
    QTimer.singleShot(45000, lambda: finish("later"))
    f._finish = finish; f._buttons = {"save": save, "later": later, "never": never}
    return f
