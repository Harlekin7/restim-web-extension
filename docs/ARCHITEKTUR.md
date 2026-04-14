# Architektur: Fake Handy Cloud + Embedded Browser

## Konzept

Wir bauen eine Python-App die:
1. Einen **Fake Handy Cloud Server** lokal betreibt (imitiert `handyfeeling.com/api/handy/v2/`)
2. Einen **eingebetteten Browser** (Qt WebEngine) öffnet, in dem FapTap.net geladen wird
3. Im Browser **JavaScript injiziert**, das alle API-Calls an `handyfeeling.com` auf unseren lokalen Server umleitet
4. Den empfangenen **Funscript parsed** und als **TCode an Restim** weiterleitet

## Datenfluss

```
┌─────────────────────────────────────────────────────────┐
│                    Unsere Software                       │
│                                                         │
│  ┌──────────────────────┐    ┌────────────────────────┐ │
│  │  Qt WebEngine Browser │    │  Fake Handy Cloud API  │ │
│  │                      │    │  (localhost:5000)       │ │
│  │  FapTap.net geladen  │───>│                        │ │
│  │                      │    │  /connected  → true    │ │
│  │  JS Injection:       │    │  /info       → fake HW │ │
│  │  fetch() umgeleitet  │    │  /hssp/setup → Script↓ │ │
│  │  von handyfeeling.com│    │  /hssp/play  → Start   │ │
│  │  auf localhost:5000  │    │  /hssp/stop  → Stop    │ │
│  │                      │    │  /hstp/time  → Sync    │ │
│  └──────────────────────┘    └───────────┬────────────┘ │
│                                          │              │
│                              ┌───────────▼────────────┐ │
│                              │  Funscript Engine      │ │
│                              │                        │ │
│                              │  1. Script-URL abfangen│ │
│                              │  2. Script downloaden  │ │
│                              │  3. JSON parsen        │ │
│                              │  4. → TCode konvertieren│ │
│                              │  5. Timing-Sync        │ │
│                              └───────────┬────────────┘ │
│                                          │              │
└──────────────────────────────────────────┼──────────────┘
                                           │
                              TCode über WebSocket
                              ws://localhost:12346/tcode
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │    Restim     │
                                    │              │
                                    │ TCode → E-Stim│
                                    └──────────────┘
```

## Komponenten im Detail

### 1. Fake Handy Cloud API (aiohttp Server)

Lokaler HTTP-Server der die handyfeeling.com API v2 nachahmt.
Der User gibt in FapTap einen beliebigen "Connection Key" ein - unser Server akzeptiert alles.

**Endpunkte die implementiert werden müssen:**

```
GET  /api/handy/v2/connected     → {"connected": true}
GET  /api/handy/v2/info          → Fake Handy Device Info
GET  /api/handy/v2/settings      → Slide-Einstellungen
GET  /api/handy/v2/status        → Aktueller Status
PUT  /api/handy/v2/mode          → Mode akzeptieren (HSSP=1)
PUT  /api/handy/v2/hssp/setup    → ★ Script-URL empfangen & downloaden
PUT  /api/handy/v2/hssp/play     → ★ Playback starten (Timing-Info)
PUT  /api/handy/v2/hssp/stop     → ★ Playback stoppen
GET  /api/handy/v2/hssp/state    → Playback-Status
GET  /api/handy/v2/hssp/loop     → Loop-Status
PUT  /api/handy/v2/hssp/loop     → Loop setzen
GET  /api/handy/v2/hstp/time     → Server-Zeit (ms Unix Epoch)
GET  /api/handy/v2/hstp/sync     → Zeit-Sync (RTD berechnen)
GET  /api/handy/v2/hstp/offset   → Offset
PUT  /api/handy/v2/hstp/offset   → Offset setzen
GET  /api/handy/v2/hstp/rtd      → Round-Trip-Delay
GET  /api/handy/v2/servertime    → Server-Zeit
PUT  /api/handy/v2/slide         → Slide-Range
GET  /api/handy/v2/slide         → Slide-Range
```

**Fake Device Info Response:**
```json
{
  "fwVersion": "3.2.0",
  "fwStatus": 0,
  "hwVersion": "1.0",
  "model": 1,
  "branch": "master",
  "sessionId": "fake-session-id"
}
```

### 2. JavaScript Injection (API Redirect)

Im Qt WebEngine Browser wird JavaScript injiziert, das `fetch()` und `XMLHttpRequest`
überschreibt und Requests an `handyfeeling.com` auf unseren lokalen Server umleitet.

```javascript
// Monkey-patch fetch() um handyfeeling.com → localhost umzuleiten
const originalFetch = window.fetch;
window.fetch = function(url, options) {
    if (typeof url === 'string') {
        url = url.replace(
            'https://www.handyfeeling.com/api/handy/v2',
            'http://localhost:5000/api/handy/v2'
        );
        // Script-Hosting auch umleiten falls nötig
        // ODER: Script-URL direkt durchlassen (ist öffentlich zugänglich)
    }
    return originalFetch.call(this, url, options);
};

// Auch XMLHttpRequest patchen für ältere Code-Pfade
const originalOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(method, url, ...args) {
    if (typeof url === 'string') {
        url = url.replace(
            'https://www.handyfeeling.com/api/handy/v2',
            'http://localhost:5000/api/handy/v2'
        );
    }
    return originalOpen.call(this, method, url, ...args);
};
```

### 3. Funscript Engine

Kernlogik die den heruntergeladenen Funscript in Echtzeit an Restim streamt:

```python
# Funscript Format:
# {"actions": [{"at": 0, "pos": 50}, {"at": 500, "pos": 100}, ...]}

# Konvertierung zu TCode für Restim:
# pos 0-100 → TCode Wert 0-10000
# Timing via "I" Parameter (Intervall in ms)

def funscript_to_tcode(current_action, next_action):
    position = int(next_action['pos'] * 100)     # 0-10000
    duration = next_action['at'] - current_action['at']  # ms
    return f"L0{position:05d}I{duration}"
```

### 4. Qt WebEngine Browser

PySide6 + QtWebEngine für den eingebetteten Browser:

```python
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineUrlRequestInterceptor
)
```

**Features:**
- Lädt FapTap.net
- Injiziert JavaScript beim Laden jeder Seite
- Optional: QWebEngineUrlRequestInterceptor für zusätzliche Request-Kontrolle
- Volle Browser-Funktionalität (Login, Navigation, Video-Playback)

## Datei-Struktur

```
src/
├── main.py                    # Einstiegspunkt
├── app.py                     # Hauptanwendung (Qt App)
├── ui/
│   ├── main_window.py         # Hauptfenster mit Browser + Controls
│   ├── browser_widget.py      # Qt WebEngine Browser-Widget
│   └── settings_dialog.py     # Einstellungen (Restim-Adresse, etc.)
├── fake_handy/
│   ├── server.py              # Fake Handy Cloud API (aiohttp)
│   ├── endpoints.py           # API Endpunkt-Handler
│   └── responses.py           # Vordefinierte Fake-Responses
├── funscript/
│   ├── parser.py              # Funscript JSON Parser
│   ├── player.py              # Echtzeit-Funscript-Player mit Timing
│   └── converter.py           # Funscript → TCode Konvertierung
├── restim/
│   ├── client.py              # WebSocket Client für Restim
│   └── tcode.py               # TCode Protokoll-Implementierung
├── injection/
│   └── redirect.js            # JavaScript für API-Umleitung
└── config.py                  # Konfiguration
```

## Abhängigkeiten

```
PySide6>=6.9.3
PySide6-WebEngine>=6.9.3      # QtWebEngine für Embedded Browser
aiohttp>=3.9.0                 # Async HTTP Server (Fake Cloud)
websockets>=12.0               # WebSocket Client für Restim
```

## Offene Fragen / Risiken

1. **Mixed Content**: FapTap (HTTPS) macht Requests an localhost (HTTP)
   → Lösung: QWebEngineSettings kann Mixed Content erlauben
   → Oder: Lokalen Server mit self-signed HTTPS betreiben

2. **CORS**: Fake Server muss korrekte CORS-Header senden
   → Access-Control-Allow-Origin: https://faptap.net

3. **Script-URL**: Die Script-URL zeigt auf `scripts01.handyfeeling.com`
   → Wir müssen den Script von dort herunterladen (öffentlich zugänglich)
   → Kein Redirect nötig, nur die URL aus dem /hssp/setup Request extrahieren

4. **Connection Key**: FapTap validiert den Key möglicherweise clientseitig
   → Testen mit verschiedenen Key-Formaten (5-64 alphanumerisch)

5. **Funscript-Konvertierung für E-Stim**: Lineare Bewegung (0-100) muss
   in sinnvolle E-Stim Parameter übersetzt werden
   → Restim's eigene 1D-to-2D Konvertierung nutzen (funscript_1d_to_2d.py)
