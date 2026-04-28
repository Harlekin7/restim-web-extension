# Restim Web Extension

Bridge between web-based interactive media platforms and [Restim](https://github.com/diglet48/restim) e-stim hardware. Captures funscripts or live position streams from the browser and routes them to a Restim session as TCode in real time.

**Supported sites (v1.0):**
- [FapTap.net](https://faptap.net) — funscript-based playback (via Handy API impersonation)
- [TheEdgy.app](https://theedgy.app) — live T-Code streaming (via WebSerial impersonation)

A switcher in the sidebar toggles between sites at runtime — no restart required.

## How it works

There are two independent data paths, one per supported site, sharing the same downstream conversion + Restim WebSocket plumbing.

### Path A — FapTap (funscript)

```
┌────────────────────────┐    ┌────────────────────────────┐
│ Embedded Browser       │    │ Fake Handy API server      │
│ (Edge WebView2)        │    │ /api/handy/v2  /v3         │
│                        │    │                            │
│ FapTap.net  + redirect │───▶│ HSSP setup → script URL    │
│             .js bridge │    │ Download + pre-process     │
└────────────────────────┘    └──────────────┬─────────────┘
                                             │
                                             ▼
                              FunscriptPlayer (offline converter)
                                             │
                                             ▼
                              ws://localhost:12346/tcode  →  Restim
```

1. `redirect.js` patches `fetch()` and `XMLHttpRequest` so every call to `handyfeeling.com` is routed through `pywebview.api.handy_call()` (a JS bridge — bypasses Content-Security-Policy restrictions of modern sites).
2. The fake server impersonates The Handy cloud API (v2 + v3). When FapTap calls `PUT /hssp/setup`, the server downloads the funscript URL and pre-processes the entire script into all 7 TCode axes.
3. On `PUT /hssp/play`, `FunscriptPlayer` streams TCode at ~100 Hz to Restim.

### Path B — TheEdgy (live)

```
┌────────────────────────┐    ┌────────────────────────────┐
│ Embedded Browser       │    │ LiveBridge (Python)        │
│                        │    │                            │
│ TheEdgy.app  + serial  │───▶│ T-Code parse → L0          │
│              .js patch │    │ LiveProcessor (causal)     │
│ (fake navigator.serial)│    │                            │
└────────────────────────┘    └──────────────┬─────────────┘
                                             │
                                             ▼
                              ws://localhost:12346/tcode  →  Restim
```

1. `serial.js` replaces `navigator.serial` with a fake implementation. When TheEdgy calls `requestPort()` + `port.open()`, our fake port answers immediately and presents itself as a TCode v0.3 device via the readable stream.
2. Bytes written to `port.writable` are forwarded via `pywebview.api.tcode_write()` to Python.
3. `LiveBridge` parses the L0 stream and `LiveProcessor` derives the remaining 6 axes (L1, V0, C0, P0, P1, P3) using **causal** rolling windows — no look-ahead delay, suitable for live data at 10/20/50 Hz.

Both paths share the same `ConvertSettings` so all sidebar sliders affect both modes identically.

## Features

### Sidebar
- **Site switcher** at the top — toggle live between FapTap and TheEdgy.
- **Settings persisted** to `data/settings.json` and restored on startup.
- All slider/toggle changes apply immediately to both data paths.

### General conversion (both paths)
- 7 TCode axes generated from a single 1D position stream:
  - `L0` Alpha (position X), `L1` Beta (position Y)
  - `V0` Volume, `C0` Carrier frequency
  - `P0` Pulse frequency, `P1` Pulse width, `P3` Pulse rise time
- **Configurable arc** (270°–360°) with clockwise / counter-clockwise toggle.
- **Speed-driven dynamics** — speed continuously modulates volume, carrier, pulse parameters.
- **Boost mode** — emphasizes short bursts inside otherwise slow passages.
- **Volume envelope** with separate smoothing window + idle fade up/down.
- **Position → Pulse Frequency** influence slider (with invert) — blends speed-driven pulse frequency with a pulse frequency that follows the position itself.
- **Position normalization** — funscript min/max mapped to 0.0 / 1.0 (FapTap path).

### TheEdgy path (live)
- `serial.js` impersonates a USB TCode device (no real hardware needed).
- `LiveProcessor` uses **causal** rolling windows — appropriate for dense (10/20/50 Hz) live streams without look-ahead.
- Dedicated **Max / Min Speed (%/s)** inputs in the sidebar (visible only in TheEdgy mode) configure the speed envelope. Without them the processor auto-observes the peak speed.

### FapTap path (funscript)
- Fake Handy Cloud API (v2 + v3, HSSP / HSTP / HDSP endpoints).
- Centered rolling-window speed (no lag) for offline conversion quality.
- HTML5 fullscreen override for the in-app browser.

## Requirements

- Windows 10 / 11
- For Python source run: Python 3.10+ and Microsoft Edge WebView2 runtime (pre-installed on Windows 10+)
- [Restim](https://github.com/diglet48/restim) running with WebSocket server enabled on `ws://127.0.0.1:12346/tcode`

## Quick start (binary)

1. Download `RestimWebExtension.exe` from the [Releases page](https://github.com/Harlekin7/restim-web-extension/releases).
2. Start Restim and enable its WebSocket server (`/tcode`).
3. Configure the TCode axis mapping in Restim:
   - `L0` → Position Alpha
   - `L1` → Position Beta
   - `V0` → Volume (external)
   - `C0` → Carrier Frequency
   - `P0` → Pulse Frequency
   - `P1` → Pulse Width
   - `P3` → Pulse Rise Time
4. Run `RestimWebExtension.exe`.
5. Pick a site from the sidebar:
   - **FapTap** → choose a video, set device to "The Handy", enter any connection key, hit play.
   - **TheEdgy** → choose **T-Code** in their device picker; the fake serial port is auto-accepted.

## From source

```bash
git clone https://github.com/Harlekin7/restim-web-extension.git
cd restim-web-extension
pip install -r requirements.txt
python src/main.py
```

The site can be preselected via env var: `SITE=theedgy python src/main.py`.

## Building the .exe

```bash
pip install pyinstaller
pyinstaller RestimWebExtension.spec
```

The output is a single-file `dist/RestimWebExtension.exe`.

## Project structure

```
src/
├── main.py                       App entry, pywebview setup, JS bridge
├── config.py                     Ports, URLs, supported sites
├── fake_handy/
│   └── server.py                 Handy API v2 + v3 impersonation (FapTap path)
├── funscript/
│   ├── converter.py              Offline converter (centered windows)
│   ├── player.py                 Real-time funscript playback (FapTap path)
│   ├── live_bridge.py            Receives WebSerial bytes, manages TCode WS
│   └── live_processor.py         Causal converter (TheEdgy path)
├── restim/
│   └── tcode_client.py           WebSocket TCode client
├── ui/
│   └── sidebar_html.py           Settings UI (rendered in pywebview)
└── injection/
    ├── redirect.js               JS bridge for Handy API → pywebview.api
    ├── serial.js                 Fake navigator.serial → pywebview.api
    └── fullscreen.js             HTML5 fullscreen API shim
```

## Disclaimer

This project is not affiliated with FapTap, TheEdgy, The Handy (Sweet Tech AS), Buttplug.io, or diglet48/restim. It is a third-party tool for personal use that bridges browser-based content with local e-stim hardware. Use it responsibly and in accordance with the terms of service of any site you visit.

## License

MIT — see [LICENSE](LICENSE).
