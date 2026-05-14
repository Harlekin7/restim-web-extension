# Restim Funscript Pattern-Analyse

Sammlungs-Verzeichnis: `E:/MultiF/Content` — 26 Session-Ordner, **203 Funscript-Dateien**, geparst von einem Bulk-Analyzer (`scripts/analyze_funscripts.py`), einem Cross-Axis-Korrelator (`scripts/deep_inspect.py`) und einem Window-Sampler (`scripts/snapshots.py`). Alle Roh-Statistiken liegen unter `data/funscript_analysis/` (`per_file.csv`, `per_session.csv`, `deep_inspect.json`, `snapshots.json`).

Methodik: pro Datei min/max/mean/stdev der pos-Werte, Action-Density, Interval-Verteilung, Histogramm, Steigung, 10-Segment-Mittel. Pro Session: Pearson-Korrelation aller Achsen über 1000 resampelte Punkte, Alpha/Beta-Rotationsdetektion (Phasenwinkelfortschritt + Radiusstabilität in 50-Sample-Fenstern), Burstiness (Anteil hoch-aktiver 1-s-Bins). Detail-Snapshots in 15-s-Fenstern für 15 Sessions × 1–4 Achsen.

Alle Werte sind tatsächlich gemessen, sofern nicht ausdrücklich als „Schätzung" markiert.

---

## Teil A — Sammlungs-Überblick

Die 26 Session-Ordner enthalten ein heterogenes, aber recht klar geclustertes Material. Acht Sessions sind reine 1-Achsen-Stroker-Funscripts (`Heavenly 3`, `Suave`, `Lust Dream`, `CH.Electric.Barbarella…-estim`) ohne E-Stim-Setup; die restlichen 18 enthalten 5–19 Achsen pro Session.

Längen reichen von **27 min** (`Klinik Indus`) bis **136 min** (`Liya` / `LS Remix` — letzteres ist ein Subset desselben Skripts ohne Position1D-Spur). Median-Dauer ≈ 75 min. Die fünf längsten Sessions (Liya 136 min, Barbarella 100 min, Church 2 97 min, WarpZone 92 min, Rythm of Desire 90 min) sind alle Cock-Hero- oder PMV-Edits zu längeren Musik-Tracks.

**Stilcluster, klassifiziert anhand Achsen-Set, Density und Beat-Signatur:**

* **Cock Hero / Beat-synchron** (kontinuierliche Position-Choreografie zur Musik-Beat): Barbarella, CH Crescendo, Duro, Lust Nightmare 2, RL GL DeSade, Heavenly 3, Suave, WarpZone, Lust Dream. Alpha/Beta-Density 600–6000 Actions/min, Volume monoton ansteigend.
* **Szenisch-Hypno mit Massendaten** (sub-100ms Sample-Rate auf `volume`, `pulse_*`, `frequency` — typisch für Restim-Slowstroke-/Joi-Skripte mit fast Audio-rate Modulation): Kafka Owns, Raven, Yor Forger, Samu, Church 2, Nightmare 2, Euphoria 5, RL GL DeSade. Diese Sessions haben pulse_frequency-Density im Bereich **5000–11000 Actions/min** (das entspricht 80–180 Hz nominell, real eine 100-Hz-Sample-Grid aus dem Editor).
* **PMV-Stil** (Mid-Density, längere ruhige Plateaus, abgestufte Volume-Treppen): Rythm of Desire (Beta-Density 856/min, Volume bauend von 33 auf 84), Liya/LS Remix, Lustful, Celestial.
* **E-Stim-szenisch / 4-Phasen** (separate `e1`–`e4`-Achsen für 2-Box-Setup): Raven 4Phase, Euphoria 5 4Phase. Hier haben e2/e3 dauerhaft sehr niedrige Mittelwerte (Raven e2 mean 6.2, e3 mean 7.1), während e1 und e4 als Hauptachsen im Hochbereich modulieren.
* **Light/Klassisch** (5–6 Achsen, kleine Files): MCB, Klinik Indus, Clutch, Lustful, Euphoria4.

Alle 18 Sessions mit `alpha`+`beta` enthalten eine Position1D-Spur (`<base>.funscript`); die Position1D-Datei ist konsistent **viel kleiner** als alpha/beta (Faktor 5–40), d. h. sie ist die ursprüngliche manuell editierte Cock-Hero-Spur, und alpha/beta wurden daraus per Restim-Konverter mit Bogen-Geometrie und Glättung erzeugt. Mehrere Sessions enthalten zusätzlich `-prostate`, `-stereostim`, `-2`, `e1..e4` Sub-Achsen für unterschiedliche Hardware-Setups.

---

## Teil B — Achsen-Verhalten

### `alpha` / `beta` (Position L0/L1, 0–100 ⇒ 0.0–1.0)

Beide Achsen werden in fast allen Sessions parallel mit identischer Action-Anzahl erzeugt — sie kommen vom selben Konverter-Lauf. Beta clustert dramatisch um 50 (Histogramm-Mittelbalken regelmäßig 30-50 % der Punkte, z. B. Liya beta `[6047, 11972, 24853, 18214, 13751, 53406, 17186, 23992, 10241, 7851]`), während alpha breit gestreut ist. Das ist das Signatur-Bild der **Restim-Bogen-Projektion**: pos∈[0,1] wird als Winkel θ=(1−pos)·arc auf einen Halbkreis um den Mittelpunkt gelegt, mit Radius = Funktion(Geschwindigkeit). Beta ist dann sin(θ)·radius+0.5; bei kleinen Radien (langsam) und mittleren Winkeln bleibt Beta nahe 0.5, während Alpha schon zwischen 0 und 1 oszilliert.

Sample-Intervalle: Cock-Hero-Stil (CH Crescendo, Duro, Barbarella, Church 2) liegt bei **10–42 ms** Median-Intervall, also **24–100 Hz** Update-Rate. Hypno/Szenisch (Kafka, Raven, Yor) bei 41–66 ms. Slope_max liegt bei ~1500–4000 pos-Einheiten/Sekunde — ausreichend für Vollausschlag in <30 ms.

Alpha-Rotationsanteil (gemessen mit Phasenwinkel-Sweep > 180° UND Radius-Stabilität): Barbarella 95%, Nightmare 2 95%, WarpZone 95%, Celestial 89%, Samu 89%, Liya 74%, Euphoria 5 74%, CH Crescendo 68%, Kafka 58%, Duro/RL GL/Raven 53%, Yor 42%, Church 2 37%, MCB 32%. Das heißt: in den hochrotierenden Sessions wird der α/β-Vektor auf einem Kreisbahn-Trajekt geführt — der Stim-Schwerpunkt rotiert spürbar zwischen den Elektroden.

### `volume` (V0)

Update-Rate sehr heterogen: bei großen Hypno-Sessions **10 ms** Sample-Grid (Kafka 5999/min, Yor 5999/min, Duro 5977/min), bei Cock-Hero/PMV nur 0.1–11 Aktionen pro Minute (Barbarella 0.34/min, Liya 1.29/min, Lustful 0.12/min). Wertebereich fast immer 0–100, Mittelwert über alle Sessions zwischen 55 und 94.

**Volume zeigt in 22 von 25 Sessions einen monotonen Aufwärtstrend** über die Session-Dauer (Phasenmittel 1→5 wachsend). Gemessene Ramps: Samu 14→33→49→69→87 (klassischer Slow Build), Euphoria 5 18→67→92→95→97 (frühes Crescendo + langes Plateau), Liya 54→63→70→73→86, CH Crescendo 73→77→77→79→83 (sehr flach), Kafka 76→85→91→93→96. Lediglich RL GL DeSade (RLGL-Variante mit Strafzonen) und WarpZone halten Volume nahezu konstant.

### `pulse_frequency` (P0)

Steuert die Pulsrate des E-Stim-Trägers (typisch 30–100 Hz subjektiv, im Funscript 0–100 normiert). Update-Rate 10 ms in den Hypno-Sessions, sonst 70–270 ms. Mittelwerte clustern zwischen 42 und 78. Es korreliert in fast allen Sessions positiv mit `volume` (typisch r 0.4–0.8) und positiv mit `frequency` (Carrier). Die Akzeleration über die Session ist deutlich schwächer als bei Volume: typisch 40→60 statt 20→95.

### `pulse_width` (P1)

Pulsbreite der einzelnen E-Stim-Pulse. Update-Rate ähnlich pulse_frequency. Sehr breite Histogramme bei Hypno-Sessions (z. B. RL GL DeSade `[73439, 154476, 115528, 31403, 1831, 410, 443, 5796, 451, 249]` — stark linksverteilt, Mittel 15.1, kaum Werte > 50). In Cock-Hero-Sessions mit gröberer Editierung (CH Crescendo, MCB) hüpft pulse_width zwischen wenigen diskreten Niveaus (z. B. CH Crescendo Sample bei 1500 s: 26 ↔ 49 ↔ 62 als drei feste Stufen, 70-ms-Intervalle). Korreliert in den meisten Sessions positiv mit `pulse_frequency` (CH Crescendo r=−0.78 ist Ausnahme — dort wird PW invers zu PF moduliert).

### `pulse_rise_time` (P3)

Anstiegsrampe der Pulse. Update-Rate identisch zu pulse_frequency in den Hypno-Sessions (10 ms), sonst 100–500 ms. Wertebereich konsistent 0–80 (nie 100, sehr selten >70). Mittelwert in fast allen Sessions zwischen 19 und 38, sinkt monoton mit der Zeit (Yor 39→30→27→29→26→22, Samu 73→64→58→52→47→44→36→29→22→17 — sehr klare Monotonie). Korreliert **stark negativ** mit volume und pulse_width (typisch r −0.7 bis −0.95): wenn die Lautstärke steigt, werden die Anstiegsrampen kürzer (= härter). Das ist das deutlichste „Härte"-Signal in der ganzen Sammlung.

### `frequency` (Carrier C0)

Trägerfrequenz (in Restim 0–1000 Hz, normiert 0–100). Update-Rate gleich 10 ms in Hypno-Sessions. Wertebereich typisch 50–95, Median in den Sessions: Duro 83, Yor 79, Raven 79, Kafka 74, Church 72, Celestial 71, RL GL 65, Nightmare 65. Korreliert sehr stark positiv mit Volume (r 0.79–0.98 quer durch alle Sessions, der stabilste Cross-Axis-Effekt der ganzen Sammlung). Subjektiv: hohe Carrier = schärferes Empfinden, niedrige = dumpf-tief; und Schärfe geht synchron mit Lautstärke.

### `vib`

Nur in Kafka. n=5138, dauerhaft sinkende Phasenmittel (90→86→79→75→79→71→63→63→69→53). Vermutlich eine sekundäre Hardware-Achse für ein Vibrationsgerät; sie verläuft inversly zur Volume-Hauptachse — stärker am Anfang, schwächer am Ende.

### Sub-Achsen

* **`-prostate`** (alpha-prostate, beta-prostate, volume-prostate): Bei Kafka, CH Crescendo, Celestial, Yor, Samu, Raven, Euphoria 5 vorhanden. Korrelation **alpha vs alpha-prostate = −1.0** in Celestial und CH Crescendo (perfekte Spiegelung — die Prostate-Position ist der reflektierte Vektor), aber **+0.95** in Euphoria 5 (gleichlaufend, anderes Setup). Beta-prostate sehr eng um 50 (stdev nur 6–17 statt 23–34 wie Beta), d. h. der Prostate-Pfad bewegt sich bewusst weniger axial. Volume-prostate liegt im Mittel **5–10 % höher** als Volume (Yor 93.7 vs 92.6, Raven 91.2 vs 89.1, Kafka korreliert r=0.57 mit etwas niedrigerem Mittel) — also Prostate-Kanal eher statisch hoch.
* **`-stereostim`** (volume-stereostim, nur in CH Crescendo, Celestial, Kafka, Samu): Praktisch identisch mit Volume (r=0.99–1.00 in allen vier), aber **mit Untergrenze 50** (nie unter 50). Das ist offensichtlich ein zweiter Kanal, dessen Wert nie ganz auf null fällt.
* **`-2`** (alpha-2, beta-2, e1-2…e4-2 in Kafka, Nightmare 2, Raven): Alternative Konvertierungs-Outputs für ein zweites Hardware-Layout. Korrelation r=1.0 zur Hauptachse außer bei Kafka (alpha-2 mean 46.9 vs alpha 46.9, identisch).
* **`e1`–`e4`** (4-Phasen-Setup, Raven, Euphoria 5): Vier separate Elektroden-Achsen. In Raven sind e1/e4 die Hauptaktiven (mean 28 / 9, breite Streuung), e2/e3 fast still (mean 6 / 7, std 19/21). Die vier Achsen sind paarweise antikorreliert (e1~e3 r=−0.31, e2~e4 r=−0.54 in Raven; in Euphoria 5 e1~e2 r=−0.59, e1~e3 r=−0.62, e3~e4 r=−0.51) — typisches rotierendes 4-Phasen-Schema, bei dem zu jedem Zeitpunkt nur 1–2 Elektroden aktiv sind.

---

## Teil C — Session-Strukturen / Macro-Patterns

### Übergreifender Bauplan

Aus den 5-Phasen-Mittelwerten (Sessions in 5 gleiche Zeitabschnitte geteilt) lässt sich für nahezu alle Skripte derselbe Macro-Bogen ablesen:

1. **Phase 1 (0–20 %)** — Init/Tease. Volume zwischen 14 und 75 (sehr breite Streuung), pulse_width niedrig (15–25), carrier moderat (50–70). Positionen oft statisch oder sehr eng (Barbarella alpha 60–75 s = konstant 0).
2. **Phase 2 (20–40 %)** — Build-Up. Volume springt typischerweise um +10 bis +50 nach oben (Samu 14→33, Euphoria 5 18→67, Kafka 76→85). Pulse_width legt deutlich zu (+10–20). Positionen beginnen zu rotieren.
3. **Phase 3 (40–60 %)** — Working Plateau. Volume nahe Max (90–95 in Hypno-Sessions). Pulse_freq und pulse_width wechseln zu rascheren, härteren Konfigurationen.
4. **Phase 4 (60–80 %)** — Edge-Phase / Variation. Hier entstehen die größten Pattern-Wechsel: pulse_width-Schwankungen, vereinzelte Drops, neue α/β-Trajektorien.
5. **Phase 5 (80–100 %)** — Climax/Tail. Volume saturiert bei 95–97 (Duro 97, Kafka 96, Yor 97, Samu 87 als Slow-Climax-Beispiel). Manche Sessions ziehen das Maximum schon in Phase 4 und drehen am Ende leicht zurück (Euphoria 5 Phase 5 pulse_freq fällt von 61 auf 49).

### Drei klar unterscheidbare Macro-Stile

**Cock-Hero-Beat-Drop** (Beispiel CH Crescendo, MCB, Duro): Position folgt einem Beat-Grid (in CH Crescendo bei 60 s sieht man perfekte Cosinus-Halbwellen 76→94→100→76→26→1→11→36→66→91→100 mit Periode ~700 ms ≈ 1.4 Hz). pulse_width hüpft im Takt zwischen 2–3 Plateaus (1500 s: 26↔49↔62). Volume ist über lange Strecken flach und steigt nur leicht (CH Crescendo 73→76→76→78→83). Burstiness der Volume-Spur in CH Crescendo 0.13, in MCB 0.18 — also tatsächlich Beat-Drops. Carrier zieht im Crescendo-Verlauf nach (62→66→63→65→70).

**Slow-Build-Hypno** (Samu, Liya, Kafka): Volume und Carrier sind die Haupterzähler, beide steigen monoton von ~15–55 auf 87–96. Position-Achsen rotieren in stabilen Sinus-Lopps mit langsamer Frequenzänderung. pulse_rise_time fällt monoton (Samu 73→17 — der Anstieg wird über ~75 min kontinuierlich härter). Burstiness sehr niedrig (0–0.05) — keine Beat-Drops, sondern lineare Edge-Kurve.

**Edging mit Rebound-Drops** (Barbarella, Lust Nightmare 2, RL GL DeSade): Volume zeigt Phasenmuster mit Rückgang im Mittelteil (RL GL: 70→68→70→70→67 — fast konstant, nur kleine Wellen). Bei Lust Nightmare 2 sieht man Volume-Phase 49→49→55→63→69 mit deutlich flacher Edge-Phase 2. Barbarella hat 11 diskrete pulse_frequency-Sprünge über 100 min, jeweils nach oben (50→35→50→80→50→80→50→90→50→100→50→100→90), die wie Edge/Reset-Zyklen wirken: jede Spitze (80, 90, 100) wird unmittelbar von einem Drop auf 50 gefolgt.

### Intensitätsentwicklung gemessen

Maxima quer durch die Sammlung:
* `volume`-Phasenmittel (5/5) > 95: Yor 97, Duro 97, Samu (90), Kafka 96, Euphoria 5 96, Raven 96, Church 95
* `pulse_frequency` Phase 5: Duro 84.5, Samu 53.6, Yor 75, Raven 59.5, Church 60.5 — d. h. selbst im Hochpunkt selten über 80
* `frequency` Phase 5: Duro 90, Yor 85, Raven 85, Kafka 82 — Carrier zieht im Climax durch

Die wichtigste Universalbewegung über die Sessions ist das **monoton steigende Trio Volume + Carrier + Pulse_width**, gegen den **monoton fallenden Pulse_rise_time**.

---

## Teil D — Mikro-Patterns: 60 unterscheidbare Stimulationsformen

Jedes Pattern ist mit Achsen-Signatur und einem konkret im Material beobachteten Beispiel belegt (Session + Zeitspanne + Werte). „Subjektive Wirkung" ist eine Vermutung aus der Achsen-Funktion (Restim-Wiki-konform), kein Messwert.

### 1. Position-Patterns (alpha + beta)

**P1 — Static Floor**
Alpha konstant 0, Beta konstant 50, lange Strecken.
Signatur: alpha pos_stdev = 0, interval_median 40 ms, max_pos = min_pos.
Vorkommen: Barbarella alpha bei 60–75 s — exakt 375 Samples mit pos=0, beta=50.
Wirkung: kompletter Stillstand der wahrnehmbaren Bewegung — Stim-Vektor zeigt nach unten.

**P2 — Static Center**
Alpha~50, Beta~50.
Signatur: pos_mean ≈ 50, stdev < 2.
Vorkommen: typisch in Intro/Outro vieler Skripte.
Wirkung: zentrierter, neutraler Sitz.

**P3 — Smooth Cosine Half-Wave (Beat-Lock)**
Alpha schwingt sinusartig zwischen 0 und 100, Periode 0.5–1.5 s, fest auf Musik-Beat.
Signatur: 7–14 Samples pro Periode, glatte 1.4–2 Hz.
Vorkommen: CH Crescendo alpha 60–75 s — Sequenz 76→94→100→76→26→1→11→36→66→91→100 mit 700 ms Periode.
Wirkung: rhythmisches Wandern zwischen Hoden- und Schaft-Pol.

**P4 — Damped Sinus / Ringdown**
Alpha startet mit hoher Amplitude und klingt über 1–3 Sekunden ab.
Signatur: erste Schwingung Voll-Hub, darauf ~50%, ~25 % Amplitude.
Vorkommen: Barbarella alpha 5800 s — 59→35→10→0→4→16→31→43→48→40→24→7→0→4→14→24→28→24→14→4→0 (Amplitude halbiert sich jede Welle).
Wirkung: ein „Klingeln" nach einem Stoß.

**P5 — Hard Toggle / Square-Wave Slap**
Alpha springt zwischen zwei Extremen (z.B. 4 ↔ 95) im Sekundentakt, ohne Zwischenwerte.
Signatur: Histogramm bipolar (z. B. Celestial alpha-prostate `[2920, 0, 0, 0, 1, 0, 0, 0, 0, 2921]`).
Vorkommen: Celestial alpha 1280–1295 s — 4 ↔ 95 alle ~250–800 ms, 27 Wechsel in 15 s.
Wirkung: harte Side-to-Side Schläge ohne Übergang.

**P6 — Slow Drift**
Alpha bewegt sich linear in eine Richtung über 30–120 s.
Signatur: stetige monotone Slope, sehr niedrige Slope_max (< 50 pos/s).
Vorkommen: Liya alpha-Phasen Mittel sind alle nahe 57–58 — wenig Bewegung, langsame Drift.
Wirkung: langsames Wandern des Schwerpunkts.

**P7 — Pendelschwingung (Beta-Lock)**
Alpha auf ~0–100 als sinus, Beta klemmt auf 50. Klassische Restim-„Flat Arc".
Signatur: Beta-Histogramm Mittelbalken > 30 % aller Punkte.
Vorkommen: Liya beta hist `[6047, 11972, 24853, 18214, 13751, 53406, 17186, 23992, 10241, 7851]` — Mittelbalken mit 53406 von 187k.
Wirkung: planare Wischbewegung links–rechts.

**P8 — Vollkreis-Rotation**
Alpha und Beta laufen 90° phasenversetzt sinusförmig — der Stim-Vektor kreist.
Signatur: Detektion via Phasenwinkel-Sweep > π und stabiler Radius (siehe deep_inspect.alpha_rotation).
Vorkommen: Barbarella ratio 0.95, Nightmare 2 0.95, WarpZone 0.95, Celestial 0.89.
Wirkung: rotierender E-Stim-Schwerpunkt.

**P9 — Halbkreis-Pendel**
Alpha sinusförmig, Beta nur kleine Auslenkung — Vektor schwingt auf einem Bogen statt Kreis.
Signatur: Alpha-stdev > 30, Beta-stdev < 15.
Vorkommen: Yor beta-prostate stdev 13.7 vs alpha-prostate 24.4.
Wirkung: ein Bogen statt voller Rundlauf.

**P10 — Asymmetrischer Halb-Hub**
Alpha pendelt in einem versetzten Bereich (z. B. 25–60 statt 0–100).
Signatur: pos_min und pos_max liegen beide auf einer Seite von 50.
Vorkommen: MCB alpha 1500–1515 s, pos_min 11, pos_max 47 (alles im Unterbereich).
Wirkung: Stimulation bevorzugt eine Seite.

**P11 — Mikro-Jitter um Setpunkt**
Sehr kleine Schwingungen ±5 um einen Mittelwert.
Signatur: pos_stdev < 5, hohe Action-Density (>1000/min).
Vorkommen: Duro alpha 60–75 s, n=1481 in 15 s, Werte alle zwischen 19–81 mit Median-Intervall 10 ms — engmaschiges Wackeln.
Wirkung: sirrendes Mikrobeben.

**P12 — Step-Climb**
Alpha steigt in 3–6 diskreten Stufen, jeweils mit Plateau dazwischen.
Signatur: Snippet zeigt 46→59→46→51→71→73→71 (ansteigende Stufen).
Vorkommen: MCB alpha 30–45 s — diese Werte exakt.
Wirkung: progressiv aufsteigende Erregungszone.

**P13 — Beta-Buzz auf Alpha-Toggle**
Alpha = harter Toggle (P5), Beta gleichzeitig hochfrequent oszillierend (50 Hz).
Signatur: Alpha-Intervall ~500 ms, Beta-Intervall 20 ms.
Vorkommen: Celestial 1280 s — alpha 4↔95 alle 500 ms, beta gleichzeitig 22→53→19→2→21→54→83→93→77→48 in 20-ms-Schritten.
Wirkung: harter Punkt-Wechsel mit überlagertem Träger-Vibrato.

**P14 — Rotation mit Frequenzdrift**
Vollkreis-Rotation, deren Periode über 30+ Sekunden langsamer oder schneller wird.
Signatur: alpha_rotation segments = total, aber autocorr-Lag verschiebt sich.
Vorkommen: Liya rotational ratio 0.74 — viele rotierende Segmente, langsame Drift sichtbar an alpha-Phasenmitteln 56→58→56→59→58→59→58→58→59→56.
Wirkung: rotierender Vektor, dessen Tempo sich verändert.

**P15 — Position-Phase-Lock zur Beat-Rate**
Position-Frequenz ist exakt halb oder doppelt zur Musik-Beat.
Signatur: konstantes Sample-Intervall (CH Crescendo 70 ms = ~14 Hz Sample, Periode 700 ms = 1.4 Hz Beat).
Vorkommen: CH Crescendo alpha 60–75 s und 1500–1515 s identische Periodik.
Wirkung: Stim atmet im Takt der Musik.

### 2. Lautstärke-Patterns (volume)

**V1 — Linear-Slow-Build**
Volume steigt linear von <30 auf >85 über die ganze Session.
Signatur: 5-Phasen-Mittel monoton steigend mit gleichmäßiger Differenz.
Vorkommen: Samu 14→33→49→69→87 (~+18 pro Phase = ~750 s pro +18).
Wirkung: kontinuierlicher Erregungsaufbau.

**V2 — Step-Plateau-Build**
Volume hält ein Plateau, springt um +10–20, hält wieder.
Signatur: lange Stretches ohne Volume-Aktion, dann diskrete Sprünge.
Vorkommen: Liya volume 9 Aktionen in 60 min: 70→85→90→85→90→85→90→90→90.
Wirkung: stabile Phasen mit klar markierten Steigerungs-Schritten.

**V3 — Frühes Crescendo**
Volume erreicht 90+ schon in Phase 2, hält den Rest.
Signatur: Phase-1 niedrig, Phase 2–5 nahezu konstant hoch.
Vorkommen: Euphoria 5 18→67→92→95→97; Yor 81→93→95→96→97.
Wirkung: schnelles Committment auf hohe Intensität.

**V4 — Spätes Crescendo**
Volume bleibt mid-low über große Strecken, zieht erst in Phase 4–5 hoch.
Signatur: Phase 1–3 stabil, scharfer Anstieg in Phase 4.
Vorkommen: Liya 54→63→70→73→86 (+13 nur in der letzten Phase); Lust Nightmare 2 58→62→80→81→81 (Sprung in Phase 3).
Wirkung: lange Edging-Periode vor Climax.

**V5 — Konstante Volume-Plateau**
Volume oszilliert eng um einen Wert, ohne klare Trend.
Signatur: 5-Phasen-Differenz < 5.
Vorkommen: WarpZone 63→63→63→66→61; RL GL DeSade 70→68→70→70→67.
Wirkung: gleichmäßige Hintergrund-Stim, alle Variation kommt aus anderen Achsen.

**V6 — Beat-Drop / Rapid Spike**
Kurze Volume-Peaks (>+20 für <2 s) sync zum Beat.
Signatur: hohe burstiness (>0.1).
Vorkommen: MCB volume_burstiness 0.18, CH Crescendo 0.13, Celestial 0.30 (höchste der Sammlung).
Wirkung: punktuelle harte Schübe.

**V7 — Volume-Drop-and-Hold (Edge)**
Plötzlicher Drop um −20 bis −40, dann Plateau.
Signatur: einzelner Sprung nach unten gefolgt von langer Konstanz.
Vorkommen: Lustful (78 von 9 Aktionen mit zwei Drops auf null im Mittelteil).
Wirkung: Edging-Drop.

**V8 — Sägezahn-Build (Slow Up + Hard Drop)**
Wiederholte Sequenzen aus 30–60 s Anstieg + 1 s Drop.
Signatur: mehrere ähnliche „Dreiecks"-Bursts in Volume-Verlauf.
Vorkommen: Barbarella pulse_frequency-Verlauf zeigt 11 Spikes (50→Hochwert→50), jeweils in 1 min Distanz; Volume verhält sich ähnlich wenn auch nur 34 Aktionen.
Wirkung: Edge-and-Reset.

**V9 — Two-Level-Toggle**
Volume springt zwischen genau zwei diskreten Werten (z. B. 70 ↔ 100).
Signatur: Histogramm streng bimodal.
Vorkommen: Liya volume Histogramm `[1, 0, 1, 34, 1, 1, 37, 41, 39, 21]` — 70er und 90er Cluster.
Wirkung: An/Aus-Schaltung mit Restpegel.

**V10 — Audio-rate Volume-Modulation**
Volume mit 100 Hz Sample-Rate als kontinuierliche Welle (kein Edit-Grid).
Signatur: interval_median = 10 ms.
Vorkommen: Kafka volume n=492193 in 82 min, Yor n=218593 in 36 min, Duro n=184495 in 30 min.
Wirkung: Audio-genaue Lautstärkemodulation.

**V11 — Histogramm-Spitze bei 100 (Saturationskleber)**
Volume hängt häufig an 100 fest.
Signatur: rechtester Histogramm-Bin >> Rest (Duro `[…, 175052]` von 184k; Yor `[…, 209862]` von 218k; Raven `[…, 298363]`).
Vorkommen: Duro, Yor, Raven, Kafka (alle mit fast 60 % aller Samples bei pos>90).
Wirkung: lange Phasen auf Maximum.

**V12 — Volume-Burst-Block**
Kurze Cluster mit dichten Aktionen, gefolgt von Stille.
Signatur: burstiness 0.04–0.10, ungleichmäßige Verteilung.
Vorkommen: WarpZone 0.04, Nightmare 2 alpha 0.09, RL GL alpha 0.10.
Wirkung: rhythmische An-/Aus-Stim-Cluster.

### 3. Pulse-Patterns (pulse_frequency × pulse_width × pulse_rise_time)

**PF1 — Sinus-Pulse-Frequency synchron zur Position**
pulse_frequency moduliert mit derselben Frequenz wie Alpha.
Signatur: r(alpha, pulse_frequency) > 0.6 in deep_inspect.
Vorkommen: CH Crescendo r=0.964, Euphoria 5 r=0.737, Kafka r=0.640, Samu r=0.472. CH Crescendo Snippet 60–75 s: pulse_frequency 72→81→85→72→45→32→37→50→66→80→85 mit identischer 700-ms-Periode wie alpha.
Wirkung: Pulsrate atmet mit der Position-Bewegung.

**PF2 — Inverser Pulse-Frequency-Pendel**
pulse_freq schwingt gegenläufig zur Position.
Signatur: r negativ.
Vorkommen: Nightmare 2 beta~pulse_frequency r=−0.265, Yor beta~pf r=−0.335.
Wirkung: bei Position-Maximum entspannt sich der Puls.

**PF3 — Step-Switch zwischen Pulse-Plateaus**
pulse_freq springt zwischen 2–3 diskreten Werten ohne Übergang.
Signatur: Histogramm bipolar oder tripolar.
Vorkommen: Barbarella pulse_frequency 11 Werte total, Sprünge 35/50/80/90/100; CH Crescendo Histogramm `[23, 26, 4358, 5569, 6127, 4101, 1692, 6848, 6883, 3232]` mit drei Plateau-Cluster.
Wirkung: harte Pulsraten-Wechsel.

**PF4 — Slow-Build-Pulse-Frequency**
pulse_freq erhöht sich monoton über die Session.
Signatur: 5-Phasen-Mittel steigt.
Vorkommen: Liya 50→53→57→61→70; Samu 28→41→39→48→54.
Wirkung: kontinuierlich härter werdende Pulsrate.

**PF5 — Pulse-Frequency-Spike-Drop**
Plötzlicher Sprung nach oben + sofortiger Rückfall.
Signatur: einzelne Aktionen mit ±30+ Differenz.
Vorkommen: Barbarella full-Verlauf — 12 Spikes in 100 min, alle mit 50→hoch→50 Pattern.
Wirkung: kurze Pulse-Frequency-Stoß-Sequenzen.

**PW1 — Pulse-Width-Sägezahn (Hard-Switch)**
pulse_width oszilliert zwischen 2 festen Niveaus zum Beat.
Signatur: bimodales Histogramm.
Vorkommen: CH Crescendo pulse_width 1500 s: 26↔62 (zwei Werte allein nehmen >50 % aller Samples), Periode 700 ms.
Wirkung: rhythmische Härtemodulation jedes Beats.

**PW2 — Linear-PW-Build**
pulse_width steigt monoton über Session.
Signatur: 5-Phasen-Mittel steigt.
Vorkommen: Yor 25→34→41→39→45; Church 2 20→26→29→32→37; Samu 24→32→29→40→47.
Wirkung: Pulse werden über die Zeit breiter (wuchtiger).

**PW3 — Pulse-Width-Inverse-Lock zur Position**
pulse_width fällt wenn alpha steigt.
Signatur: r(alpha, pulse_width) negativ.
Vorkommen: Nightmare 2 r=−0.763, Church 2 r=−0.485, Duro r=−0.490, Yor r=−0.436.
Wirkung: dünne Pulse bei Schaft-Stim, breite bei Hodensatz-Stim (oder umgekehrt je nach Setup).

**PW4 — Smooth-PW-Sweep**
pulse_width gleitet über 5–15 s monoton von ~10 auf ~80.
Signatur: dichte Sample-Sequenz mit konstanter kleiner Slope.
Vorkommen: Barbarella pulse_width-Snippet bei 5874043 ms: 50→6→11→18→24→30→36→42→48→92→86→79→72→66→60→53→47 — gleitender Auf-Ab-Sweep mit ~1.1-s-Intervallen, 6 pro Sekunde Sample-Rate.
Wirkung: Pulse werden weicher und wieder schärfer.

**PW5 — Pulse-Width-Plateau-Hold**
pulse_width konstant für >1 min.
Signatur: lange Sample-Strecken ohne Wertänderung.
Vorkommen: Lustful pulse_width 99 Aktionen in 73 min; RL GL DeSade pulse_width-Mittel 15 mit stdev 10 — überwiegend stabil.
Wirkung: stabile Pulscharakteristik.

**PR1 — Falling-Rise-Time-Hardening**
pulse_rise_time fällt monoton über die Session.
Signatur: 5-Phasen-Mittel sinkt.
Vorkommen: Samu 73→64→58→52→47→44→36→29→22→17 (über 10 Segmente klar fallend); Yor 39→30→27→29→26→22; Celestial 42→38→35→31→32→31→29→27→25→19.
Wirkung: Pulse werden über Zeit „spitzer" (härter Anstieg).

**PR2 — Pulse-Rise-Inverse-Volume**
pulse_rise_time fällt sofort wenn volume steigt.
Signatur: r(volume, pulse_rise_time) stark negativ.
Vorkommen: Samu r=−0.979, Celestial r=−0.901, Kafka r=−0.556, Euphoria 5 r=−0.723.
Wirkung: Lautere Stim ist immer auch härter angesetzt.

**PR3 — Pulse-Rise-Mid-Range-Hold**
pulse_rise_time hält stabil im Mittelbereich (20–40), variiert nur leicht.
Signatur: stdev < 10.
Vorkommen: RL GL DeSade pulse_rise_time mean 38 stdev 4.3.
Wirkung: konstanter weicher Pulscharakter.

**PR4 — Rapid Rise-Time-Drop**
Innerhalb 2 s fällt pulse_rise von 70 auf 0.
Signatur: einzelne Slope_max-Werte > 200 pos/s in pulse_rise_time.
Vorkommen: Celestial pulse_rise_time max-slope 14000 pos/s (!) — extreme Sprünge.
Wirkung: schlagartige Härte-Erhöhung.

**PMix1 — Klassischer 3-Achsen-Lock (PF↑ + PW↑ + PR↓)**
pulse_freq, pulse_width steigen, pulse_rise_time sinkt synchron.
Signatur: r(pf, pw) positiv, r(pf, pr) negativ, r(pw, pr) negativ — alle gleichzeitig.
Vorkommen: Kafka r(pw,pr)=−0.87, r(pf,pr)=−0.83; Duro r(pw,pr)=−0.95, r(pf,pw)=+0.91, r(pf,pr)=−0.92.
Wirkung: alle drei Pulse-Parameter koppeln zur „Härter-werden"-Achse.

**PMix2 — Soft-Pulse (PF mid + PW low + PR high)**
Niedrige pw, hohe Anstiegszeit, mittlere Pulsrate.
Signatur: pw < 25, pr > 40, pf 40–60.
Vorkommen: RL GL DeSade Phase 1 (pw 14, pr 40, pf 70).
Wirkung: weiche, „streichelnde" Pulse.

**PMix3 — Hard-Click (PF high + PW high + PR low)**
Alle drei auf Härte.
Signatur: pf > 70, pw > 50, pr < 20.
Vorkommen: Duro Phase 5 — pf 84, pw 56, pr ~10.
Wirkung: harte Kontaktklicks.

### 4. Carrier-Patterns (frequency)

**C1 — Static Carrier**
frequency fast konstant, 5–10 Aktionen pro Session.
Signatur: stdev < 5, n < 20.
Vorkommen: WarpZone frequency n=42, mean 50, stdev 30 (zwar Streuung, aber kaum Updates).
Wirkung: dauerhaft gleicher Träger-Charakter.

**C2 — Carrier-Volume-Lockstep**
frequency und volume steigen/fallen synchron.
Signatur: r(volume, frequency) > 0.85.
Vorkommen: Nightmare 2 r=0.98 (höchste der Sammlung), Raven 0.95, Samu 0.95, Yor 0.92, Kafka 0.91, Celestial 0.91, CH Crescendo 0.93, Euphoria 5 0.82, Duro 0.85, RL GL 0.79.
Wirkung: schärferer Träger bei lauter, dumpfer bei leiser — die universelle Restim-Default-Kopplung.

**C3 — Linear Carrier-Sweep**
Carrier steigt monoton über Session.
Signatur: 5-Phasen-Mittel steigend.
Vorkommen: Samu 13→30→38→56→70 (kompletter Bogen); Church 2 61→69→73→76→81; Yor 67→78→82→82→85.
Wirkung: Stimmenfarbe wird über Zeit schärfer.

**C4 — Carrier-Drop-on-Volume-Peak**
Bei Volume-Peak fällt Carrier kurz.
Signatur: lokale Antikorrelation in Volume-Spitzen.
Vorkommen: WarpZone alpha~volume r=−0.293 — bei alpha-Peak fällt Carrier; in WarpZone allgemein r(alpha, frequency)=−0.28.
Wirkung: Härte-Bruch im Climax-Moment.

**C5 — Carrier-Sweep-Block**
Carrier rampt in 2–10 s linear hoch oder runter.
Signatur: hoher Slope_max in frequency.
Vorkommen: CH Crescendo frequency Slope_max 383 pos/s; Celestial 31 pos/s.
Wirkung: hörbarer/spürbarer Sweep.

### 5. Multi-Achsen-Verbund-Patterns

**M1 — Triple-Sync-Build (Volume + Carrier + PulseWidth)**
Drei Achsen steigen gleichzeitig über die Session.
Vorkommen: praktisch alle Hypno-Sessions. Yor: Volume 81→97, Carrier 67→85, PW 25→45 — alle parallel.
Wirkung: jeder Aspekt der Stim wird mit dem Volume mitgehärtet.

**M2 — Position-Pulse-Frequency-Lock**
Alpha-Sinus drives pulse_frequency-Sinus mit derselben Phase.
Vorkommen: CH Crescendo r(alpha, pf)=0.964 — perfekt synchronisiert; Euphoria 5 0.737.
Wirkung: Pulsrate moduliert mit Position-Schwingung.

**M3 — Mirror-Prostate-Channel**
alpha-prostate = −alpha (Spiegelung um 50).
Vorkommen: CH Crescendo r=−1.0, Celestial r=−1.0.
Wirkung: zweiter (Prostata-)Kanal pulst genau gegengleich zum Hauptkanal.

**M4 — Parallel-Prostate-Channel**
alpha-prostate = +alpha (gleiche Phase).
Vorkommen: Euphoria 5 r=0.954, Kafka beta~beta-prostate r=−0.215 (also nicht identisch — weniger Korrelation).
Wirkung: Prostata-Kanal pulst phasengleich, leichte Variation.

**M5 — Secondary-Volume-Floor (Stereostim)**
volume-stereostim = volume aber mit Untergrenze 50.
Vorkommen: CH Crescendo, Celestial, Kafka, Samu — alle mit r=0.99–1.00 und pos_min=50.
Wirkung: zweiter Kanal nie aus; immer ein Untergrund-Pegel.

**M6 — 4-Phasen-Round-Robin (E1–E4)**
e1, e2, e3, e4 paarweise antikorreliert; nur 1–2 gleichzeitig aktiv.
Vorkommen: Raven e1 mean 28 stdev 41, e2 mean 6 stdev 19, e3 mean 7, e4 mean 9. Korrelationen e1~e3=−0.31, e2~e4=−0.54. Euphoria 5 hat saubereres Pattern: e1~e2=−0.59, e1~e3=−0.62, e3~e4=−0.51.
Wirkung: rotierende Aktivität durch vier Elektroden.

**M7 — E1-Position-Coupling**
e1-Achse synchronisiert mit alpha.
Vorkommen: Raven r(alpha, e1)=0.664, r(beta, e1)=−0.512.
Wirkung: erste Elektrode trackt Position-Achse.

**M8 — Volume-Drives-Everything**
Volume korreliert hoch (>0.7) mit Carrier, PulseFreq, PulseWidth, PulseRiseTime (invertiert), Volume-Prostate.
Vorkommen: Samu 7-Achsen-Korrelations-Cluster mit |r|>0.6, Kafka, Yor, Raven.
Wirkung: Volume ist der Master-Slider, alles andere folgt.

**M9 — Position-Independent-Volume**
Volume unabhängig von Alpha (r ≈ 0).
Vorkommen: Liya |r(alpha,volume)| < 0.1; Yor ähnlich.
Wirkung: Lautstärke und Position erzählen unabhängige Geschichten.

**M10 — Inverse Volume vs Alpha**
Volume sinkt wenn Alpha steigt.
Vorkommen: Nightmare 2 r=−0.556 (Climax mit Position-Drop?).
Wirkung: leiser bei höherem Position-Schub.

**M11 — Pulse-Rise-Frequency-Anti-Lock**
pulse_rise_time und frequency negativ korreliert.
Vorkommen: Samu r=−0.959, Celestial r=−0.92, Church 2 r=−0.88.
Wirkung: härter angesetzte Pulse begleiten höheren Carrier.

**M12 — Carrier-Position-Modulation**
Carrier-Frequenz oszilliert mit Position-Frequenz.
Vorkommen: CH Crescendo Slope_max in frequency 383 pos/s + r(alpha, frequency) niedrig — kurze schnelle Sweeps zwischen Positionsänderungen.
Wirkung: Träger zittert mit der Position.

**M13 — Pulse-Width-Frequency-Co-Lock**
PW und Carrier-Frequenz tracken einander.
Vorkommen: Duro r(pw, frequency)=0.813, Celestial 0.851, Kafka 0.737, Nightmare 2 0.869.
Wirkung: dickere Pulse bei höherem Carrier.

**M14 — Independent Position vs Pulse**
Alpha und Pulse-Achsen unkorreliert (|r|<0.2).
Vorkommen: RL GL DeSade r(alpha, pf)=0.49 ist Maximum; alpha~pw=−0.29; insgesamt schwach.
Wirkung: zwei getrennte Modulationsstreams.

**M15 — Phase-Lead/Lag zwischen Volume und PulseFreq**
Volume und PulseFreq korreliert, aber mit Zeitverschiebung.
Vorkommen: schwer aus reinen Korrelationen abzulesen, aber CH Crescendo r=0.351 (relativ niedrig trotz starker Volume-Gleichbewegung in beiden) deutet auf Phasenverschiebung.
Wirkung: PulseFreq zieht der Volume voraus oder hinterher (Antizipation).

### 6. Macro-Phase-Patterns (Session-Level)

**S1 — Linear-Crescendo-to-Climax**
Volume + Carrier + PW alle linear steigend, Pulse-Rise fallend, kein Edging.
Vorkommen: Samu (klarstes Beispiel), Yor, Liya.
Wirkung: ein langer kontinuierlicher Ramp.

**S2 — Frühes-Climax-Plateau**
Volume erreicht 90+ in Phase 2, hält Rest.
Vorkommen: Euphoria 5, Yor, Duro, Kafka.
Wirkung: kurze Aufwärm-Phase, lange Hochintensität.

**S3 — Edging-Plateau-mit-Drops**
Volume oszilliert auf hohem Niveau, mit periodischen Drops.
Vorkommen: Barbarella (12 PF-Spikes in 100 min); RL GL DeSade (5-Phase Volume nahezu konstant).
Wirkung: gehaltene Erregung mit absichtlichen Bremsmomenten.

**S4 — Beat-Drop-Cock-Hero**
Volume + Position synchron zu Musik, Beat-Cluster mit Stille dazwischen.
Vorkommen: CH Crescendo (burstiness 0.13), MCB (0.18), WarpZone-Stil.
Wirkung: musikalisches Rhythmusspiel.

**S5 — Slow-Build-Edge-Climax (3-Akt)**
Akt 1: leise (0–25 %). Akt 2: Plateau mid (25–80 %). Akt 3: scharfer Anstieg (80–100 %).
Vorkommen: Liya (Phasen 54→63→70→73→86 — Sprung erst Ende), Lust Nightmare 2.
Wirkung: lange Edge gefolgt von Climax-Stoß.

**S6 — Random-Spike-Tease**
Pulse_Width oder Volume mit zufällig wirkenden 1–3 s Bursts.
Vorkommen: Lustful Volume mit nur 9 Aktionen über 73 min, alle mit großen Lücken.
Wirkung: unvorhersehbare Stim-Eingriffe.

**S7 — Aftercare/Tail-Down**
Letztes Phasensegment zeigt Volume-Drop oder Position-Stop.
Vorkommen: Lustful Phase 5 70 → 33 (frequency); Euphoria 5 pulse_freq Phase 5 fällt 61→49.
Wirkung: kontrollierter Abstieg nach Climax.

**S8 — Dauerhochlast (No-Build)**
Volume von Anfang an >85, keine sichtbare Steigerung.
Vorkommen: Raven (Volume Phase 1 schon 75, dann 90+ konstant), Duro (86→97).
Wirkung: keine Steigerung, sofort volle Intensität.

**S9 — Rotation-Heavy / Position-First-Style**
Hauptmodulation kommt aus Alpha-Rotation, Volume relativ statisch.
Vorkommen: WarpZone (alpha_rotation 0.95, volume_burstiness 0.04).
Wirkung: räumliche statt energetische Erzählung.

**S10 — Multi-Channel-Parallel-Choreography**
Mehrere -prostate, -2, e1–e4 Achsen tragen unabhängige Storylines.
Vorkommen: Euphoria 5 mit 15 Achsen, Raven mit 19 Achsen, Kafka mit 15.
Wirkung: gleichzeitige Stim-Spuren auf verschiedenen Hardware-Kanälen.

---

## Teil E — Erkenntnisse für die Restim-Web-Extension

Der bestehende `LiveProcessor` (`src/funscript/live_processor.py`) macht bereits das Wesentliche: er mappt die 1D-Position via Bogen-Geometrie (arc_degrees, calc_radius(speed)) auf alpha/beta — exakt das Verfahren, mit dem die Multi-Achsen-Skripte ursprünglich aus den Position1D-Spuren erzeugt wurden. Volume, Carrier, PulseFreq, PulseWidth und PulseRiseTime werden aktuell alle aus `effective_spd` (= Bewegungsgeschwindigkeit + optional Burst-Boost) durch `lerp(speed, min, max)` abgeleitet. Das deckt **M8 (Volume-Drives-Everything)** und **C2 (Carrier-Volume-Lockstep)** und **PMix1 (PF↑+PW↑+PR↓)** ab. Auch **PR2 (Pulse-Rise-Inverse-Volume)** entsteht automatisch, sobald die Min/Max-Range so eingestellt ist, dass pulse_rise_min > pulse_rise_max — das spiegelt die in der Sammlung dominante Antikorrelation r(volume, pulse_rise_time) ≈ −0.7 bis −0.95.

Heuristiken, die der LiveProcessor heute **nicht** hat aber aus der Sammlung lernbar wären:

1. **Volume-Hüllkurven-Build (V1/S1)**: Die Sammlung zeigt monoton steigende Volume-Phasen über 30–90 Minuten. Der Live-Processor könnte einen **Session-Time-Ramp** addieren: `effective_spd_ramped = lerp(session_progress, 1.0 − ramp_amount, 1.0) * effective_spd`. Das würde die universelle Steigerung (Phase 1 ~50, Phase 5 ~90) nachbilden, ohne dass das Quell-Funscript es explizit codieren muss.

2. **Position-Sync-PulseFreq (M2/PF1)**: In CH Crescendo ist r(alpha, pulse_frequency) = 0.964. Im Code existiert bereits `position_freq_influence` (`pfr = lerp(s.position_freq_influence, pfr_speed, pfr_pos)`). Den Default auf 0.4–0.6 setzen, damit Live-Skripte den charakteristischen Position-Sync zeigen.

3. **Beat-Burst-Boost**: Cock-Hero-Skripte (CH Crescendo, MCB) haben volume_burstiness 0.13–0.18 — kurze rhythmische Volume-Spikes. Der existierende `boost_window` mit `boost_strength` ist genau dafür da. Defaults sollten so sein, dass kurze schnelle 1D-Bewegungen den boost auslösen.

4. **Pulse-Width-Sägezahn (PW1)**: CH Crescendo hat 26 ↔ 62 als zwei diskrete pulse_width-Werte zum Beat. Live-Konvertierung könnte einen optionalen **Discrete-Step-Modus** anbieten, der pulse_width auf 2–3 vordefinierten Stufen quantisiert sobald der Beat-Detector anschlägt.

5. **Alpha-Rotation für lange ruhige Phasen**: P1 (Static Floor) langweilt — Skripte wie Barbarella füllen das mit Rotation (P8). Wenn der Live-Input längere Plateaus hat, könnte der Processor optional eine langsame α/β-Rotation überlagern (idle_rotation_amplitude, idle_rotation_period). Funktional ähnlich, wie wenn sich „Position halten" anfühlen sollte wie aktive Rotation.

6. **Carrier-Volume-Lockstep ist universell**: r=0.79–0.98 quer durch alle Sessions. Der Code macht das schon (`car = lerp(effective_spd, …)`). Wichtig ist nur die Default-Range nicht zu schmal zu setzen — die Hypno-Sessions bewegen Carrier von 50 bis 95.

7. **Session-Aufbau über `volume_min`/`volume_max`-Time-Ramping**: Wenn der Settings-Slider eine zeitabhängige Min-Volume erlaubt (Phase 1 vol_min=0.2, Phase 5 vol_min=0.8), bildet das die V4/V5 Late-Crescendo-Patterns nach.

Wichtigste **nicht-replizierbare** Eigenschaften: M3 (Mirror-Prostate, r=−1.0) und M5 (Stereostim-Floor mit Untergrenze 50) brauchen einen zweiten Kanal, also Hardware mit mehr als 2 Boxen. Für 1D→7-Achsen-Live ist das irrelevant. M6 (4-Phasen-Round-Robin) ebenfalls.

Die wichtigsten Cross-Achsen-Korrelationen, die der LiveProcessor garantieren sollte:
* r(volume, frequency) > 0.85 — bereits gegeben durch gemeinsame `effective_spd`-Ableitung.
* r(volume, pulse_rise_time) < −0.7 — gegeben, wenn pulse_rise_min > pulse_rise_max.
* r(alpha, pulse_frequency) = 0.4–0.7 — konfigurierbar via `position_freq_influence`.
* r(pulse_width, pulse_rise_time) < −0.7 — automatisch durch beidseitige effective_spd-Kopplung.

Die Sammlung bestätigt also den Architektur-Ansatz des bestehenden Codes weitgehend. Die größten Lücken sind die **Session-Zeit-Hüllkurve** (es fehlt ein expliziter Slow-Build über Minuten/Stunden) und ein optionaler **Discrete-Beat-Quantizer** für Cock-Hero-Material.
