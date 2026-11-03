"""SPS VPN - a browser-level VPN that is free, honest and fail-closed.

How it works (no administrator rights, nothing installed on Windows):
  browser  ->  local SOCKS5 gateway (127.0.0.1, this file)  ->  upstream:  direct | your SOCKS5/HTTP proxy |
                                                                           WireGuard tunnel (wireproxy) | Tor
* Only the BROWSER's traffic is tunnelled (not the whole PC).  Local / private addresses are never sent through the VPN.
* Kill switch: when a tunnel is expected but down, the gateway refuses every connection instead of leaking your real IP.
* No servers are bundled or promised: you add WireGuard configs (e.g. from a free Proton VPN / Cloudflare WARP account or your own
  server), your own proxy, or use Tor.  SPS never connects you to random "free proxy lists" (they can read and change your traffic).
Optional helper programs (looked for in <program folder>/vpn, then PATH):  wireproxy  (WireGuard),  tor  (Tor).
"""
import base64, ipaddress, json, os, random, re, select, shutil, socket, struct, subprocess, sys, threading, time

IS_WIN = sys.platform == "win32"
CONNECT_TIMEOUT = 12
CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0

# ───────────────────────────── paths ─────────────────────────────
def vpn_dir(base=None):
    d = os.path.join(base or os.environ.get("SPS_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".sps_browser"), "vpn")
    os.makedirs(d, exist_ok=True)
    return d


def find_helper(name, extra_dirs=()):
    exe = name + (".exe" if IS_WIN else "")
    cands = []
    for d in extra_dirs:
        cands += [os.path.join(d, exe), os.path.join(d, name, exe), os.path.join(d, name, "tor", exe)]
    try:
        ub = os.path.join(vpn_dir(), "bin")                      # helpers the program downloaded by itself
        cands += [os.path.join(ub, exe), os.path.join(ub, name, exe), os.path.join(ub, name, "tor", exe)]
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    for base in (here, os.path.dirname(here)):
        cands += [os.path.join(base, "vpn", exe), os.path.join(base, "vpn", name, exe), os.path.join(base, "vpn", name, "tor", exe)]
    for c in cands:
        if os.path.isfile(c):
            return c
    return shutil.which(name)


def ensure_helper(name, helper_dirs=(), log=None):
    """Path of the helper program; when it is missing it is downloaded once from its official release (never fails silently)."""
    exe = find_helper(name, helper_dirs)
    if exe:
        return exe
    log = log or (lambda m: None)
    try:
        import sps_vpn_fetch
        log("downloading %s ..." % name)
        dest = os.path.join(vpn_dir(), "bin")
        if name == "wireproxy":
            return sps_vpn_fetch.fetch_wireproxy(dest)
        if name == "tor":
            sps_vpn_fetch.fetch_tor(dest)
            exe = find_helper("tor", helper_dirs)
            if exe:
                return exe
    except Exception as e:
        raise RuntimeError("The helper '%s' is missing and could not be downloaded automatically (%s). "
                           "Check your internet connection and try again." % (name, e))
    raise RuntimeError("The helper '%s' was not found." % name)


# ───────────────────────────── helpers ─────────────────────────────
def is_local_address(host):
    """Loopback / private / link-local / .local names never go through the VPN."""
    h = (host or "").strip("[]").lower()
    if h in ("localhost", "") or h.endswith(".local") or h.endswith(".localhost") or h.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast
    except ValueError:
        return False


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_port(port, timeout=20, proc=None):
    end = time.time() + timeout
    while time.time() < end:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def socks5_connect(proxy_host, proxy_port, dest_host, dest_port, user=None, password=None, timeout=CONNECT_TIMEOUT):
    """Open a TCP connection to dest through a SOCKS5 proxy (the proxy resolves the name = no DNS leak)."""
    s = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    try:
        s.settimeout(timeout)
        if user:
            s.sendall(b"\x05\x02\x00\x02")
        else:
            s.sendall(b"\x05\x01\x00")
        ver, method = _recv_exact(s, 2)
        if ver != 5 or method == 0xFF:
            raise ConnectionError("SOCKS5 proxy refused the login method")
        if method == 2:
            u, p = (user or "").encode(), (password or "").encode()
            s.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            if _recv_exact(s, 2)[1] != 0:
                raise ConnectionError("SOCKS5 login failed")
        try:
            ip = ipaddress.ip_address(dest_host.strip("[]"))
            addr = (b"\x01" + ip.packed) if ip.version == 4 else (b"\x04" + ip.packed)
        except ValueError:
            hb = dest_host.encode("idna")
            addr = b"\x03" + bytes([len(hb)]) + hb
        s.sendall(b"\x05\x01\x00" + addr + struct.pack(">H", dest_port))
        hdr = _recv_exact(s, 4)
        if hdr[1] != 0:
            raise ConnectionError("SOCKS5 connect failed (code %d)" % hdr[1])
        atyp = hdr[3]
        _recv_exact(s, {1: 4, 4: 16}.get(atyp, 0) if atyp != 3 else (_recv_exact(s, 1)[0]))
        _recv_exact(s, 2)
        s.settimeout(None)
        return s
    except Exception:
        s.close()
        raise


def http_connect(proxy_host, proxy_port, dest_host, dest_port, user=None, password=None, timeout=CONNECT_TIMEOUT):
    s = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    try:
        s.settimeout(timeout)
        auth = ""
        if user:
            auth = "Proxy-Authorization: Basic %s\r\n" % base64.b64encode(("%s:%s" % (user, password or "")).encode()).decode()
        host = "[%s]" % dest_host if ":" in dest_host and not dest_host.startswith("[") else dest_host
        s.sendall(("CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n%s\r\n" % (host, dest_port, host, dest_port, auth)).encode())
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 8192:
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
        if not data.startswith(b"HTTP/1.") or b" 200" not in data.split(b"\r\n", 1)[0]:
            raise ConnectionError("HTTP proxy refused: %s" % data.split(b"\r\n", 1)[0][:60].decode("latin1"))
        s.settimeout(None)
        return s
    except Exception:
        s.close()
        raise


def exit_info(upstream, timeout=CONNECT_TIMEOUT):
    """(ip, country, ms) as seen by Cloudflare through the given upstream - proves where traffic leaves from."""
    t0 = time.time()
    s = open_upstream(upstream, "1.1.1.1", 80, timeout=timeout) if upstream else socket.create_connection(("1.1.1.1", 80), timeout=timeout)
    try:
        s.settimeout(timeout)
        s.sendall(b"GET /cdn-cgi/trace HTTP/1.1\r\nHost: 1.1.1.1\r\nConnection: close\r\n\r\n")
        data = b""
        while len(data) < 8192:
            chunk = s.recv(2048)
            if not chunk:
                break
            data += chunk
    finally:
        s.close()
    ms = int((time.time() - t0) * 1000)
    kv = dict(l.split("=", 1) for l in data.decode("utf-8", "replace").splitlines() if "=" in l)
    return kv.get("ip", "?"), kv.get("loc", "?"), ms


def open_upstream(up, host, port, timeout=CONNECT_TIMEOUT):
    """up = None (direct) or {'kind':'socks5'|'http','host','port','user','password'}"""
    if not up:
        return socket.create_connection((host, port), timeout=timeout)
    if up["kind"] == "http":
        return http_connect(up["host"], up["port"], host, port, up.get("user"), up.get("password"), timeout)
    return socks5_connect(up["host"], up["port"], host, port, up.get("user"), up.get("password"), timeout)


# ───────────────────────────── the local gateway ─────────────────────────────
class Gateway:
    """SOCKS5 server on 127.0.0.1. The browser always talks to this; what is behind it can change instantly."""

    def __init__(self):
        self.upstream = None          # None = direct
        self.block_all = False        # kill switch
        self.port = 0
        self._srv = None
        self._stop = threading.Event()
        self.bytes_up = self.bytes_down = 0
        self.refused = 0

    def start(self, port=0):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(256)
        self._srv = srv
        self.port = srv.getsockname()[1]
        threading.Thread(target=self._accept, name="sps-vpn-gateway", daemon=True).start()
        return self.port

    def stop(self):
        self._stop.set()
        try:
            self._srv.close()
        except Exception:
            pass

    def _accept(self):
        while not self._stop.is_set():
            try:
                c, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def _serve(self, c):
        remote = None
        try:
            c.settimeout(CONNECT_TIMEOUT)
            ver, n = _recv_exact(c, 2)
            if ver != 5:
                return
            _recv_exact(c, n)
            c.sendall(b"\x05\x00")
            ver, cmd, _, atyp = _recv_exact(c, 4)
            if cmd != 1:
                c.sendall(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")      # only CONNECT (TCP); UDP is not tunnelled
                return
            if atyp == 1:
                host = socket.inet_ntoa(_recv_exact(c, 4))
            elif atyp == 3:
                host = _recv_exact(c, _recv_exact(c, 1)[0]).decode("utf-8", "replace")        # browsers send punycode (ASCII)
            else:
                host = socket.inet_ntop(socket.AF_INET6, _recv_exact(c, 16))
            port = struct.unpack(">H", _recv_exact(c, 2))[0]
            local = is_local_address(host)
            if self.block_all and not local:
                self.refused += 1
                c.sendall(b"\x05\x02\x00\x01\x00\x00\x00\x00\x00\x00")      # "not allowed by ruleset"
                return
            try:
                remote = open_upstream(None if local else self.upstream, host, port)
            except Exception:
                c.sendall(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")      # connection refused
                return
            c.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            c.settimeout(None)
            self._relay(c, remote)
        except Exception:
            pass
        finally:
            for s in (c, remote):
                try:
                    if s:
                        s.close()
                except Exception:
                    pass

    def _relay(self, a, b):
        socks = [a, b]
        while True:
            try:
                r, _, x = select.select(socks, [], socks, 120)
            except Exception:
                return
            if x or not r:
                return
            for s in r:
                try:
                    data = s.recv(65536)
                except Exception:
                    return
                if not data:
                    return
                other = b if s is a else a
                try:
                    other.sendall(data)
                except Exception:
                    return
                if s is a:
                    self.bytes_up += len(data)
                else:
                    self.bytes_down += len(data)


# ───────────────────────────── WireGuard / Tor helpers ─────────────────────────────
_B64 = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_FORBIDDEN = ("postup", "predown", "postdown", "preup", "table", "saveconfig")


def parse_wireguard(text):
    """Validate a wg-quick .conf and return (clean_text, info). Raises ValueError with a friendly message."""
    section, kv_if, kv_peer, out = None, {}, {}, []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            section = line.strip("[]").strip().lower()
            if section not in ("interface", "peer"):
                raise ValueError("unknown section [%s]" % section)
            out.append("[%s]" % section.capitalize())
            continue
        if "=" not in line or section is None:
            raise ValueError("cannot read the line: %s" % line[:40])
        k, v = [x.strip() for x in line.split("=", 1)]
        if k.lower() in _FORBIDDEN:
            continue                                     # wg-quick scripts could run programs: never copied
        (kv_if if section == "interface" else kv_peer)[k.lower()] = v
        out.append("%s = %s" % (k, v))
    if not _B64.match(kv_if.get("privatekey", "")):
        raise ValueError("the [Interface] PrivateKey is missing or not valid")
    if not _B64.match(kv_peer.get("publickey", "")):
        raise ValueError("the [Peer] PublicKey is missing or not valid")
    ep = kv_peer.get("endpoint", "")
    if not re.match(r"^[^\s:]+:\d{1,5}$|^\[[0-9a-fA-F:]+\]:\d{1,5}$", ep):
        raise ValueError("the [Peer] Endpoint must look like host:port")
    if "address" not in kv_if:
        raise ValueError("the [Interface] Address is missing")
    host, _, port = ep.rpartition(":")
    return "\n".join(out) + "\n", {"endpoint": ep, "host": host.strip("[]"), "port": int(port)}


class Tunnel:
    """One running helper process that exposes a local SOCKS5 port."""

    def __init__(self, profile, workdir, log=None):
        self.p, self.workdir, self.proc, self.port = profile, workdir, None, 0
        self._log = log or (lambda m: None)
        self.error = ""

    def start(self, helper_dirs=()):
        kind = self.p["kind"]
        self.port = free_port()
        if kind == "wireguard":
            exe = ensure_helper("wireproxy", helper_dirs, self._log)
            conf = os.path.join(self.workdir, "wp_%d.conf" % self.port)
            fd = os.open(conf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(self.p["conf"].rstrip() + "\n\n[Socks5]\nBindAddress = 127.0.0.1:%d\n" % self.port)
            self.conf = conf
            cmd = [exe, "-c", conf, "-s"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            if not wait_port(self.port, 15, self.proc):
                self.stop()
                raise RuntimeError("The WireGuard tunnel did not start (check the config).")
        elif kind == "tor":
            exe = ensure_helper("tor", helper_dirs, self._log)
            data = os.path.join(self.workdir, "tor_data")
            os.makedirs(data, exist_ok=True)
            cmd = [exe, "--SocksPort", "127.0.0.1:%d" % self.port, "--DataDirectory", data, "--ClientOnly", "1",
                   "--AvoidDiskWrites", "1", "--Log", "notice stdout"]
            geo = os.path.join(os.path.dirname(exe), "..", "data", "geoip")
            if os.path.isfile(geo):
                cmd += ["--GeoIPFile", geo, "--GeoIPv6File", geo + "6"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW,
                                         cwd=os.path.dirname(exe))
            ok = False
            end = time.time() + 120
            while time.time() < end and self.proc.poll() is None:
                line = self.proc.stdout.readline().decode("utf-8", "replace")
                if "Bootstrapped 100%" in line:
                    ok = True
                    break
            if not ok:
                self.stop()
                raise RuntimeError("Tor could not connect (is the internet blocked here?).")
            threading.Thread(target=lambda: [None for _ in iter(self.proc.stdout.readline, b"")], daemon=True).start()
        else:
            raise RuntimeError("unknown server type")
        return {"kind": "socks5", "host": "127.0.0.1", "port": self.port}

    def alive(self):
        return self.proc is None or self.proc.poll() is None

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        for f in [getattr(self, "conf", None)]:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except OSError:
                pass


# ───────────────────────────── profiles + manager ─────────────────────────────
class Store:
    def __init__(self, base=None):
        self.dir = vpn_dir(base)
        self.path = os.path.join(self.dir, "servers.json")
        self.data = {"servers": [], "enabled": False, "autoconnect": False, "killswitch": True, "last": ""}
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                self.data.update(d)
        except Exception:
            pass

    def save(self):
        tmp = self.path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)      # contains keys: owner-only file
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1)
        os.replace(tmp, self.path)

    def add(self, server):
        server["id"] = "%08x" % random.getrandbits(32)
        self.data["servers"].append(server)
        self.save()
        return server

    def remove(self, sid):
        self.data["servers"] = [s for s in self.data["servers"] if s["id"] != sid]
        self.save()

    def get(self, sid):
        for s in self.data["servers"]:
            if s["id"] == sid:
                return s


class VpnManager:
    """State machine: off -> connecting -> connected | error.  Safe to call from any thread."""

    def __init__(self, base=None, helper_dirs=()):
        self.store = Store(base)
        self.gw = Gateway()
        self.helper_dirs = helper_dirs
        self.state = "off"
        self.message = "Not connected - your own IP address is used."
        self.server = None
        self.exit = ("", "", 0)
        self.tunnel = None
        self._lock = threading.Lock()
        self._watch = None
        self._gen = 0

    # -- lifecycle --
    def start_gateway(self):
        if not self.gw.port:
            self.gw.start()
        self.gw.block_all = False
        return self.gw.port

    def browser_flags(self):
        """Chromium flags that make the browser use the gateway (only when VPN support is switched on)."""
        if not self.store.data.get("enabled"):
            return []
        port = self.start_gateway()
        return ["--proxy-server=socks5://127.0.0.1:%d" % port, "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--disable-quic"]

    def connect(self, server):
        """Blocking (run it in a thread). Returns True on success."""
        with self._lock:
            self._gen += 1
            gen = self._gen
            self._teardown(keep_block=self.store.data.get("killswitch", True))
            self.state, self.server, self.message = "connecting", server, "Connecting to %s…" % server["name"]
            try:
                if server["kind"] in ("socks5", "http"):
                    up = {"kind": server["kind"], "host": server["host"], "port": int(server["port"]),
                          "user": server.get("user"), "password": server.get("password")}
                else:
                    self.tunnel = Tunnel(server, self.store.dir)
                    up = self.tunnel.start(self.helper_dirs)
                ip, loc, ms = exit_info(up)
            except Exception as e:
                self._teardown(keep_block=self.store.data.get("killswitch", True))
                self.state, self.message = "error", "Could not connect: %s" % e
                return False
            self.gw.upstream = up
            self.gw.block_all = False
            self.exit = (ip, loc, ms)
            self.state, self.message = "connected", "Connected to %s  (exit %s, %s, %d ms)" % (server["name"], ip, loc, ms)
            self.store.data["last"] = server["id"]
            self.store.save()
            self._watch = threading.Thread(target=self._watchdog, args=(gen,), daemon=True)
            self._watch.start()
            return True

    def disconnect(self):
        with self._lock:
            self._gen += 1
            self._teardown(keep_block=False)
            self.state, self.server, self.message = "off", None, "Not connected - your own IP address is used."
            self.exit = ("", "", 0)

    def _teardown(self, keep_block):
        self.gw.upstream = None
        self.gw.block_all = bool(keep_block and self.store.data.get("enabled"))
        if self.tunnel:
            self.tunnel.stop()
            self.tunnel = None
        if not keep_block:
            self.gw.block_all = False

    def _watchdog(self, gen):
        while True:
            time.sleep(2)
            if gen != self._gen:
                return
            t = self.tunnel
            if t is not None and not t.alive():
                with self._lock:
                    if gen != self._gen:
                        return
                    self.gw.upstream = None
                    self.gw.block_all = bool(self.store.data.get("killswitch", True))
                    self.state = "error"
                    self.message = "The connection was lost. %s" % (
                        "Internet access from the browser is BLOCKED (kill switch)." if self.gw.block_all else "Your own IP is used again.")
                return

    # -- auto selection --
    def test_server(self, server):
        """Latency in ms through that server (or None). Opens a temporary tunnel; never touches the live connection."""
        tun = None
        try:
            if server["kind"] in ("socks5", "http"):
                up = {"kind": server["kind"], "host": server["host"], "port": int(server["port"]),
                      "user": server.get("user"), "password": server.get("password")}
            else:
                tun = Tunnel(server, self.store.dir)
                up = tun.start(self.helper_dirs)
            return exit_info(up)[2]
        except Exception:
            return None
        finally:
            if tun:
                tun.stop()

    def auto_connect(self, progress=None):
        """Try the saved servers, fastest-known first (Tor last); connect to the first that works."""
        servers = list(self.store.data["servers"])
        servers.sort(key=lambda s: (s["kind"] == "tor", s.get("last_ms") or 99999))
        for s in servers:
            if progress:
                progress("Trying %s…" % s["name"])
            if self.connect(s):
                return True
        return False


def make_server(kind, name, **kw):
    s = {"kind": kind, "name": name or kind}
    s.update(kw)
    return s
