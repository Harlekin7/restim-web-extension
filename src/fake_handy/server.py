import asyncio
import json
import threading
import time

import aiohttp
from aiohttp import web

from funscript.player import FunscriptPlayer


class FakeHandyServer:
    """Fake Handy Cloud API server that mimics handyfeeling.com/api/handy/v2."""

    def __init__(self, host, port, restim_url="ws://127.0.0.1:12346/tcode",
                 on_log=None, on_funscript=None, on_playback=None):
        self.host = host
        self.port = port
        self._on_log = on_log or (lambda msg: None)
        self._on_funscript = on_funscript or (lambda data: None)
        self._on_playback = on_playback or (lambda event, data: None)
        self._thread = None
        self._loop = None

        # Player
        self._player = FunscriptPlayer(restim_url=restim_url, on_log=self._log)
        self._restim_url = restim_url

        # Device state
        self._mode = 0  # 0=HAMP, 1=HSSP, 2=HDSP
        self._hssp_state = 2  # 1=NEED_SYNC, 2=NEED_SETUP, 3=STOPPED, 4=PLAYING
        self._loop_enabled = False
        self._offset = 0
        self._slide_min = 0
        self._slide_max = 100
        self._script_url = None
        self._funscript_data = None

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            self._log(f"Server error: {e}")

    async def _serve(self):
        app = web.Application(middlewares=[self._cors_middleware])
        self._add_routes(app)

        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        self._log(f"Fake Handy Server running on {self.host}:{self.port}")

        # Run forever
        await asyncio.Event().wait()

    # ── Routes ─────────────────────────────────────────────────────

    def _add_routes(self, app):
        base = "/api/handy/v2"

        # Base endpoints
        app.router.add_get(f"{base}/connected", self._handle_connected)
        app.router.add_get(f"{base}/info", self._handle_info)
        app.router.add_get(f"{base}/settings", self._handle_settings)
        app.router.add_get(f"{base}/status", self._handle_status)
        app.router.add_put(f"{base}/mode", self._handle_set_mode)
        app.router.add_get(f"{base}/mode", self._handle_get_mode)

        # HSSP
        app.router.add_put(f"{base}/hssp/setup", self._handle_hssp_setup)
        app.router.add_put(f"{base}/hssp/play", self._handle_hssp_play)
        app.router.add_put(f"{base}/hssp/stop", self._handle_hssp_stop)
        app.router.add_get(f"{base}/hssp/state", self._handle_hssp_state)
        app.router.add_get(f"{base}/hssp/loop", self._handle_get_loop)
        app.router.add_put(f"{base}/hssp/loop", self._handle_set_loop)

        # HSTP
        app.router.add_get(f"{base}/hstp/time", self._handle_hstp_time)
        app.router.add_get(f"{base}/hstp/sync", self._handle_hstp_sync)
        app.router.add_get(f"{base}/hstp/offset", self._handle_get_offset)
        app.router.add_put(f"{base}/hstp/offset", self._handle_set_offset)
        app.router.add_get(f"{base}/hstp/rtd", self._handle_hstp_rtd)

        # Slide
        app.router.add_get(f"{base}/slide", self._handle_get_slide)
        app.router.add_put(f"{base}/slide", self._handle_set_slide)

        # Server time (used by some clients for RTD)
        app.router.add_get(f"{base}/servertime", self._handle_servertime)

        # HDSP (direct streaming – fallback)
        app.router.add_put(f"{base}/hdsp/xpt", self._handle_hdsp_xpt)
        app.router.add_put(f"{base}/hdsp/xpvp", self._handle_hdsp_xpvp)
        app.router.add_put(f"{base}/hdsp/xpva", self._handle_hdsp_xpva)
        app.router.add_put(f"{base}/hdsp/xava", self._handle_hdsp_xava)
        app.router.add_put(f"{base}/hdsp/xat", self._handle_hdsp_xat)

        # Catch-all for unknown v2 endpoints
        app.router.add_route("*", f"{base}/{{path:.*}}", self._handle_fallback)

        # v3 API (theedgy.app) — observation mode: log everything, respond plausibly
        for v3_base in ("/api/handy-rest/v3", "/api/handy/v3"):
            app.router.add_route("*", f"{v3_base}/{{path:.*}}", self._handle_v3)

    # ── CORS Middleware ────────────────────────────────────────────

    @web.middleware
    async def _cors_middleware(self, request, handler):
        if request.method == "OPTIONS":
            resp = web.Response(status=204)
        else:
            try:
                resp = await handler(request)
            except web.HTTPException as exc:
                resp = exc
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, PUT, POST, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = (
            "X-Connection-Key, Content-Type, Authorization, Accept"
        )
        resp.headers["Access-Control-Max-Age"] = "3600"
        return resp

    # ── Base Handlers ──────────────────────────────────────────────

    async def _handle_connected(self, request):
        key = request.headers.get("X-Connection-Key", "?")
        self._log(f"Connection check (key: {key})")
        return web.json_response({"connected": True})

    async def _handle_info(self, request):
        self._log("Device info requested")
        return web.json_response({
            "fwVersion": "3.2.3",
            "fwStatus": 0,
            "hwVersion": "1.0",
            "model": 1,
            "branch": "master",
            "sessionId": "restim-ext-0001",
        })

    async def _handle_settings(self, request):
        return web.json_response({
            "slideMin": self._slide_min,
            "slideMax": self._slide_max,
        })

    async def _handle_status(self, request):
        return web.json_response({
            "mode": self._mode,
            "state": self._hssp_state,
        })

    async def _handle_get_mode(self, request):
        return web.json_response({"mode": self._mode})

    async def _handle_set_mode(self, request):
        data = await request.json()
        self._mode = data.get("mode", 0)
        mode_names = {0: "HAMP", 1: "HSSP", 2: "HDSP", 3: "MAINTENANCE"}
        self._log(f"Mode set: {mode_names.get(self._mode, self._mode)}")
        return web.json_response({"result": 0})

    # ── HSSP Handlers ──────────────────────────────────────────────

    async def _handle_hssp_setup(self, request):
        data = await request.json()
        url = data.get("url", "")
        sha256 = data.get("sha256", "")
        self._script_url = url
        self._log(f"HSSP Setup - Script URL: {url[:80]}...")

        # Download the funscript
        script_data = await self._download_script(url)
        if script_data:
            self._funscript_data = script_data
            action_count = len(script_data.get("actions", []))
            actions = script_data.get("actions", [])
            duration_ms = actions[-1]["at"] if actions else 0
            duration_s = duration_ms / 1000
            mins, secs = divmod(int(duration_s), 60)
            self._log(
                f"Funscript received! {action_count} actions, "
                f"duration: {mins}:{secs:02d}"
            )
            self._on_funscript(script_data)

            # Pre-process for playback
            self._player.load(script_data)

            self._hssp_state = 3  # STOPPED (ready)
            return web.json_response({"result": 1})  # DOWNLOADED
        else:
            self._log("Funscript download failed!")
            self._hssp_state = 2  # NEED_SETUP
            return web.json_response({"result": -1})

    async def _handle_hssp_play(self, request):
        data = await request.json()
        est_server_time = data.get("estimatedServerTime", 0)
        start_time = data.get("startTime", 0)
        self._hssp_state = 4  # PLAYING
        self._log(f"HSSP Play - Start: {start_time}ms")
        self._on_playback("play", {
            "estimatedServerTime": est_server_time,
            "startTime": start_time,
        })

        # Start playback to Restim
        await self._player.play(start_time_ms=start_time)

        return web.json_response({"result": 0})

    async def _handle_hssp_stop(self, request):
        self._hssp_state = 3  # STOPPED
        self._log("HSSP Stop")
        self._on_playback("stop", {})

        # Stop playback
        await self._player.stop()

        return web.json_response({"result": 0})

    async def _handle_hssp_state(self, request):
        return web.json_response({"state": self._hssp_state})

    async def _handle_get_loop(self, request):
        return web.json_response({"activated": self._loop_enabled})

    async def _handle_set_loop(self, request):
        data = await request.json()
        self._loop_enabled = data.get("activated", False)
        return web.json_response({"result": 0})

    # ── HSTP Handlers ──────────────────────────────────────────────

    def _server_time_ms(self):
        return int(time.time() * 1000)

    async def _handle_hstp_time(self, request):
        return web.json_response({"time": self._server_time_ms()})

    async def _handle_hstp_sync(self, request):
        return web.json_response({
            "time": self._server_time_ms(),
            "rtd": 2,
        })

    async def _handle_get_offset(self, request):
        return web.json_response({"offset": self._offset})

    async def _handle_set_offset(self, request):
        data = await request.json()
        self._offset = data.get("offset", 0)
        return web.json_response({"result": 0})

    async def _handle_hstp_rtd(self, request):
        return web.json_response({"rtd": 2})

    async def _handle_servertime(self, request):
        return web.json_response({"serverTime": self._server_time_ms()})

    # ── Slide Handlers ─────────────────────────────────────────────

    async def _handle_get_slide(self, request):
        return web.json_response({
            "min": self._slide_min,
            "max": self._slide_max,
        })

    async def _handle_set_slide(self, request):
        data = await request.json()
        self._slide_min = data.get("min", self._slide_min)
        self._slide_max = data.get("max", self._slide_max)
        return web.json_response({"result": 0})

    # ── HDSP Handlers (fallback, log only) ─────────────────────────

    async def _handle_hdsp_xpt(self, request):
        data = await request.json()
        self._log(
            f"HDSP xpt - pos: {data.get('position')}%, "
            f"duration: {data.get('duration')}ms"
        )
        return web.json_response({"result": 0})

    async def _handle_hdsp_xpvp(self, request):
        return web.json_response({"result": 0})

    async def _handle_hdsp_xpva(self, request):
        return web.json_response({"result": 0})

    async def _handle_hdsp_xava(self, request):
        return web.json_response({"result": 0})

    async def _handle_hdsp_xat(self, request):
        return web.json_response({"result": 0})

    # ── Fallback ───────────────────────────────────────────────────

    async def _handle_fallback(self, request):
        path = request.match_info.get("path", "")
        self._log(f"Unknown endpoint: {request.method} /{path}")
        return web.json_response({"result": 0})

    # ── v3 (observation mode) ──────────────────────────────────────

    async def _handle_v3(self, request):
        """Catch-all v3 handler: log everything, return plausible responses.

        Used to observe theedgy.app's API usage — once we know the exact
        endpoints and payloads, specific handlers replace this.
        """
        path = request.match_info.get("path", "")
        body_text = ""
        try:
            raw = await request.read()
            if raw:
                body_text = raw.decode("utf-8", errors="replace")
        except Exception:
            pass

        log_msg = f"v3 {request.method} /{path}"
        if body_text:
            log_msg += f"  body={body_text[:200]}"
        self._log(log_msg)

        # Minimal responses so theedgy keeps talking to us.
        suffix = path.rstrip("/").split("/")[-1] if path else ""

        if suffix == "info":
            return web.json_response({
                "fwVersion": "4.0.0",
                "fwStatus": "up_to_date",
                "hwVersion": 3,
                "model": "handy",
                "branch": "master",
                "sessionId": "restim-ext-v3-0001",
                "connected": True,
            })
        if suffix == "connected":
            return web.json_response({"connected": True})
        if suffix == "status":
            return web.json_response({"mode": self._mode, "state": self._hssp_state})
        if suffix == "mode":
            if request.method == "GET":
                return web.json_response({"mode": self._mode})
            return web.json_response({"result": 0})
        if suffix == "time":
            return web.json_response({"time": self._server_time_ms()})
        if suffix == "servertime":
            return web.json_response({"serverTime": self._server_time_ms()})

        return web.json_response({})

    # ── Script Download ────────────────────────────────────────────

    async def _download_script(self, url):
        """Download and parse a funscript from the given URL."""
        self._log(f"Downloading script: {url[:80]}...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        self._log(f"Download failed: HTTP {resp.status}")
                        return None
                    content = await resp.text()
                    return self._parse_script(content)
        except Exception as e:
            self._log(f"Download error: {e}")
            return None

    def _parse_script(self, content):
        """Parse funscript JSON or CSV content."""
        # Try JSON funscript
        try:
            data = json.loads(content)
            if "actions" in data:
                return data
        except (json.JSONDecodeError, KeyError):
            pass

        # Try CSV (timestamp,position)
        actions = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    at = int(float(parts[0]))
                    pos = int(float(parts[1]))
                    actions.append({"at": at, "pos": pos})
                except ValueError:
                    continue

        if actions:
            return {"actions": actions, "_format": "csv"}
        return None

    # ── Settings ───────────────────────────────────────────────────

    def update_settings(self, data):
        """Update converter settings from sidebar sliders."""
        s = self._player.settings
        for key in [
            "arc_degrees", "speed_window", "min_radius", "speed_threshold",
            "volume_min", "volume_max", "volume_window", "volume_fade_down", "volume_fade_up",
            "carrier_freq_min", "carrier_freq_max",
            "pulse_freq_min", "pulse_freq_max",
            "pulse_width_min", "pulse_width_max",
            "pulse_rise_min", "pulse_rise_max",
        ]:
            if key in data:
                setattr(s, key, float(data[key]))
        if "arc_invert" in data:
            s.arc_invert = bool(data["arc_invert"])
        if "boost_enabled" in data:
            s.boost_enabled = bool(data["boost_enabled"])
        if "boost_strength" in data:
            s.boost_strength = float(data["boost_strength"])
        if "boost_window" in data:
            s.boost_window = float(data["boost_window"])
        if "position_freq_influence" in data:
            s.position_freq_influence = float(data["position_freq_influence"])
        if "position_freq_invert" in data:
            s.position_freq_invert = bool(data["position_freq_invert"])

        # Re-convert if we have a loaded funscript
        if self._funscript_data:
            self._player.load(self._funscript_data)

    # ── Logging ────────────────────────────────────────────────────

    def _log(self, msg):
        print(f"[fake-handy] {msg}", flush=True)
        self._on_log(msg)
