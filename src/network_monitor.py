"""
╔══════════════════════════════════════════════════════════════════╗
║  SPS SANDBOX — Network Monitor  v1.0                             ║
║  Watches all network connections made by the browser process     ║
╚══════════════════════════════════════════════════════════════════╝

Tracks:
  - Every new domain/IP the browser connects to
  - Alerts sandbox when a NEW domain appears (user must allow)
  - Blocks known malware/tracker IPs (optional blocklist)
  - Logs all connections to audit file

How it works:
  Uses psutil to poll the browser process's network connections.
  When a new remote IP appears that the user hasn't allowed yet,
  it emits a permission_needed signal for the sandbox controller.
"""

import os
import sys
import time
import json
import socket
import threading
from pathlib import Path
from typing import Optional, Set, Dict, Callable
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None


# ══════════════════════════════════════════════════════════════════
#  BUILT-IN BLOCKLIST  (known malware / tracker domains/IPs)
# ══════════════════════════════════════════════════════════════════

# Extend this list — these are always blocked without asking
ALWAYS_BLOCK_DOMAINS = {
    # Known malware C&C patterns (examples)
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "facebook.com",    # remove if user uses Facebook
    "connect.facebook.net",
    "analytics.google.com",
    "google-analytics.com",
    "hotjar.com",
    "mouseflow.com",
    "fullstory.com",
    "loggly.com",
    # Add more as needed
}

# IPs that are always allowed (localhost, LAN, sandbox IPC)
ALWAYS_ALLOW_IPS = {
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "localhost",
}


# ══════════════════════════════════════════════════════════════════
#  REVERSE DNS CACHE
# ══════════════════════════════════════════════════════════════════

class ReverseDNSCache:
    """Caches IP → hostname lookups so we don't spam DNS."""

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._lock = threading.Lock()

    def lookup(self, ip: str) -> str:
        with self._lock:
            if ip in self._cache:
                return self._cache[ip]
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = ip
        with self._lock:
            self._cache[ip] = hostname
        return hostname


# ══════════════════════════════════════════════════════════════════
#  CONNECTION LOG
# ══════════════════════════════════════════════════════════════════

class ConnectionLog:
    LOG_FILE = Path.home() / ".sps_sandbox" / "connections.log"

    def __init__(self):
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._entries = []

    def record(self, ip: str, port: int, hostname: str,
                status: str, decision: str):
        entry = {
            "time":     datetime.now().isoformat(timespec="seconds"),
            "ip":       ip,
            "port":     port,
            "hostname": hostname,
            "status":   status,
            "decision": decision,
        }
        self._entries.append(entry)
        try:
            with open(self.LOG_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
        return entry

    def recent(self, n=100):
        return list(reversed(self._entries[-n:]))

    def all(self):
        return list(self._entries)


# ══════════════════════════════════════════════════════════════════
#  NETWORK MONITOR THREAD
# ══════════════════════════════════════════════════════════════════

class NetworkMonitor(threading.Thread):
    """
    Polls psutil for new connections from the browser PID.
    Calls permission_callback when a new connection is found.

    permission_callback(ip, port, hostname) → bool
        True  = allowed
        False = (can't block after the fact via psutil, but it's logged)
    """

    def __init__(
        self,
        pid: int,
        permission_callback: Callable[[str, int, str], bool],
        conn_log: Optional[ConnectionLog] = None,
        poll_interval: float = 0.5,
    ):
        super().__init__(daemon=True)
        self.pid                 = pid
        self.permission_callback = permission_callback
        self.conn_log            = conn_log or ConnectionLog()
        self.poll_interval       = poll_interval

        self._stop_event  = threading.Event()
        self._seen_conns: Set[str]  = set()   # "ip:port" strings
        self._allowed:    Set[str]  = set()   # allowed hostnames/IPs
        self._denied:     Set[str]  = set()   # denied (just logged)
        self._dns         = ReverseDNSCache()

    def stop(self):
        self._stop_event.set()

    def run(self):
        if psutil is None:
            print("[NetworkMonitor] psutil not available — network monitoring disabled")
            return

        try:
            proc = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            print(f"[NetworkMonitor] Process {self.pid} not found")
            return

        print(f"[NetworkMonitor] Watching PID {self.pid}")

        while not self._stop_event.is_set():
            try:
                conns = proc.net_connections(kind="inet")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception:
                time.sleep(self.poll_interval)
                continue

            for conn in conns:
                if not conn.raddr:
                    continue
                ip   = conn.raddr.ip
                port = conn.raddr.port
                key  = f"{ip}:{port}"

                if key in self._seen_conns:
                    continue
                self._seen_conns.add(key)

                # Skip local/LAN
                if ip in ALWAYS_ALLOW_IPS or ip.startswith("192.168.") \
                        or ip.startswith("10.") or ip.startswith("172."):
                    self.conn_log.record(ip, port, ip, "LAN", "auto-allow")
                    continue

                # Resolve hostname
                hostname = self._dns.lookup(ip)

                # Check always-block list
                blocked = any(hostname.endswith(d) for d in ALWAYS_BLOCK_DOMAINS)
                if blocked:
                    print(f"[NetworkMonitor] BLOCKED (blocklist): {hostname} ({ip}:{port})")
                    self.conn_log.record(ip, port, hostname, "blocked", "blocklist")
                    self._denied.add(ip)
                    continue

                # Check already-allowed/denied
                if ip in self._allowed or hostname in self._allowed:
                    self.conn_log.record(ip, port, hostname, "established", "allow [cached]")
                    continue
                if ip in self._denied or hostname in self._denied:
                    self.conn_log.record(ip, port, hostname, "established", "deny [cached]")
                    continue

                # Ask user
                print(f"[NetworkMonitor] New connection: {hostname} ({ip}:{port})")
                try:
                    allowed = self.permission_callback(ip, port, hostname)
                except Exception as e:
                    print(f"[NetworkMonitor] Callback error: {e}")
                    allowed = False

                decision = "allow" if allowed else "deny"
                self.conn_log.record(ip, port, hostname, "established", decision)

                if allowed:
                    self._allowed.add(ip)
                    self._allowed.add(hostname)
                else:
                    self._denied.add(ip)
                    self._denied.add(hostname)
                    # Note: we can't actually block after connection is established
                    # via psutil. True blocking requires a firewall rule or proxy.
                    # The sandbox_firewall module handles that.

            time.sleep(self.poll_interval)

        print("[NetworkMonitor] Stopped")

    def get_stats(self) -> dict:
        return {
            "total_seen":    len(self._seen_conns),
            "allowed":       len(self._allowed),
            "denied":        len(self._denied),
            "recent_conns":  self.conn_log.recent(20),
        }


# ══════════════════════════════════════════════════════════════════
#  OPTIONAL: FIREWALL RULES  (actual blocking, requires admin)
# ══════════════════════════════════════════════════════════════════

class SandboxFirewall:
    """
    Adds/removes firewall rules to actually block outbound connections.
    Requires admin/root on both Windows and Linux.

    Windows: uses netsh advfirewall
    Linux:   uses iptables
    """

    def __init__(self, browser_pid: int):
        self.pid    = browser_pid
        self._rules = []  # track rules we added so we can remove them

    def block_ip(self, ip: str) -> bool:
        """Add a firewall rule to block this IP. Returns True if added."""
        if sys.platform == "win32":
            return self._block_ip_windows(ip)
        elif sys.platform.startswith("linux"):
            return self._block_ip_linux(ip)
        return False

    def _block_ip_windows(self, ip: str) -> bool:
        import subprocess
        rule_name = f"SPS_SANDBOX_BLOCK_{ip.replace('.','_')}"
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}",
            "dir=out", "action=block",
            f"remoteip={ip}",
            "enable=yes",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self._rules.append(("windows", rule_name))
                print(f"[Firewall] Blocked IP {ip} via Windows Firewall")
                return True
            else:
                print(f"[Firewall] Failed to block {ip}: {result.stderr}")
                return False
        except Exception as e:
            print(f"[Firewall] Error: {e} (need admin?)")
            return False

    def _block_ip_linux(self, ip: str) -> bool:
        import subprocess
        cmd = ["iptables", "-A", "OUTPUT",
               "-d", ip, "-p", "tcp",
               "-j", "DROP"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self._rules.append(("linux", ip))
                print(f"[Firewall] Blocked IP {ip} via iptables")
                return True
            else:
                print(f"[Firewall] iptables failed: {result.stderr}")
                print("[Firewall] Try running sandbox as root for actual blocking")
                return False
        except Exception as e:
            print(f"[Firewall] Error: {e}")
            return False

    def unblock_all(self):
        """Remove all firewall rules added by this sandbox session."""
        for rule_type, rule_id in self._rules:
            try:
                if rule_type == "windows":
                    import subprocess
                    subprocess.run([
                        "netsh", "advfirewall", "firewall", "delete", "rule",
                        f"name={rule_id}"
                    ], capture_output=True)
                    print(f"[Firewall] Removed Windows rule: {rule_id}")
                elif rule_type == "linux":
                    import subprocess
                    subprocess.run([
                        "iptables", "-D", "OUTPUT",
                        "-d", rule_id, "-p", "tcp", "-j", "DROP"
                    ], capture_output=True)
                    print(f"[Firewall] Removed iptables rule for: {rule_id}")
            except Exception as e:
                print(f"[Firewall] Could not remove rule: {e}")
        self._rules.clear()


if __name__ == "__main__":
    print("Network Monitor — standalone test")
    print(f"psutil available: {psutil is not None}")

    def fake_callback(ip, port, hostname):
        print(f"  → Permission needed: {hostname} ({ip}:{port})")
        return True  # auto-allow in test

    log = ConnectionLog()
    mon = NetworkMonitor(os.getpid(), fake_callback, log)
    mon.start()
    print("Monitoring this process for 5 seconds...")
    time.sleep(5)
    mon.stop()
    print("Stats:", mon.get_stats())
