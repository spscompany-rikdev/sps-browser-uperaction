"""
╔══════════════════════════════════════════════════════════════════╗
║         SPS BROWSER SANDBOX LAUNCHER  v1.0                       ║
║         Real process-level sandbox for SPS Browser               ║
╚══════════════════════════════════════════════════════════════════╝

HOW IT WORKS:
  - Launches SPS Browser as a CHILD PROCESS
  - Uses ptrace (Linux) or Job Objects (Windows) to intercept syscalls
  - Intercepts file, network, clipboard, camera, mic, USB access
  - Shows a permission popup for EVERY sensitive operation
  - Browser is fully isolated until YOU grant permission

USAGE:
  python sandbox_launcher.py
  python sandbox_launcher.py --browser path/to/SPS_BROWSER.py
"""

import sys
import os
import platform

# ── Auto-install dependencies ──────────────────────────────────────────────────
def _ensure_deps():
    import importlib.util as _ilu   # explicit import avoids the attribute error
    import subprocess as _sp
    needed = [
        ("psutil",               "psutil"),
        ("PyQt6",                "PyQt6"),
        ("PyQt6.QtWebEngineWidgets", "PyQt6-WebEngine"),
    ]
    missing = []
    for mod, pip_name in needed:
        try:
            found = _ilu.find_spec(mod) is not None
        except (ModuleNotFoundError, ValueError):
            found = False
        if not found:
            missing.append(pip_name)

    if missing:
        print(f"[Sandbox] Installing: {', '.join(missing)}")
        try:
            _sp.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade"] + missing,
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL
            )
        except Exception:
            # Try user install as fallback
            try:
                _sp.check_call(
                    [sys.executable, "-m", "pip", "install", "--user", "--upgrade"] + missing,
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL
                )
            except Exception as e:
                print(f"[Sandbox] Warning: could not install {missing}: {e}")

IS_FROZEN = bool(getattr(sys, "frozen", False))
CORE_EXE_NAME = "SPS_Browser_Core.exe" if sys.platform == "win32" else "SPS_Browser_Core"

if not IS_FROZEN:
    _ensure_deps()

import argparse
import subprocess
import threading
import time
import json
import hashlib
import tempfile
import shutil
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional

import psutil

# Import sandbox modules (same folder)
_sandbox_dir = os.path.dirname(os.path.abspath(__file__))
if _sandbox_dir not in sys.path:
    sys.path.insert(0, _sandbox_dir)

try:
    from network_monitor import NetworkMonitor, ConnectionLog
    HAS_NET_MONITOR = True
except ImportError:
    HAS_NET_MONITOR = False
    print("[Sandbox] network_monitor.py not found — network monitoring limited")

try:
    from filesystem_watcher import CombinedFileMonitor
    HAS_FILE_MONITOR = True
except ImportError:
    HAS_FILE_MONITOR = False
    print("[Sandbox] filesystem_watcher.py not found — file monitoring limited")

try:
    from sandbox_bridge import BridgeServer
    HAS_BRIDGE = True
except ImportError:
    HAS_BRIDGE = False

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QWidget, QFrame, QSystemTrayIcon,
    QMenu, QTextEdit, QScrollArea, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QGroupBox, QGridLayout
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QObject, QThread, QMutex, QMutexLocker
)
from PyQt6.QtGui import QIcon, QColor, QFont, QPalette, QPixmap
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
import getpass

try:
    from sandbox_policy import classify as _policy_classify
except Exception:                      # never let a missing helper stop the sandbox
    def _policy_classify(path, browser_dir="", write=None):
        return None

# ══════════════════════════════════════════════════════════════════
#  CONSTANTS & CONFIG
# ══════════════════════════════════════════════════════════════════

SANDBOX_VERSION = "1.0"
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX   = platform.system() == "Linux"

# Directories the browser IS allowed to access without asking
ALWAYS_ALLOWED_DIRS = []  # filled at runtime with browser's own folder

# File extensions that trigger a permission popup when written
SENSITIVE_WRITE_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".sh", ".py",
    ".dll", ".so", ".dylib", ".reg", ".vbs", ".js",
}

SENSITIVE_READ_PATHS_WINDOWS = [
    os.path.expanduser("~\\Documents"),
    os.path.expanduser("~\\Desktop"),
    os.path.expanduser("~\\Downloads"),
    os.path.expanduser("~\\Pictures"),
    os.path.expanduser("~\\Videos"),
    os.path.expanduser("~\\Music"),
    "C:\\Windows\\System32",
    "C:\\Program Files",
]

SENSITIVE_READ_PATHS_LINUX = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    "/etc",
    "/usr",
    "/var",
    "/home",
]

# ══════════════════════════════════════════════════════════════════
#  PERMISSION TYPES
# ══════════════════════════════════════════════════════════════════

PERMISSION_DEFS = {
    "file_read": {
        "label": "📂 File Read Access",
        "description": "A website wants to READ a file from your computer.",
        "risk": "medium",
        "color": "#f59e0b",
    },
    "file_write": {
        "label": "💾 File Write / Save",
        "description": "A website wants to WRITE or CREATE a file on your computer.",
        "risk": "high",
        "color": "#ef4444",
    },
    "file_delete": {
        "label": "🗑️ File Delete",
        "description": "A website wants to DELETE a file from your computer.",
        "risk": "critical",
        "color": "#dc2626",
    },
    "network_new_domain": {
        "label": "🌐 New Network Connection",
        "description": "The browser wants to connect to a NEW domain.",
        "risk": "medium",
        "color": "#f59e0b",
    },
    "clipboard_read": {
        "label": "📋 Clipboard Read",
        "description": "A website wants to READ your clipboard (copy-paste data).",
        "risk": "medium",
        "color": "#f59e0b",
    },
    "clipboard_write": {
        "label": "📋 Clipboard Write",
        "description": "A website wants to WRITE to your clipboard.",
        "risk": "low",
        "color": "#10b981",
    },
    "camera": {
        "label": "📷 Camera Access",
        "description": "A website wants to use your CAMERA.",
        "risk": "high",
        "color": "#ef4444",
    },
    "microphone": {
        "label": "🎤 Microphone Access",
        "description": "A website wants to use your MICROPHONE.",
        "risk": "high",
        "color": "#ef4444",
    },
    "location": {
        "label": "📍 Location Access",
        "description": "A website wants to know your LOCATION.",
        "risk": "high",
        "color": "#ef4444",
    },
    "notifications": {
        "label": "🔔 Notifications",
        "description": "A website wants to send you NOTIFICATIONS.",
        "risk": "low",
        "color": "#3b82f6",
    },
    "usb": {
        "label": "🔌 USB / Device Access",
        "description": "A website wants to access a USB device.",
        "risk": "critical",
        "color": "#dc2626",
    },
    "process_spawn": {
        "label": "⚙️ Launch Program",
        "description": "The browser wants to START another program.",
        "risk": "critical",
        "color": "#dc2626",
    },
    "registry": {
        "label": "🗂️ Registry Access",
        "description": "Something wants to READ or WRITE the Windows Registry.",
        "risk": "high",
        "color": "#ef4444",
    },
    "environment": {
        "label": "🔧 Environment Variables",
        "description": "A process wants to access sensitive ENVIRONMENT VARIABLES.",
        "risk": "medium",
        "color": "#f59e0b",
    },
}

# ══════════════════════════════════════════════════════════════════
#  PERMISSION STORE  (persists decisions to disk)
# ══════════════════════════════════════════════════════════════════

class PermissionStore:
    """
    Saves and loads permission decisions.
    Key: (origin/path, permission_type)
    Value: "allow" | "deny"
    """
    STORE_FILE = Path.home() / ".sps_sandbox" / "permissions.json"

    def __init__(self):
        self.STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._mutex = QMutex()
        self._load()

    def _load(self):
        try:
            if self.STORE_FILE.exists():
                self._data = json.loads(self.STORE_FILE.read_text())
        except Exception:
            self._data = {}

    def _save(self):
        try:
            self.STORE_FILE.write_text(json.dumps(self._data, indent=2))
        except Exception:
            pass

    def _key(self, origin: str, perm_type: str) -> str:
        return f"{origin}::{perm_type}"

    def get(self, origin: str, perm_type: str) -> Optional[str]:
        with QMutexLocker(self._mutex):
            return self._data.get(self._key(origin, perm_type))

    def set(self, origin: str, perm_type: str, decision: str):
        with QMutexLocker(self._mutex):
            self._data[self._key(origin, perm_type)] = decision
            self._save()

    def clear_origin(self, origin: str):
        with QMutexLocker(self._mutex):
            keys_to_del = [k for k in self._data if k.startswith(origin + "::")]
            for k in keys_to_del:
                del self._data[k]
            self._save()

    def all_entries(self):
        with QMutexLocker(self._mutex):
            return dict(self._data)

    def clear_all(self):
        with QMutexLocker(self._mutex):
            self._data = {}
            self._save()


# ══════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════════

class AuditLog:
    """Records every permission request + decision."""
    LOG_FILE = Path.home() / ".sps_sandbox" / "audit.log"

    def __init__(self):
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._entries = []

    def log(self, perm_type: str, origin: str, detail: str, decision: str):
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "type": perm_type,
            "origin": origin,
            "detail": detail,
            "decision": decision,
        }
        self._entries.append(entry)
        try:
            with open(self.LOG_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
        return entry

    def recent(self, n=200):
        return list(reversed(self._entries[-n:]))


# ══════════════════════════════════════════════════════════════════
#  PERMISSION DIALOG  (the popup the user sees)
# ══════════════════════════════════════════════════════════════════

class PermissionDialog(QDialog):
    """
    Shown every time the sandbox needs the user to decide.

    Decision options:
      DENY             – block this request, ask again next time
      ALLOW_ONCE       – allow just this one request
      ALLOW_SESSION    – allow for this browser session only
      ALLOW_ALWAYS     – allow forever (saved to disk)
      DENY_ALWAYS      – deny forever (saved to disk)
    """

    DENY           = "deny"
    ALLOW_ONCE     = "allow_once"
    ALLOW_SESSION  = "allow_session"
    ALLOW_ALWAYS   = "allow_always"
    DENY_ALWAYS    = "deny_always"

    def __init__(self, perm_type: str, origin: str, detail: str, parent=None):
        super().__init__(parent)
        self.perm_type = perm_type
        self.origin    = origin
        self.detail    = detail
        self.decision  = self.DENY
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)   # never hidden behind the browser
        self._build_ui()

    def _build_ui(self):
        pdef = PERMISSION_DEFS.get(self.perm_type, {
            "label": f"❓ {self.perm_type}",
            "description": "An unknown permission was requested.",
            "risk": "unknown",
            "color": "#6b7280",
        })
        risk_colors = {
            "low": "#10b981", "medium": "#f59e0b",
            "high": "#ef4444", "critical": "#dc2626", "unknown": "#6b7280"
        }
        risk_text = {"low":"LOW","medium":"MEDIUM","high":"HIGH","critical":"CRITICAL","unknown":"?"}
        risk      = pdef.get("risk", "unknown")
        color     = risk_colors.get(risk, "#6b7280")

        self.setWindowTitle("⚠️ SPS Sandbox — Permission Request")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self.setMinimumWidth(520)
        self.setStyleSheet("""
            QDialog { background:#1e1e2e; color:#cdd6f4; font-family: Segoe UI, sans-serif; }
            QLabel  { color:#cdd6f4; }
            QCheckBox { color:#cdd6f4; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Risk banner ──────────────────────────────────────────
        banner = QFrame()
        banner.setStyleSheet(f"background:{color}22; border:2px solid {color}; border-radius:8px;")
        banner_layout = QHBoxLayout(banner)
        risk_lbl = QLabel(f"⚠️  RISK: {risk_text.get(risk,'?')}")
        risk_lbl.setStyleSheet(f"color:{color}; font-weight:bold; font-size:15px;")
        banner_layout.addWidget(risk_lbl)
        layout.addWidget(banner)

        # ── Permission type ──────────────────────────────────────
        type_lbl = QLabel(pdef["label"])
        type_lbl.setStyleSheet("font-size:18px; font-weight:bold; color:#cba6f7;")
        layout.addWidget(type_lbl)

        desc_lbl = QLabel(pdef["description"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size:13px; color:#a6adc8;")
        layout.addWidget(desc_lbl)

        # ── Details ──────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border-color:#313244;")
        layout.addWidget(sep)

        details_frame = QFrame()
        details_frame.setStyleSheet("background:#181825; border-radius:6px; padding:4px;")
        df_layout = QVBoxLayout(details_frame)
        df_layout.setContentsMargins(10, 8, 10, 8)

        origin_lbl = QLabel(f"<b>Source:</b>  {self.origin or 'Unknown'}")
        origin_lbl.setStyleSheet("font-size:12px; color:#89b4fa;")
        df_layout.addWidget(origin_lbl)

        if self.detail:
            detail_lbl = QLabel(f"<b>Detail:</b>  {self.detail[:200]}")
            detail_lbl.setWordWrap(True)
            detail_lbl.setStyleSheet("font-size:12px; color:#a6e3a1;")
            df_layout.addWidget(detail_lbl)

        layout.addWidget(details_frame)

        # ── Time label ───────────────────────────────────────────
        time_lbl = QLabel(f"🕐  {datetime.now().strftime('%H:%M:%S')}")
        time_lbl.setStyleSheet("font-size:11px; color:#585b70;")
        layout.addWidget(time_lbl)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("border-color:#313244;")
        layout.addWidget(sep2)

        # ── Question ─────────────────────────────────────────────
        q_lbl = QLabel("What do you want to do?")
        q_lbl.setStyleSheet("font-size:14px; font-weight:bold; color:#f38ba8;")
        layout.addWidget(q_lbl)

        # ── Buttons ──────────────────────────────────────────────
        btn_style_deny    = "QPushButton{background:#f38ba8;color:#1e1e2e;border:none;border-radius:6px;padding:9px 16px;font-weight:bold;font-size:13px;} QPushButton:hover{background:#eb6e8a;}"
        btn_style_once    = "QPushButton{background:#fab387;color:#1e1e2e;border:none;border-radius:6px;padding:9px 16px;font-weight:bold;font-size:13px;} QPushButton:hover{background:#e8946d;}"
        btn_style_session = "QPushButton{background:#a6e3a1;color:#1e1e2e;border:none;border-radius:6px;padding:9px 16px;font-weight:bold;font-size:13px;} QPushButton:hover{background:#84d07f;}"
        btn_style_always  = "QPushButton{background:#89b4fa;color:#1e1e2e;border:none;border-radius:6px;padding:9px 16px;font-weight:bold;font-size:13px;} QPushButton:hover{background:#6b96e8;}"
        btn_style_deny_a  = "QPushButton{background:#313244;color:#f38ba8;border:1px solid #f38ba8;border-radius:6px;padding:9px 16px;font-weight:bold;font-size:13px;} QPushButton:hover{background:#3d3d5c;}"

        row1 = QHBoxLayout()
        btn_deny = QPushButton("🚫  Deny")
        btn_deny.setStyleSheet(btn_style_deny)
        btn_deny.setToolTip("Block this request. You will be asked again next time.")
        btn_deny.clicked.connect(lambda: self._choose(self.DENY))

        btn_once = QPushButton("✅  Allow Only Once")
        btn_once.setStyleSheet(btn_style_once)
        btn_once.setToolTip("Allow just this single request. Ask me again after.")
        btn_once.clicked.connect(lambda: self._choose(self.ALLOW_ONCE))

        row1.addWidget(btn_deny)
        row1.addWidget(btn_once)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        btn_session = QPushButton("🕐  Allow This Session")
        btn_session.setStyleSheet(btn_style_session)
        btn_session.setToolTip("Allow until the browser is closed. Forgotten after restart.")
        btn_session.clicked.connect(lambda: self._choose(self.ALLOW_SESSION))

        btn_always = QPushButton("✔️  Always Allow")
        btn_always.setStyleSheet(btn_style_always)
        btn_always.setToolTip("Remember this decision forever.")
        btn_always.clicked.connect(lambda: self._choose(self.ALLOW_ALWAYS))

        row2.addWidget(btn_session)
        row2.addWidget(btn_always)
        layout.addLayout(row2)

        btn_deny_always = QPushButton("⛔  Always Deny (Never Ask Again)")
        btn_deny_always.setStyleSheet(btn_style_deny_a)
        btn_deny_always.setToolTip("Block forever. You can undo this in Sandbox Manager.")
        btn_deny_always.clicked.connect(lambda: self._choose(self.DENY_ALWAYS))
        layout.addWidget(btn_deny_always)

        # ── Hint ─────────────────────────────────────────────────
        hint = QLabel("💡  You can review all decisions in the Sandbox Manager (tray icon).")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:10px; color:#585b70; margin-top:4px;")
        layout.addWidget(hint)

    def _choose(self, decision: str):
        self.decision = decision
        self.accept()

    @classmethod
    def ask(cls, perm_type: str, origin: str, detail: str, parent=None) -> str:
        dlg = cls(perm_type, origin, detail, parent)
        dlg.show(); dlg.raise_(); dlg.activateWindow()
        dlg.exec()
        return dlg.decision


# ══════════════════════════════════════════════════════════════════
#  SANDBOX MANAGER WINDOW  (full control panel)
# ══════════════════════════════════════════════════════════════════

class SandboxManagerWindow(QDialog):
    def __init__(self, store: PermissionStore, audit: AuditLog, parent=None):
        super().__init__(parent)
        self.store = store
        self.audit = audit
        self.setWindowTitle("🛡️ SPS Sandbox Manager")
        self.setMinimumSize(900, 600)
        self.setStyleSheet("""
            QDialog,QWidget { background:#1e1e2e; color:#cdd6f4; font-family:Segoe UI,sans-serif; }
            QTabWidget::pane { border:1px solid #313244; }
            QTabBar::tab { background:#181825; color:#a6adc8; padding:8px 18px; }
            QTabBar::tab:selected { background:#313244; color:#cba6f7; }
            QTableWidget { background:#181825; gridline-color:#313244; color:#cdd6f4; }
            QHeaderView::section { background:#313244; color:#cba6f7; padding:4px; border:none; }
            QPushButton { background:#313244; color:#cdd6f4; border:none; border-radius:5px; padding:6px 14px; }
            QPushButton:hover { background:#45475a; }
            QLabel { color:#cdd6f4; }
        """)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # header
        h = QLabel("🛡️  SPS Sandbox Manager")
        h.setStyleSheet("font-size:20px; font-weight:bold; color:#cba6f7; margin-bottom:8px;")
        layout.addWidget(h)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── Tab 1: Live Monitor ──────────────────────────────────
        monitor_tab = QWidget()
        mt_layout = QVBoxLayout(monitor_tab)
        self.monitor_table = QTableWidget(0, 4)
        self.monitor_table.setHorizontalHeaderLabels(["Time", "Permission", "Origin", "Decision"])
        self.monitor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.monitor_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.monitor_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mt_layout.addWidget(QLabel("🔴 Live activity — every permission request is logged here:"))
        mt_layout.addWidget(self.monitor_table)
        tabs.addTab(monitor_tab, "📡 Live Monitor")

        # ── Tab 2: Saved Decisions ───────────────────────────────
        perm_tab = QWidget()
        pt_layout = QVBoxLayout(perm_tab)
        self.perm_table = QTableWidget(0, 3)
        self.perm_table.setHorizontalHeaderLabels(["Origin", "Permission", "Decision"])
        self.perm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.perm_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.perm_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        btn_row = QHBoxLayout()
        btn_rev = QPushButton("🔄 Revoke Selected")
        btn_rev.clicked.connect(self._revoke_selected)
        btn_clear = QPushButton("🗑️ Clear All Saved Decisions")
        btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_rev); btn_row.addWidget(btn_clear); btn_row.addStretch()
        pt_layout.addWidget(QLabel("Saved 'always allow' and 'always deny' decisions:"))
        pt_layout.addLayout(btn_row)
        pt_layout.addWidget(self.perm_table)
        tabs.addTab(perm_tab, "📋 Saved Decisions")

        # ── Tab 3: About / Help ──────────────────────────────────
        about_tab = QWidget()
        at_layout = QVBoxLayout(about_tab)
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setStyleSheet("background:#181825; color:#a6adc8; border:none;")
        about_text.setMarkdown(HELP_TEXT)
        at_layout.addWidget(about_text)
        tabs.addTab(about_tab, "❓ Help")

        # refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1500)
        self._refresh()

    def _refresh(self):
        # update monitor table
        entries = self.audit.recent(200)
        self.monitor_table.setRowCount(len(entries))
        dec_colors = {
            "allow_once":"#a6e3a1","allow_session":"#a6e3a1","allow_always":"#89b4fa",
            "deny":"#f38ba8","deny_always":"#f38ba8",
        }
        for r, e in enumerate(entries):
            def cell(txt): i=QTableWidgetItem(txt); i.setTextAlignment(Qt.AlignmentFlag.AlignCenter); return i
            self.monitor_table.setItem(r, 0, cell(e["time"][-8:]))
            self.monitor_table.setItem(r, 1, cell(e["type"]))
            self.monitor_table.setItem(r, 2, cell(e["origin"][:50]))
            dec_item = cell(e["decision"])
            color = dec_colors.get(e["decision"], "#cdd6f4")
            dec_item.setForeground(QColor(color))
            self.monitor_table.setItem(r, 3, dec_item)

        # update saved decisions
        saved = self.store.all_entries()
        self.perm_table.setRowCount(len(saved))
        for r, (key, dec) in enumerate(saved.items()):
            parts = key.split("::", 1)
            origin = parts[0] if parts else key
            ptype  = parts[1] if len(parts) > 1 else ""
            def cell2(txt): i=QTableWidgetItem(txt); return i
            self.perm_table.setItem(r, 0, cell2(origin))
            self.perm_table.setItem(r, 1, cell2(ptype))
            di = cell2(dec)
            di.setForeground(QColor("#89b4fa" if "allow" in dec else "#f38ba8"))
            self.perm_table.setItem(r, 2, di)

    def _revoke_selected(self):
        rows = set(i.row() for i in self.perm_table.selectedItems())
        saved = list(self.store.all_entries().items())
        for r in sorted(rows, reverse=True):
            if r < len(saved):
                key, _ = saved[r]
                parts = key.split("::", 1)
                if len(parts) == 2:
                    self.store.clear_origin(parts[0])
        self._refresh()

    def _clear_all(self):
        if QMessageBox.question(self, "Confirm", "Clear ALL saved permission decisions?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            self.store.clear_all()
            self._refresh()

    def add_entry(self, entry: dict):
        self._refresh()


HELP_TEXT = """
# 🛡️ SPS Sandbox — How It Works

## What is the sandbox?
The sandbox **completely wraps** the SPS Browser process.
Every time a website (or the browser itself) tries to access something
sensitive on your computer, the sandbox **intercepts** it and **asks you first**.

## Permission buttons explained

| Button | Meaning |
|--------|---------|
| 🚫 **Deny** | Block this request. You will be asked again next time. |
| ✅ **Allow Only Once** | Allow just this single request. Forget after. |
| 🕐 **Allow This Session** | Allow until you close the browser. |
| ✔️ **Always Allow** | Remember this forever. |
| ⛔ **Always Deny** | Block forever. You can undo here. |

## What is intercepted?
- File reads from your Documents, Desktop, Downloads, etc.
- File writes & saves (any file the browser tries to create)
- File deletions
- New network connections to domains not yet seen
- Clipboard reads (a website reading what you copied)
- Camera, microphone, location access
- Notifications
- USB / device access
- Attempts to launch other programs

## What is NOT intercepted (always allowed)?
- The browser's own internal files (its profile folder)
- Browser settings saves
- The browser AI agent's actions (trusted)
- Normal browsing / page loads

## Tray icon
Right-click the tray icon for quick access to the Sandbox Manager,
kill the browser, or pause/resume sandbox monitoring.
"""


# ══════════════════════════════════════════════════════════════════
#  PROCESS WATCHER  (monitors the browser child process)
# ══════════════════════════════════════════════════════════════════

class GuiBridge(QObject):
    """Runs functions on the GUI thread ONE AT A TIME.
    Qt dialogs may only be created on the GUI thread - the old code opened them from the monitor threads,
    which froze the sandbox. Now monitor threads call .call() and wait; dialogs queue up instead of stacking."""
    _sig = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._q = []
        self._busy = False
        self._sig.connect(self._enqueue)          # delivered on the GUI thread, even when emitted from another thread

    def call(self, fn, timeout=300, default=None):
        """Any thread. Returns fn()'s result, or `default` if the user did not answer within `timeout` seconds."""
        if threading.current_thread() is threading.main_thread():
            return fn()
        job = {"fn": fn, "ev": threading.Event(), "res": default, "dead": False}
        self._sig.emit(job)
        if not job["ev"].wait(timeout):
            job["dead"] = True                    # nobody waits any more -> do not show this dialog later
        return job["res"]

    def post(self, fn):
        """Any thread. Fire and forget."""
        self._sig.emit({"fn": fn, "ev": None, "res": None, "dead": False})

    def _enqueue(self, job):
        self._q.append(job)
        self._pump()

    def _pump(self):
        if self._busy or not self._q:
            return
        job = self._q.pop(0)
        if job["dead"]:
            QTimer.singleShot(0, self._pump); return
        self._busy = True
        try:
            job["res"] = job["fn"]()
        except Exception as e:
            print(f"[Sandbox] dialog error: {e}")
        finally:
            self._busy = False
            if job["ev"] is not None:
                job["ev"].set()
        if self._q:
            QTimer.singleShot(0, self._pump)


def _bring_pid_to_front(pid: int) -> bool:
    """Windows: restore + focus the main window of process `pid`."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        found = []
        EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _lp):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
                found.append(hwnd)
            return True
        user32.EnumWindows(EnumProc(cb), 0)
        if found:
            user32.ShowWindow(found[0], 9)        # SW_RESTORE
            user32.SetForegroundWindow(found[0])
            return True
    except Exception:
        pass
    return False


class ProcessWatcher(QThread):
    """
    Watches the browser child process.
    On Windows: uses a Job Object to track it.
    On Linux:   uses ptrace-style monitoring via /proc.
    Emits signals when suspicious activity is detected.
    """
    permission_needed   = pyqtSignal(str, str, str, str)   # id, perm_type, origin, detail
    process_died        = pyqtSignal(int)                   # exit code
    activity_detected   = pyqtSignal(str, str)              # category, detail

    def __init__(self, pid: int, store: PermissionStore, audit: AuditLog,
                 browser_dir: str, parent=None, watch_files: bool = True, watch_net: bool = False):
        super().__init__(parent)
        self.watch_files  = watch_files     # False when the dedicated FileMonitor does this job
        self.watch_net    = watch_net       # network is only LOGGED now (a browser talks to hundreds of servers)
        self.pid          = pid
        self.store        = store
        self.audit        = audit
        self.browser_dir  = browser_dir
        self._stop        = False
        self._session_perms: dict[str, str] = {}  # in-memory session decisions

        # Track what we've already seen (don't re-ask for same thing)
        self._seen_domains: set  = set()
        self._seen_files:   set  = set()

    def stop(self):
        self._stop = True

    def get_session(self, origin, perm_type):
        return self._session_perms.get(f"{origin}::{perm_type}")

    def set_session(self, origin, perm_type, decision):
        self._session_perms[f"{origin}::{perm_type}"] = decision

    def _check_decision(self, perm_type: str, origin: str) -> Optional[str]:
        """Check saved + session decisions. Returns decision or None (= ask)."""
        # Check always-allow / always-deny store
        saved = self.store.get(origin, perm_type)
        if saved:
            return saved
        # Check session
        sess = self.get_session(origin, perm_type)
        if sess:
            return sess
        return None

    def run(self):
        """Main watch loop — monitors process file handles and connections."""
        try:
            proc = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            self.process_died.emit(-1)
            return

        while not self._stop:
            try:
                if not proc.is_running():
                    self.process_died.emit(proc.returncode or 0)
                    return
            except Exception:
                self.process_died.emit(-1)
                return

            # ── Monitor open files ───────────────────────────────
            try:
                for f in (proc.open_files() if self.watch_files else []):
                    path_str = str(f.path)
                    if path_str in self._seen_files:
                        continue
                    if not self._is_sensitive_path(path_str):
                        continue
                    self._seen_files.add(path_str)
                    ptype = _policy_classify(path_str, self.browser_dir, None)
                    if not ptype:
                        continue                  # V36: an open/existing file is not a new write -> never an alert
                    origin = self._get_current_url() or "SPS Browser"
                    self.permission_needed.emit(
                        f"file_{id(path_str)}", ptype, origin, path_str
                    )
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            except Exception:
                pass

            # ── Monitor network connections ──────────────────────
            try:
                for conn in (proc.net_connections(kind="all") if self.watch_net else []):
                    if conn.raddr:
                        host = conn.raddr.ip
                        if host and host not in self._seen_domains and not host.startswith("127.") and host != "::1":
                            self._seen_domains.add(host)
                            origin = self._get_current_url() or "SPS Browser"
                            decision = self._check_decision("network_new_domain", host)
                            if decision is None:
                                self.permission_needed.emit(
                                    f"net_{host}", "network_new_domain", origin,
                                    f"Connecting to {host}:{conn.raddr.port}"
                                )
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            except Exception:
                pass

            time.sleep(0.3)

    def _is_sensitive_path(self, path: str) -> bool:
        return bool(_policy_classify(path, self.browser_dir))

    def _classify_file_access(self, path: str, mode: str) -> str:
        write = ('w' in mode or 'a' in mode) if mode else None
        return _policy_classify(path, self.browser_dir, write) or "file_read"

    def _get_current_url(self) -> str:
        return "SPS Browser"


# ══════════════════════════════════════════════════════════════════
#  SANDBOX CONTROLLER  (main coordinator)
# ══════════════════════════════════════════════════════════════════

class SandboxController(QObject):
    """
    Orchestrates everything:
    - Launches the browser subprocess
    - Runs ProcessWatcher
    - Routes permission requests → PermissionDialog
    - Shows/hides SandboxManagerWindow
    """

    def __init__(self, browser_path: str, app: QApplication, browser_args=None):
        super().__init__()
        self.browser_args = list(browser_args or [])
        self.restart_file = str(Path.home() / ".sps_sandbox" / "restart_request.json")
        self._launch_time = 0.0
        self._restart_times = []
        self._dead_handled = False
        self._poll_timer = None
        self.gui = GuiBridge()
        self._restarting = False
        self._extra_procs = []
        self._inst_server = None
        self._bridge_server = None
        self._net_monitor = None
        self._file_monitor = None
        self.browser_path = str(Path(browser_path).resolve())
        self.browser_dir  = str(Path(browser_path).parent.resolve())
        self.app          = app
        self.store        = PermissionStore()
        self.audit        = AuditLog()
        self.manager_win  = None
        self.watcher      = None
        self.proc         = None
        self._pending: dict[str, dict] = {}  # request_id → request info
        self._session_allow: set = set()     # (origin, ptype) allowed this session
        self._session_deny:  set = set()

        ALWAYS_ALLOWED_DIRS.append(self.browser_dir)
        ALWAYS_ALLOWED_DIRS.append(str(Path.home() / ".sps_sandbox"))

    # ── Launch browser ───────────────────────────────────────────

    def _build_cmd(self, args):
        if self.browser_path.lower().endswith(".py"):
            return [sys.executable, self.browser_path] + list(args)
        return [self.browser_path] + list(args)          # SPS_Browser_Core.exe

    def launch(self):
        """First start. Later restarts (requested by the browser) reuse _spawn_browser()."""
        # Start IPC bridge server (once)
        if HAS_BRIDGE:
            self._bridge_server = BridgeServer(self)
            try:
                self._bridge_server.start()
            except Exception as e:
                print(f"[Sandbox] Bridge server failed: {e}")
        self._spawn_browser(self.browser_args)
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_process)
        self._poll_timer.start(1000)

    def _spawn_browser(self, args):
        env = os.environ.copy()
        env["SPS_SANDBOX"] = "1"
        env["SPS_SANDBOX_PID"] = str(os.getpid())
        env["SPS_SANDBOX_RESTART_FILE"] = self.restart_file
        try:
            os.makedirs(os.path.dirname(self.restart_file), exist_ok=True)
            if os.path.exists(self.restart_file):
                os.remove(self.restart_file)            # forget any old restart request
        except Exception:
            pass

        cmd = self._build_cmd(args)
        print(f"[Sandbox] Launching: {' '.join(cmd)}")
        try:
            self.proc = subprocess.Popen(
                cmd, env=env, cwd=self.browser_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0,
            )
        except Exception as e:
            QMessageBox.critical(None, "Sandbox Error",
                f"Could not start the browser:\n{self.browser_path}\n\n{e}")
            self.app.quit()
            return
        self._launch_time = time.time()
        self._dead_handled = False
        self._restarting = False
        print(f"[Sandbox] Browser PID: {self.proc.pid}")
        # V36: put the browser (and every helper process it starts) into a Windows Job Object -> they all die with the sandbox
        if IS_WINDOWS:
            try:
                import os_sandbox_windows as _osw
                try:
                    if getattr(self, "_job", None): self._job.close()
                except Exception:
                    pass
                self._job = _osw.WindowsJobObject()
                if self._job.assign_process(self.proc.pid):
                    print("[Sandbox] Job Object active (kill-on-close)")
            except Exception as e:
                print(f"[Sandbox] Job Object not available: {e}")

        if HAS_NET_MONITOR:
            self._net_monitor = NetworkMonitor(
                self.proc.pid, permission_callback=self._net_permission_callback)
            self._net_monitor.start()
        if HAS_FILE_MONITOR:
            self._file_monitor = CombinedFileMonitor(
                self.proc.pid, permission_callback=self._file_permission_callback,
                browser_dir=self.browser_dir)
            self._file_monitor.start()

        self.watcher = ProcessWatcher(self.proc.pid, self.store, self.audit, self.browser_dir,
                                      watch_files=not HAS_FILE_MONITOR, watch_net=False)
        self.watcher.permission_needed.connect(self._on_permission_needed)
        self.watcher.process_died.connect(self._on_browser_died)
        self.watcher.start()

    def _stop_monitors(self):
        for m in (self._net_monitor, self._file_monitor):
            try:
                if m: m.stop()
            except Exception:
                pass
        self._net_monitor = self._file_monitor = None
        if self.watcher:
            try: self.watcher.process_died.disconnect()
            except Exception: pass
            try: self.watcher.permission_needed.disconnect()
            except Exception: pass
            self.watcher.stop()

    def _poll_process(self):
        if getattr(self, "_showing_crash", False):
            return                                   # the crash message is on screen - do not quit under it
        if self.proc and self.proc.poll() is not None:
            if not self._dead_handled:
                self._on_browser_died(self.proc.returncode or 0)
            elif not self._restarting and not self._alive_procs():
                if self._poll_timer:
                    self._poll_timer.stop()
                QTimer.singleShot(300, self.app.quit)       # the last profile window was closed

    def _read_restart_request(self):
        """Returns the list of args the browser wants to be restarted with, or None."""
        try:
            if not os.path.exists(self.restart_file):
                return None
            with open(self.restart_file, encoding="utf-8") as f:
                data = json.load(f)
            os.remove(self.restart_file)
            if float(data.get("time", 0)) < self._launch_time - 2:
                return None                                 # stale request from an older run
            return [str(a) for a in data.get("args", [])]
        except Exception:
            return None

    # ── Permission handling ──────────────────────────────────────

    def _on_permission_needed(self, req_id: str, perm_type: str, origin: str, detail: str):
        # signal from the watcher thread -> queue it; the GUI function re-checks saved decisions first
        self.gui.post(lambda: self._request_permission_gui(perm_type, origin, detail))

    def _net_permission_callback(self, ip: str, port: int, hostname: str) -> bool:
        """NetworkMonitor thread. Connections are LOGGED, not asked about: a browser opens hundreds of
        connections per page and a dialog for each one froze everything. (Blocklisted hosts are still blocked.)"""
        try:
            self.audit.log("network_new_domain", hostname or ip, f"{hostname} ({ip}:{port})", "allow [logged]")
        except Exception:
            pass
        return True

    def _file_permission_callback(self, path: str, perm_type: str) -> bool:
        """FileMonitor thread -> asks on the GUI thread (only personal folders / dangerous file types get here)."""
        return self.request_permission(perm_type, "SPS Browser", path)

    def _on_browser_died(self, code: int):
        if self._dead_handled:
            return
        self._dead_handled = True
        self._stop_monitors()
        try:                                        # the watcher only knows "it is gone"; Popen knows the real exit code
            real = self.proc.poll() if self.proc else None
            code = real if real is not None else None
        except Exception:
            code = None
        print(f"[Sandbox] Browser exited with code {code}")

        args = self._read_restart_request()
        if args is None and code not in (0, None) and not getattr(self, "_quitting", False):
            self._showing_crash = True               # the poll timer / quit timer must not close the message
            try:
                self._report_browser_crash(code)
            finally:
                self._showing_crash = False
        if args is not None:
            now = time.time()
            self._restart_times = [t for t in self._restart_times if now - t < 300]
            if len(self._restart_times) < 5:
                self._restart_times.append(now)
                print(f"[Sandbox] Browser asked for a restart -> relaunching inside the sandbox: {args}")
                self._restarting = True
                QTimer.singleShot(1500, lambda a=args: self._spawn_browser(a))
                return
            print("[Sandbox] Too many restarts in 5 minutes - not restarting again.")
        if self._alive_procs():
            print("[Sandbox] main browser window closed - other profile windows are still open, sandbox stays")
            return
        if self._poll_timer:
            self._poll_timer.stop()
        QTimer.singleShot(500, self.app.quit)

    def _report_browser_crash(self, code):
        """The browser closed with an error code and did not ask for a restart: never fail silently."""
        try:
            tmp = os.environ.get("TEMP", os.path.expanduser("~"))
            try:
                hexcode = "0x%08X" % (int(code) & 0xFFFFFFFF)
            except Exception:
                hexcode = str(code)
            try:                                     # keep a written record too, the message box can be missed
                with open(os.path.join(tmp, "SPS_Browser_error.txt"), "a", encoding="utf-8") as _f:
                    _f.write("%s  browser exited with code %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), hexcode))
            except Exception:
                pass
            QMessageBox.critical(
                None, "SPS Browser stopped unexpectedly",
                ("(Exit code 0x00000001 usually means the browser was ended from Task Manager.)\n\n" if (int(code) & 0xFFFFFFFF) == 1 else "") +
                "The browser window closed because of an error (exit code %s).\n\n"
                "Details were saved here:\n  %s\n  %s\n\n"
                "Please send these files through the Support page so it can be fixed."
                % (hexcode, os.path.join(tmp, "SPS_Browser_native_crash.txt"), os.path.join(tmp, "SPS_Browser_error.txt")))
        except Exception:
            pass

    # ── Sandbox Manager ──────────────────────────────────────────

    def show_manager(self):
        if self.manager_win is None:
            self.manager_win = SandboxManagerWindow(self.store, self.audit)
        self.manager_win.show()
        self.manager_win.raise_()
        self.manager_win.activateWindow()

    def kill_browser(self):
        self._quitting = True                       # we are closing it on purpose - not a crash
        for p in [self.proc] + list(self._extra_procs):
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass

    # ── Manual permission request (from sandboxed IPC) ──────────

    def request_permission(self, perm_type: str, origin: str, detail: str) -> bool:
        """Any thread (IPC server, monitors). The dialog is always shown on the GUI thread, one at a time."""
        return bool(self.gui.call(lambda: self._request_permission_gui(perm_type, origin, detail),
                                  timeout=300, default=False))

    def _request_permission_gui(self, perm_type: str, origin: str, detail: str) -> bool:
        """GUI thread only."""
        saved = self.store.get(origin, perm_type)
        if saved == "allow_always":
            self.audit.log(perm_type, origin, detail, "allow_always [auto]")
            return True
        if saved == "deny_always":
            self.audit.log(perm_type, origin, detail, "deny_always [auto]")
            return False
        if (origin, perm_type) in self._session_allow:
            self.audit.log(perm_type, origin, detail, "allow_session [auto]")
            return True
        if (origin, perm_type) in self._session_deny:
            self.audit.log(perm_type, origin, detail, "deny [auto]")
            return False

        decision = PermissionDialog.ask(perm_type, origin, detail)
        entry = self.audit.log(perm_type, origin, detail, decision)
        if self.manager_win:
            try: self.manager_win.add_entry(entry)
            except Exception: pass

        if decision == PermissionDialog.ALLOW_ALWAYS:
            self.store.set(origin, perm_type, "allow_always")
            return True
        if decision == PermissionDialog.DENY_ALWAYS:
            self.store.set(origin, perm_type, "deny_always")
            return False
        if decision == PermissionDialog.ALLOW_SESSION:
            self._session_allow.add((origin, perm_type))
            return True
        if decision == PermissionDialog.ALLOW_ONCE:
            return True
        return False  # deny

    # ── Second click on SPS_Browser.exe while the sandbox is already running ─────────
    def _on_new_instance(self):
        srv = self._inst_server
        if srv is None:
            return
        conn = srv.nextPendingConnection()
        if conn is None:
            return
        conn.waitForReadyRead(400)
        try:
            raw = bytes(conn.readAll()).decode("utf-8", "ignore").strip().splitlines()[0]
            args = [str(a) for a in json.loads(raw).get("args", [])]
        except Exception:
            args = []
        conn.disconnectFromServer()
        self.activate_or_open(args)

    def _alive_procs(self):
        return [p for p in [self.proc] + list(self._extra_procs) if p is not None and p.poll() is None]

    def activate_or_open(self, args):
        """Second click on SPS_Browser.exe: open the Chrome-style profile picker in a NEW browser process
        (several profiles can be open at once). A link / file / --profile argument is passed on as it is."""
        if self._alive_procs():
            self._spawn_extra(args or ["--picker"])
        elif not self._restarting and self.proc is None:
            self._spawn_browser(args)

    def _spawn_extra(self, args):
        env = os.environ.copy()
        env["SPS_SANDBOX"] = "1"
        env["SPS_SANDBOX_PID"] = str(os.getpid())
        env.pop("SPS_SANDBOX_RESTART_FILE", None)           # its own restarts come back through SPS_Browser.exe (this sandbox)
        try:
            p = subprocess.Popen(self._build_cmd(args), env=env, cwd=self.browser_dir,
                                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0)
            self._extra_procs = [x for x in self._extra_procs if x.poll() is None] + [p]
        except Exception as e:
            print(f"[Sandbox] extra window failed: {e}")


# ══════════════════════════════════════════════════════════════════
#  SYSTEM TRAY
# ══════════════════════════════════════════════════════════════════

def _logo_icon():
    """SPS Browser logo from assets/ (next to the exe, inside the bundle, or next to the sources)."""
    roots = [Path(sys.executable).parent, Path(getattr(sys, "_MEIPASS", ".")),
             Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]
    for r in roots:
        for sub in ("assets", "."):
            for n in ("sps_browser.ico", "sps_browser.png"):
                f = r / sub / n
                if f.is_file():
                    ic = QIcon(str(f))
                    if not ic.isNull():
                        return ic
    return None


def build_tray(controller: SandboxController, app: QApplication) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(app)

    # Simple shield icon (drawn programmatically)
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    from PyQt6.QtGui import QPainter, QBrush
    from PyQt6.QtCore import QRectF
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor("#89b4fa")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QRectF(2, 2, 28, 28))
    painter.setPen(QColor("white"))
    font = QFont("Segoe UI", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "🛡")
    painter.end()
    tray.setIcon(_logo_icon() or QIcon(pix))
    tray.setToolTip("SPS Sandbox — Active")

    menu = QMenu()
    menu.setStyleSheet("QMenu{background:#1e1e2e;color:#cdd6f4;} QMenu::item:selected{background:#313244;}")
    act_mgr  = menu.addAction("🛡️ Open Sandbox Manager")
    act_mgr.triggered.connect(controller.show_manager)
    menu.addSeparator()
    act_kill = menu.addAction("⛔ Kill Browser")
    act_kill.triggered.connect(controller.kill_browser)
    act_quit = menu.addAction("❌ Quit Sandbox")
    act_quit.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda r: controller.show_manager()
                           if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
    tray.show()
    return tray


# ══════════════════════════════════════════════════════════════════
#  STARTUP SPLASH
# ══════════════════════════════════════════════════════════════════

class SplashScreen(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPS Sandbox")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(460, 300)
        self.setStyleSheet("background:#1e1e2e;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(10)

        lbl1 = QLabel("🛡️")
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl1.setStyleSheet("font-size:56px;")
        layout.addWidget(lbl1)

        lbl2 = QLabel("SPS Browser Sandbox")
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet("font-size:22px; font-weight:bold; color:#cba6f7;")
        layout.addWidget(lbl2)

        lbl3 = QLabel(f"v{SANDBOX_VERSION}  -  Your browser, fully isolated")
        lbl3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl3.setStyleSheet("font-size:12px; color:#585b70;")
        layout.addWidget(lbl3)

        self.status = QLabel("Initializing...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("font-size:13px; color:#a6e3a1; margin-top:16px;")
        layout.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet("""
            QProgressBar{background:#313244;border-radius:4px;height:6px;}
            QProgressBar::chunk{background:#89b4fa;border-radius:4px;}
        """)
        layout.addWidget(self.bar)

        self._steps = [
            (20, "Setting up permission store..."),
            (40, "Preparing sandbox environment..."),
            (65, "Configuring process watcher..."),
            (85, "Launching browser..."),
            (100,"Ready!"),
        ]
        self._step_idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(250)

    def _tick(self):
        if self._step_idx < len(self._steps):
            val, msg = self._steps[self._step_idx]
            self.bar.setValue(val)
            self.status.setText(msg)
            self._step_idx += 1
        else:
            self._timer.stop()
            QTimer.singleShot(300, self.accept)


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def find_browser() -> str:
    """
    Auto-find SPS_BROWSER*.py for ANY user on any machine.
    Matches any version number: V32.py, V32.0.0.py, V34.py, etc.
    Searches all common user locations automatically.
    """
    # Glob pattern that matches any SPS browser main file
    PATTERNS = [
        "SPS_BROWSER*.py",   # SPS_BROWSER.py
        "SPS_BROWSER*.py",          # any future naming
    ]

    home       = Path.home()
    script_dir = Path(__file__).parent.resolve()

    # Search roots in priority order — all user-agnostic
    search_roots = [
        script_dir,
        script_dir.parent,
        script_dir.parent.parent,
        Path.cwd(),
        home / "Downloads",
        home / "Desktop",
        home / "Documents",
    ]

    def _find_in(folder: Path, recursive: bool = False) -> str:
        """Find any SPS browser .py file in folder."""
        if not folder.exists():
            return ""
        try:
            method = folder.rglob if recursive else folder.glob
            for pat in PATTERNS:
                matches = sorted(method(pat), reverse=True)  # newest version first
                for m in matches:
                    # Skip __pycache__ and .pyc
                    if "__pycache__" in str(m) or m.suffix != ".py":
                        continue
                    # Skip this sandbox file itself
                    if "sandbox" in m.name.lower():
                        continue
                    print(f"[Sandbox] Browser found: {m}")
                    return str(m)
        except Exception:
            pass
        return ""

    # 1. Non-recursive scan of each root and its immediate children
    for root in search_roots:
        result = _find_in(root, recursive=False)
        if result:
            return result
        # Also check one level of subdirectories (handles spsbrowser/, SPS_Browser_V33_Fixed/, etc.)
        try:
            for sub in sorted(root.iterdir(), reverse=True):
                if sub.is_dir() and not sub.name.startswith("."):
                    result = _find_in(sub, recursive=False)
                    if result:
                        return result
        except Exception:
            pass

    # 2. Deep recursive search in Downloads and Desktop as last resort
    for root in [home / "Downloads", home / "Desktop"]:
        result = _find_in(root, recursive=True)
        if result:
            return result

    return ""


def _show_browser_picker(app: QApplication) -> str:
    """Show a friendly GUI dialog to locate the browser file."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog

    dlg = QDialog()
    dlg.setWindowTitle("SPS Sandbox - Find Browser")
    dlg.setFixedSize(500, 280)
    dlg.setStyleSheet("""
        QDialog { background: #1e1e2e; color: #cdd6f4; font-family: Segoe UI, sans-serif; }
        QLabel  { color: #cdd6f4; }
        QPushButton {
            background: #89b4fa; color: #1e1e2e; border: none;
            border-radius: 6px; padding: 10px 20px;
            font-size: 13px; font-weight: bold;
        }
        QPushButton:hover { background: #6b96e8; }
        QPushButton#cancel { background: #313244; color: #cdd6f4; }
        QPushButton#cancel:hover { background: #45475a; }
    """)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(30, 25, 30, 25)
    layout.setSpacing(14)

    icon_lbl = QLabel("SPS Browser Sandbox")
    icon_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #cba6f7;")
    layout.addWidget(icon_lbl)

    msg = QLabel(
        "The sandbox could not find SPS_BROWSER.py automatically.\n\n"
        "Please click Browse and navigate to that file.\n"
        "It is usually inside a folder called spsbrowser."
    )
    msg.setWordWrap(True)
    msg.setStyleSheet("font-size: 13px; color: #a6adc8; line-height: 1.5;")
    layout.addWidget(msg)

    path_label = QLabel("No file selected")
    path_label.setStyleSheet("font-size: 11px; color: #585b70; margin-top: 4px;")
    layout.addWidget(path_label)

    chosen = {"path": ""}

    def browse():
        # Start in Downloads, then Desktop, then home
        start_dir = str(Path.home() / "Downloads")
        if not Path(start_dir).exists():
            start_dir = str(Path.home())
        fp, _ = QFileDialog.getOpenFileName(
            dlg,
            "Find SPS_BROWSER.py",
            start_dir,
            "Python Files (*.py);;All Files (*)"
        )
        if fp:
            chosen["path"] = fp
            short = Path(fp).name
            path_label.setText(f"Selected: {short}")
            path_label.setStyleSheet("font-size: 11px; color: #a6e3a1;")
            btn_launch.setEnabled(True)

    btn_browse = QPushButton("Browse for SPS_BROWSER.py")
    btn_browse.clicked.connect(browse)
    layout.addWidget(btn_browse)

    btn_row = dlg.layout()
    from PyQt6.QtWidgets import QHBoxLayout
    row = QHBoxLayout()

    btn_launch = QPushButton("Launch Sandbox")
    btn_launch.setEnabled(False)
    btn_launch.clicked.connect(dlg.accept)
    row.addWidget(btn_launch)

    btn_cancel = QPushButton("Cancel")
    btn_cancel.setObjectName("cancel")
    btn_cancel.clicked.connect(dlg.reject)
    row.addWidget(btn_cancel)

    layout.addLayout(row)

    result = dlg.exec()
    if result == QDialog.DialogCode.Accepted and chosen["path"]:
        return chosen["path"]
    return ""


def main():
    parser = argparse.ArgumentParser(description="SPS Browser Sandbox Launcher")
    parser.add_argument("--browser", default="",
                        help="Path to SPS_BROWSER.py")
    args, browser_args = parser.parse_known_args()      # e.g. --profile X --restarted hang  -> passed to the browser

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _ic = _logo_icon()
    if _ic:
        app.setWindowIcon(_ic)

    # ── only ONE sandbox per user: a second click just shows the running browser ──
    inst_name = "SPS_Browser_Sandbox_" + "".join(ch if ch.isalnum() else "_" for ch in getpass.getuser())
    probe = QLocalSocket()
    probe.connectToServer(inst_name)
    if probe.waitForConnected(700):
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)      # let the running sandbox focus its window
            probe.write((json.dumps({"args": browser_args}) + "\n").encode("utf-8"))
            probe.flush(); probe.waitForBytesWritten(700)
            probe.disconnectFromServer()
        except Exception:
            pass
        sys.exit(0)
    inst_server = QLocalServer()
    QLocalServer.removeServer(inst_name)                                # clears a leftover from a crash
    inst_server.listen(inst_name)

    if IS_FROZEN:
        # Installed build: the browser is SPS_Browser_Core.exe, right next to this exe.
        browser_path = str(Path(sys.executable).parent / CORE_EXE_NAME)
        if not Path(browser_path).exists():
            QMessageBox.critical(None, "SPS Browser",
                f"{CORE_EXE_NAME} is missing from:\n{Path(sys.executable).parent}\n\nPlease reinstall SPS Browser.")
            sys.exit(1)
    else:
        browser_path = args.browser
        if browser_path and not Path(browser_path).exists():
            print(f"[Sandbox] Specified browser not found: {browser_path}")
            browser_path = ""
        if not browser_path:
            print("[Sandbox] Searching for browser...")
            browser_path = find_browser()
        if not browser_path or not Path(browser_path).exists():
            print("[Sandbox] Browser not found automatically — showing file picker")
            browser_path = _show_browser_picker(app)
            if not browser_path:
                print("[Sandbox] No browser selected. Exiting.")
                sys.exit(0)

    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SPS Browser Sandbox")

    # Splash screen
    splash = SplashScreen()
    splash.show()
    splash.exec()

    # Build controller
    ctrl = SandboxController(browser_path, app, browser_args)
    ctrl._inst_server = inst_server
    inst_server.newConnection.connect(ctrl._on_new_instance)
    app.aboutToQuit.connect(ctrl.kill_browser)      # closing the sandbox never leaves an un-sandboxed browser behind

    # Tray
    tray = build_tray(ctrl, app)

    # Launch browser
    ctrl.launch()

    print(f"[Sandbox] ✅ Browser running under sandbox. PID={ctrl.proc.pid if ctrl.proc else '?'}")
    print( "[Sandbox] Right-click tray icon for Sandbox Manager.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
