# Restim Web Extension

Bridge between web-based interactive media platforms and [Restim](https://github.com/diglet48/restim) e-stim hardware. Captures funscripts or live position streams from the browser and routes them to a Restim session as TCode in real time.

**Supported sites (v1.0):**
- [FapTap.net](https://faptap.net) — funscript-based playback (via Handy API impersonation)
- [TheEdgy.app](https://theedgy.app) — live T-Code streaming (via WebSerial impersonation)
- **Network proxy** — serves FapTap or [SexLikeReal.com](https://www.sexlikereal.com) to other devices on the LAN (phones, tablets, VR headsets) without any client-side cert/DNS setup

A switcher in the sidebar toggles between modes at runtime — no restart required.

## Modes at a glance

| Mode | What it does | Where you browse |
|------|---|---|
| **FapTap** | Embedded browser loads FapTap. JS bridge intercepts the Handy API. | In the app's browser window |
| **TheEdgy** | Embedded browser loads TheEdgy. Fake `navigator.serial` answers as a TCode device. | In the app's browser window |
| **Network** | Reverse proxy serves FapTap or SLR through your PC. Handy API still impersonated. | On any LAN device — `http://<your-pc-ip>:8080` |

## How it works

Three independent data paths share the same downstream conversion + Restim WebSocket plumbing.

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

`redirect.js` patches `fetch()` and `XMLHttpRequest` so every call to `handyfeeling.com` is routed through `pywebview.api.handy_call()` (a JS bridge — bypasses the Content-Security-Policy of modern sites). When FapTap calls `PUT /hssp/setup`, the fake server downloads the funscript URL and pre-processes the entire script into all 7 TCode axes. On `PUT /hssp/play`, `FunscriptPlayer` streams TCode at ~100 Hz to Restim.

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

`serial.js` replaces `navigator.serial` with a fake implementation. When TheEdgy calls `requestPort()` + `port.open()`, our fake port answers immediately and presents itself as a TCode v0.3 device. Bytes written to `port.writable` are forwarded via `pywebview.api.tcode_write()` to Python. `LiveProcessor` derives the remaining 6 axes (L1, V0, C0, P0, P1, P3) using **causal** rolling windows — no look-ahead delay, suitable for live data at 10/20/50 Hz.

### Path C — Network (LAN reverse proxy)

```
[Phone / VR / Laptop on LAN]
            │  http://<host-ip>:8080
            ▼
┌─────────────────────────────┐
│ Reverse proxy (aiohttp)     │
│  /api/handy/* → fake server │
│  /scripts-api/* → CDN       │
│  /*  → upstream site        │
│        (rewrite + strip CSP)│
└──────────────┬──────────────┘
               │
               ▼
   FunscriptPlayer → Restim
```

A reverse proxy fetches `https://faptap.net` (or `https://www.sexlikereal.com`) server-side, strips the security headers, and rewrites every reference to `handyfeeling.com` so it points back at the proxy. Handy API endpoints are routed locally to the same fake server FapTap/SLR talks to. **No DNS hijacking, no client-side certificate install, no JS injection on the client are required.** The proxy upstream is switchable at runtime via the sidebar.

Both proxied sites share the same `ConvertSettings` so all sidebar sliders affect every mode identically.

## Features

### Sidebar
- **Mode switcher** at the top — toggle live between FapTap, TheEdgy, and Network.
- **Network target picker** (visible only in Network mode) — switch between FapTap and SexLikeReal upstream without restart.
- **Settings persisted** to `data/settings.json` and restored on startup.
- All slider/toggle changes apply immediately to all data paths.

### General conversion (all paths)
- 7 TCode axes generated from a single 1D position stream:
  - `L0` Alpha (position X), `L1` Beta (position Y)
  - `V0` Volume, `C0` Carrier frequency
  - `P0` Pulse frequency, `P1` Pulse width, `P3` Pulse rise time
- **Configurable arc** (270°–360°) with clockwise / counter-clockwise toggle.
- **Speed-driven dynamics** — speed continuously modulates volume, carrier, pulse parameters.
- **Boost mode** — emphasises short bursts inside otherwise slow passages.
- **Volume envelope** with separate smoothing window + idle fade up/down.
- **Position → Pulse Frequency** influence slider (with invert) — blends speed-driven pulse frequency with a pulse frequency that follows the position itself.
- **Position normalization** — funscript min/max mapped to 0.0 / 1.0 (FapTap path).

### Per-path specifics
- **TheEdgy:** dedicated **Max / Min Speed (%/s)** inputs (visible only in TheEdgy mode). Without them the live processor auto-observes the peak speed.
- **FapTap:** Fake Handy Cloud API (v2 + v3, HSSP / HSTP / HDSP endpoints). Centred rolling-window speed (no lag). HTML5 fullscreen override for the embedded browser.
- **Network:** runtime upstream switch (FapTap ↔ SexLikeReal). Browser-like User-Agent and Cookie session per upstream. Set-Cookie domain/Secure attributes are rewritten so cookies stick on the proxy host.

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
5. Pick a mode in the sidebar:
   - **FapTap** → choose a video, set device to "The Handy", enter any connection key, hit play.
   - **TheEdgy** → choose **T-Code** in their device picker; the fake serial port is auto-accepted.
   - **Network** → the embedded browser shows the proxy URL. Open that URL on any LAN device, then proceed as in FapTap mode (or pick SexLikeReal in the sub-picker).

## From source

```bash
git clone https://github.com/Harlekin7/restim-web-extension.git
cd restim-web-extension
pip install -r requirements.txt
python src/main.py
```

The mode can be preselected via env var: `SITE=theedgy python src/main.py` (also supports `faptap`, `network`). The network upstream defaults to `faptap` — switch via `NETWORK_TARGET=sexlikereal python src/main.py`.

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
├── config.py                     Ports, URLs, supported sites + network targets
├── fake_handy/
│   └── server.py                 Handy API v2 + v3 impersonation (FapTap + Network)
├── proxy/
│   └── server.py                 LAN reverse proxy with runtime-switchable upstream
├── funscript/
│   ├── converter.py              Offline converter (centered windows)
│   ├── player.py                 Real-time funscript playback (FapTap / Network)
│   ├── live_bridge.py            Receives WebSerial bytes, manages TCode WS
│   └── live_processor.py         Causal converter (TheEdgy)
├── restim/
│   └── tcode_client.py           WebSocket TCode client
├── ui/
│   └── sidebar_html.py           Settings UI (rendered in pywebview)
└── injection/
    ├── redirect.js               JS bridge for Handy API → pywebview.api
    ├── serial.js                 Fake navigator.serial → pywebview.api
    └── fullscreen.js             HTML5 fullscreen API shim
```

## Known limitations

- The Network proxy currently does not tunnel WebSocket connections. Sites that rely on a WebSocket for live state (other than Handy cloud calls) may not fully work through the proxy.
- Cloudflare bot detection occasionally challenges the proxy on first load — refresh in the client browser to retry. If a target site blocks the proxy persistently, the FapTap embedded mode is unaffected.

## Disclaimer

This project is not affiliated with FapTap, TheEdgy, SexLikeReal, The Handy (Sweet Tech AS), Buttplug.io, or diglet48/restim. It is a third-party tool for personal use that bridges browser-based content with local e-stim hardware. Use it responsibly and in accordance with the terms of service of any site you visit.

## License

MIT — see [LICENSE](LICENSE).
