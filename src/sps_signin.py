"""Google sign-in notice.

Google refuses account sign-in inside every embedded browser (Qt, Electron, CEF ...). Instead of letting the user land on a
confusing "This browser or app may not be secure" page, SPS Browser catches the sign-in page BEFORE it loads and shows a
friendly choice: open it in the computer's default browser, or carry on without signing in.

is_google_signin(url_string) is plain Python (testable without Qt); show_signin_dialog() needs PyQt6.
"""
from urllib.parse import urlsplit

_HOSTS = ("accounts.google.com",)
_PATH_PREFIXES = ("/signin", "/v3/signin", "/servicelogin", "/accountchooser", "/o/oauth2", "/embedded/setup", "/gsi/")

TITLE = "Google sign-in"
MESSAGE = "Google blocks sign-in here. Open it in your default browser, or continue without signing in."
HINT = ("You don't need to sign in to watch YouTube. Most features (VPN, print, ad-block) "
        "work without a Google account.")
BTN_OPEN = "🌐  Open in default browser"
BTN_SKIP = "▶  Continue without signing in"
BTN_TRY = "Try here anyway"


def is_google_signin(url):
    """True for the Google account sign-in / account-chooser / OAuth pages (not for logout or cookie-check helpers)."""
    try:
        u = urlsplit(str(url))
    except ValueError:
        return False
    if u.scheme not in ("http", "https") or (u.hostname or "").lower() not in _HOSTS:
        return False
    path = (u.path or "/").lower()
    return any(path == p.rstrip("/") or path.startswith(p) for p in _PATH_PREFIXES)


def show_signin_dialog(parent, url, theme=None):
    """Modal choice. Returns "open", "skip" or "try"."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
    t = dict(theme or {})
    bg = t.get("bg_primary", "#ffffff"); fg = t.get("text_primary", "#202124")
    fg2 = t.get("text_secondary", "#5f6368"); acc = t.get("accent", "#1a73e8"); card = t.get("bg_secondary", "#f1f3f4")
    dlg = QDialog(parent)
    dlg.setWindowTitle(TITLE); dlg.setModal(True); dlg.setMinimumWidth(460)
    dlg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dlg.setStyleSheet(
        f"QDialog{{background:{bg};}} QLabel{{color:{fg};}}"
        f"QPushButton{{border-radius:10px;padding:11px 18px;font-size:14px;border:1px solid {fg2};background:{card};color:{fg};}}"
        f"QPushButton:hover{{border-color:{acc};}}"
        f"QPushButton#primary{{background:{acc};color:#fff;border:none;font-weight:600;}}"
        f"QPushButton#primary:hover{{background:{acc};opacity:.9;}}"
        f"QPushButton#link{{border:none;background:transparent;color:{fg2};text-decoration:underline;padding:4px;font-size:12px;}}")
    lay = QVBoxLayout(dlg); lay.setContentsMargins(26, 24, 26, 18); lay.setSpacing(12)
    icon = QLabel("🔐"); icon.setStyleSheet("font-size:38px;"); icon.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(icon)
    msg = QLabel(MESSAGE); msg.setWordWrap(True); msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
    msg.setStyleSheet("font-size:16px;font-weight:600;"); lay.addWidget(msg)
    hint = QLabel(HINT); hint.setWordWrap(True); hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint.setStyleSheet(f"font-size:13px;color:{fg2};padding:8px 10px;background:{card};border-radius:8px;"); lay.addWidget(hint)
    result = {"v": "skip"}
    def pick(v):
        result["v"] = v; dlg.accept()
    b1 = QPushButton(BTN_OPEN); b1.setObjectName("primary"); b1.setDefault(True); b1.clicked.connect(lambda: pick("open"))
    b2 = QPushButton(BTN_SKIP); b2.clicked.connect(lambda: pick("skip"))
    b3 = QPushButton(BTN_TRY); b3.setObjectName("link"); b3.setFlat(True); b3.clicked.connect(lambda: pick("try"))
    lay.addSpacing(4); lay.addWidget(b1); lay.addWidget(b2)
    row = QHBoxLayout(); row.addStretch(); row.addWidget(b3); row.addStretch(); lay.addLayout(row)
    dlg.exec()                                   # Esc / X = "skip" (the default in result)
    return result["v"]
