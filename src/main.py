import sys
import os
import json
import urllib.request
import urllib.error

# Ensure src/ is on the path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview

from pathlib import Path
from fake_handy.server import FakeHandyServer
from funscript.live_bridge import LiveBridge
from ui.sidebar_html import SIDEBAR_HTML
from config import FAKE_HANDY_HOST, FAKE_HANDY_PORT, RESTIM_WS_URL, SITES


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
            self._app._log(f"Settings-Fehler: {e}")

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

    def set_site(self, site):
        if site not in SITES or site == self._app._current_site:
            return False
        self._app._current_site = site
        try:
            if self._app._browser_window:
                self._app._browser_window.load_url(SITES[site])
            self._app._log(f"Site gewechselt zu {site}")
        except Exception as e:
            self._app._log(f"Site-Wechsel Fehler: {e}")
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
        self._current_site = os.environ.get("SITE", "faptap").lower()
        if self._current_site not in SITES:
            self._current_site = "faptap"

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
        # Restore saved settings
        self._sidebar_eval("loadSavedSettings()")
        self._log("Fake Handy Server gestartet")

    def _on_browser_loaded(self):
        try:
            self._browser_window.evaluate_js(self._redirect_js)
            self._browser_window.evaluate_js(self._serial_js)
            self._browser_window.evaluate_js(self._fullscreen_js)
            self._log("JS-Injection: Redirect + Serial + Fullscreen")
        except Exception as e:
            self._log(f"JS-Injection Fehler: {e}")

    def _on_funscript(self, data):
        json_str = json.dumps(data)
        escaped = json_str.replace("\\", "\\\\").replace("'", "\\'")
        self._sidebar_eval(f"showFunscript('{escaped}')")

    def _on_playback(self, event, data):
        if event == "play":
            self._log(f"Playback gestartet (start={data.get('startTime', 0)}ms)")
        elif event == "stop":
            self._log("Playback gestoppt")

    # ── Helpers ────────────────────────────────────────────────────

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
