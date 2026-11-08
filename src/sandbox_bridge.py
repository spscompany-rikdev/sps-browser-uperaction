"""
╔══════════════════════════════════════════════════════════════════╗
║  SPS SANDBOX BRIDGE  v1.0                                        ║
║  Injected into / imported by the SPS Browser                     ║
║  Communicates with sandbox_launcher.py via a local socket        ║
╚══════════════════════════════════════════════════════════════════╝

Usage: place this file next to SPS_BROWSER.py
The browser can optionally import it; the sandbox auto-patches
the environment so the bridge is loaded automatically.

Standalone use:
    from sandbox_bridge import SandboxBridge, ask_permission

    # returns True  = user allowed
    # returns False = user denied
    allowed = ask_permission("camera", "https://meet.example.com", "Front camera")
"""

import os
import sys
import json
import socket
import threading
import time
from typing import Optional

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

BRIDGE_HOST    = "127.0.0.1"
BRIDGE_PORT    = 47291          # arbitrary local port
BRIDGE_TIMEOUT = 60.0           # seconds to wait for user decision

# Are we running inside the sandbox?
INSIDE_SANDBOX = os.environ.get("SPS_SANDBOX") == "1"


# ══════════════════════════════════════════════════════════════════
#  CLIENT SIDE  (used by the browser)
# ══════════════════════════════════════════════════════════════════

class SandboxBridge:
    """
    Used by the browser to communicate with the sandbox controller.
    Falls back to 'always allow' if sandbox is not running.
    """

    _instance = None

    @classmethod
    def get(cls) -> "SandboxBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._connected = False
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        if INSIDE_SANDBOX:
            self._try_connect()

    def _try_connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((BRIDGE_HOST, BRIDGE_PORT))
            s.settimeout(BRIDGE_TIMEOUT)
            self._sock = s
            self._connected = True
            print(f"[SandboxBridge] Connected to sandbox controller.")
        except Exception as e:
            print(f"[SandboxBridge] Could not connect to sandbox: {e}")
            self._connected = False

    def ask(self, perm_type: str, origin: str, detail: str = "") -> bool:
        """
        Ask the sandbox controller for permission.
        Returns True if allowed, False if denied.
        If sandbox is not active, returns True (normal mode).
        """
        if not INSIDE_SANDBOX or not self._connected:
            return True  # not sandboxed — allow everything

        msg = json.dumps({
            "action":    "request_permission",
            "perm_type": perm_type,
            "origin":    origin,
            "detail":    detail,
        }) + "\n"

        with self._lock:
            try:
                self._sock.sendall(msg.encode("utf-8"))
                # Wait for response
                buf = ""
                while True:
                    chunk = self._sock.recv(4096).decode("utf-8")
                    if not chunk:
                        break
                    buf += chunk
                    if "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        resp = json.loads(line)
                        return resp.get("allowed", False)
            except Exception as e:
                print(f"[SandboxBridge] Communication error: {e}")
                # If connection broke, try to reconnect
                self._try_connect()
                return False  # deny on error


# ── Module-level convenience function ─────────────────────────────

_bridge: Optional[SandboxBridge] = None

def ask_permission(perm_type: str, origin: str, detail: str = "") -> bool:
    """
    Module-level function for quick one-off permission checks.
    Example:
        from sandbox_bridge import ask_permission
        if ask_permission("camera", current_url):
            start_camera()
    """
    global _bridge
    if _bridge is None:
        _bridge = SandboxBridge.get()
    return _bridge.ask(perm_type, origin, detail)


# ══════════════════════════════════════════════════════════════════
#  SERVER SIDE  (runs inside sandbox_launcher.py)
# ══════════════════════════════════════════════════════════════════

class BridgeServer:
    """
    TCP server that listens for permission requests from the browser.
    Runs inside sandbox_launcher.py.
    """

    def __init__(self, controller):
        self.controller = controller
        self._server: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((BRIDGE_HOST, BRIDGE_PORT))
        self._server.listen(5)
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        print(f"[BridgeServer] Listening on {BRIDGE_HOST}:{BRIDGE_PORT}")

    def stop(self):
        self._running = False
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server.accept()
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn,),
                    daemon=True
                )
                t.start()
            except Exception:
                break

    def _handle_client(self, conn: socket.socket):
        buf = ""
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    try:
                        req = json.loads(line)
                        if req.get("action") == "request_permission":
                            allowed = self.controller.request_permission(
                                req.get("perm_type", "unknown"),
                                req.get("origin", "unknown"),
                                req.get("detail", ""),
                            )
                            resp = json.dumps({"allowed": allowed}) + "\n"
                            conn.sendall(resp.encode("utf-8"))
                    except Exception as e:
                        print(f"[BridgeServer] Error handling request: {e}")
        finally:
            conn.close()


# ══════════════════════════════════════════════════════════════════
#  PERMISSION HOOK DECORATORS  (wrap sensitive functions)
# ══════════════════════════════════════════════════════════════════

def sandboxed(perm_type: str, origin_arg: int = 0, detail_fn=None):
    """
    Decorator that wraps a function with a sandbox permission check.

    Example:
        @sandboxed("camera")
        def start_camera(url):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            origin = args[origin_arg] if args else "unknown"
            detail = detail_fn(*args, **kwargs) if detail_fn else ""
            if not ask_permission(perm_type, str(origin), detail):
                print(f"[Sandbox] BLOCKED: {perm_type} from {origin}")
                return None  # blocked
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__  = func.__doc__
        return wrapper
    return decorator


if __name__ == "__main__":
    # Quick test
    print("SandboxBridge standalone test")
    print(f"INSIDE_SANDBOX = {INSIDE_SANDBOX}")
    if not INSIDE_SANDBOX:
        print("Not inside sandbox. ask_permission() will always return True.")
    result = ask_permission("camera", "https://test.example.com", "Test camera")
    print(f"Camera permission: {result}")
