import asyncio
import re
import threading
import time

from funscript.live_processor import LiveProcessor
from restim.tcode_client import TCodeClient


# Matches axis commands in a TCode stream, e.g. "L05000", "L05000I100", "L05000S50".
# Capture 1: axis name (e.g. L0). Capture 2: 4-digit value.
_AXIS_RE = re.compile(r"([LRVAP]\d)(\d{1,4})", re.IGNORECASE)


def parse_l0_positions(text):
    """Yield (pos_0_1) values for every L0 command in text.

    Ignores interval / speed / magnitude modifiers — we use wall-clock timing.
    """
    for match in _AXIS_RE.finditer(text):
        axis = match.group(1).upper()
        if axis != "L0":
            continue
        try:
            raw = int(match.group(2))
        except ValueError:
            continue
        # Handy/TCode convention: 4-digit value 0-9999 → 0.0-1.0
        yield max(0.0, min(1.0, raw / 9999.0))


class LiveBridge:
    """Live T-Code pass-through from browser WebSerial to Restim.

    Owns its own thread + asyncio loop so it can host an async TCode WebSocket
    client. Text arrives via write(text) from any thread (typically the UI
    thread) and is queued onto the loop.
    """

    def __init__(self, restim_url, on_log=None):
        self._restim_url = restim_url
        self._on_log = on_log or (lambda m: None)
        self._processor = LiveProcessor()
        self._tcode = None
        self._thread = None
        self._loop = None
        self._queue = None
        self._running = False

    @property
    def settings(self):
        return self._processor.settings

    def start(self):
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def write(self, text):
        """Thread-safe: enqueue a chunk of T-Code text for processing."""
        if not text or self._loop is None or self._queue is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._queue.put(text), self._loop)
        except Exception as e:
            self._log(f"Live write queue error: {e}")

    def update_settings(self, data):
        """Apply sidebar-slider updates to the live processor."""
        s = self._processor.settings
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
        # theedgy-specific: speed envelope overrides (in %/s, convert to units/s)
        if "max_speed_pct" in data:
            self._processor.max_speed = float(data["max_speed_pct"]) / 100.0
        if "min_speed_pct" in data:
            self._processor.min_speed = float(data["min_speed_pct"]) / 100.0

    def _run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._queue = asyncio.Queue()
            self._tcode = TCodeClient(url=self._restim_url, on_log=self._log)
            self._loop.run_until_complete(self._main())
        except Exception as e:
            self._log(f"LiveBridge error: {e}")

    async def _main(self):
        connected_once = False
        while self._running:
            text = await self._queue.get()

            # Lazy connect on first frame so we don't spam restim at startup.
            if not connected_once:
                await self._tcode.connect()
                connected_once = True
                if not self._tcode.connected:
                    self._log("LiveBridge: Restim nicht erreichbar")
                    continue

            t_ms = int(time.monotonic() * 1000)
            for pos in parse_l0_positions(text):
                axes = self._processor.process(t_ms, pos)
                await self._tcode.send(axes, interval_ms=20)

    def _log(self, msg):
        print(f"[live-bridge] {msg}", flush=True)
        try:
            self._on_log(msg)
        except Exception:
            pass
