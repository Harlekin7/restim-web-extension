# Restim Web Extension

Bridge between [FapTap.net](https://faptap.net) and [Restim](https://github.com/diglet48/restim) — capture funscripts from the browser and stream them as TCode to a Restim e-stim session in real time.

## How it works

```
┌────────────────────────────┐      ┌─────────────────────────────┐
│  Embedded Browser          │      │  Fake Handy Cloud Server    │
│  (Edge WebView2)           │      │  localhost:5000             │
│                            │      │                             │
│  FapTap.net                │─────▶│  Mimics handyfeeling.com    │
│                            │ JS   │  /api/handy/v2              │
│  + redirect.js injection   │      │                             │
└────────────────────────────┘      └──────────────┬──────────────┘
                                                   │
                                      1. /hssp/setup → script URL
                                      2. Download funscript
                                      3. Pre-process (Arc + Speed)
                                      4. On /hssp/play → stream TCode
                                                   │
                                                   ▼
                                    ┌──────────────────────────────┐
                                    │  Restim                      │
                                    │  ws://localhost:12346/tcode  │
                                    └──────────────────────────────┘
```

1. The app launches two windows: an embedded browser (pywebview / Edge WebView2) and an HTML sidebar for settings.
2. A local HTTP server impersonates The Handy cloud API (`handyfeeling.com/api/handy/v2`).
3. Injected JavaScript redirects every `handyfeeling.com` request from the page to `localhost:5000`.
4. When FapTap starts a video, it uploads the funscript to a hosting URL and calls `PUT /hssp/setup` on what it thinks is The Handy API. The fake server extracts the URL and downloads the script.
5. On `PUT /hssp/play`, the script is converted on the fly (arc-based 1D→2D + speed-derived parameters) and streamed as TCode over WebSocket to Restim.

No real Handy device is required — any connection key is accepted.

## Features

- **Embedded browser** with full codec support (H.264 / AAC via Edge WebView2).
- **Fake Handy Cloud API** (HSSP / HSTP / HDSP endpoints).
- **Live funscript conversion** to 7 TCode axes:
  - `L0` Alpha (position X)
  - `L1` Beta (position Y)
  - `V0` Volume
  - `C0` Carrier frequency
  - `P0` Pulse frequency
  - `P1` Pulse width
  - `P3` Pulse rise time
- **Configurable arc** (270°–360°) with clockwise / counter-clockwise toggle.
- **Centered rolling-window speed** (no lag) driving all dynamic parameters.
- **Separate volume window** with independent smoothing and idle fade.
- **Boost mode** that emphasizes short bursts inside otherwise slow passages.
- **Position normalization** — min/max of the funscript are mapped to 0.0 / 1.0.
- **HTML5 fullscreen override** for the in-app browser.
- **Settings persisted** to `data/settings.json` and restored on startup.

## Requirements

- Windows 10 / 11
- Python 3.10+
- Microsoft Edge WebView2 runtime (pre-installed on Windows 10+)
- [Restim](https://github.com/diglet48/restim) running and configured with its WebSocket server enabled on `ws://127.0.0.1:12346/tcode`

## Installation

```bash
git clone https://github.com/<your-user>/restim-web-extension.git
cd restim-web-extension
pip install -r requirements.txt
```

## Usage

1. Start Restim and make sure its WebSocket server (`/tcode`) is enabled on port `12346`.
2. Configure the TCode axis mapping in Restim (funscript kit):
   - `L0` → Position Alpha
   - `L1` → Position Beta
   - `V0` → Volume (external)
   - `C0` → Carrier Frequency
   - `P0` → Pulse Frequency
   - `P1` → Pulse Width
   - `P3` → Pulse Rise Time
3. Run the app:
   ```bash
   python src/main.py
   ```
4. Two windows open. In the browser window, pick a video on FapTap, choose "The Handy" as the device, and enter **any** connection key.
5. Hit play — the sidebar shows the intercepted funscript and Restim starts receiving TCode.

## Project structure

```
src/
├── main.py                      App entry, pywebview window setup
├── config.py                    Ports, URLs
├── fake_handy/
│   └── server.py                aiohttp server mimicking The Handy API v2
├── funscript/
│   ├── converter.py             Arc + Speed + axis generation
│   └── player.py                Real-time playback loop (~100 Hz)
├── restim/
│   └── tcode_client.py          WebSocket client, TCode formatter
├── ui/
│   └── sidebar_html.py          Settings UI (rendered in pywebview)
└── injection/
    ├── redirect.js              Patches fetch / XHR to redirect to local server
    └── fullscreen.js            HTML5 fullscreen API shim for pywebview
```

## Disclaimer

This project is not affiliated with FapTap, The Handy (Sweet Tech AS), Buttplug.io, or diglet48/restim. It is a third-party tool for personal use that bridges a web funscript source with local e-stim hardware. Use it responsibly and in accordance with the terms of service of any site you visit.

## License

MIT — see [LICENSE](LICENSE).
