import sys
import os
import json
import urllib.request
import urllib.error

# Ensure src/ is on the path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import socket

import webview

from pathlib import Path
from fake_handy.server import FakeHandyServer
from funscript.live_bridge import LiveBridge
from proxy.server import ProxyServer
from ui.sidebar_html import SIDEBAR_HTML
from config import (
    DEFAULT_NETWORK_TARGET,
    FAKE_HANDY_HOST,
    FAKE_HANDY_PORT,
    NETWORK_PROXY_HOST,
    NETWORK_PROXY_PORT,
    NETWORK_TARGETS,
    NETWORK_TARGET_LABELS,
    RESTIM_WS_URL,
    SITES,
)


def _lan_ip() -> str:
    """Best-effort detection of the host's LAN IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _resource_dir():
    """Directory holding bundled resources (injection JS files etc.)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "src"
    return Path(__file__).parent


def _user_data_dir():
    """Writable directory for runtime state (settings, cache)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).parent.parent / "data"


class BrowserAPI:
    """Python API exposed to the browser window via pywebview.api."""

    def __init__(self, app):
        self._app = app
        self._is_fullscreen = False

    def set_fullscreen(self, enter):
        w = self._app._browser_window
        if not w:
            return
        if enter and not self._is_fullscreen:
            self._is_fullscreen = True
            w.toggle_fullscreen()
        elif not enter and self._is_fullscreen:
            self._is_fullscreen = False
            w.toggle_fullscreen()

    def tcode_write(self, text):
        """Called from the browser's patched navigator.serial when theedgy
        writes T-Code bytes to the fake port. Forwarded to the live bridge.
        """
        bridge = self._app._live_bridge
        if bridge:
            bridge.write(text)

    def handy_call(self, method, path, body=None):
        """Proxy a Handy API call from the browser through Python.

        Needed because sites like theedgy.app use a Content Security Policy
        that blocks direct fetches to 127.0.0.1. We route requests through
        the pywebview JS bridge and re-issue them from Python, where CSP
        does not apply.
        """
        url = f"http://{FAKE_HANDY_HOST}:{FAKE_HANDY_PORT}{path}"
        data = None
        if body:
            data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {
                    "status": resp.status,
                    "body": resp.read().decode("utf-8", errors="replace"),
                }
        except urllib.error.HTTPError as e:
            try:
                body_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""
            return {"status": e.code, "body": body_text}
        except Exception as e:
            return {"status": 0, "body": json.dumps({"error": str(e)})}


class SidebarAPI:
    """Python API exposed to the sidebar window via pywebview.api."""

    def __init__(self, app):
        self._app = app
        self._settings_path = str(_user_data_dir() / "settings.json")

    def update_settings(self, json_str):
        """Called from sidebar JS when a slider/input changes."""
        try:
            data = json.loads(json_str)
            if self._app._server:
                self._app._server.update_settings(data)
            if self._app._live_bridge:
                self._app._live_bridge.update_settings(data)
            self._save(data)
        except Exception as e:
            self._app._log(f"Settings error: {e}")

    def load_settings(self):
        """Load saved settings. Returns JSON string or empty string."""
        try:
            p = Path(self._settings_path)
            if p.exists():
                return p.read_text(encoding="utf-8")
        except Exception:
            pass
        return ""

    def get_site(self):
        return self._app._current_site

    def get_network_target(self):
        return self._app._network_target

    def set_network_target(self, target):
        if target not in NETWORK_TARGETS or target == self._app._network_target:
            return False
        self._app._network_target = target
        self._app._proxy.set_upstream(NETWORK_TARGETS[target])
        # If we're currently in network mode, refresh the info page so the
        # label reflects the new target.
        if self._app._current_site == "network" and self._app._browser_window:
            try:
                self._app._browser_window.load_html(self._app._network_info_html())
            except Exception:
                pass
        return True

    def set_site(self, site):
        if site not in SITES or site == self._app._current_site:
            return False
        old = self._app._current_site
        self._app._current_site = site
        try:
            # Manage proxy lifecycle when entering/leaving network mode.
            if site == "network":
                self._app._proxy.start()
            elif old == "network":
                self._app._proxy.stop()

            if self._app._browser_window:
                if site == "network":
                    html = self._app._network_info_html()
                    self._app._browser_window.load_html(html)
                else:
                    self._app._browser_window.load_url(SITES[site])
            self._app._log(f"Site switched to {site}")
        except Exception as e:
            self._app._log(f"Site switch error: {e}")
            return False
        return True

    def _save(self, data):
        try:
            p = Path(self._settings_path)
            p.parent.mkdir(exist_ok=True)
            p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass


class App:
    def __init__(self):
        self._sidebar_window = None
        self._browser_window = None
        self._server = None
        self._live_bridge = None
        self._proxy = None
        self._lan_ip = _lan_ip()
        self._current_site = os.environ.get("SITE", "faptap").lower()
        if self._current_site not in SITES:
            self._current_site = "faptap"
        self._network_target = os.environ.get("NETWORK_TARGET", DEFAULT_NETWORK_TARGET).lower()
        if self._network_target not in NETWORK_TARGETS:
            self._network_target = DEFAULT_NETWORK_TARGET

        # Load JS injection code
        inject_dir = _resource_dir() / "injection"
        self._redirect_js = (inject_dir / "redirect.js").read_text(encoding="utf-8")
        self._redirect_js = self._redirect_js.replace("{{HOST}}", FAKE_HANDY_HOST)
        self._redirect_js = self._redirect_js.replace("{{PORT}}", str(FAKE_HANDY_PORT))

        self._serial_js = (inject_dir / "serial.js").read_text(encoding="utf-8")
        self._fullscreen_js = (inject_dir / "fullscreen.js").read_text(encoding="utf-8")

    def run(self):
        # Create both windows before starting
        self._sidebar_api = SidebarAPI(self)
        self._sidebar_window = webview.create_window(
            title="Restim - Steuerung",
            html=SIDEBAR_HTML,
            width=380,
            height=900,
            resizable=True,
            on_top=False,
            js_api=self._sidebar_api,
        )

        self._browser_api = BrowserAPI(self)
        if self._current_site == "network":
            self._browser_window = webview.create_window(
                title="Restim - Browser (network)",
                html=self._network_info_html(),
                width=1100,
                height=900,
                resizable=True,
                js_api=self._browser_api,
            )
        else:
            self._browser_window = webview.create_window(
                title=f"Restim - Browser ({self._current_site})",
                url=SITES[self._current_site],
                width=1100,
                height=900,
                resizable=True,
                js_api=self._browser_api,
            )

        # Start fake Handy server with player
        self._server = FakeHandyServer(
            host=FAKE_HANDY_HOST,
            port=FAKE_HANDY_PORT,
            restim_url=RESTIM_WS_URL,
            on_log=self._log,
            on_funscript=self._on_funscript,
            on_playback=self._on_playback,
        )
        self._server.start()

        # Live bridge (for sites that stream T-Code via WebSerial, e.g. theedgy.app)
        self._live_bridge = LiveBridge(
            restim_url=RESTIM_WS_URL,
            on_log=self._log,
        )
        self._live_bridge.start()

        # Reverse proxy (started on demand when "network" site is active)
        self._proxy = ProxyServer(
            host=NETWORK_PROXY_HOST,
            port=NETWORK_PROXY_PORT,
            handy_host=FAKE_HANDY_HOST,
            handy_port=FAKE_HANDY_PORT,
            upstream=NETWORK_TARGETS[self._network_target],
            on_log=self._log,
        )
        if self._current_site == "network":
            self._proxy.start()

        # pywebview events
        self._browser_window.events.loaded += self._on_browser_loaded
        self._sidebar_window.events.loaded += self._on_sidebar_loaded

        # Start the GUI (blocks until all windows closed)
        webview.start(debug=False, gui="edgechromium")

    # ── Events ─────────────────────────────────────────────────────

    def _on_sidebar_loaded(self):
        self._sidebar_eval(
            f"setServerStatus('{FAKE_HANDY_HOST}:{FAKE_HANDY_PORT}', true)"
        )
        self._sidebar_eval(f"setActiveSite('{self._current_site}')")
        self._sidebar_eval(f"setActiveTarget('{self._network_target}')")
        # Restore saved settings
        self._sidebar_eval("loadSavedSettings()")
        self._log("Fake Handy Server started")

    def _on_browser_loaded(self):
        if self._current_site == "network":
            return  # static info page, no JS injection needed
        try:
            self._browser_window.evaluate_js(self._redirect_js)
            self._browser_window.evaluate_js(self._serial_js)
            self._browser_window.evaluate_js(self._fullscreen_js)
            self._log("JS injection: Redirect + Serial + Fullscreen")
        except Exception as e:
            self._log(f"JS injection error: {e}")

    def _on_funscript(self, data):
        json_str = json.dumps(data)
        escaped = json_str.replace("\\", "\\\\").replace("'", "\\'")
        self._sidebar_eval(f"showFunscript('{escaped}')")

    def _on_playback(self, event, data):
        if event == "play":
            self._log(f"Playback started (start={data.get('startTime', 0)}ms)")
        elif event == "stop":
            self._log("Playback stopped")

    # ── Helpers ────────────────────────────────────────────────────

    def _network_info_html(self) -> str:
        url = f"http://{self._lan_ip}:{NETWORK_PROXY_PORT}"
        target_label = NETWORK_TARGET_LABELS.get(self._network_target, self._network_target)
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Network mode</title>"
            "<style>"
            "body{background:#1e1e1e;color:#ddd;font-family:Segoe UI,Tahoma,sans-serif;"
            "display:flex;align-items:center;justify-content:center;height:100vh;margin:0;padding:24px;}"
            ".card{max-width:640px;text-align:center;}"
            "h1{color:#5a8;font-size:22px;margin-bottom:16px;}"
            ".target{color:#7af;font-weight:600;}"
            "code{background:#2d2d2d;color:#7af;padding:8px 14px;border-radius:6px;"
            "font-size:24px;display:inline-block;margin:8px 0;font-family:Consolas,monospace;}"
            "p{line-height:1.6;color:#bbb;font-size:14px;}"
            "small{color:#888;font-size:12px;}"
            "</style></head><body><div class='card'>"
            "<h1>Network mode active</h1>"
            f"<p>Active site: <span class='target'>{target_label}</span><br>"
            "(Switch via the picker in the sidebar.)</p>"
            "<p>Open this URL on the device on your home network "
            "(phone, VR headset, laptop):</p>"
            f"<code>{url}</code>"
            f"<p>The reverse proxy serves {target_label} through this PC and "
            "intercepts the Handy API calls. Funscripts are streamed to Restim "
            "running on this machine.</p>"
            "<small>Cloudflare bot detection can block the proxy - "
            "if the site doesn't load, check the sidebar log.</small>"
            "</div></body></html>"
        )

    def _log(self, msg):
        escaped = msg.replace("\\", "\\\\").replace("'", "\\'")
        self._sidebar_eval(f"appendLog('{escaped}')")

    def _sidebar_eval(self, js):
        try:
            if self._sidebar_window:
                self._sidebar_window.evaluate_js(js)
        except Exception:
            pass


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
