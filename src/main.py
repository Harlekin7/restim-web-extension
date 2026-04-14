import sys
import os
import json

# Ensure src/ is on the path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview

from pathlib import Path
from fake_handy.server import FakeHandyServer
from ui.sidebar_html import SIDEBAR_HTML
from config import FAKE_HANDY_HOST, FAKE_HANDY_PORT, FAPTAP_URL, RESTIM_WS_URL


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


class SidebarAPI:
    """Python API exposed to the sidebar window via pywebview.api."""

    def __init__(self, app):
        self._app = app
        self._settings_path = str(Path(__file__).parent.parent / "data" / "settings.json")

    def update_settings(self, json_str):
        """Called from sidebar JS when a slider/input changes."""
        try:
            data = json.loads(json_str)
            if self._app._server:
                self._app._server.update_settings(data)
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

        # Load JS injection code
        inject_dir = Path(__file__).parent / "injection"
        self._redirect_js = (inject_dir / "redirect.js").read_text(encoding="utf-8")
        self._redirect_js = self._redirect_js.replace("{{HOST}}", FAKE_HANDY_HOST)
        self._redirect_js = self._redirect_js.replace("{{PORT}}", str(FAKE_HANDY_PORT))

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
            title="Restim - Browser",
            url=FAPTAP_URL,
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
        # Restore saved settings
        self._sidebar_eval("loadSavedSettings()")
        self._log("Fake Handy Server gestartet")

    def _on_browser_loaded(self):
        try:
            self._browser_window.evaluate_js(self._redirect_js)
            self._browser_window.evaluate_js(self._fullscreen_js)
            self._log("JS-Redirect + Fullscreen injiziert")
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
