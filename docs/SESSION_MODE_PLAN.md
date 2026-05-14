# Session-Modus — Konzeptioneller Plan

Status: Entwurf zur Diskussion. Noch keine Code-Änderungen vorgesehen.

Ein generativer dritter Modus neben FapTap, TheEdgy und Network. Er erzeugt eine vollständige Restim-Session aus einem User-Profil — ohne Video, ohne Funscript-Vorlage. Die Session folgt dem Profil zuverlässig in Charakter und Bogen, wird aber bei jedem Start konkret anders realisiert. Sie soll sich wie eine zusammenhängende Erzählung anfühlen, nicht wie zufällige Achsen-Wackelei.

---

## 1. Architektur in drei Ebenen

```
┌──────────────────────────────────────────────────────────────┐
│ USER-PROFIL (deterministisch)                                │
│  Dauer · Stil · Sensations-Mix · Hardware · Toleranzen ·     │
│  Verlaufs-Kurven · Sicherheits-Caps · Seed (optional)        │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ MACRO PLANNER (deterministisch aus Profil + Seed)            │
│  → Phasen-Plan: Init / Build / Plateau / Edge / Climax       │
│  → Master-Hüllkurven (Volume, Härte, Schärfe, Bewegung)      │
│  → Edge-Zeitpunkte mit Tiefe                                 │
│  → Stil-Wechsel-Marker                                       │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ MESO SCHEDULER (seeded-stochastisch, regel-basiert)          │
│  → wählt für jedes 5–30 s-Fenster ein Mikro-Pattern aus      │
│    dem 60-Pattern-Katalog                                    │
│  → respektiert Pattern-Compatibility-Matrix                  │
│    (kein Hard-Click direkt nach Slow-Sweep, etc.)            │
│  → vermeidet kürzliche Wiederholungen ("recency penalty")    │
│  → bindet Pattern-Wahl an aktuelle Phase + Stil              │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ MICRO RENDERER (smooth-stochastisch)                         │
│  → rendert das gewählte Pattern in 7 Achsen × ~50 Hz         │
│  → respektiert empirische Korrelationen aus dem Funscript-   │
│    Empirie-Memory (Vol↔Carrier, Vol↔Rise, PW↔Rise…)          │
│  → Perlin/OU-Noise statt White-Noise → smoothes Wackeln      │
│  → Crossfade an Pattern-Grenzen                              │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ SAFETY GUARD                                                 │
│  → User-Caps + absolute Limits clampen                       │
│  → Volume-Ramp erzwingen                                     │
│  → DC-Bias prüfen, charge-balance einhalten                  │
└──────────────┬───────────────────────────────────────────────┘
               ▼
        TCode → ws://127.0.0.1:12346/tcode → Restim
```

**Jede Ebene reicht ihren Output als Schiene an die nächste**, nicht als Sample-Stream. Macro plant einmalig die ganze Session als Datenstruktur, Meso bestimmt eine Pattern-Sequenz mit Zeitstempeln, erst Micro rendert in Echtzeit den 50-Hz-TCode-Strom. Das macht Pause/Skip/Replan jederzeit billig.

---

## 2. Konfigurations-Faktoren — vollständige Liste

Gegliedert nach Wirkungs-Ebene. Was fett ist, **muss** konfigurierbar sein. Der Rest ist Profi-Modus.

### A. Session-Geometrie
- **Gesamtdauer** (5 min – 3 h, Slider mit logarithmischer Skala)
- **Ziel-Modus**: Climax · Edge & Hold · Ruined Drop · Open-End / Tease-Loop
- Anzahl Phasen (Default 5; kann 3–7)
- Phasen-Gewichtung (z.B. extra langes Plateau, kurzer Build)

### B. Hardware-Profil
- **Geräteklasse**: 3-Phase (Stereostim/FOC V1) · 4-Phase (FOC V4) · 2-Channel klassisch
- **Aktive Achsen**: welche der 7 sollen wirklich moduliert werden? (Defaults aus Geräteklasse)
- Achsen-Caps (max Volume, max Carrier, max PW) — pro Achse
- Carrier-Range (z.B. „erlaubt 600–1400 Hz")
- Pulse-Width-Range (z.B. „nur 80–250 µs zulassen")

### C. Elektroden-Setup (für Sensations-Mapping)
- Anzahl Elektroden (2 / 3 / 4)
- **Position pro Elektrode** aus Preset-Liste:
  - Eichel · Schaft oben · Schaft unten · unter Hoden · Damm
  - Anal-Plug · Prostata-Insert
  - Brustwarze L/R · andere Body-Spots
- **Common-Elektrode** markieren (welche ist die geteilte) — wichtig für 3-Phase
- Elektrodengröße (klein/mittel/groß) — beeinflusst Stromdichte → Schmerz-Caps

### D. Erfahrungs-Stufe (1 Slider statt 3 Toleranz-Werte)
**Funktion**: harte Caps und Floors für Hüllkurven und Achsen-Range. Macht keinen Random, beeinflusst nicht den Charakter — definiert nur wie weit der Generator gehen darf.

| Stufe | Name | Vol Floor/Ceiling | Carrier max | PW max | Volume-Ramp | Max Drop-Tiefe |
|---|---|---|---|---|---|---|
| 1 | **Beginner** | 20 / 70 | 1000 Hz | 150 µs | 1 %/min | 25 % |
| 2 | **Eingewöhnt** | 25 / 80 | 1300 Hz | 200 µs | 2 %/min | 35 % |
| 3 | **Erfahren** | 30 / 85 | 1600 Hz | 250 µs | 3 %/min | 45 % |
| 4 | **Routiniert** | 35 / 92 | 1800 Hz | 300 µs | 4 %/min | 55 % |
| 5 | **Profi** | 40 / 100 | 2200 Hz | 400 µs | 5 %/min | 70 % |

Zahlen sind Erstvorschläge, kalibrieren mit erster Test-Session-Welle.

Wichtig: Stufe 1 + Sensations-Slider „Hart" → härteste Pulse **innerhalb der Stufe** (PW=150 µs), nicht absolut. Stufe = Sicherheitskorridor, Slider = Position im Korridor.

### E. Session-Stil (Macro-Vibe) — 6 user-facing Stile

| # | Name | Charakteristik | Macro-Bogen |
|---|---|---|---|
| 1 | **Sanfter Aufbau** | Langer linearer Hypno-Build, kein Beat, fließend | Volume linear 30→85 |
| 2 | **Crescendo** | Klassischer Build zur Erlösung, klare Steigerung mit Climax | Volume 25→95, Phase 5 holt das Letzte raus |
| 3 | **Beat-Drop** | Rhythmische Patterns auf Beat-Grid, deutliche Bursts | Volume-Plateaus mit Beat-Pulse-Bursts, hohe lokale Burstiness |
| 4 | **Edging** | Gehaltene hohe Erregung mit periodischen Pull-Backs | Volume hält 70–85, planmäßige Drops auf 40, Re-Build |
| 5 | **Ruin** | Steil zum Climax, harter Drop kurz davor | Phase 1–4 schneller Climb, Phase 5 massive Negative-SubWave |
| 6 | **Endlos-Tease** | Kein Ziel, kein Climax, oszilliert ewig | Volume zwischen 30 und 60, kein Final |

„Aftermath" ist kein eigener Stil — entspricht „Sanfter Aufbau" mit kurzer Dauer + niedriger Erfahrungs-Stufe.

### F. Sensations-Mix (zentrale 4 Slider — bilden die Charakter-Persönlichkeit)
Diese Slider treiben den Mikro-Pattern-Katalog-Filter und die Achsen-Default-Bänder:

1. **Schärfe ↔ Tiefe**  →  Carrier-Range
   - Schärfe-Pol: 500–800 Hz, oberflächlich, kribbelnd
   - Tiefe-Pol: 1500–2500 Hz, dumpf, durchdringend

2. **Granular ↔ Glatt**  →  Pulse-Frequency-Range
   - Granular-Pol: 5–35 Hz, einzeln-klopfend
   - Glatt-Pol: 60–150 Hz, summend
   - Mitte ist die schwierige Zone (Flutter)

3. **Weich ↔ Hart**  →  Pulse-Width + Pulse-Rise-Time-Range
   - Weich-Pol: PW 60–120 µs, Rise hoch (40–60)
   - Hart-Pol: PW 200–400 µs, Rise niedrig (10–20)

4. **Statisch ↔ Wandernd**  →  alpha/beta Bewegungsanteil
   - Statisch-Pol: Position bleibt minutenlang
   - Wandernd-Pol: konstante Rotation, wechselnde Trajektorien

### G. Verlaufs-Kurven (das ist der Graph aus dem Bild)
Pro Master-Größe wird eine Hüllkurve über die Session-Dauer konfiguriert. Kurven sind drag-able, Bänder werden aus „Variabilität-Stärke" gefüllt:

- **Master-Intensität** (Volume-Hüllkurve) — die wichtigste, immer sichtbar
- **Härte** (Pulse-Hardening-Kombi) — koppelt PW + Rise
- **Schärfe** (Carrier-Verlauf) — folgt empirisch oft der Intensität
- **Bewegungs-Aktivität** (alpha/beta-Rotations-Anteil)
- **Edge-Density** (wie viele Pull-Backs pro Minute) — separat sichtbar als Drop-Marker

Defaults werden aus Stil-Wahl + Dauer + Ziel-Modus generiert. User kann Punkte verziehen.

### H. Charakter (1 Wahl statt 3 Slider) — 4 Presets
**Funktion**: steuert Generator-Persönlichkeit. Wie unvorhersehbar wird die konkrete Realisation bei gleichem Profil. Macht keine Sicherheits-Änderungen.

| Charakter | Band-Breite | Pattern-Vielfalt | Surprises | Pattern-Dauer | Übergang |
|---|---|---|---|---|---|
| **Sanft** | ±5 % | niedrig (~10 Patterns aktiv) | keine | 15–30 s | sehr glatt |
| **Lebendig** *(Default)* | ±10 % | mittel (~25 Patterns) | 1 / 5 min | 8–15 s | glatt |
| **Spielerisch** | ±15 % | hoch (~40 Patterns) | 1 / 2 min | 5–10 s | normal, mit Mikro-Edges zwischendurch |
| **Wild** | ±20 % | maximal (alle Patterns) | 1 / Min, inkl. Sub-Stil-Sprünge | 3–8 s | längere/disorientierende Crossfades, Patterns dürfen Hüllkurve kurz übersteuern |

Wild bricht niemals Sicherheits-Limits oder Macro-Bogen — spielt nur innerhalb des Erlaubten erratischer.
Sub-Wave-Amplitude und -Frequenz wird vom Charakter skaliert: Sanft = lange flache SubWaves, Wild = kurze scharfe.

### I. Live-Override
- Master-Volume (0–100%, jederzeit drehbar)
- Pause / Resume
- Skip Current Phase
- Edge Now (sofortiger Pull-Back)
- Boost Now (kurzer Spike)
- **Panic-Stop** (sofort 0)

### J. Seed
- **Seed-Eingabe** (optional sichtbar): leer = neuer Random-Seed pro Start. Gleicher Seed + gleiches Profil → bit-identische Session (für Wiederholbarkeit). User normal: leer lassen, jede Session ist neu.

---

## 3. Determinismus-Negation OHNE Random-Chaos

Drei eingebaute Mechanismen, die zusammenwirken:

### Schicht 1 — Macro: deterministisch
Aus `(Profil, Seed)` wird ein eindeutiger Phasen-Plan abgeleitet. Gleicher Input → gleicher Plan. Hier gibt es keine Stochastik. Das garantiert: jede Session erfüllt das Wunschprofil.

### Schicht 2 — Meso: seeded-stochastisch mit Regeln
Pattern-Auswahl ist eine gewichtete Stichprobe aus einem Pool kompatibler Patterns. Gewichtung kommt aus:
- aktuelle Phase (Build vs. Edge bevorzugen unterschiedliche Patterns)
- aktueller Sensations-Mix (Slider-Position)
- Recency-Penalty (kürzlich gespielte Patterns sinken im Gewicht)
- Compatibility-Score zum vorherigen Pattern

Mit gleichem Seed → identische Sequenz. Mit anderem Seed → andere Pattern-Reihenfolge, aber innerhalb derselben Pool-Constraints. **Kein freies Random.**

### Schicht 3 — Micro: smooth-stochastisch
Innerhalb eines Patterns wird kein White-Noise verwendet. Stattdessen:
- **Perlin-/Simplex-Noise** für Volume-Jitter (smooth, kein Zappel)
- **Ornstein-Uhlenbeck-Prozess** für PW/Carrier-Jitter (mean-reverting, bleibt im Band)
- **Phase-getriebene Sinus** für Position-Trajektorie (stabile Frequenzen mit langsamer Frequenz-Drift)

Diese Prozesse sind seeded und kontinuierlich differenzierbar — ergo immer „konsistent wirkend", nie zackig.

### Schicht 4 — Nested Envelopes (linear-aber-wellig)
Das wichtigste Realismus-Prinzip. Echte Sessions sind nicht monoton-glatt steigend, sondern **lokal lebendig auf einem global linearen Trend**. Modelliert als hierarchische Hüllkurven-Komposition:

```
Final(t) = MacroTrend(t) + SubWaves(t) + PatternForm(t) + Jitter(t)
```

- **MacroTrend**: linearer Aufstieg über die 5 Phasen, von Phase-1-Floor bis Phase-5-Peak. Glatt, monoton, deterministisch.
- **SubWaves**: 30–90 s Mini-Crescendi mit eigener Form (kleines Build → Peak → kleiner Drop → Re-Build). Amplituden-Hüllkurve **wächst über die Session** (späte Sub-Wellen sind höher) und **Perioden werden kürzer** (späte Sub-Wellen folgen dichter aufeinander). Anzahl: 8–25 pro Session, je nach Stil und Dauer.
- **PatternForm**: jeder Mikro-Pattern bringt seine eigene 5–15 s lange Form mit (Spike-Drop, Sweep, Step-Hold, etc.). Sitzt auf der aktuellen SubWave-Position auf.
- **Jitter**: Perlin-Noise mit niedriger Amplitude, sorgt für mikroskopische Lebendigkeit.

**Kompositions-Operator**: Standard ist **mischender Operator** statt reine Addition — die Sub-Welle moduliert den verbleibenden Headroom: `Final = MacroTrend + (1 - MacroTrend/Cap) * SubWaveAmplitude`. Damit beißen sich Macro und SubWave nicht über dem Cap, und SubWaves werden in Phase 5 (wo MacroTrend nahe Cap ist) automatisch flacher — was richtig ist, weil dort kein Headroom mehr ist.

**Wichtige Konsequenz**: Auch in flachen Edging-Plateaus passiert immer was. Niemals minutenlange Stagnation. Selbst „Plateau" hat Mini-Wellen. Das ist der Realismus, der Generated-Sessions von Random-Sessions trennt.

**Stil-spezifische Kalibrierung**:
- Slow-Hypno: viele lange flache SubWaves (60–90 s), niedrige Amplitude → fließt
- Cock-Hero-Beat: kurze scharfe SubWaves (15–30 s) auf Beat-Grid → pulsiert
- Edging-Plateau: SubWaves mit deutlichen Drop-Anteilen (Drop-Tiefe = 30–50 % der Amplitude) → wellig mit Pull-Backs
- Ruined-Path: SubWaves wachsen extrem stark in Phase 4, Phase 5 hat eine massive Negative-SubWave (= der Ruin-Drop)

---

## 4. Konsistenz-Garantie

Damit die generierte Session wie ein Stück fließt, nicht wie aneinandergeklebte Patterns:

### Mechanismus 1 — Pattern-Compatibility-Matrix
Aus den 60 Patterns wird eine 60×60-Matrix gebaut. Werte 0–1 = Erlaubt-direkt-danach-Score. Beispiele:
- `Hard-Click → Slow-Sweep` = 0.1 (verbieten)
- `Smooth-PW-Sweep → Linear-PW-Build` = 0.9 (passt)
- `Static-Floor → Static-Center` = 0.7 (ok)
- `Beat-Drop → Spike-Drop` = 0.8 (passt rhythmisch)

Initial heuristisch befüllt, später aus Funscript-Empirie verfeinerbar (welche Patterns folgen real aufeinander in der 26-Session-Sammlung).

### Mechanismus 2 — Macro-Bogen wird hart durchgesetzt
Pattern-Auswahl darf den Macro-Volume-Plan nicht verletzen. Wenn Phase 3 maximal Volume 0.85 verlangt, sind High-Intensity-Patterns gefiltert. Dadurch: der globale Bogen ist immer sauber.

### Mechanismus 3 — Crossfade an Pattern-Grenzen
Übergang zwischen zwei Patterns wird über 1–3 s linear-gemischt: alle Achsen werden zwischen dem Endwert des alten und dem Startwert des neuen Patterns interpoliert. Verhindert Sprünge und „Klicks" in der Ausgabe.

### Mechanismus 4 — Smoothing-Buffer
Letzte 200 ms aller Achsen-Werte sind in einem Ringpuffer. Jeder neue Sample wird gegen den Buffer geslewratet — d.h. maximale Änderungs-Rate pro 10 ms ist gedeckelt. Das eliminiert pathologische Edge-Cases.

### Mechanismus 5 — Konsistenz-Nachweis im Macro-Plan
Der Macro-Plan wird vor Session-Start auf 4 Eigenschaften geprüft:
1. **Monotonie** (steigt globaler Trend wie geplant?)
2. **Plateau-Länge** (gibt es Edge-Plateaus die zu lang/kurz sind?)
3. **Drop-Tiefe** (Drops nicht tiefer als Toleranz erlaubt)
4. **Climax-Erreichbarkeit** (würde Phase 5 das Ziel-Volume erreichen?)

Wenn nicht erfüllt: Plan wird neu gewürfelt, bis er passt (max 10 Versuche).

---

## 5. Der Graph (UI-Element)

Wie im Referenzbild — vier Master-Kurven, aber bewusst **nur eine ist direkt editierbar**: die Master-Intensität. Die anderen drei folgen automatisch aus den empirisch gemessenen Korrelationen (Vol↔Carrier r≈0.9, Vol↔Härte r≈0.85, etc.). Das hält die UI schlank und garantiert konsistente Sessions, weil der User die universelle Restim-Kopplung nicht versehentlich brechen kann.

```
   100 ┤                              ╭╮     ╭──╮
       │  Master-Intensität ────╮  ╭──╯╰╮ ╭──╯  ╰─
       │  (drag-bar)         ╭──╯╮╭╯    ╰─╯
       │                  ╭──╯  ╰╯       ↑ SubWaves sichtbar
       │             ╭────╯
    50 ┤  ────────────────  Härte (auto-folgt)
       │  ──────────────  Schärfe (auto-folgt)
       │  ──────────────  Bewegung (auto-folgt)
       │
     0 ┴───────────────────────────────────────────
       0          25          50          75      100 %
       Init      Build      Plateau     Edge   Climax
       
       ◯ Drop                ◯ Drop          ▲ Climax
```

- **Master-Intensität als Hauptlinie**, fett, drag-bar an Stützpunkten
- **Härte / Schärfe / Bewegung** als dünnere abhängige Linien, automatisch berechnet — sichtbar als Vorschau, nicht direkt manipulierbar
- **SubWaves sind sichtbar** auf der Master-Linie (kleine Auf-und-Ab-Wellen über dem linearen Trend) — nicht editierbar, aber visualisiert dass es nicht monoton wird
- Halb-transparente Bänder = Variabilitäts-Range aus dem gewählten Charakter-Preset
- **Drop-Marker** (◯) sind klickbar zum Verschieben, hinzufügen, löschen
- X-Achse: Zeit-Skala + Phasen-Sektoren als Hintergrund-Bänder
- Hover zeigt momentane Werte aller vier Linien

Editierbar nur:
- Master-Intensitäts-Stützpunkte (drag, add, delete)
- Drop-Marker (verschieben, hinzufügen, löschen)

Schnell-Presets über dem Graph:
- „Sanfter Build" · „Steiler Crescendo" · „1 Edge" · „3 Edges" · „Tease-Loop" · „Reset" (Stil-Default)

---

## 6. UI-Layout (Sidebar erweitert) — schlank, smart-defaults

Reduziert auf **5 Cluster, ~10 sichtbare Eingaben**. Detail-Caps und Variabilitäts-Parameter werden aus Stil + Erfahrungs-Stufe + Hardware-Preset abgeleitet, nicht einzeln eingegeben. Profi-Tab versteckt die Feinjustage hinter einem „Erweitert"-Toggle.

```
┌───────────────────────────────────────────────────┐
│ MODE: [FapTap] [TheEdgy] [Network] [SESSION ◀]   │
├───────────────────────────────────────────────────┤
│                                                   │
│ ▼ Session                                         │
│   Stil:    [Slow-Hypno         ▼]                 │
│   Dauer:   ◇──────●─────────◇   45 min            │
│   Ziel:    [Edge & Hold        ▼]                 │
│                                                   │
│ ▼ Sensations-Mix                                  │
│   Schärfe ◇──────●────────────◇ Tiefe             │
│   Granular ◇──────────●────◇ Glatt                │
│   Weich ◇─────────●─────◇ Hart                    │
│   Statisch ◇──●──────────◇ Wandernd               │
│                                                   │
│ ▼ Charakter                                       │
│   ⚪ Sanft  ⚫ Lebendig  ⚪ Spielerisch  ⚪ Wild    │
│   (steuert Variabilität, Pattern-Vielfalt,        │
│    Überraschungs-Häufigkeit als Bundle)           │
│                                                   │
│ ▼ Erfahrung                                       │
│   ◇──●────────◇  Stufe 2 (Eingewöhnt)             │
│   (1=Beginner … 5=Profi — setzt intern Caps für  │
│    Volume, Carrier, Pulse-Width)                  │
│                                                   │
│ ▼ Hardware & Elektroden                           │
│   Preset: [3-Phase FOC Standard ▼]                │
│   ┌──────────────────────┐                        │
│   │   [Body-Schema mit    │  ← visuelle           │
│   │    Klickpunkten für   │     Auswahl der       │
│   │    Elektroden]        │     Elektroden-Spots  │
│   └──────────────────────┘                        │
│   E1 Eichel ★ Common · E2 Schaft · E3 unter Hoden │
│                                                   │
│ ───────────────────────────────────────────────── │
│ [GRAPH: Master-Line + Drops + SubWaves visible]   │
│ Quick-Presets: [Sanfter Build] [3 Edges] [Reset]  │
│ ───────────────────────────────────────────────── │
│                                                   │
│ ▶ Erweitert (Profi-Modus)                         │
│   – Achsen-Caps einzeln                           │
│   – Pattern-Wiederhol-Sperre                      │
│   – Crossfade-Zeit                                │
│   – Seed manuell setzen                           │
│   – Pattern-Pool kuratieren                       │
│                                                   │
│ ┌────────────────────────────────────────────┐   │
│ │   ▶  START SESSION                         │   │
│ └────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────┘
```

**Designprinzip**: Default-Konfiguration soll für 90 % der Nutzer eine gute Session ergeben. Stil + Dauer + Ziel + ein Schieber im Sensations-Mix reicht als Mindest-Eingabe. Alles andere ist optional.

**Was im Erweitert-Tab versteckt ist**:
- Per-Achse Caps (statt aus Erfahrungs-Stufe abgeleitet)
- Pattern-Pool-Kuration (welche Patterns sind im Spiel — Default: alle)
- Pattern-Wiederhol-Sperre (s)
- Crossfade-Zeit (s)
- Seed manuell
- SubWave-Parameter (Anzahl, Amplituden-Wachstum, Periode)

**Live-View während Session** (ersetzt obige Form, gleiches Panel):
- Großer Indicator: Phase + verbleibende Zeit + nächster Drop in N s
- Live-Werte der 7 Achsen als kleine Streifen-Plots
- Live-Marker auf dem Graph (Cursor wandert über die Master-Linie)
- Override-Buttons als große Tap-Targets:
  **Pause · Skip Phase · Edge Now · Boost · STOP**

---

---

## 7. Datenmodell

### SessionProfile (vom User konfiguriert, JSON-serialisierbar)
```python
@dataclass
class SessionProfile:
    duration_s: int
    style: SessionStyle              # slow_hypno | cock_hero_beat | ...
    target: SessionTarget            # climax | edge_hold | ruined | tease
    sensation: SensationMix          # 4 Slider 0..1
    hardware: HardwareProfile        # device_class, electrodes, caps
    tolerance: ToleranceProfile      # 3 Slider, no_go list
    envelope: EnvelopePlan           # 4 Master-Kurven mit Stützpunkten
    variability: VariabilityProfile  # 3 Slider + recency_lockout
    safety_caps: SafetyCaps
    seed: Optional[int]              # None = random per start
```

### MacroPlan (vom Macro Planner erzeugt)
```python
@dataclass
class MacroPlan:
    phases: list[Phase]              # 3–7 Phasen mit Zeit-Boundaries
    master_envelopes: dict[str, Curve]   # 4 Curves über Zeit, sample-bar
    edge_events: list[EdgeEvent]     # geplante Drops (t, depth, recovery_s)
    style_markers: list[StyleMarker] # Übergangs-Punkte für Stilwechsel
    seed: int
```

### MesoSchedule (vom Meso Scheduler erzeugt, optional vorgeneriert oder live)
```python
@dataclass
class PatternSlot:
    t_start_s: float
    t_end_s: float
    pattern_id: str                  # aus 60-Pattern-Katalog
    intensity_scale: float           # wie stark Pattern auf Master-Kurve liegt
    parameters: dict                 # pattern-spezifisch
```

### MicroState (live, im Renderer)
Aktuelle Slew-Buffer + Noise-Generator-States, wird intern gehalten.

---

## 8. Wo das in unserer Codebase landet

Vorgeschlagene neue Module:

```
src/
├── session/                          ← neu
│   ├── __init__.py
│   ├── profile.py                    SessionProfile-Dataclasses + Validation
│   ├── macro_planner.py              MacroPlan aus Profile
│   ├── meso_scheduler.py             Pattern-Auswahl mit Compatibility-Matrix
│   ├── pattern_catalog.py            Die 60 Mikro-Patterns als Renderer-Funktionen
│   ├── micro_renderer.py             Pattern → 7 Achsen mit Noise + Crossfade
│   ├── safety_guard.py               Caps + DC-Balance + Volume-Ramp
│   ├── session_runner.py             Orchestriert Macro+Meso+Micro, sendet zu TCode-WS
│   └── presets.py                    Stil-Defaults, Verlaufs-Templates
├── ui/
│   ├── sidebar_html.py               (existing — erweitern)
│   └── session_graph.py              ← neu, Graph-Komponente (HTML+JS)
└── main.py                           Mode-Switcher um SESSION-Modus erweitern
```

Output-Pfad bleibt identisch: `session_runner` schreibt TCode in den selben WebSocket wie FapTap/TheEdgy → keine Änderung an Restim selbst nötig.

Pattern-Katalog (`pattern_catalog.py`): die 60 Patterns aus `docs/FUNSCRIPT_PATTERNS.md` werden als Python-Funktionen implementiert mit Signatur:

```python
def render(t_local: np.ndarray, slot: PatternSlot, master: dict, rng: np.random.Generator) -> dict[str, np.ndarray]
```

Jeder Pattern liefert für sein Zeitfenster die 7 Achsen-Arrays. Master-Werte (aktuelle Hüllkurven-Position) werden als Multiplikator/Offset berücksichtigt.

---

## 9. Workflow für den User

**Anlegen einer Session:**
1. Modus „SESSION" wählen
2. Stil + Dauer + Ziel wählen → System generiert Default-Verlaufs-Kurven
3. Optional: Sensations-Slider, Toleranzen, Hardware feinjustieren
4. Optional: Stützpunkte im Graph verziehen, Drops setzen
5. **Speichern als Preset** (Name + JSON in `data/session_presets/`)
6. **▶ Start**

**Während der Session:**
- Live-View mit aktuellen Achsen + Phasen-Indicator
- Override-Buttons jederzeit verfügbar
- Bei „Edge Now" → ein extra Drop wird in die Live-Sequenz injiziert, danach normal weiter
- Bei „Skip Phase" → Macro-Plan wird vorgespult

**Wiederholbarkeit:**
- Jede gestartete Session loggt Profile + Seed in `data/session_log.jsonl`
- „Replay" Button auf vergangene Session → setzt Profile + Seed → identische Session

---

## 10. Entscheidungs-Log

### Entschieden (User-Direktiven, Stand Iteration 3)
- **Pattern-Katalog**: alle Patterns aus `docs/FUNSCRIPT_PATTERNS.md` ab v1, nicht kuriert.
- **Sessions-Charakter**: linear ansteigender Globaltrend MIT permanenten lokalen Steigerungen und Schwankungen → Nested-Envelopes (Section 3, Schicht 4).
- **UI-Philosophie**: keine Detail-Granularität. Smart-Defaults pro Stil/Erfahrung. Profi-Tab versteckt Feinjustage. Vier Master-Linien im Graph, aber **nur Master-Intensität direkt editierbar**.
- **Stile**: 6 user-facing Stile (Sanfter Aufbau, Crescendo, Beat-Drop, Edging, Ruin, Endlos-Tease).
- **Erfahrungs-Stufe**: 5 Stufen (Beginner → Profi), definiert harte Caps/Floors. Tabelle in Section E.
- **Charakter**: 4 Presets (Sanft, Lebendig, Spielerisch, Wild), steuert Generator-Persönlichkeit. Tabelle in Section H.
- **Macro-Planung**: **lernend** — zwei Modelle auf den 26 Sessions in `E:\MultiF\Content` trainiert:
  - Macro-Hüllkurven-Sampler (MLP oder Gauß-Prozess auf Phasen-Mittelwerte, conditioned on Stil/Dauer/Ziel)
  - Pattern-Sequenz-Markov pro (Stil, Phase) für Meso-Layer
  - Pre-Processing-Step nötig: automatische Pattern-Annotation der 26 Sessions
  - Mikro-Renderer bleibt regelbasiert (deterministische Wellenform-Mathematik)

### Noch zu klären
**(a) UI-Stack für den Graph**
- `pywebview` HTML/JS. Drag-able Multi-Line: **D3.js** (mächtig, viel Code) vs. **Chart.js** + Plugin (einfach, weniger flexibel) vs. **uPlot** (schnell, mid-flexibel).
- Empfehlung: **uPlot + custom Drag-Layer**.

**(d) Konsistenz-Smoothing**
- Global Slew-Limit (kann Hard-Click-Patterns kaputt smoothen) vs. pattern-spezifisch.
- Empfehlung: **pattern-spezifisch** mit globalem Default.
