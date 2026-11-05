"""SPS VPN: gateway, kill switch, upstream chaining, WireGuard config checks, manager state machine (all offline, local sockets only)."""
import os, socket, struct, sys, tempfile, threading, time, unittest, http.server, socketserver
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sps_vpn as V

WG = """[Interface]
PrivateKey = %s
Address = 10.2.0.2/32
DNS = 10.2.0.1
PostUp = rm -rf /
[Peer]
PublicKey = %s
AllowedIPs = 0.0.0.0/0
Endpoint = vpn.example.org:51820
""" % ("A" * 43 + "=", "B" * 43 + "=")


class Web(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        s.send_response(200); s.send_header("Content-Length", "2"); s.end_headers(); s.wfile.write(b"ok")
    def log_message(*a): pass


class FakeUpstream:
    """A SOCKS5 server that sends EVERY destination to one local port (so we can see that the gateway really used it)."""
    def __init__(self, target_port):
        self.target, self.seen = target_port, []
        self.srv = socket.socket(); self.srv.bind(("127.0.0.1", 0)); self.srv.listen(8)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self.loop, daemon=True).start()
    def loop(self):
        while True:
            try: c, _ = self.srv.accept()
            except OSError: return
            threading.Thread(target=self.one, args=(c,), daemon=True).start()
    def one(self, c):
        try:
            V._recv_exact(c, 2 + V._recv_exact(c, 1)[0] - 1) if False else None
        except Exception:
            pass
    def stop(self): self.srv.close()


def start_fake_upstream(target_port, seen):
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(8)
    def serve(c):
        try:
            ver, n = V._recv_exact(c, 2); V._recv_exact(c, n); c.sendall(b"\x05\x00")
            _, cmd, _, atyp = V._recv_exact(c, 4)
            host = V._recv_exact(c, V._recv_exact(c, 1)[0]).decode() if atyp == 3 else socket.inet_ntoa(V._recv_exact(c, 4))
            V._recv_exact(c, 2); seen.append(host)
            r = socket.create_connection(("127.0.0.1", target_port)); c.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            g = V.Gateway(); g._relay(c, r)
        except Exception:
            pass
        finally:
            c.close()
    def loop():
        while True:
            try: c, _ = srv.accept()
            except OSError: return
            threading.Thread(target=serve, args=(c,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    return srv


def http_get_via(port, host, dest_port):
    s = V.socks5_connect("127.0.0.1", port, host, dest_port)
    s.sendall(b"GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
    data = b""
    while True:
        ch = s.recv(1024)
        if not ch: break
        data += ch
    s.close()
    return data


class VpnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.web = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Web)
        cls.web.daemon_threads = True
        cls.web_port = cls.web.server_address[1]
        threading.Thread(target=cls.web.serve_forever, daemon=True).start()

    def test_local_addresses(self):
        for h in ("localhost", "127.0.0.1", "192.168.1.1", "10.0.0.5", "fe80::1", "printer.local"):
            self.assertTrue(V.is_local_address(h), h)
        for h in ("example.com", "8.8.8.8", "1.1.1.1"):
            self.assertFalse(V.is_local_address(h), h)

    def test_gateway_direct_and_local_bypass(self):
        gw = V.Gateway(); port = gw.start()
        self.assertIn(b"200 OK", http_get_via(port, "127.0.0.1", self.web_port))
        gw.stop()

    def test_gateway_uses_upstream_and_kill_switch(self):
        seen = []
        up = start_fake_upstream(self.web_port, seen)
        gw = V.Gateway(); port = gw.start()
        gw.upstream = {"kind": "socks5", "host": "127.0.0.1", "port": up.getsockname()[1]}
        self.assertIn(b"200 OK", http_get_via(port, "secret-site.test", 80))       # a public name goes through the upstream
        self.assertEqual(seen, ["secret-site.test"])                               # ...and the NAME was sent (remote DNS, no leak)
        self.assertIn(b"200 OK", http_get_via(port, "127.0.0.1", self.web_port))   # local never uses the upstream
        self.assertEqual(seen, ["secret-site.test"])
        gw.block_all = True                                                        # kill switch
        with self.assertRaises(ConnectionError):
            http_get_via(port, "secret-site.test", 80)
        self.assertIn(b"200 OK", http_get_via(port, "127.0.0.1", self.web_port))   # local still works
        self.assertGreaterEqual(gw.refused, 1)
        gw.stop(); up.close()

    def test_wireguard_parser(self):
        clean, info = V.parse_wireguard(WG)
        self.assertNotIn("PostUp", clean)
        self.assertEqual((info["host"], info["port"]), ("vpn.example.org", 51820))
        for bad in (WG.replace("A" * 43 + "=", "short"), WG.replace("Address = 10.2.0.2/32\n", ""),
                    WG.replace("vpn.example.org:51820", "nohost"), "not a config"):
            with self.assertRaises(ValueError):
                V.parse_wireguard(bad)

    def test_manager_connect_disconnect_and_flags(self):
        seen = []
        up = start_fake_upstream(self.web_port, seen)
        old = V.exit_info
        V.exit_info = lambda upstream, *a, **k: ("203.0.113.9", "NL", 42)
        try:
            m = V.VpnManager(base=tempfile.mkdtemp())
            self.assertEqual(m.browser_flags(), [])                                # VPN support is off by default
            m.store.data["enabled"] = True
            flags = m.browser_flags()
            self.assertTrue(flags[0].startswith("--proxy-server=socks5://127.0.0.1:"))
            self.assertIn("--force-webrtc-ip-handling-policy=disable_non_proxied_udp", flags)
            s = m.store.add(V.make_server("socks5", "Test", host="127.0.0.1", port=up.getsockname()[1]))
            self.assertTrue(m.connect(s))
            self.assertEqual((m.state, m.exit[0]), ("connected", "203.0.113.9"))
            self.assertIn(b"200 OK", http_get_via(m.gw.port, "anything.test", 80))
            m.disconnect()
            self.assertEqual(m.state, "off")
            self.assertIsNone(m.gw.upstream)
            self.assertFalse(m.gw.block_all)
            # a failing server: error state and the kill switch keeps traffic blocked
            bad = m.store.add(V.make_server("socks5", "Dead", host="127.0.0.1", port=1))
            V.exit_info = old
            self.assertFalse(m.connect(bad))
            self.assertEqual(m.state, "error")
            self.assertTrue(m.gw.block_all)
            m.disconnect()
            self.assertFalse(m.gw.block_all)
            if os.name == "posix":
                self.assertEqual(os.stat(m.store.path).st_mode & 0o777, 0o600)    # keys are stored owner-only
        finally:
            V.exit_info = old
            up.close()


if __name__ == "__main__":
    unittest.main()


class VpnWiringTests(unittest.TestCase):
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def _t(self, *p):
        return open(os.path.join(self.ROOT, *p), encoding="utf-8").read()

    def test_spec_bundles_vpn_modules(self):
        spec = self._t("SPS_Browser.spec")
        self.assertIn('"sps_vpn"', spec); self.assertIn('"sps_vpn_ui"', spec)

    def test_browser_has_vpn_button_menu_and_startup_flags(self):
        b = self._t("src", "SPS_BROWSER.py")
        for needle in ("self.vpn_btn", "SPS VPN…", "sps_vpn_ui.startup_flags"):
            self.assertIn(needle, b)
        self.assertIn("_v39_open_vpn", self._t("src", "_v36_patch.py"))

    def test_root_requirements_and_fetch_script(self):
        r = self._t("requirements.txt")
        self.assertIn("-r requirements-build.txt", r)
        self.assertIn("fetch_vpn_components", self._t("tools", "ci_build.py"))

    def test_dialog_opens_headless(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import tempfile
        sys.path.insert(0, os.path.join(self.ROOT, "src"))
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(["x"])
        import sps_vpn_ui, sps_vpn
        m = sps_vpn.VpnManager(tempfile.mkdtemp())
        d = sps_vpn_ui.SpsVpnDialog(None, m, None)
        d.show(); app.processEvents()
        self.assertIn("Not connected", d.status.text())
        d.close()


class ExtensionTests(unittest.TestCase):
    def test_manifest_and_rules(self):
        import json
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "extension"))
        m = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
        self.assertEqual(m["manifest_version"], 3)
        for rr in m["declarative_net_request"]["rule_resources"]:
            rules = json.load(open(os.path.join(root, rr["path"]), encoding="utf-8"))
            ids = [r["id"] for r in rules]
            self.assertEqual(len(ids), len(set(ids)))
        for f in ("background.js", "popup/popup.html", "options/options.html", "icons/128.png", "content/area_print.js"):
            self.assertTrue(os.path.isfile(os.path.join(root, f)), f)


class SystemVpnTests(unittest.TestCase):
    def test_commands_and_conf(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        import sps_vpn_system as S
        d = tempfile.mkdtemp()
        p = S.write_conf(d, "[Interface]\nPrivateKey = x\n")
        self.assertTrue(p.endswith("spsvpn.conf"))
        self.assertEqual(S.commands("up", p)[-1], p)
        self.assertIn("up" if not S.IS_WIN else "/installtunnelservice", S.commands("up", p))
        with self.assertRaises(ValueError):
            S.write_conf(d, "nonsense")


class AndroidWorkflowTests(unittest.TestCase):
    def test_no_broken_setup_android_action(self):
        wf = open(os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "build.yml"), encoding="utf-8").read()
        self.assertNotIn("android-actions/setup-android", wf)      # its sdkmanager 'tools' step fails on current runners
        self.assertIn("platforms;android-34", wf)


class SystemVpnStopTests(unittest.TestCase):
    """Stopping twice must not contact WireGuard the second time."""
    def test_second_stop_makes_no_os_call(self):
        import sps_vpn_system as sv, tempfile
        d = tempfile.mkdtemp()
        calls = []
        sv.is_active = lambda workdir=None: state["on"]
        sv.run = lambda action, path: (calls.append(action), state.__setitem__("on", False))
        state = {"on": True}
        self.assertIn("stopped", sv.stop(d, wait_seconds=1))
        self.assertEqual(calls, ["down"])                         # exactly one request to the OS
        self.assertIn("already stopped", sv.stop(d, wait_seconds=1))
        self.assertIn("already stopped", sv.stop(d, wait_seconds=1))
        self.assertEqual(calls, ["down"])                         # still one: later clicks never reach WireGuard

    def test_start_twice(self):
        import sps_vpn_system as sv, tempfile
        d = tempfile.mkdtemp(); calls = []
        sv.available = lambda: (True, "")
        sv.is_active = lambda workdir=None: bool(calls)
        sv.run = lambda action, path: calls.append(action)
        sv.start(d, "[Interface]\nPrivateKey=x\n")
        self.assertIn("already running", sv.start(d, "[Interface]\nPrivateKey=x\n"))
        self.assertEqual(calls, ["up"])


class AndroidUiTests(unittest.TestCase):
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "android", "app", "src", "main"))

    def _j(self, name):
        return open(os.path.join(self.ROOT, "java", "com", "spscompany", "spsbrowser", name), encoding="utf-8").read()

    def test_files_exist(self):
        for f in ("Ico.java", "UI.java", "Crypto.java", "Store.java", "Profiles.java", "ListPage.java", "TabsPage.java",
                  "Vault.java", "PasswordGen.java", "Host.java", "BTab.java"):
            self.assertTrue(os.path.isfile(os.path.join(self.ROOT, "java", "com", "spscompany", "spsbrowser", f)), f)
        self.assertTrue(os.path.isfile(os.path.join(self.ROOT, "assets", "icons.txt")))

    def test_security_design(self):
        c = self._j("Crypto.java")
        self.assertIn("AndroidKeyStore", c); self.assertIn("AES/GCM/NoPadding", c); self.assertIn("updateAAD", c)
        m = self._j("MainActivity.java")
        self.assertIn("createConfirmDeviceCredentialIntent", m)       # screen lock before passwords are used
        self.assertIn("FLAG_SECURE", m)
        self.assertIn("equals(real)", m)                              # the page cannot speak for another host
        self.assertIn('"secure"', m)
        self.assertNotIn("setJavaScriptEnabled(true);\n        s.setAllowFileAccess(true", m)

    def test_icons_parse(self):
        import re
        for line in open(os.path.join(self.ROOT, "assets", "icons.txt"), encoding="utf-8"):
            name, ops = line.rstrip("\n").split("|", 1)
            if ops.startswith("S "):                                  # Material path data, parsed by SvgPath.java (tested in test_android_icons)
                self.assertRegex(ops[2:], r"^[MmLlHhVvCcSsQqTtAaZz0-9eE.,\s+-]+$", name); continue
            toks = ops.split()
            self.assertTrue(toks and toks[0] in ("M", "N", "C", "F", "A", "R"), name)
            for t in toks:
                self.assertTrue(t in ("M", "N", "L", "Z", "C", "F", "A", "R") or re.match(r"^-?[\d.]+(,-?[\d.]+)*$", t), (name, t))

    def test_features_present(self):
        m = self._j("MainActivity.java")
        for needle in ("showProfiles", "showTabs", "showBookmarks", "showHistory", "showDownloads", "showSettings", "fillAddress", "offerSaveBanner"):
            self.assertIn(needle, m)
        t = self._j("TabsPage.java")
        for needle in ("closeDuplicates", "recentlyClosed", "Pin", "Select tabs", "Sort A to Z"):
            self.assertIn(needle, t)


class HelperAutoFetchTests(unittest.TestCase):
    def test_missing_wireproxy_is_downloaded_not_reported(self):
        import tempfile, sps_vpn, sps_vpn_fetch
        d = tempfile.mkdtemp()
        calls = []
        orig_find, orig_fetch, orig_dir = sps_vpn.find_helper, sps_vpn_fetch.fetch_wireproxy, sps_vpn.vpn_dir
        try:
            sps_vpn.vpn_dir = lambda base=None: d
            sps_vpn.find_helper = lambda n, e=(): None
            sps_vpn_fetch.fetch_wireproxy = lambda dest: calls.append(dest) or os.path.join(dest, "wireproxy")
            self.assertTrue(sps_vpn.ensure_helper("wireproxy").endswith("wireproxy"))
            self.assertEqual(calls, [os.path.join(d, "bin")])
            sps_vpn_fetch.fetch_wireproxy = lambda dest: (_ for _ in ()).throw(RuntimeError("offline"))
            with self.assertRaises(RuntimeError) as cm:
                sps_vpn.ensure_helper("wireproxy")
            self.assertIn("could not be downloaded", str(cm.exception))
        finally:
            sps_vpn.find_helper, sps_vpn_fetch.fetch_wireproxy, sps_vpn.vpn_dir = orig_find, orig_fetch, orig_dir

    def test_build_is_strict_and_spec_packs_fetcher(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertIn("--strict", open(os.path.join(root, "tools", "ci_build.py"), encoding="utf-8").read())
        self.assertIn("sps_vpn_fetch", open(os.path.join(root, "SPS_Browser.spec"), encoding="utf-8").read())


class WindowsArmFetchTests(unittest.TestCase):
    """The GitHub Windows-ARM runner has no wireproxy/Tor ARM builds: the x64 ones (run emulated) must be used."""
    def test_arm_falls_back_to_x64(self):
        import io, tarfile, platform
        import sps_vpn_fetch as F
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            data = b"MZ-fake"; ti = tarfile.TarInfo("wireproxy.exe"); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        blob, asked = buf.getvalue(), []

        def fake_get(url, timeout=120, tries=3):
            asked.append(url)
            if "arm64" in url:
                raise RuntimeError("HTTP Error 404")
            return blob
        o_get, o_sys, o_mach = F._get, platform.system, platform.machine
        try:
            F._get = fake_get; platform.system = lambda: "Windows"; platform.machine = lambda: "ARM64"
            d = tempfile.mkdtemp()
            path = F.fetch_wireproxy(d)
        finally:
            F._get, platform.system, platform.machine = o_get, o_sys, o_mach
        self.assertTrue(path.endswith("wireproxy.exe") and os.path.isfile(path))
        self.assertTrue(any("windows_arm64" in u for u in asked) and any("windows_amd64" in u for u in asked))
