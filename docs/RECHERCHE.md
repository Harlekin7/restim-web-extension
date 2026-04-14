# Recherche: FapTap.net -> Restim Extension

## 1. FapTap.net - Analyse

### Seitenstruktur
- **Typ**: Single Page Application (SPA) mit Cloudflare-Schutz
- **Rendering**: Client-side JavaScript - HTML enthält nur Bootstrap/Cloudflare-Challenge-Code
- **Analytics**: Google Analytics `G-3H4HYM16Q4`
- **CAPTCHA**: Key `05aeb4b9-56e7-480f-8b00-9b2a26208975`

### URL-Muster
| Pfad | Beschreibung |
|------|-------------|
| `/v/{numeric_id}` | Einzelne Videos (z.B. `/v/2041092104276414465`) |
| `/videos` | Video-Übersicht |
| `/videos/trending` | Trending Videos |
| `/videos/best` | Beste Videos |
| `/videos/underrated` | Underrated Videos |
| `/funscripts` | Funscript-Bibliothek |
| `/tags` | Tag-basierte Navigation |
| `/creators` | Creator-Profile |
| `/performers` | Performer-Profile |
| `/playlists` | Playlisten |
| `/explore` | Entdecken |
| `/studio/` | Studio (blockiert in robots.txt) |
| `/ai-stroking` | AI-Stroking Feature |

### Content-Umfang
- **~149 Sitemap-Dateien** für Videos = tausende Videos
- Separate Sitemaps für: Videos, Tags, Playlists, Creators, Performers
- Unterstützte Geräte: The Handy, Kiiroo Keon, Lovense, Autoblow, Svakom, LELO, Fleshy

### Geräte-Kommunikation (Key Finding!)
- FapTap verbindet sich **direkt per WebSocket** zu einem lokalen **Buttplug/Intiface-Server**
- Verwendet **WSS (Secure WebSocket)** da die Seite HTTPS nutzt
- Standard-Port: **12345** (Intiface Central Default)
- Protokoll: **Buttplug v3** JSON Messages über WebSocket
- **Kein eigenes API** - FapTap hat keinen öffentlichen REST/GraphQL API-Endpunkt

### Datenfluss auf FapTap
```
FapTap.net (Browser/JS)
    |
    |-- Lädt Video von CDN
    |-- Lädt Funscript (JSON) von CDN/Server
    |-- Parsed Funscript clientseitig
    |-- Verbindet zu Intiface via WSS://localhost:12345
    |-- Sendet Buttplug LinearCmd/ScalarCmd basierend auf Funscript-Timing
    |
    v
Intiface Central (lokal)
    |
    v
Physisches Gerät (BLE/USB/Serial)
```

### Problem: Datenabgriff
Da FapTap eine SPA mit Cloudflare-Schutz ist, können wir die Funscript-Daten **NICHT** einfach per HTTP-Request abgreifen. 

**Mögliche Strategien:**
1. **Buttplug-Proxy**: Eigenen Buttplug-Server starten, der sich als Intiface ausgibt, FapTap's Commands abfängt und an Restim weiterleitet
2. **Browser-Extension**: JS in FapTap injizieren, Funscript-Daten und/oder Buttplug-Commands abfangen
3. **WebSocket-MITM**: Zwischen FapTap und Intiface einen Proxy schalten
4. **Embedded Browser (CEF/Qt WebEngine)**: FapTap in eigenem Browser laden, WebSocket-Traffic abfangen

---

## 2. Restim - Netzwerk-Interfaces

### Verfügbare Eingabe-Protokolle

| Protokoll | Port | Pfad | Format | Standard |
|-----------|------|------|--------|----------|
| **WebSocket** | 12346 | `/tcode` | TCode Commands | Aktiviert |
| **WebSocket** | 12346 | `/sensors/*` | Sensor-Daten | Aktiviert |
| **TCP** | 12347 | - | TCode (newline-getrennt) | Konfigurierbar |
| **UDP** | 12347 | - | TCode (newline-getrennt) | Konfigurierbar |
| **Serial** | COM-Port | - | TCode (115200 baud) | Konfigurierbar |
| **Buttplug WSDM** | Variabel | - | Buttplug Binary | Konfigurierbar |

### TCode-Format (Restim-Variante)
```
Syntax:  [Achse][Wert]I[Intervall]
Achse:   2 Zeichen (z.B. L0, L1, L2)
Wert:    0-10000 (entspricht 0.0-1.0)
Intervall: Millisekunden für Interpolation

Beispiele:
  L05000        -> Achse L0 auf 50%
  L05000I100    -> Achse L0 auf 50% über 100ms
  L00000 L10000 -> Achse L0=0%, L1=0% (Leerzeichen-getrennt)
```

### Achsen-Mapping in Restim
TCode-Achsen können auf folgende Restim-Parameter gemappt werden:
- Position Alpha/Beta (Bewegungsrichtung)
- Volume API/External
- Carrier Frequency
- Pulse Frequency, Width, Interval, Rise Time
- Vibration (Frequency, Strength, Bias)
- Intensity A/B/C/D (4-Phasen-System)

### Bester Übertragungsweg: **WebSocket auf Port 12346 `/tcode`**
- Bereits standardmäßig aktiviert
- Bidirektional
- TCode-Format ist einfach zu generieren
- Kein zusätzlicher Server nötig

---

## 3. Funscript-Format

### JSON-Struktur
```json
{
  "version": "1.0",
  "inverted": false,
  "range": 100,
  "actions": [
    {"at": 0, "pos": 50},
    {"at": 500, "pos": 100},
    {"at": 1000, "pos": 0},
    {"at": 1500, "pos": 75}
  ],
  "metadata": {
    "creator": "...",
    "description": "...",
    "duration": 300000,
    "license": "...",
    "notes": "...",
    "performers": ["..."],
    "script_url": "...",
    "tags": ["..."],
    "title": "...",
    "type": "basic",
    "video_url": "..."
  }
}
```

### Wertebereiche
- `at`: Zeitstempel in Millisekunden
- `pos`: Position 0-100 (0=unten, 100=oben)

### Multi-Achsen
Über Dateinamen-Konvention:
- `video.funscript` -> L0 (auf/ab)
- `video.surge.funscript` -> L1 (vor/zurück)
- `video.sway.funscript` -> L2 (links/rechts)
- `video.twist.funscript` -> R0 (Drehung)
- `video.roll.funscript` -> R1 (Rollen)
- `video.pitch.funscript` -> R2 (Neigung)

---

## 4. Buttplug-Protokoll (für Proxy-Ansatz)

### Handshake
```json
// Client -> Server
[{"RequestServerInfo": {"Id": 1, "ClientName": "FapTap", "ProtocolVersionMajor": 4, "ProtocolVersionMinor": 0}}]

// Server -> Client
[{"ServerInfo": {"Id": 1, "ServerName": "Restim Proxy", "MaxPingTime": 100, "ProtocolVersionMajor": 4, "ProtocolVersionMinor": 0}}]
```

### LinearCmd (für Funscript-Bewegungen)
```json
[{"LinearCmd": {"Id": 1, "DeviceIndex": 0, "Vectors": [{"Index": 0, "Duration": 500, "Position": 0.75}]}}]
```

### ScalarCmd (v3, generisch)
```json
[{"ScalarCmd": {"Id": 1, "DeviceIndex": 0, "Scalars": [{"Index": 0, "Scalar": 0.5, "ActuatorType": "Vibrate"}]}}]
```

---

## 5. Python-Bibliotheken

### buttplug-py (Community)
```bash
pip install buttplug-py
```
- Async Python Client für Buttplug Protocol v3
- WebSocket-Verbindung zu Intiface
- LinearCmd, ScalarCmd, RotateCmd Support

### Weitere benötigte Libraries
```
PySide6          # GUI + QtWebEngine für integrierten Browser
websockets       # WebSocket Server/Client
aiohttp          # Async HTTP
```

---

## 6. Geclonte Referenz-Repositories

| Repository | Pfad | Relevanz |
|-----------|------|----------|
| diglet48/restim | `references/restim/` | Ziel-Software, TCode/WebSocket Interface |
| Siege-Wizard/buttplug-py | `references/buttplug-py/` | Python Buttplug Client |
| buttplugio/buttplug | `references/buttplug/` | Buttplug Protokoll-Spezifikation |
| buttplugio/buttplug-py | `references/buttplugio-buttplug-py/` | Offizieller (deprecated) Python Client |
| intiface/intiface-central | `references/intiface-central/` | Intiface Server-Referenz |
| Yoooi0/MultiFunPlayer | `references/MultiFunPlayer/` | Referenz für Multi-Achsen + TCode |
| multiaxis/TCode-Specification | `references/TCode-Specification/` | TCode Protokoll-Spezifikation |

---

## 7. Empfohlene Architektur

### Variante A: Buttplug-Proxy (Empfohlen)
```
FapTap.net (Browser)
    |
    | WSS://localhost:12345 (Buttplug Protocol)
    v
[Unsere Software: Buttplug-Proxy-Server]
    |
    | Empfängt LinearCmd/ScalarCmd
    | Konvertiert zu TCode
    | L0{pos*100}I{duration}
    v
Restim (WebSocket :12346/tcode)
    |
    v
E-Stim Gerät
```

**Vorteile:**
- Keine Browser-Extension nötig
- FapTap denkt, es spricht mit Intiface
- Einfache Konvertierung Buttplug -> TCode
- Funktioniert auch mit anderen Funscript-Websites

### Variante B: Integrierter Browser + Proxy
```
[Unsere Software]
    |
    +-- Qt WebEngine Browser (zeigt FapTap.net an)
    |     |
    |     | Interceptet WebSocket-Verbindungen
    |     | ODER injiziert JS für Funscript-Abgriff
    |     v
    +-- Buttplug-Proxy / Direkt-Konvertierung
    |
    | TCode über WebSocket
    v
Restim (:12346/tcode)
```

**Vorteile:**
- Integrierte Erfahrung
- Volle Kontrolle über den Browser
- Kann auch Funscript-Daten direkt abfangen (nicht nur Buttplug-Commands)
- Video-Synchronisation möglich

### Empfehlung: Variante B (Integrierter Browser + Proxy)
Kombiniert die Vorteile beider Ansätze und bietet die beste User Experience.
