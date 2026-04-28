import asyncio
import time

from funscript.converter import convert_funscript, ConvertSettings, lerp
from restim.tcode_client import TCodeClient, AXES


class FunscriptPlayer:
    """Real-time funscript playback engine.

    Pre-processes funscript on setup, then streams TCode to Restim
    during playback with accurate timing.
    """

    def __init__(self, restim_url="ws://127.0.0.1:12346/tcode", on_log=None):
        self._on_log = on_log or (lambda msg: None)
        self._tcode = TCodeClient(url=restim_url, on_log=on_log)
        self.settings = ConvertSettings()

        self._converted = None      # pre-processed data
        self._playing = False
        self._play_start_real = 0   # real time when play was called
        self._play_start_offset = 0 # offset into the script (ms)
        self._task = None
        self._loop = None

    def set_loop(self, loop):
        """Store the asyncio event loop for scheduling."""
        self._loop = loop

    def load(self, funscript_data):
        """Pre-process funscript into all TCode axes."""
        self._converted = convert_funscript(funscript_data, self.settings)
        if self._converted:
            count = len(self._converted["times_ms"])
            dur = self._converted["times_ms"][-1] / 1000
            self._on_log(f"Konvertiert: {count} Punkte, {dur:.0f}s")
        else:
            self._on_log("Konvertierung fehlgeschlagen (zu wenig Daten)")

    async def play(self, start_time_ms=0):
        """Start playback from the given position."""
        if not self._converted:
            self._on_log("Kein Script geladen")
            return

        await self.stop()
        await self._tcode.connect()

        if not self._tcode.connected:
            return

        self._playing = True
        self._play_start_offset = start_time_ms
        self._play_start_real = time.monotonic()
        self._task = asyncio.ensure_future(self._playback_loop())
        self._on_log(f"Playback gestartet bei {start_time_ms}ms")

    async def stop(self):
        """Stop playback."""
        self._playing = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._tcode.disconnect()

    async def _playback_loop(self):
        """Main playback loop: interpolate and send TCode at ~100Hz."""
        times = self._converted["times_ms"]
        total_duration_ms = times[-1]
        interval_ms = 10  # 100 Hz update rate (10ms)

        try:
            while self._playing:
                tick_start = time.monotonic()

                # Calculate current position in the script
                elapsed_s = tick_start - self._play_start_real
                current_ms = self._play_start_offset + int(elapsed_s * 1000)

                if current_ms > total_duration_ms:
                    self._on_log("Playback beendet (Ende erreicht)")
                    break

                # Interpolate all axes at current time
                values = {}
                for axis in AXES:
                    if axis in self._converted:
                        values[axis] = interp_at_ms(
                            current_ms, times, self._converted[axis]
                        )

                await self._tcode.send(values, interval_ms)

                # Log values every 2 seconds for debugging
                if current_ms % 2000 < interval_ms:
                    parts = [f"{a}={values[a]:.2f}" for a in AXES if a in values]
                    self._on_log(f"t={current_ms/1000:.0f}s {' '.join(parts)}")

                # Precise sleep: account for processing time
                elapsed_tick = time.monotonic() - tick_start
                sleep_s = max(0, (interval_ms / 1000.0) - elapsed_tick)
                await asyncio.sleep(sleep_s)

        except asyncio.CancelledError:
            pass
        finally:
            self._playing = False


def interp_at_ms(t_ms, times_ms, values):
    """Interpolate a value at time t_ms from pre-processed arrays."""
    if t_ms <= times_ms[0]:
        return values[0]
    if t_ms >= times_ms[-1]:
        return values[-1]

    # Binary search
    lo, hi = 0, len(times_ms) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if times_ms[mid] <= t_ms:
            lo = mid
        else:
            hi = mid

    dt = times_ms[hi] - times_ms[lo]
    if dt == 0:
        return values[lo]
    frac = (t_ms - times_ms[lo]) / dt
    return values[lo] + (values[hi] - values[lo]) * frac
