# Restim-Funscript-Quellen — Recherche

Stand: 2026-05-14. Recherche zur Erweiterung der bestehenden 26-Session/203-File-Sammlung um zusatzliche Restim-spezifische Multi-Achsen-Skripte (`*.alpha.funscript`, `*.beta.funscript`, `*.volume.funscript`, `*.pulse_frequency.funscript`, `*.pulse_width.funscript`, `*.pulse_rise_time.funscript`, `*.frequency.funscript`, sowie Sub-Setups `-prostate`, `-stereostim`, `e1`-`e4`).

Wichtigste Erkenntnis vorab: **Es gibt im offenen Web keine grosse, fertig kuratierte Restim-Multi-Achsen-Sammlung.** Die Restim-Pipeline ist designt fuer *Konvertierung-on-demand* aus 1D-Funscripts. Die einzige bisher offentlich auffindbare Pre-Generated-Sammlung mit Restim-Event-Files ist Senorgif33s Repo (siehe unten).

---

## 1. Bestatigte aktive Quellen

### 1.1 Senorgif33 / Senorgifs-Restim-Event-Files (GitHub)
- URL: https://github.com/Senorgif33/Senorgifs-Restim-Event-Files
- Inhalt: ~10–11 Ordner mit Base-Funscripts plus zugehorigen `.events.yml`-Dateien fuer den Restim Funscript Processor (v2.3.5). Die Events definieren timed Effekte (fast, edge, cum, ruin, etc.), die beim Processor-Lauf in komplette Multi-Achsen-Setups expandiert werden.
- Konkrete Titel (alle nicht in der bestehenden 26-Session-Liste): `CH Audition 3`, `CH Blue Angel` (mit "ReStim Generated"-Variante), `CH Champion of Cocknia`, `CH Crescendo / MattMan FOC`, `CH Eroclip` (plus alternate "LG Script"-Variante), `CH Erocomp`, `CH Fail`, `Earn_your_Release-1080p`, `Shibby / The-Box`. (`CH Crescendo` ist evtl. ein Alias zur "Crescendo"-Session des Users — bitte beim Download abgleichen.)
- Zugang: free (offentliches GitHub-Repo, `git clone` reicht)
- Stand: aktiv (5 Commits, README dokumentiert Workflow). Stars/Forks niedrig — Geheimtipp.
- Hinweis: Das sind **Event-Files + Base-Funscripts**, nicht direkt die fertigen `.alpha.funscript`/`.beta.funscript`. Der Workflow ist: Base-Funscript + `.events.yml` -> Restim Funscript Processor -> 10 Output-Funscripts inkl. alpha/beta/volume/pulse_*. Effektiv eine deutlich groessere Multi-Achsen-Sammlung, als die Repo-Groesse vermuten laesst.

### 1.2 edger477 / funscript-tools (Restim Funscript Processor)
- URL: https://github.com/edger477/funscript-tools
- Inhalt: Der Processor selbst (Python GUI, ab v2.3.5 standalone .exe). Erzeugt aus *einem* 1D-Funscript automatisch 10 Output-Files inkl. `alpha`, `beta`, `volume`, `pulse_frequency`, `pulse_width`, `pulse_rise_time`, `frequency`, plus `-prostate`-Variante und (ab v2.1.0) `Motion Axis (4P)` mit `e1`–`e4` fuer FOC-Stim 4-Phasen-Setup. Enthaelt nur ein `examples/sample.funscript` als Test-Input — **keine fertige Skript-Sammlung**.
- Releases: https://github.com/edger477/funscript-tools/releases
- Konsequenz fuer den User: Jede beliebige 1D-Funscript-Sammlung (Eroscripts, Faptap, SLR-Scripts) wird damit zur Multi-Achsen-Quelle. Das ist der eigentliche "Funscript-Multiplier" im Restim-Ecosystem.

### 1.3 blucrew / FOCtave (Audio -> 4-Phase Funscript)
- URL: https://github.com/blucrew/FOCtave
- Inhalt: CLI-Tool, das bestehende **Stereo-eStim-Audio-Files** (WAV/FLAC/MP3/M4A/OGG) in Restim-kompatible 4-Phase-Funscripts (5 Output-Files) konvertiert. 4 Presets (`french_fries`, `baked`, `roasted`, `mashed`).
- Zugang: free, Python 3.11+
- Relevanz: Erschliesst den **gesamten Estim-Audio-Bestand** als Multi-Achsen-Source — hunderte Tracks von ESTIM MUSIC LABS, e-stim.info, SoundCloud-Sets etc.
- Audio-Quellen, die damit zu Restim-Skripten werden:
  - https://e-stim.info/downloads/audio (free downloads)
  - https://www.estimmusiclabs.com/ (kuratiert, teils paid)
  - https://soundcloud.com/tags/estim/popular-tracks (Tag-Feed)
  - "FunBelgium"-Style (wird in FOCtave-Default referenziert; kein direkter Hosting-Link verifiziert)

### 1.4 diglet48 / restim Wiki — Funscript-Konvertierung
- URL: https://github.com/diglet48/restim/wiki/funscript-conversion
- Inhalt: Eingebauter 1D->2D-Konverter direkt in der Restim-App (Tools -> Funscript Conversion). Algorithmen: Circular (0–180), Top-Left-Right (0–270), Top-Right-Left (0–90), 0–360 (restim original).
- Praxis: Falls beim Download nur das `.funscript` (Stroker-File) verfuegbar ist, sofort vor Ort in alpha/beta wandeln — das ist der Standard-Workflow im Restim-Ecosystem.

### 1.5 Eroscripts (Community-Hub)
- URL: https://discuss.eroscripts.com/
- Sichtbare Top-Level-Kategorien (frontpage): Help, General, Software, DIY, Events, Review, howto, Site Feedback. Eine eigene `estim`-Kategorie ist nicht oeffentlich gelistet — zugehorige Inhalte stecken hinter Login bzw. in der `Software`/Scripts-Kategorie mit `estim`-Tag.
- Zugang: kostenloses Forum-Signup erforderlich, um Tag-Filter wie `estim`/`multi-axis` zu nutzen und Skripte herunterzuladen.
- Empfohlene URLs nach Login:
  - Tag-Filter: `https://discuss.eroscripts.com/tag/estim`
  - Volltext-Suche: `https://discuss.eroscripts.com/search?q=restim` bzw. `?q=alpha+beta`
- Hinweis: site:-Suche ueber Google liefert aktuell kaum Treffer fuer `restim` — Eroscripts blockiert Crawler weitgehend, deshalb sind Inhalte praktisch nur via Login auffindbar.

---

## 2. Vermutete Quellen (nicht inhaltlich verifiziert)

- **Eroscripts-Threads von Restim-Aktivposten**: Die in der Community ueblichen Namen (djj fuer Warp Zone, lolol2 fuer Stimbox-Material, edger477 als Tool-Autor) tauchen in Web-Suchergebnissen nicht als Profil-URLs auf — vermutlich nur nach Login einsehbar via `https://discuss.eroscripts.com/u/<username>`. Lohnt sich als erste Anlaufstelle nach Account-Anlage.
- **Restim/Estim-Discord**: In der "Big List of Useful Discord Servers" auf discuss.buttplug.io sind die wahrscheinlichsten Anlaufstellen:
  - Joanne's E-Stim Community: https://discord.com/invite/rY8C27S (4.5k Mitglieder, dezidiert Estim)
  - DeviceWeb: https://discord.com/invite/GGz7w22 (DIY/Framework, ~1k)
  - Buttplug.io main: https://discord.com/invite/t9g9RuD (13k, Channel-Suche nach `#estim`/`#restim`)
  - eStimStation: https://discord.gg/VXYYduDX4T (Audio-Estim Community, kein Restim-Support, aber Cross-Posting wahrscheinlich)
  - Ein offizieller "Restim"-Server von diglet48 ist weder auf Restim-README, Wiki noch in den GitHub-Issues verlinkt — falls existent, dann nur ueber Discord-Suche / Community-Empfehlung erreichbar.
- **Patreon-Konvertierungen**: Patreon-Creator wie "Eternal Enigma" und "Funscript Studios" liefern Stroker-Funscripts zu konkreten VR-Szenen. Diese sind Patreon-paywall, lassen sich aber via Restim Funscript Processor in Multi-Achsen-Sets verwandeln — nicht als Restim-Pakete vermarktet, aber technisch gleichwertig.
- **brucedkyle/_restim**: https://github.com/brucedkyle/_restim — Fork von diglet48/restim mit Tutorial-Material; keine Skripte, nur Doku, aber lesenswert fuer Background.
- **diglet48 Repos `toy-designs`, `FOC-Stim`**: Hardware-/Design-Repos, keine Funscripts.

---

## 3. Methode zum kontinuierlichen Auffinden

1. **GitHub-Repo-Watch** (zuverlaessigste Pipeline):
   - `https://github.com/Senorgif33?tab=repositories` (RSS via `.atom`-Suffix moeglich) — neue Restim-Event-Files-Pushes erscheinen direkt.
   - `https://github.com/edger477/funscript-tools/releases.atom` — neue Processor-Versionen.
   - GitHub Code-Search (eingeloggt): `extension:funscript "alpha" "beta"` und `path:.events.yml restim`.
   - GitHub Repo-Search: `restim funscript` regelmaessig per Web-UI checken — seit User-Repo `Harlekin7/restim-web-extension` bereits indiziert ist, tauchen verwandte neue Forks/Collections auf gleichem Suchpfad auf.
2. **Eroscripts (nach Account-Anlage)**:
   - RSS-Feed der Tag-Seite: `https://discuss.eroscripts.com/tag/estim.rss`
   - User-Watch der bekannten Estim-Skripter (`/u/<username>/activity` als RSS).
3. **Discord** (nach Beitritt der unter 2 genannten Server):
   - Gepinnte Posts/Resources-Channels fuer Repo-Indices.
   - Channel-Search `restim funscript` bzw. `alpha beta`.
4. **Estim-Audio-Aggregatoren** kombiniert mit FOCtave-Conversion:
   - SoundCloud-Tag `estim` (https://soundcloud.com/tags/estim/popular-tracks) als RSS.
   - https://e-stim.info/downloads/audio Neuzugaenge (kein RSS — manuelles Polling).
5. **archive.org Wayback** fuer alte Eroscripts-Threads, die sonst nicht mehr indiziert sind: `https://web.archive.org/web/*/discuss.eroscripts.com/t/*restim*`.
6. **Reddit** (auch wenn r/estim WebFetch oft blockiert): `https://www.reddit.com/r/estim/search/?q=restim+funscript&restrict_sr=1&sort=new` — manuell oder via reddit-API. r/funscript und r/eroscripts ebenso.

---

## 4. Hinweise zur Konvertierung

Wenn nur 1D-Skripte (Stroker-Funscripts) gefunden werden — was der Normalfall ist — gibt es zwei Wege zu vollwertigen Multi-Achsen-Setups:

1. **In-App, schnell**: Restim oeffnen -> Tools -> Funscript Conversion. Konvertiert das `.funscript` zu `.alpha.funscript` + `.beta.funscript` (Algorithmen: Circular, Top-Left-Right, Top-Right-Left, 0-360). Reicht fuer Stereostim/3-Phasen-Setup ohne Pulse-Modulation.
2. **Vollausstattung, batch**: edger477/funscript-tools (Restim Funscript Processor) installieren. Generiert in einem Lauf alle 10 Output-Files: `.alpha`, `.beta`, `.volume`, `.pulse_frequency`, `.pulse_width`, `.pulse_rise_time`, `.frequency`, plus `-prostate`-Variante (Beta invertiert + verstaerkte Volume) und ab v2.1.0 separate `Motion Axis (4P)` mit `e1`–`e4` fuer FOC-Stim 4-Phasen. Optional `.events.yml` fuer Event-Layer-Effekte (Edge/Cum/Ruin/Fast).
3. **Audio-Quelle vorhanden**: blucrew/FOCtave nutzen, um Estim-Audio (Stereo) in 4-Phase-Funscript zu wandeln. Erschliesst hunderte Tracks aus ESTIM MUSIC LABS, e-stim.info, SoundCloud-Sets als Restim-Material.

Praktischer Tipp: Die existierende 26-Session-Bibliothek des Users sollte mit Eroscripts-Tag `estim` plus dem Senorgif33-Repo-Inhalt schnell auf 40–50 Sessions wachsen koennen. Fuer einen sprunghaften Anstieg ist der Weg "beliebige populaere 1D-Funscripts aus Eroscripts + Restim Funscript Processor" um Groessenordnungen ergiebiger als die Suche nach pre-generierten Multi-Achsen-Packs.
