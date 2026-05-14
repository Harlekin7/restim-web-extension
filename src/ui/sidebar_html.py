"""Sidebar HTML for the pywebview control panel.

Now supports four modes: FapTap / TheEdgy / Network / SESSION.

`SIDEBAR_HTML` is exported as a module-level string for backward
compatibility with main.py — it is built once on import via
`build_sidebar_html()`, which composes the static layout with the
session-graph and body-schema fragments and embeds uPlot's iife bundle
inline so the page works without any HTTP server / file-loading.
"""
from __future__ import annotations

import json
from pathlib import Path

from .body_schema import build_body_schema_html
from .session_graph import build_session_graph_html


def _load_uplot_assets() -> tuple[str, str]:
    """Return (uplot.iife.min.js, uplot.min.css) as inline strings.

    We embed the assets directly to avoid having to expose a static-file
    HTTP server through pywebview. Files are bundled by the build (see
    RestimWebExtension.spec) so this works in both dev and frozen mode.
    """
    base = Path(__file__).parent / "static" / "uplot"
    try:
        js = (base / "uplot.iife.min.js").read_text(encoding="utf-8")
        css = (base / "uplot.min.css").read_text(encoding="utf-8")
    except FileNotFoundError:
        # Fall back to CDN at runtime — the graph will gracefully degrade.
        js = (
            "if (typeof uPlot === 'undefined') {\n"
            "  var s = document.createElement('script');\n"
            "  s.src = 'https://cdn.jsdelivr.net/npm/uplot@1.6.32/dist/uPlot.iife.min.js';\n"
            "  document.head.appendChild(s);\n"
            "}\n"
        )
        css = ""
    return js, css


def _default_session_profile_json() -> str:
    """Return a JSON-stub used by the graph for its initial state.

    We keep this independent from `session.profile.SessionProfile` to
    avoid circular dependencies between UI and session modules — the
    payload is only consumed by the graph JS to pick defaults.
    """
    return json.dumps({
        "style": "sanfter_aufbau",
        "duration_s": 45 * 60,
        "target": "climax",
        "character": "lebendig",
        "experience": 2,
    })


def build_sidebar_html() -> str:
    uplot_js, uplot_css = _load_uplot_assets()
    graph_fragment = build_session_graph_html(_default_session_profile_json())
    body_schema_fragment = build_body_schema_html(None)

    return _SIDEBAR_TEMPLATE.replace(
        "/*__UPLOT_CSS__*/", uplot_css
    ).replace(
        "/*__UPLOT_JS__*/", uplot_js
    ).replace(
        "<!--__SESSION_GRAPH__-->", graph_fragment
    ).replace(
        "<!--__BODY_SCHEMA__-->", body_schema_fragment
    )


# ─────────────────────────────────────────────────────────────────────
# Template
# ─────────────────────────────────────────────────────────────────────
# The previous (non-session) layout is preserved verbatim. New SESSION
# mode is gated by a single visibility-switch on body[data-mode].
_SIDEBAR_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
/*__UPLOT_CSS__*/

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: 'Segoe UI', Tahoma, sans-serif;
        font-size: 13px;
        background: #1e1e1e;
        color: #ccc;
        padding: 8px;
        overflow-y: auto;
        user-select: none;
    }
    .group {
        background: #2d2d2d;
        border: 1px solid #3e3e3e;
        border-radius: 6px;
        margin-bottom: 8px;
        padding: 10px;
    }
    .group-title {
        font-size: 11px;
        font-weight: 600;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .status-line {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 4px;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #555; }
    .dot.green { background: #4c4; }
    .label { color: #999; min-width: 70px; }
    .value { color: #eee; font-weight: 500; }
    .value.green { color: #4c4; }

    /* Slider rows */
    .param-row {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 5px;
    }
    .param-label {
        color: #aaa;
        font-size: 11px;
        min-width: 80px;
        white-space: nowrap;
    }
    .param-range {
        flex: 1;
        height: 4px;
        -webkit-appearance: none;
        appearance: none;
        background: #444;
        border-radius: 2px;
        outline: none;
    }
    .param-range::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 14px; height: 14px;
        border-radius: 50%;
        background: #7af;
        cursor: pointer;
    }
    .param-val {
        color: #eee;
        font-size: 11px;
        min-width: 36px;
        text-align: right;
        font-family: Consolas, monospace;
    }

    /* Number input fields */
    .param-input {
        width: 60px;
        background: #1a1a1a;
        border: 1px solid #444;
        border-radius: 3px;
        color: #eee;
        font-size: 11px;
        font-family: Consolas, monospace;
        padding: 2px 4px;
        text-align: right;
        outline: none;
    }
    .param-input:focus { border-color: #7af; }

    /* Select dropdowns */
    .param-select {
        flex: 1;
        background: #1a1a1a;
        border: 1px solid #444;
        border-radius: 3px;
        color: #eee;
        font-size: 11px;
        padding: 3px 4px;
        outline: none;
    }
    .param-select:focus { border-color: #7af; }

    /* Toggle button */
    .toggle-btn {
        background: #444;
        border: 1px solid #555;
        border-radius: 3px;
        color: #ccc;
        font-size: 11px;
        padding: 3px 10px;
        cursor: pointer;
        margin-left: 4px;
    }
    .toggle-btn.active {
        background: #5a8;
        border-color: #6b9;
        color: #fff;
    }

    #script-preview {
        background: #1a1a1a;
        border: 1px solid #333;
        border-radius: 4px;
        padding: 6px;
        font-family: Consolas, monospace;
        font-size: 11px;
        color: #aaa;
        max-height: 120px;
        overflow-y: auto;
        white-space: pre;
        margin-top: 6px;
    }
    #log {
        background: #1a1a1a;
        border: 1px solid #333;
        border-radius: 4px;
        padding: 6px;
        font-family: Consolas, monospace;
        font-size: 11px;
        color: #aaa;
        height: 140px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-break: break-all;
    }
    .log-time { color: #666; }
    .section-sep { border-top: 1px solid #3e3e3e; margin: 6px 0; }

    /* Site switcher */
    .site-switcher {
        display: flex;
        gap: 4px;
    }
    .site-btn {
        flex: 1;
        background: #2d2d2d;
        border: 1px solid #3e3e3e;
        border-radius: 4px;
        color: #888;
        font-size: 11px;
        font-weight: 600;
        padding: 6px 8px;
        cursor: pointer;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .site-btn.active {
        background: #5a8;
        border-color: #6b9;
        color: #fff;
    }
    .site-btn:not(.active):hover { background: #3a3a3a; color: #ccc; }

    /* ── SESSION-mode bits ── */

    /* Hide all non-session groups when in session mode, and vice-versa. */
    body[data-mode="session"] .non-session { display: none; }
    body:not([data-mode="session"]) .session-only { display: none; }

    .radio-row {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
    }
    .radio-pill {
        flex: 1;
        min-width: 60px;
        background: #2d2d2d;
        border: 1px solid #3e3e3e;
        color: #888;
        font-size: 11px;
        font-weight: 600;
        padding: 5px 6px;
        text-align: center;
        cursor: pointer;
        border-radius: 4px;
        text-transform: capitalize;
    }
    .radio-pill.active {
        background: #5a8;
        border-color: #6b9;
        color: #fff;
    }
    .radio-pill:not(.active):hover { background: #3a3a3a; color: #ccc; }

    .bipolar-row {
        display: grid;
        grid-template-columns: 60px 1fr 60px;
        align-items: center;
        gap: 4px;
        margin-bottom: 5px;
        font-size: 10px;
    }
    .bipolar-row .pole-l { color: #aaa; text-align: left; }
    .bipolar-row .pole-r { color: #aaa; text-align: right; }

    .exp-display {
        text-align: center;
        font-size: 11px;
        color: #ccc;
        margin-top: 4px;
        font-weight: 600;
    }

    .collapse-header {
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
        user-select: none;
    }
    .collapse-arrow {
        display: inline-block;
        transition: transform 0.15s;
        color: #888;
        font-size: 9px;
    }
    .collapse-open .collapse-arrow { transform: rotate(90deg); }
    .collapse-body { display: none; margin-top: 8px; }
    .collapse-open .collapse-body { display: block; }

    /* START / Override buttons */
    .start-btn {
        display: block;
        width: 100%;
        background: linear-gradient(180deg, #6b9 0%, #5a8 100%);
        border: 1px solid #6b9;
        color: #fff;
        font-size: 14px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        padding: 12px;
        border-radius: 6px;
        cursor: pointer;
        margin-top: 8px;
    }
    .start-btn:hover { background: linear-gradient(180deg, #7ca 0%, #6b9 100%); }
    .start-btn.stop {
        background: linear-gradient(180deg, #c55 0%, #a44 100%);
        border-color: #c55;
    }
    .start-btn.stop:hover { background: linear-gradient(180deg, #d66 0%, #b55 100%); }

    .override-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        margin-top: 8px;
    }
    .override-btn {
        background: #333;
        border: 1px solid #444;
        color: #ddd;
        font-size: 12px;
        font-weight: 600;
        padding: 10px;
        border-radius: 5px;
        cursor: pointer;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .override-btn:hover { background: #444; }
    .override-btn.danger {
        grid-column: 1 / -1;
        background: #722;
        border-color: #a33;
        color: #fff;
    }
    .override-btn.danger:hover { background: #a44; }

    /* Live-view */
    .live-bigvalue {
        text-align: center;
        padding: 12px 8px;
    }
    .live-phase {
        font-size: 18px;
        font-weight: 700;
        color: #fff;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    .live-time {
        font-size: 24px;
        font-weight: 700;
        color: #5a8;
        font-family: Consolas, monospace;
        margin-top: 4px;
    }
    .live-nextdrop {
        font-size: 11px;
        color: #aaa;
        margin-top: 4px;
    }
    .live-axes {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 4px;
        margin-top: 8px;
    }
    .live-axis {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 3px;
        padding: 4px 2px;
        text-align: center;
    }
    .live-axis .ax-name {
        font-size: 8px;
        color: #888;
        text-transform: uppercase;
    }
    .live-axis canvas {
        width: 100%;
        height: 24px;
        display: block;
        margin: 2px 0;
    }
    .live-axis .ax-val {
        font-size: 9px;
        color: #ddd;
        font-family: Consolas, monospace;
    }
</style>
</head>
<body data-mode="faptap">

<!-- Mode / Site switcher -->
<div class="group">
    <div class="group-title">Mode</div>
    <div class="site-switcher">
        <button class="site-btn" data-site="faptap">FapTap</button>
        <button class="site-btn" data-site="theedgy">TheEdgy</button>
        <button class="site-btn" data-site="network">Network</button>
        <button class="site-btn" data-site="session">Session</button>
    </div>
</div>

<!-- Server -->
<div class="group">
    <div class="group-title">Server</div>
    <div class="status-line">
        <span class="dot" id="server-dot"></span>
        <span class="value" id="server-status">Starting...</span>
    </div>
</div>

<!-- Network proxy target (only visible in network mode) -->
<div class="group non-session" id="group-network" style="display:none;">
    <div class="group-title">Network Target</div>
    <div class="site-switcher">
        <button class="site-btn target-btn" data-target="faptap">FapTap</button>
        <button class="site-btn target-btn" data-target="sexlikereal">SexLikeReal</button>
    </div>
</div>

<!-- TheEdgy live settings (only visible on theedgy) -->
<div class="group non-session" id="group-theedgy" style="display:none;">
    <div class="group-title">TheEdgy Live</div>
    <div class="param-row">
        <span class="param-label">Max Speed</span>
        <input type="number" class="param-input" id="s-max-speed" min="0" max="10000" step="10" value="330">
        <span class="param-val">%/s</span>
    </div>
    <div class="param-row">
        <span class="param-label">Min Speed</span>
        <input type="number" class="param-input" id="s-min-speed" min="0" max="10000" step="5" value="32">
        <span class="param-val">%/s</span>
    </div>
</div>

<!-- ══════════════════════════════════════════════════════════ -->
<!-- ═════════════════ SESSION CONFIG (config view) ══════════ -->
<!-- ══════════════════════════════════════════════════════════ -->

<div id="session-config" class="session-only">

<!-- 1. Session basics: stil, dauer, ziel -->
<div class="group">
    <div class="group-title">Session</div>
    <div class="param-row">
        <span class="param-label">Stil</span>
        <select class="param-select" id="ss-style">
            <option value="sanfter_aufbau">Sanfter Aufbau</option>
            <option value="crescendo">Crescendo</option>
            <option value="beat_drop">Beat-Drop</option>
            <option value="edging">Edging</option>
            <option value="ruin">Ruin</option>
            <option value="endlos_tease">Endlos-Tease</option>
        </select>
    </div>
    <!-- Duration uses linear input but is displayed via log-scaled slider. -->
    <div class="param-row">
        <span class="param-label">Dauer</span>
        <input type="range" class="param-range" id="ss-duration"
               min="0" max="1000" step="1" value="555">
        <span class="param-val" id="ss-duration-val">45m</span>
    </div>
    <div class="param-row">
        <span class="param-label">Ziel</span>
        <select class="param-select" id="ss-target">
            <option value="climax">Climax</option>
            <option value="edge_hold">Edge &amp; Hold</option>
            <option value="ruined">Ruined Drop</option>
            <option value="open_end">Open-End / Tease</option>
        </select>
    </div>
</div>

<!-- 2. Sensations-Mix -->
<div class="group">
    <div class="group-title">Sensations-Mix</div>
    <div class="bipolar-row">
        <span class="pole-l">Schärfe</span>
        <input type="range" class="param-range" id="ss-sense-sd" min="0" max="1" step="0.01" value="0.5">
        <span class="pole-r">Tiefe</span>
    </div>
    <div class="bipolar-row">
        <span class="pole-l">Granular</span>
        <input type="range" class="param-range" id="ss-sense-gs" min="0" max="1" step="0.01" value="0.5">
        <span class="pole-r">Glatt</span>
    </div>
    <div class="bipolar-row">
        <span class="pole-l">Weich</span>
        <input type="range" class="param-range" id="ss-sense-sh" min="0" max="1" step="0.01" value="0.5">
        <span class="pole-r">Hart</span>
    </div>
    <div class="bipolar-row">
        <span class="pole-l">Statisch</span>
        <input type="range" class="param-range" id="ss-sense-sm" min="0" max="1" step="0.01" value="0.5">
        <span class="pole-r">Wandernd</span>
    </div>
</div>

<!-- 3. Charakter -->
<div class="group">
    <div class="group-title">Charakter</div>
    <div class="radio-row">
        <div class="radio-pill" data-char="sanft">Sanft</div>
        <div class="radio-pill active" data-char="lebendig">Lebendig</div>
        <div class="radio-pill" data-char="spielerisch">Spielerisch</div>
        <div class="radio-pill" data-char="wild">Wild</div>
    </div>
</div>

<!-- 4. Erfahrung -->
<div class="group">
    <div class="group-title">Erfahrung</div>
    <div class="param-row">
        <span class="param-label">Stufe</span>
        <input type="range" class="param-range" id="ss-exp" min="1" max="5" step="1" value="2">
        <span class="param-val" id="ss-exp-val">2</span>
    </div>
    <div class="exp-display" id="ss-exp-label">Eingewöhnt</div>
</div>

<!-- 5. Hardware & Elektroden -->
<div class="group">
    <div class="group-title">Hardware &amp; Elektroden</div>
    <div class="param-row">
        <span class="param-label">Geräteklasse</span>
        <select class="param-select" id="ss-device">
            <option value="3_phase_foc">3-Phase FOC Standard</option>
            <option value="4_phase_foc">4-Phase FOC</option>
            <option value="stereostim">Stereostim (2-Ch)</option>
            <option value="single_channel">Single-Channel</option>
        </select>
    </div>
    <!--__BODY_SCHEMA__-->
</div>

<!-- Graph -->
<!--__SESSION_GRAPH__-->

<!-- Erweitert -->
<div class="group">
    <div class="collapse-header" id="adv-toggle">
        <span class="collapse-arrow">▶</span>
        <span class="group-title" style="margin-bottom:0;">Erweitert (Profi-Modus)</span>
    </div>
    <div class="collapse-body">
        <div class="param-row">
            <span class="param-label">Vol Cap</span>
            <input type="range" class="param-range" id="ss-vol-cap" min="0.3" max="1.0" step="0.01" value="0.8">
            <span class="param-val" id="ss-vol-cap-val">0.80</span>
        </div>
        <div class="param-row">
            <span class="param-label">Carrier Cap</span>
            <input type="number" class="param-input" id="ss-carrier-cap" min="500" max="2500" step="50" value="1300">
            <span class="param-val">Hz</span>
        </div>
        <div class="param-row">
            <span class="param-label">PW Cap</span>
            <input type="number" class="param-input" id="ss-pw-cap" min="60" max="500" step="10" value="200">
            <span class="param-val">µs</span>
        </div>
        <div class="param-row">
            <span class="param-label">Crossfade</span>
            <input type="range" class="param-range" id="ss-crossfade" min="0.5" max="5.0" step="0.1" value="1.5">
            <span class="param-val" id="ss-crossfade-val">1.5s</span>
        </div>
        <div class="param-row">
            <span class="param-label">Pat Lockout</span>
            <input type="number" class="param-input" id="ss-pat-lockout" min="0" max="120" step="1" value="30">
            <span class="param-val">s</span>
        </div>
        <div class="param-row">
            <span class="param-label">Seed</span>
            <input type="number" class="param-input" id="ss-seed" min="0" max="9999999" step="1" placeholder="random">
        </div>
    </div>
</div>

<!-- START -->
<button class="start-btn" id="ss-start">▶ START SESSION</button>

</div>  <!-- /session-config -->

<!-- ══════════════════════════════════════════════════════════ -->
<!-- ═════════════════ SESSION LIVE-VIEW ═════════════════════ -->
<!-- ══════════════════════════════════════════════════════════ -->

<div id="session-live" class="session-only" style="display:none;">
    <div class="group">
        <div class="group-title">Live</div>
        <div class="live-bigvalue">
            <div class="live-phase" id="live-phase">Build</div>
            <div class="live-time" id="live-time">00:00</div>
            <div class="live-nextdrop" id="live-nextdrop">next drop in –</div>
        </div>
        <div class="live-axes" id="live-axes">
            <div class="live-axis"><div class="ax-name">α</div><canvas data-ax="alpha"></canvas><div class="ax-val" data-ax-val="alpha">–</div></div>
            <div class="live-axis"><div class="ax-name">β</div><canvas data-ax="beta"></canvas><div class="ax-val" data-ax-val="beta">–</div></div>
            <div class="live-axis"><div class="ax-name">V</div><canvas data-ax="volume"></canvas><div class="ax-val" data-ax-val="volume">–</div></div>
            <div class="live-axis"><div class="ax-name">C</div><canvas data-ax="carrier"></canvas><div class="ax-val" data-ax-val="carrier">–</div></div>
            <div class="live-axis"><div class="ax-name">PF</div><canvas data-ax="pf"></canvas><div class="ax-val" data-ax-val="pf">–</div></div>
            <div class="live-axis"><div class="ax-name">PW</div><canvas data-ax="pw"></canvas><div class="ax-val" data-ax-val="pw">–</div></div>
            <div class="live-axis"><div class="ax-name">PR</div><canvas data-ax="pr"></canvas><div class="ax-val" data-ax-val="pr">–</div></div>
        </div>
        <div class="override-grid">
            <button class="override-btn" data-act="pause">Pause</button>
            <button class="override-btn" data-act="skip">Skip Phase</button>
            <button class="override-btn" data-act="edge">Edge Now</button>
            <button class="override-btn" data-act="boost">Boost</button>
            <button class="override-btn danger" data-act="stop">STOP</button>
        </div>
    </div>
</div>

<!-- ══════════════════════════════════════════════════════════ -->
<!-- ═════════════════ LEGACY (FapTap/TheEdgy) ═══════════════ -->
<!-- ══════════════════════════════════════════════════════════ -->

<div class="non-session">

<!-- Funscript -->
<div class="group">
    <div class="group-title">Funscript</div>
    <div class="status-line">
        <span class="label">Status:</span>
        <span class="value" id="script-status">Waiting for connection...</span>
    </div>
    <div class="status-line">
        <span class="label">Actions:</span>
        <span class="value" id="script-actions">-</span>
    </div>
    <div class="status-line">
        <span class="label">Duration:</span>
        <span class="value" id="script-duration">-</span>
    </div>
    <div id="script-preview">Script preview...</div>
</div>

<!-- ════════ GENERAL ════════ -->
<div class="group">
    <div class="group-title">General</div>

    <!-- Arc -->
    <div class="param-row">
        <span class="param-label">Arc Degrees</span>
        <input type="range" class="param-range" id="s-arc" min="270" max="360" step="5" value="270">
        <span class="param-val" id="v-arc">270</span>
        <button class="toggle-btn active" id="btn-invert" title="Invert arc">Inv</button>
    </div>

    <div class="section-sep"></div>

    <!-- Speed -->
    <div class="param-row">
        <span class="param-label">Speed Window</span>
        <input type="number" class="param-input" id="s-speed-win" min="1" max="30" step="0.5" value="3">
        <span class="param-val">s</span>
    </div>
    <div class="param-row">
        <span class="param-label">Min Radius</span>
        <input type="range" class="param-range" id="s-min-rad" min="0.05" max="0.5" step="0.05" value="0.5">
        <span class="param-val" id="v-min-rad">0.50</span>
    </div>
    <div class="param-row">
        <span class="param-label">Speed Thr.</span>
        <input type="range" class="param-range" id="s-speed-thr" min="0.1" max="1.0" step="0.05" value="1.0">
        <span class="param-val" id="v-speed-thr">1.00</span>
    </div>

    <div class="section-sep"></div>

    <!-- Volume -->
    <div class="param-row">
        <span class="param-label">Vol Min</span>
        <input type="number" class="param-input" id="s-vol-min" min="0" max="1" step="0.01" value="0.85">
    </div>
    <div class="param-row">
        <span class="param-label">Vol Max</span>
        <input type="number" class="param-input" id="s-vol-max" min="0" max="1" step="0.01" value="1.0">
    </div>
    <div class="param-row">
        <span class="param-label">Vol Window</span>
        <input type="range" class="param-range" id="s-vol-win" min="1" max="30" step="0.5" value="3">
        <span class="param-val" id="v-vol-win">3.0s</span>
    </div>
    <div class="param-row">
        <span class="param-label">Fade Down</span>
        <input type="number" class="param-input" id="s-fade-down" min="0.1" max="10" step="0.1" value="1.0">
        <span class="param-val">s</span>
    </div>
    <div class="param-row">
        <span class="param-label">Fade Up</span>
        <input type="number" class="param-input" id="s-fade-up" min="0.1" max="5" step="0.1" value="0.3">
        <span class="param-val">s</span>
    </div>

    <div class="section-sep"></div>

    <!-- Boost -->
    <div class="param-row">
        <span class="param-label">Boost</span>
        <button class="toggle-btn" id="btn-boost" title="Burst detection">Off</button>
    </div>
    <div class="param-row" id="boost-settings" style="display:none;">
        <span class="param-label">Strength</span>
        <input type="range" class="param-range" id="s-boost-str" min="0.5" max="3.0" step="0.1" value="1.5">
        <span class="param-val" id="v-boost-str">1.5</span>
    </div>
    <div class="param-row" id="boost-settings2" style="display:none;">
        <span class="param-label">Boost Win</span>
        <input type="range" class="param-range" id="s-boost-win" min="0.1" max="2.0" step="0.1" value="0.5">
        <span class="param-val" id="v-boost-win">0.5s</span>
    </div>

    <div class="section-sep"></div>

    <!-- Position → Pulse Freq -->
    <div class="param-row">
        <span class="param-label">Pos Freq</span>
        <input type="range" class="param-range" id="s-pos-freq" min="0" max="1" step="0.05" value="0.30">
        <span class="param-val" id="v-pos-freq">0.30</span>
        <button class="toggle-btn active" id="btn-pos-freq-inv" title="Invert position">Inv</button>
    </div>
</div>

<!-- ════════ PULSE SETTINGS ════════ -->
<div class="group">
    <div class="group-title">Pulse Settings</div>

    <!-- Carrier Freq -->
    <div class="param-row">
        <span class="param-label">CarFreq Min</span>
        <input type="range" class="param-range" id="s-car-min" min="0" max="1.0" step="0.05" value="0.80">
        <span class="param-val" id="v-car-min">0.80</span>
    </div>
    <div class="param-row">
        <span class="param-label">CarFreq Max</span>
        <input type="range" class="param-range" id="s-car-max" min="0.2" max="1.0" step="0.05" value="1.0">
        <span class="param-val" id="v-car-max">1.00</span>
    </div>

    <div class="section-sep"></div>

    <!-- Pulse Freq -->
    <div class="param-row">
        <span class="param-label">PulseF Min</span>
        <input type="range" class="param-range" id="s-pf-min" min="0" max="1.0" step="0.05" value="0.0">
        <span class="param-val" id="v-pf-min">0.00</span>
    </div>
    <div class="param-row">
        <span class="param-label">PulseF Max</span>
        <input type="range" class="param-range" id="s-pf-max" min="0" max="1.0" step="0.05" value="1.0">
        <span class="param-val" id="v-pf-max">1.00</span>
    </div>

    <div class="section-sep"></div>

    <!-- Pulse Width -->
    <div class="param-row">
        <span class="param-label">PulseW Min</span>
        <input type="range" class="param-range" id="s-pw-min" min="0" max="1.0" step="0.05" value="0.0">
        <span class="param-val" id="v-pw-min">0.00</span>
    </div>
    <div class="param-row">
        <span class="param-label">PulseW Max</span>
        <input type="range" class="param-range" id="s-pw-max" min="0" max="1.0" step="0.05" value="1.0">
        <span class="param-val" id="v-pw-max">1.00</span>
    </div>

    <div class="section-sep"></div>

    <!-- Pulse Rise Time -->
    <div class="param-row">
        <span class="param-label">Rise Min</span>
        <input type="range" class="param-range" id="s-pr-min" min="0" max="0.5" step="0.05" value="0.0">
        <span class="param-val" id="v-pr-min">0.00</span>
    </div>
    <div class="param-row">
        <span class="param-label">Rise Max</span>
        <input type="range" class="param-range" id="s-pr-max" min="0.1" max="1.0" step="0.05" value="0.8">
        <span class="param-val" id="v-pr-max">0.80</span>
    </div>
</div>

</div> <!-- /non-session -->

<!-- Log (always visible) -->
<div class="group">
    <div class="group-title">Log</div>
    <div id="log"></div>
</div>

<!-- ───────── uPlot bundle (inlined) ───────── -->
<script>
/*__UPLOT_JS__*/
</script>

<script>
    // ── Toggle states ─────────────────────────────────────────
    var arcInverted = true;
    document.getElementById('btn-invert').addEventListener('click', function() {
        arcInverted = !arcInverted;
        this.className = 'toggle-btn' + (arcInverted ? ' active' : '');
        notifySettingsChanged();
    });

    var boostEnabled = false;
    document.getElementById('btn-boost').addEventListener('click', function() {
        boostEnabled = !boostEnabled;
        this.className = 'toggle-btn' + (boostEnabled ? ' active' : '');
        this.textContent = boostEnabled ? 'On' : 'Off';
        document.getElementById('boost-settings').style.display = boostEnabled ? 'flex' : 'none';
        document.getElementById('boost-settings2').style.display = boostEnabled ? 'flex' : 'none';
        notifySettingsChanged();
    });

    var posFreqInverted = true;
    document.getElementById('btn-pos-freq-inv').addEventListener('click', function() {
        posFreqInverted = !posFreqInverted;
        this.className = 'toggle-btn' + (posFreqInverted ? ' active' : '');
        notifySettingsChanged();
    });

    // ── Slider wiring ─────────────────────────────────────────
    var sliders = {
        's-arc':       { val: 'v-arc',       fmt: function(v){ return Math.round(v); } },
        's-boost-str': { val: 'v-boost-str', fmt: function(v){ return parseFloat(v).toFixed(1); } },
        's-boost-win': { val: 'v-boost-win', fmt: function(v){ return parseFloat(v).toFixed(1)+'s'; } },
        's-min-rad':   { val: 'v-min-rad',   fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-speed-thr': { val: 'v-speed-thr', fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-vol-win':   { val: 'v-vol-win',   fmt: function(v){ return parseFloat(v).toFixed(1)+'s'; } },
        's-car-min':   { val: 'v-car-min',   fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-car-max':   { val: 'v-car-max',   fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-pf-min':    { val: 'v-pf-min',    fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-pf-max':    { val: 'v-pf-max',    fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-pw-min':    { val: 'v-pw-min',    fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-pw-max':    { val: 'v-pw-max',    fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-pr-min':    { val: 'v-pr-min',    fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-pr-max':    { val: 'v-pr-max',    fmt: function(v){ return parseFloat(v).toFixed(2); } },
        's-pos-freq':  { val: 'v-pos-freq',  fmt: function(v){ return parseFloat(v).toFixed(2); } }
    };

    Object.keys(sliders).forEach(function(id) {
        var el = document.getElementById(id);
        var cfg = sliders[id];
        el.addEventListener('input', function() {
            document.getElementById(cfg.val).textContent = cfg.fmt(el.value);
            notifySettingsChanged();
        });
    });

    // ── Number input wiring ───────────────────────────────────
    var inputs = ['s-speed-win', 's-vol-min', 's-vol-max', 's-fade-down', 's-fade-up',
                  's-max-speed', 's-min-speed'];
    inputs.forEach(function(id) {
        document.getElementById(id).addEventListener('change', function() {
            notifySettingsChanged();
        });
    });

    // ── Mode / Site switcher ──────────────────────────────────
    var currentSite = 'faptap';
    document.querySelectorAll('.site-btn[data-site]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var site = btn.getAttribute('data-site');
            if (site === currentSite) return;
            // 'session' is UI-only — no Python set_site call.
            if (site === 'session') {
                setActiveSite('session');
                return;
            }
            if (window.pywebview && window.pywebview.api && window.pywebview.api.set_site) {
                window.pywebview.api.set_site(site).then(function(ok) {
                    if (ok) setActiveSite(site);
                });
            } else {
                setActiveSite(site);
            }
        });
    });

    function setActiveSite(site) {
        currentSite = site;
        document.body.setAttribute('data-mode', site);
        document.querySelectorAll('.site-btn[data-site]').forEach(function(b) {
            b.classList.toggle('active', b.getAttribute('data-site') === site);
        });
        document.getElementById('group-theedgy').style.display =
            (site === 'theedgy') ? 'block' : 'none';
        document.getElementById('group-network').style.display =
            (site === 'network') ? 'block' : 'none';
    }

    // ── Network target picker ─────────────────────────────────
    var currentTarget = 'faptap';
    document.querySelectorAll('.target-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var target = btn.getAttribute('data-target');
            if (target === currentTarget) return;
            if (window.pywebview && window.pywebview.api && window.pywebview.api.set_network_target) {
                window.pywebview.api.set_network_target(target).then(function(ok) {
                    if (ok) setActiveTarget(target);
                });
            }
        });
    });

    function setActiveTarget(target) {
        currentTarget = target;
        document.querySelectorAll('.target-btn').forEach(function(b) {
            b.classList.toggle('active', b.getAttribute('data-target') === target);
        });
    }

    // ── Collect all (legacy) settings ─────────────────────────
    function getSettings() {
        return {
            arc_degrees:      parseFloat(document.getElementById('s-arc').value),
            arc_invert:       arcInverted,
            boost_enabled:    boostEnabled,
            boost_strength:   parseFloat(document.getElementById('s-boost-str').value),
            boost_window:     parseFloat(document.getElementById('s-boost-win').value),
            speed_window:     parseFloat(document.getElementById('s-speed-win').value),
            min_radius:       parseFloat(document.getElementById('s-min-rad').value),
            speed_threshold:  parseFloat(document.getElementById('s-speed-thr').value),
            volume_min:       parseFloat(document.getElementById('s-vol-min').value),
            volume_max:       parseFloat(document.getElementById('s-vol-max').value),
            volume_window:    parseFloat(document.getElementById('s-vol-win').value),
            volume_fade_down: parseFloat(document.getElementById('s-fade-down').value),
            volume_fade_up:   parseFloat(document.getElementById('s-fade-up').value),
            carrier_freq_min: parseFloat(document.getElementById('s-car-min').value),
            carrier_freq_max: parseFloat(document.getElementById('s-car-max').value),
            pulse_freq_min:   parseFloat(document.getElementById('s-pf-min').value),
            pulse_freq_max:   parseFloat(document.getElementById('s-pf-max').value),
            pulse_width_min:  parseFloat(document.getElementById('s-pw-min').value),
            pulse_width_max:  parseFloat(document.getElementById('s-pw-max').value),
            pulse_rise_min:   parseFloat(document.getElementById('s-pr-min').value),
            pulse_rise_max:   parseFloat(document.getElementById('s-pr-max').value),
            max_speed_pct:    parseFloat(document.getElementById('s-max-speed').value),
            min_speed_pct:    parseFloat(document.getElementById('s-min-speed').value),
            position_freq_influence: parseFloat(document.getElementById('s-pos-freq').value),
            position_freq_invert:    posFreqInverted
        };
    }

    function notifySettingsChanged() {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.update_settings(JSON.stringify(getSettings()));
        }
    }

    // ── Mapping: settings key → element id + type ─────────────
    var settingsMap = {
        arc_degrees:      { id: 's-arc',       type: 'slider' },
        arc_invert:       { id: 'btn-invert',  type: 'toggle' },
        boost_enabled:    { id: 'btn-boost',   type: 'boost-toggle' },
        boost_strength:   { id: 's-boost-str', type: 'slider' },
        boost_window:     { id: 's-boost-win', type: 'slider' },
        speed_window:     { id: 's-speed-win', type: 'input' },
        min_radius:       { id: 's-min-rad',   type: 'slider' },
        speed_threshold:  { id: 's-speed-thr', type: 'slider' },
        volume_min:       { id: 's-vol-min',   type: 'input' },
        volume_max:       { id: 's-vol-max',   type: 'input' },
        volume_window:    { id: 's-vol-win',   type: 'slider' },
        volume_fade_down: { id: 's-fade-down', type: 'input' },
        volume_fade_up:   { id: 's-fade-up',   type: 'input' },
        carrier_freq_min: { id: 's-car-min',   type: 'slider' },
        carrier_freq_max: { id: 's-car-max',   type: 'slider' },
        pulse_freq_min:   { id: 's-pf-min',    type: 'slider' },
        pulse_freq_max:   { id: 's-pf-max',    type: 'slider' },
        pulse_width_min:  { id: 's-pw-min',    type: 'slider' },
        pulse_width_max:  { id: 's-pw-max',    type: 'slider' },
        pulse_rise_min:   { id: 's-pr-min',    type: 'slider' },
        pulse_rise_max:   { id: 's-pr-max',    type: 'slider' },
        max_speed_pct:    { id: 's-max-speed', type: 'input' },
        min_speed_pct:    { id: 's-min-speed', type: 'input' },
        position_freq_influence: { id: 's-pos-freq',       type: 'slider' },
        position_freq_invert:    { id: 'btn-pos-freq-inv', type: 'pos-freq-toggle' }
    };

    function applySettings(data) {
        Object.keys(settingsMap).forEach(function(key) {
            if (!(key in data)) return;
            var m = settingsMap[key];
            if (m.type === 'toggle') {
                arcInverted = !!data[key];
                document.getElementById(m.id).className =
                    'toggle-btn' + (arcInverted ? ' active' : '');
            } else if (m.type === 'boost-toggle') {
                boostEnabled = !!data[key];
                var btn = document.getElementById(m.id);
                btn.className = 'toggle-btn' + (boostEnabled ? ' active' : '');
                btn.textContent = boostEnabled ? 'On' : 'Off';
                document.getElementById('boost-settings').style.display = boostEnabled ? 'flex' : 'none';
                document.getElementById('boost-settings2').style.display = boostEnabled ? 'flex' : 'none';
            } else if (m.type === 'pos-freq-toggle') {
                posFreqInverted = !!data[key];
                document.getElementById(m.id).className =
                    'toggle-btn' + (posFreqInverted ? ' active' : '');
            } else {
                var el = document.getElementById(m.id);
                el.value = data[key];
                if (m.type === 'slider' && sliders[m.id]) {
                    var cfg = sliders[m.id];
                    document.getElementById(cfg.val).textContent = cfg.fmt(data[key]);
                }
            }
        });
    }

    function loadSavedSettings() {
        if (!window.pywebview || !window.pywebview.api) return;
        var json = window.pywebview.api.load_settings();
        if (json) {
            try {
                var data = JSON.parse(json);
                applySettings(data);
                notifySettingsChanged();
            } catch(e) {}
        }
    }

    // ── Public functions called from Python ───────────────────
    function setServerStatus(text, ok) {
        document.getElementById('server-status').textContent = text;
        document.getElementById('server-dot').className = 'dot ' + (ok ? 'green' : 'yellow');
    }

    function appendLog(msg) {
        var log = document.getElementById('log');
        var now = new Date();
        var ts = now.getHours().toString().padStart(2,'0') + ':'
               + now.getMinutes().toString().padStart(2,'0') + ':'
               + now.getSeconds().toString().padStart(2,'0');
        log.innerHTML += '<div><span class="log-time">' + ts + '</span> ' + msg + '</div>';
        log.scrollTop = log.scrollHeight;
    }

    function showFunscript(jsonStr) {
        try {
            var data = JSON.parse(jsonStr);
            var actions = data.actions || [];
            var count = actions.length;
            if (count === 0) {
                document.getElementById('script-status').textContent = 'Empty script';
                return;
            }
            var durMs = actions[count - 1].at;
            var mins = Math.floor(durMs / 60000);
            var secs = Math.floor((durMs % 60000) / 1000);
            var el = document.getElementById('script-status');
            el.textContent = 'Script received!';
            el.className = 'value green';
            document.getElementById('script-actions').textContent = count;
            document.getElementById('script-duration').textContent =
                mins + ':' + secs.toString().padStart(2, '0');

            var lines = [];
            var show = Math.min(15, count);
            for (var i = 0; i < show; i++) {
                var a = actions[i];
                lines.push(('       ' + a.at).slice(-7) + 'ms  pos=' + ('   ' + a.pos).slice(-3));
            }
            if (count > 15) {
                lines.push('  ... (' + (count - 15) + ' more) ...');
            }
            document.getElementById('script-preview').textContent = lines.join('\n');
        } catch(e) {
            appendLog('Parse error: ' + e.message);
        }
    }

    // ══════════════════════════════════════════════════════════
    // ══════════════ SESSION MODE WIRING ═══════════════════════
    // ══════════════════════════════════════════════════════════
    (function() {
        const EXP_LABELS = {
            1: 'Beginner', 2: 'Eingewöhnt', 3: 'Erfahren',
            4: 'Routiniert', 5: 'Profi',
        };

        // Duration slider is linear 0..1000 → log-mapped to 5min..3h.
        function durationFromSlider(v) {
            // 5*60 = 300s, 3*60*60 = 10800s. Log-interp.
            const lo = Math.log(300), hi = Math.log(10800);
            return Math.round(Math.exp(lo + (hi - lo) * (v / 1000)));
        }
        function formatDuration(s) {
            if (s < 3600) return Math.round(s / 60) + 'm';
            const h = Math.floor(s / 3600);
            const m = Math.round((s - h*3600) / 60);
            return h + 'h' + (m ? ' ' + m + 'm' : '');
        }

        const ssDur = document.getElementById('ss-duration');
        const ssDurVal = document.getElementById('ss-duration-val');
        ssDur.addEventListener('input', () => {
            const s = durationFromSlider(parseFloat(ssDur.value));
            ssDurVal.textContent = formatDuration(s);
            notifySessionProfile();
        });

        // Exp slider
        const ssExp = document.getElementById('ss-exp');
        const ssExpVal = document.getElementById('ss-exp-val');
        const ssExpLabel = document.getElementById('ss-exp-label');
        ssExp.addEventListener('input', () => {
            const lvl = parseInt(ssExp.value);
            ssExpVal.textContent = String(lvl);
            ssExpLabel.textContent = EXP_LABELS[lvl];
            notifySessionProfile();
        });

        // Character pills
        let currentChar = 'lebendig';
        document.querySelectorAll('.radio-pill[data-char]').forEach(p => {
            p.addEventListener('click', () => {
                currentChar = p.getAttribute('data-char');
                document.querySelectorAll('.radio-pill[data-char]').forEach(x => {
                    x.classList.toggle('active', x === p);
                });
                if (window.__sessionGraph) window.__sessionGraph.setCharacter(currentChar);
                notifySessionProfile();
            });
        });

        // Style / Target dropdowns sync to graph defaults
        document.getElementById('ss-style').addEventListener('change', (e) => {
            if (window.__sessionGraph) window.__sessionGraph.setStyle(e.target.value);
            notifySessionProfile();
        });
        document.getElementById('ss-target').addEventListener('change', (e) => {
            if (window.__sessionGraph) window.__sessionGraph.setTarget(e.target.value);
            notifySessionProfile();
        });

        // Sensation sliders
        ['ss-sense-sd','ss-sense-gs','ss-sense-sh','ss-sense-sm'].forEach(id => {
            document.getElementById(id).addEventListener('input', notifySessionProfile);
        });

        // Device class → body schema preset
        document.getElementById('ss-device').addEventListener('change', (e) => {
            if (window.__bodySchema) window.__bodySchema.setHardwarePreset(e.target.value);
            notifySessionProfile();
        });

        // Body-schema change feedback
        window.__bodySchemaOnChange = function(list) {
            notifySessionProfile();
        };

        // Erweitert collapse
        const advHdr = document.getElementById('adv-toggle');
        advHdr.addEventListener('click', () => {
            advHdr.parentElement.classList.toggle('collapse-open');
        });
        // Advanced sliders with live labels
        const advLabels = {
            'ss-vol-cap': { val: 'ss-vol-cap-val', fmt: v => parseFloat(v).toFixed(2) },
            'ss-crossfade': { val: 'ss-crossfade-val', fmt: v => parseFloat(v).toFixed(1) + 's' },
        };
        Object.keys(advLabels).forEach(id => {
            const el = document.getElementById(id);
            const cfg = advLabels[id];
            el.addEventListener('input', () => {
                document.getElementById(cfg.val).textContent = cfg.fmt(el.value);
                notifySessionProfile();
            });
        });
        ['ss-carrier-cap','ss-pw-cap','ss-pat-lockout','ss-seed'].forEach(id => {
            document.getElementById(id).addEventListener('change', notifySessionProfile);
        });

        // ── Build & emit SessionProfile dict ──────────────────
        function getSessionProfile() {
            const style = document.getElementById('ss-style').value;
            const target = document.getElementById('ss-target').value;
            const duration_s = durationFromSlider(parseFloat(ssDur.value));
            const experience = parseInt(ssExp.value);
            const device_class = document.getElementById('ss-device').value;
            const electrodes = window.__bodySchema ? window.__bodySchema.get() : [];

            // Map size-string → cm² (defaults from session.profile.Electrode).
            const sizeMap = { small: 4.0, medium: 9.0, large: 16.0 };
            const electrodesPy = electrodes.map(e => ({
                position: e.position,
                is_common: !!e.is_common,
                size_cm2: sizeMap[e.size] || 9.0,
            }));

            const seedStr = document.getElementById('ss-seed').value.trim();
            const seed = seedStr ? parseInt(seedStr) : null;

            const envelope = (window.__sessionGraph
                ? window.__sessionGraph.getEnvelope()
                : null);

            return {
                style: style,
                duration_s: duration_s,
                target: target,
                sensation: {
                    sharp_to_deep:      parseFloat(document.getElementById('ss-sense-sd').value),
                    granular_to_smooth: parseFloat(document.getElementById('ss-sense-gs').value),
                    soft_to_hard:       parseFloat(document.getElementById('ss-sense-sh').value),
                    static_to_moving:   parseFloat(document.getElementById('ss-sense-sm').value),
                },
                character: currentChar,
                experience: experience,
                hardware: {
                    device_class: device_class,
                    electrodes: electrodesPy,
                },
                safety: {
                    max_volume:       parseFloat(document.getElementById('ss-vol-cap').value),
                    max_carrier_hz:   parseFloat(document.getElementById('ss-carrier-cap').value),
                    max_pulse_width_us: parseFloat(document.getElementById('ss-pw-cap').value),
                    min_volume_ramp_s: 5.0,
                },
                advanced: {
                    pattern_repeat_lockout_s: parseFloat(document.getElementById('ss-pat-lockout').value),
                    crossfade_s: parseFloat(document.getElementById('ss-crossfade').value),
                    pattern_pool: null,
                    subwave_count: null,
                },
                seed: seed,
                // UI-only extra, the backend may ignore it:
                envelope: envelope,
            };
        }

        let emitTimer = null;
        function notifySessionProfile() {
            clearTimeout(emitTimer);
            emitTimer = setTimeout(() => {
                if (window.pywebview && window.pywebview.api &&
                    typeof window.pywebview.api.set_session_profile === 'function') {
                    try {
                        window.pywebview.api.set_session_profile(getSessionProfile());
                    } catch (e) {}
                }
            }, 100);
        }

        // ── START / Live-view ─────────────────────────────────
        const cfgPanel = document.getElementById('session-config');
        const livePanel = document.getElementById('session-live');

        document.getElementById('ss-start').addEventListener('click', () => {
            if (window.pywebview && window.pywebview.api &&
                typeof window.pywebview.api.start_session === 'function') {
                try { window.pywebview.api.start_session(getSessionProfile()); } catch (e) {}
            }
            cfgPanel.style.display = 'none';
            livePanel.style.display = 'block';
        });

        // Override-buttons
        const overrideMap = {
            pause: 'session_pause',
            skip:  'session_skip',
            edge:  'session_edge_now',
            boost: 'session_boost',
            stop:  'session_stop',
        };
        document.querySelectorAll('.override-btn').forEach(b => {
            b.addEventListener('click', () => {
                const act = b.getAttribute('data-act');
                const apiName = overrideMap[act];
                if (window.pywebview && window.pywebview.api &&
                    typeof window.pywebview.api[apiName] === 'function') {
                    try { window.pywebview.api[apiName](); } catch (e) {}
                }
                if (act === 'stop') {
                    livePanel.style.display = 'none';
                    cfgPanel.style.display = 'block';
                }
            });
        });

        // Live-axis mini-sparklines: 64-sample circular buffer per axis.
        const axisBuffers = {};
        document.querySelectorAll('#live-axes canvas[data-ax]').forEach(c => {
            const name = c.getAttribute('data-ax');
            axisBuffers[name] = { canvas: c, ctx: c.getContext('2d'), buf: new Array(64).fill(0) };
        });

        function drawAxis(name) {
            const a = axisBuffers[name];
            if (!a) return;
            const w = a.canvas.clientWidth, h = a.canvas.clientHeight;
            const dpr = window.devicePixelRatio || 1;
            a.canvas.width = w * dpr; a.canvas.height = h * dpr;
            a.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            a.ctx.clearRect(0, 0, w, h);
            a.ctx.strokeStyle = '#7af';
            a.ctx.lineWidth = 1.0;
            a.ctx.beginPath();
            const n = a.buf.length;
            for (let i = 0; i < n; i++) {
                const x = (i / (n - 1)) * w;
                const y = h - a.buf[i] * h;
                if (i === 0) a.ctx.moveTo(x, y); else a.ctx.lineTo(x, y);
            }
            a.ctx.stroke();
        }

        // Public hook for Python: pushLiveAxes({alpha, beta, volume, ...}, t)
        window.pushLiveAxes = function(values, t) {
            Object.keys(values).forEach(name => {
                if (!axisBuffers[name]) return;
                const v = Math.max(0, Math.min(1, values[name]));
                axisBuffers[name].buf.shift();
                axisBuffers[name].buf.push(v);
                drawAxis(name);
                const lbl = document.querySelector('[data-ax-val="' + name + '"]');
                if (lbl) lbl.textContent = v.toFixed(2);
            });
            if (typeof t === 'number' && window.__sessionGraph) {
                window.__sessionGraph.setLiveCursor(t);
            }
        };

        // Phase / time updates from Python:
        // pushLivePhase({phase: 'Edge', remaining_s: 1234, next_drop_s: 12})
        window.pushLivePhase = function(info) {
            if (info.phase) document.getElementById('live-phase').textContent = info.phase;
            if (typeof info.remaining_s === 'number') {
                const s = Math.max(0, Math.round(info.remaining_s));
                const mm = String(Math.floor(s / 60)).padStart(2, '0');
                const ss = String(s % 60).padStart(2, '0');
                document.getElementById('live-time').textContent = mm + ':' + ss;
            }
            if (typeof info.next_drop_s === 'number') {
                document.getElementById('live-nextdrop').textContent =
                    'next drop in ' + Math.round(info.next_drop_s) + 's';
            }
        };

        // Initial display sync
        ssDurVal.textContent = formatDuration(durationFromSlider(parseFloat(ssDur.value)));
        ssExpVal.textContent = ssExp.value;
        ssExpLabel.textContent = EXP_LABELS[parseInt(ssExp.value)];
    })();
</script>
</body>
</html>
"""

# Materialised once at import time so callers can keep using `SIDEBAR_HTML`.
SIDEBAR_HTML = build_sidebar_html()
