"""SPS VPN window (PyQt6).  Everything is free: you bring your own server (WireGuard .conf, SOCKS5/HTTP proxy) or use Tor.

The window only talks to sps_vpn.VpnManager.  Network work always runs in a worker thread so the window never freezes.
"""
import os, sys, threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
                             QCheckBox, QMessageBox, QFileDialog, QInputDialog, QFrame, QDialogButtonBox,
                             QFormLayout, QLineEdit, QSpinBox, QComboBox)

import sps_vpn
import sps_vpn_system

_MANAGER = None


def get_manager(base=None, helper_dirs=()):
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = sps_vpn.VpnManager(base, helper_dirs)
    return _MANAGER


def startup_flags(base=None):
    """Chromium flags for the browser process. Call BEFORE QtWebEngine starts. Never raises."""
    try:
        m = get_manager(base)
        flags = m.browser_flags()
        if flags and m.store.data.get("autoconnect") and m.store.data["servers"]:
            threading.Thread(target=m.auto_connect, daemon=True).start()
        return " ".join(flags)
    except Exception:
        return ""


class _Bus(QObject):
    changed = pyqtSignal()
    note = pyqtSignal(str)


class _AddServerDialog(QDialog):
    def __init__(self, parent, kind):
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle({"socks5": "Add SOCKS5 proxy", "http": "Add HTTP proxy"}.get(kind, "Add server"))
        f = QFormLayout(self)
        self.name = QLineEdit(); self.host = QLineEdit(); self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(1080 if kind == "socks5" else 8080)
        self.user = QLineEdit(); self.pw = QLineEdit(); self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("Name", self.name); f.addRow("Host", self.host); f.addRow("Port", self.port)
        f.addRow("User (optional)", self.user); f.addRow("Password (optional)", self.pw)
        f.addRow(QLabel("Only use a server you own or fully trust: it can see where your traffic goes."))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); f.addRow(bb)

    def server(self):
        h = self.host.text().strip()
        if not h:
            return None
        return sps_vpn.make_server(self.kind, self.name.text().strip() or h, host=h, port=self.port.value(),
                                   user=self.user.text().strip() or None, password=self.pw.text() or None)


class SpsVpnDialog(QDialog):
    def __init__(self, parent, manager, restart_cb=None):
        super().__init__(parent)
        self.m = manager
        self.restart_cb = restart_cb
        self.bus = _Bus()
        self.bus.changed.connect(self.refresh)
        self.setWindowTitle("SPS VPN")
        self.setMinimumSize(560, 600)
        lay = QVBoxLayout(self)

        self.status = QLabel(); self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size:15px;font-weight:700;padding:10px;border-radius:8px;")
        lay.addWidget(self.status)
        self.detail = QLabel(); self.detail.setWordWrap(True); lay.addWidget(self.detail)

        row = QHBoxLayout()
        self.btn_connect = QPushButton("Connect"); self.btn_connect.clicked.connect(self.on_connect)
        self.btn_auto = QPushButton("⚡ Auto (best server)"); self.btn_auto.clicked.connect(self.on_auto)
        self.btn_off = QPushButton("Disconnect"); self.btn_off.clicked.connect(self.on_disconnect)
        for b in (self.btn_connect, self.btn_auto, self.btn_off):
            b.setMinimumHeight(36); row.addWidget(b)
        lay.addLayout(row)

        lay.addWidget(QLabel("Servers (choose one, then press Connect):"))
        self.list = QListWidget(); self.list.itemDoubleClicked.connect(lambda *_: self.on_connect()); lay.addWidget(self.list, 1)

        r2 = QHBoxLayout()
        for text, fn in (("+ WireGuard file…", self.add_wg), ("+ SOCKS5", lambda: self.add_proxy("socks5")),
                         ("+ HTTP proxy", lambda: self.add_proxy("http")), ("+ Tor", self.add_tor)):
            b = QPushButton(text); b.clicked.connect(fn); r2.addWidget(b)
        lay.addLayout(r2)
        r3 = QHBoxLayout()
        b = QPushButton("Test all"); b.clicked.connect(self.on_test_all); r3.addWidget(b)
        b = QPushButton("Remove"); b.clicked.connect(self.on_remove); r3.addWidget(b)
        b = QPushButton("Open VPN folder"); b.clicked.connect(self.open_folder); r3.addWidget(b)
        lay.addLayout(r3)
        r4 = QHBoxLayout()
        self.btn_sys_on = QPushButton("🖥 Protect WHOLE computer (WireGuard server)"); self.btn_sys_on.clicked.connect(self.sys_on)
        self.btn_sys_off = QPushButton("Stop whole-computer VPN"); self.btn_sys_off.clicked.connect(self.sys_off)
        r4.addWidget(self.btn_sys_on); r4.addWidget(self.btn_sys_off)
        lay.addLayout(r4)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); lay.addWidget(sep)
        self.chk_enabled = QCheckBox("Turn on VPN support (the whole browser then goes through SPS VPN; restart needed)")
        self.chk_enabled.clicked.connect(self.on_enabled)
        self.chk_kill = QCheckBox("Kill switch: block internet if the VPN drops (recommended)")
        self.chk_kill.clicked.connect(lambda v: self._set("killswitch", bool(v)))
        self.chk_auto = QCheckBox("Connect automatically when the browser starts")
        self.chk_auto.clicked.connect(lambda v: self._set("autoconnect", bool(v)))
        for c in (self.chk_enabled, self.chk_kill, self.chk_auto):
            lay.addWidget(c)
        self.comp = QLabel(); self.comp.setWordWrap(True); self.comp.setStyleSheet("color:gray;font-size:11px;"); lay.addWidget(self.comp)
        note = QLabel("IMPORTANT: SPS VPN is a VPN CLIENT, not a VPN service like Proton VPN. It has NO servers of its own. "
                      "Normal connect = only SPS Browser is protected. 'Protect WHOLE computer' protects every app but needs the free "
                      "WireGuard program, administrator approval and a WireGuard server config (your own server or a provider that gives you one). "
                      "Random public proxy lists are never used (they can read and change your traffic). Tor is free but slower.")
        note.setWordWrap(True); note.setStyleSheet("color:gray;font-size:11px;"); lay.addWidget(note)

        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1500)
        self.refresh()

    # ---- helpers ----
    def _set(self, key, val):
        self.m.store.data[key] = val
        self.m.store.save()

    def _selected(self):
        it = self.list.currentItem()
        return self.m.store.get(it.data(Qt.ItemDataRole.UserRole)) if it else None

    def _busy(self, text):
        self.m.state, self.m.message = "connecting", text
        self.refresh()

    def refresh(self):
        st = self.m.state
        colors = {"off": ("#555", "#eee"), "connecting": ("#8a6d00", "#fff3c4"), "connected": ("#0b6b2a", "#d6f5df"), "error": ("#8a1010", "#fbd9d9")}
        fg, bg = colors.get(st, colors["off"])
        self.status.setStyleSheet(f"font-size:15px;font-weight:700;padding:10px;border-radius:8px;color:{fg};background:{bg};")
        self.status.setText({"off": "○ Not connected", "connecting": "◌ Connecting…", "connected": "● Connected", "error": "⚠ Problem"}[st])
        self.detail.setText(self.m.message)
        d = self.m.store.data
        cur = self.list.currentItem().data(Qt.ItemDataRole.UserRole) if self.list.currentItem() else d.get("last")
        self.list.blockSignals(True); self.list.clear()
        for s in d["servers"]:
            ms = s.get("last_ms")
            mark = "●" if (self.m.server and self.m.server.get("id") == s["id"] and st == "connected") else " "
            label = "%s %s   [%s]%s" % (mark, s["name"], s["kind"], ("   %d ms" % ms) if ms else "")
            it = QListWidgetItem(label); it.setData(Qt.ItemDataRole.UserRole, s["id"]); self.list.addItem(it)
            if s["id"] == cur:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        busy = st == "connecting"
        self.btn_connect.setEnabled(not busy); self.btn_auto.setEnabled(not busy); self.btn_off.setEnabled(st in ("connected", "error", "connecting"))
        for c, k, dflt in ((self.chk_enabled, "enabled", False), (self.chk_kill, "killswitch", True), (self.chk_auto, "autoconnect", False)):
            c.blockSignals(True); c.setChecked(bool(d.get(k, dflt))); c.blockSignals(False)
        wp, tor = sps_vpn.find_helper("wireproxy", self.m.helper_dirs), sps_vpn.find_helper("tor", self.m.helper_dirs)
        self.comp.setText("Components - WireGuard helper: %s   |   Tor: %s" % ("found" if wp else "not found", "found" if tor else "not found"))

    # ---- actions ----
    def _need_enabled(self):
        if self.m.store.data.get("enabled") and self.m.gw.port:
            return True
        ask = ("SPS VPN must be switched on first. The browser will restart once so that all its traffic can go through the VPN.\n\n"
               "Switch it on and restart now?")
        if QMessageBox.question(self, "SPS VPN", ask) == QMessageBox.StandardButton.Yes:
            self._set("enabled", True)
            self._restart()
        return False

    def _restart(self):
        if self.restart_cb:
            self.restart_cb()
        else:
            QMessageBox.information(self, "SPS VPN", "Please close and start SPS Browser again.")

    def _run(self, fn):
        def work():
            try:
                fn()
            finally:
                self.bus.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    def on_connect(self):
        s = self._selected()
        if not s:
            QMessageBox.information(self, "SPS VPN", "Add or choose a server first (or press Auto)."); return
        if not self._need_enabled():
            return
        self._busy("Connecting to %s…" % s["name"])
        self._run(lambda: self.m.connect(s))

    def on_auto(self):
        if not self.m.store.data["servers"]:
            self.m.store.add(sps_vpn.make_server("tor", "Tor (free)"))
        if not self._need_enabled():
            return
        self._busy("Looking for the best working server…")
        self._run(lambda: self.m.auto_connect(lambda t: setattr(self.m, "message", t)))

    def on_disconnect(self):
        self.m.disconnect(); self.refresh()

    def on_remove(self):
        s = self._selected()
        if s:
            if self.m.server and self.m.server.get("id") == s["id"]:
                self.m.disconnect()
            self.m.store.remove(s["id"]); self.refresh()

    def on_test_all(self):
        servers = list(self.m.store.data["servers"])
        if not servers:
            return
        self._busy("Testing %d server(s)…" % len(servers))

        def work():
            for s in servers:
                ms = self.m.test_server(s)
                s["last_ms"] = ms
            self.m.store.save()
            if self.m.state == "connecting":
                self.m.state, self.m.message = "off", "Test finished."
        self._run(work)

    def sys_on(self):
        s = self._selected()
        if not s or s["kind"] != "wireguard":
            QMessageBox.information(self, "SPS VPN", "Choose a WireGuard server in the list first (add a .conf file)."); return
        ok, msg = sps_vpn_system.available()
        if not ok:
            QMessageBox.information(self, "SPS VPN", msg); return
        if QMessageBox.question(self, "Protect whole computer",
                                "This changes the network settings of the WHOLE computer and needs administrator approval.\n"
                                "Use 'Stop whole-computer VPN' to undo it.\n\nContinue?") != QMessageBox.StandardButton.Yes:
            return
        try:
            sps_vpn_system.start(self.m.store.dir, s["conf"])
            self.m.message = "Whole-computer VPN requested for %s. Check your IP at a 'what is my IP' site." % s["name"]
        except Exception as e:
            QMessageBox.warning(self, "SPS VPN", "Could not start it: %s" % e)
        self.refresh()

    def sys_off(self):
        try:
            sps_vpn_system.stop(self.m.store.dir)
            self.m.message = "Whole-computer VPN stop requested."
        except Exception as e:
            QMessageBox.warning(self, "SPS VPN", "Could not stop it: %s" % e)
        self.refresh()

    def on_enabled(self, v):
        v = bool(v)
        if v == bool(self.m.store.data.get("enabled")):
            return
        self._set("enabled", v)
        if QMessageBox.question(self, "SPS VPN", "Restart SPS Browser now to apply this?") == QMessageBox.StandardButton.Yes:
            self._restart()

    def add_wg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a WireGuard .conf file", "", "WireGuard (*.conf);;All files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                clean, info = sps_vpn.parse_wireguard(f.read())
            name = os.path.splitext(os.path.basename(path))[0]
            self.m.store.add(sps_vpn.make_server("wireguard", name, conf=clean, endpoint=info.get("endpoint", "")))
            self.refresh()
            if not sps_vpn.find_helper("wireproxy", self.m.helper_dirs):
                QMessageBox.information(self, "SPS VPN", "Saved. The WireGuard helper (wireproxy) was not found in the 'vpn' folder yet - "
                                        "put wireproxy(.exe) there (Open VPN folder) before connecting.")
        except Exception as e:
            QMessageBox.warning(self, "SPS VPN", "That file could not be used: %s" % e)

    def add_proxy(self, kind):
        dlg = _AddServerDialog(self, kind)
        if dlg.exec():
            s = dlg.server()
            if s:
                self.m.store.add(s); self.refresh()

    def add_tor(self):
        if any(s["kind"] == "tor" for s in self.m.store.data["servers"]):
            QMessageBox.information(self, "SPS VPN", "Tor is already in the list."); return
        self.m.store.add(sps_vpn.make_server("tor", "Tor (free, anonymous, slower)")); self.refresh()

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.m.store.dir))

    def done(self, r):
        self.timer.stop()
        super().done(r)


def show_vpn_dialog(parent, base=None, restart_cb=None, helper_dirs=()):
    m = get_manager(base, helper_dirs)
    dlg = SpsVpnDialog(parent, m, restart_cb)
    dlg.exec()
