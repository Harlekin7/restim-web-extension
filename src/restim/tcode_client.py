import asyncio
import websockets


# TCode axis names
AXES = ["L0", "L1", "V0", "C0", "P0", "P1", "P3"]


def format_tcode(axis_values, interval_ms=50):
    """Format a dict of {axis: float_0_1} into a TCode command string.

    Restim format: L05000I50 L15000I50 V05000I50 ...
    Value range: 0-9999 (4 digits, representing 0.0-0.9999)
    """
    parts = []
    for axis in AXES:
        if axis in axis_values:
            val = max(0.0, min(1.0, axis_values[axis]))
            ival = min(int(val * 9999), 9999)
            parts.append(f"{axis}{ival:04d}I{interval_ms}")
    return " ".join(parts)


class TCodeClient:
    """Async WebSocket client that sends TCode commands to Restim."""

    def __init__(self, url="ws://127.0.0.1:12346/tcode", on_log=None):
        self.url = url
        self._on_log = on_log or (lambda msg: None)
        self._ws = None
        self._connected = False

    async def connect(self):
        try:
            self._ws = await websockets.connect(self.url)
            self._connected = True
            self._on_log(f"Restim verbunden: {self.url}")
        except Exception as e:
            self._connected = False
            self._on_log(f"Restim Verbindung fehlgeschlagen: {e}")

    async def disconnect(self):
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            self._connected = False

    async def send(self, axis_values, interval_ms=50):
        """Send a TCode command. axis_values = {axis: float_0_1}."""
        if not self._connected or not self._ws:
            return
        cmd = format_tcode(axis_values, interval_ms)
        try:
            await self._ws.send(cmd)
        except Exception:
            self._connected = False
            self._on_log("Restim Verbindung verloren")

    @property
    def connected(self):
        return self._connected
