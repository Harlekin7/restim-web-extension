"""Main-window HTML for the Session mode.

Sits in the wide browser window (1100px) instead of the narrow sidebar so the
graph and the body-schema have proper room. Self-contained: ships its own CSS,
inlines uPlot, and embeds the session-graph + body-schema fragments.

`SESSION_MAIN_HTML` is exported as a module-level string so main.py can pass it
to `browser_window.load_html()` when the user enters Session mode.
"""
from __future__ import annotations

import json
from pathlib import Path

from .body_schema import build_body_schema_html
from .session_graph import build_session_graph_html


def _load_uplot_assets() -> tuple[str, str]:
    base = Path(__file__).parent / "static" / "uplot"
    try:
        js = (base / "uplot.iife.min.js").read_text(encoding="utf-8")
        css = (base / "uplot.min.css").read_text(encoding="utf-8")
    except FileNotFoundError:
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
    return json.dumps({
        "style": "sanfter_aufbau",
        "duration_s": 45 * 60,
        "target": "climax",
        "character": "lebendig",
        "experience": 2,
    })


def build_session_main_html() -> str:
    uplot_js, uplot_css = _load_uplot_assets()
    graph_fragment = build_session_graph_html(_default_session_profile_json())
    body_schema_fragment = build_body_schema_html(None)

    return _TEMPLATE.replace(
        "/*__UPLOT_CSS__*/", uplot_css
    ).replace(
        "/*__UPLOT_JS__*/", uplot_js
    ).replace(
        "<!--__SESSION_GRAPH__-->", graph_fragment
    ).replace(
        "<!--__BODY_SCHEMA__-->", body_schema_fragment
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Restim Session</title>
<!-- uPlot must be loaded BEFORE the graph fragment runs its inline script. -->
<script>
/*__UPLOT_JS__*/
</script>
<style>
/*__UPLOT_CSS__*/

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Segoe UI', Tahoma, sans-serif;
    font-size: 14px;
    background: #1a1a1a;
    color: #ddd;
    padding: 16px;
    overflow-y: auto;
    user-select: none;
}
h1 { font-size: 18px; color: #5af; font-weight: 500; margin-bottom: 14px; }

.layout {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: 16px;
    align-items: start;
}

.col-left  { display: flex; flex-direction: column; gap: 12px; }
.col-right { display: flex; flex-direction: column; gap: 12px; }

.group {
    background: #232323;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    padding: 12px;
}
.group-title {
    font-size: 12px;
    color: #5af;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 10px;
}
.param-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.param-label { flex: 0 0 95px; color: #aaa; font-size: 12px; }
.param-range { flex: 1 1 auto; }
.param-input {
    width: 80px; background: #1c1c1c; color: #ddd; border: 1px solid #3a3a3a;
    border-radius: 3px; padding: 4px 6px; font-size: 12px;
}
.param-select {
    flex: 1 1 auto; background: #1c1c1c; color: #ddd; border: 1px solid #3a3a3a;
    border-radius: 3px; padding: 5px 8px; font-size: 13px;
}
.param-val { flex: 0 0 60px; text-align: right; font-size: 12px; color: #888;
             font-family: Consolas, monospace; }

.bipolar-row {
    display: grid;
    grid-template-columns: 70px 1fr 70px;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 12px;
}
.bipolar-row .pole-l { color: #aaa; text-align: right; }
.bipolar-row .pole-r { color: #aaa; }

.radio-row { display: flex; gap: 6px; flex-wrap: wrap; }
.radio-pill {
    flex: 1 1 0; min-width: 70px; text-align: center;
    background: #1c1c1c; border: 1px solid #3a3a3a; border-radius: 16px;
    padding: 6px 12px; font-size: 12px; cursor: pointer; color: #aaa;
}
.radio-pill.active {
    background: #2c5577; color: #fff; border-color: #5af;
}

.exp-display { font-size: 11px; color: #5af; text-align: center; padding-top: 4px; }

.collapse-header { display: flex; align-items: center; gap: 6px; cursor: pointer; }
.collapse-arrow { font-size: 10px; color: #888; transition: transform 0.15s; }
.collapse-open .collapse-arrow { transform: rotate(90deg); }
.collapse-body { display: none; margin-top: 10px; }
.collapse-open .collapse-body { display: block; }

.start-btn {
    width: 100%; padding: 14px; border: none; border-radius: 6px;
    background: #2a8045; color: #fff; font-size: 16px; font-weight: 600;
    cursor: pointer; margin-top: 4px;
}
.start-btn:hover { background: #339a52; }

/* ── LIVE-VIEW (sticky top bar shown only while a session is running) ── */
.live-view {
    display: none;
    position: sticky;
    top: -1px;                     /* hide the 1px border into the viewport edge */
    z-index: 100;
    margin: -16px -16px 16px -16px; /* extend beyond body padding to the edges */
    padding: 12px 16px;
    background: linear-gradient(180deg, #1c2630 0%, #1a2128 100%);
    border-bottom: 1px solid #2c5577;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
.live-view.active { display: block; }
.live-bar {
    display: grid;
    grid-template-columns: auto auto auto 1fr auto;
    align-items: center;
    gap: 18px;
}
.live-bar .live-phase { font-size: 22px; font-weight: 600; color: #5af; min-width: 90px; }
.live-bar .live-time { font-size: 18px; font-family: Consolas, monospace; color: #fff; }
.live-bar .live-nextdrop { font-size: 12px; color: #aaa; }
.live-bar .live-axes-row {
    display: grid;
    grid-template-columns: repeat(7, minmax(60px, 1fr));
    gap: 6px;
    justify-self: stretch;
}
.live-bar .live-axis {
    background: rgba(0,0,0,0.25);
    border: 1px solid #2a3a4a;
    border-radius: 3px;
    padding: 3px 4px;
    text-align: center;
    min-width: 0;
}
.live-bar .live-axis .ax-name { font-size: 10px; color: #5af; }
.live-bar .live-axis canvas { width: 100%; height: 22px; display: block; margin: 2px 0 1px; }
.live-bar .live-axis .ax-val { font-size: 11px; color: #ddd; font-family: Consolas, monospace; }

.live-bar .override-grid {
    display: flex;
    gap: 6px;
}
.override-btn {
    padding: 6px 10px;
    border: 1px solid #444;
    border-radius: 3px;
    background: #2a2a2a;
    color: #ddd;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
}
.override-btn:hover { background: #353535; }
.override-btn.danger { background: #6a2a2a; border-color: #a55; color: #fff; }
.override-btn.danger:hover { background: #883535; }

/* Make the start button reflect a running session */
.start-btn.running { background: #444; color: #888; cursor: not-allowed; }
.start-btn.running:hover { background: #444; }
</style>
</head>
<body>

<!-- ════════ LIVE-VIEW (sticky top bar — visible only while a session is running) ═══ -->
<div id="live-view" class="live-view">
  <div class="live-bar">
    <div class="live-phase" id="live-phase">Init</div>
    <div class="live-time" id="live-time">00:00</div>
    <div class="live-nextdrop" id="live-nextdrop">next drop –</div>
    <div class="live-axes-row" id="live-axes">
      <div class="live-axis"><div class="ax-name">α</div><canvas data-ax="alpha"></canvas><div class="ax-val" data-ax-val="alpha">–</div></div>
      <div class="live-axis"><div class="ax-name">β</div><canvas data-ax="beta"></canvas><div class="ax-val" data-ax-val="beta">–</div></div>
      <div class="live-axis"><div class="ax-name">V</div><canvas data-ax="volume"></canvas><div class="ax-val" data-ax-val="volume">–</div></div>
      <div class="live-axis"><div class="ax-name">C</div><canvas data-ax="carrier"></canvas><div class="ax-val" data-ax-val="carrier">–</div></div>
      <div class="live-axis"><div class="ax-name">PF</div><canvas data-ax="pulse_frequency"></canvas><div class="ax-val" data-ax-val="pulse_frequency">–</div></div>
      <div class="live-axis"><div class="ax-name">PW</div><canvas data-ax="pulse_width"></canvas><div class="ax-val" data-ax-val="pulse_width">–</div></div>
      <div class="live-axis"><div class="ax-name">PR</div><canvas data-ax="pulse_rise_time"></canvas><div class="ax-val" data-ax-val="pulse_rise_time">–</div></div>
    </div>
    <div class="override-grid">
      <button class="override-btn" data-act="pause">Pause</button>
      <button class="override-btn" data-act="skip">Skip</button>
      <button class="override-btn" data-act="edge">Edge</button>
      <button class="override-btn" data-act="boost">Boost</button>
      <button class="override-btn danger" data-act="stop">STOP</button>
    </div>
  </div>
</div>

<h1>Session-Modus — generative Stimulation</h1>

<!-- ════════ CONFIG-VIEW ════════════════════════════════════════════ -->
<div id="cfg-view" class="layout">

  <div class="col-left">

    <!-- 1. Session basics -->
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

    <button class="start-btn" id="ss-start">▶ START SESSION</button>

  </div>  <!-- /col-left -->

  <div class="col-right">
    <div class="group">
      <div class="group-title">Verlauf</div>
      <!--__SESSION_GRAPH__-->
    </div>
  </div>

</div>  <!-- /cfg-view -->

<script>
(function() {
    const EXP_LABELS = {1:'Beginner',2:'Eingewöhnt',3:'Erfahren',4:'Routiniert',5:'Profi'};

    function durationFromSlider(v) {
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
        ssDurVal.textContent = formatDuration(durationFromSlider(parseFloat(ssDur.value)));
        notifySessionProfile();
    });

    const ssExp = document.getElementById('ss-exp');
    const ssExpVal = document.getElementById('ss-exp-val');
    const ssExpLabel = document.getElementById('ss-exp-label');
    ssExp.addEventListener('input', () => {
        const lvl = parseInt(ssExp.value);
        ssExpVal.textContent = String(lvl);
        ssExpLabel.textContent = EXP_LABELS[lvl];
        notifySessionProfile();
    });

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

    document.getElementById('ss-style').addEventListener('change', (e) => {
        if (window.__sessionGraph) window.__sessionGraph.setStyle(e.target.value);
        notifySessionProfile();
    });
    document.getElementById('ss-target').addEventListener('change', (e) => {
        if (window.__sessionGraph) window.__sessionGraph.setTarget(e.target.value);
        notifySessionProfile();
    });

    ['ss-sense-sd','ss-sense-gs','ss-sense-sh','ss-sense-sm'].forEach(id => {
        document.getElementById(id).addEventListener('input', notifySessionProfile);
    });

    document.getElementById('ss-device').addEventListener('change', (e) => {
        if (window.__bodySchema) window.__bodySchema.setHardwarePreset(e.target.value);
        notifySessionProfile();
    });

    window.__bodySchemaOnChange = function(list) { notifySessionProfile(); };

    const advHdr = document.getElementById('adv-toggle');
    advHdr.addEventListener('click', () => advHdr.parentElement.classList.toggle('collapse-open'));
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

    function getSessionProfile() {
        const electrodes = window.__bodySchema ? window.__bodySchema.get() : [];
        const sizeMap = { small: 4.0, medium: 9.0, large: 16.0 };
        const electrodesPy = electrodes.map(e => ({
            position: e.position,
            is_common: !!e.is_common,
            size_cm2: sizeMap[e.size] || 9.0,
        }));
        const seedStr = document.getElementById('ss-seed').value.trim();
        const seed = seedStr ? parseInt(seedStr) : null;
        const envelope = (window.__sessionGraph ? window.__sessionGraph.getEnvelope() : null);

        return {
            style:       document.getElementById('ss-style').value,
            duration_s:  durationFromSlider(parseFloat(ssDur.value)),
            target:      document.getElementById('ss-target').value,
            sensation: {
                sharp_to_deep:      parseFloat(document.getElementById('ss-sense-sd').value),
                granular_to_smooth: parseFloat(document.getElementById('ss-sense-gs').value),
                soft_to_hard:       parseFloat(document.getElementById('ss-sense-sh').value),
                static_to_moving:   parseFloat(document.getElementById('ss-sense-sm').value),
            },
            character:  currentChar,
            experience: parseInt(ssExp.value),
            hardware: {
                device_class: document.getElementById('ss-device').value,
                electrodes:   electrodesPy,
            },
            safety: {
                max_volume:         parseFloat(document.getElementById('ss-vol-cap').value),
                max_carrier_hz:     parseFloat(document.getElementById('ss-carrier-cap').value),
                max_pulse_width_us: parseFloat(document.getElementById('ss-pw-cap').value),
                min_volume_ramp_s:  5.0,
            },
            advanced: {
                pattern_repeat_lockout_s: parseFloat(document.getElementById('ss-pat-lockout').value),
                crossfade_s: parseFloat(document.getElementById('ss-crossfade').value),
                pattern_pool: null,
                subwave_count: null,
            },
            seed: seed,
            envelope: envelope,
        };
    }

    let emitTimer = null;
    function notifySessionProfile() {
        clearTimeout(emitTimer);
        emitTimer = setTimeout(() => {
            if (window.pywebview && window.pywebview.api &&
                typeof window.pywebview.api.set_session_profile === 'function') {
                try { window.pywebview.api.set_session_profile(getSessionProfile()); } catch (e) {}
            }
        }, 100);
    }

    // ── START / Live-view ──────────────────────────────────────
    // Live-view is now a sticky top bar that appears IN ADDITION to the config,
    // not in place of it. The config stays scrollable underneath.
    const liveView = document.getElementById('live-view');
    const startBtn = document.getElementById('ss-start');
    const startLabel = startBtn.textContent;

    function setRunning(running) {
        if (running) {
            liveView.classList.add('active');
            startBtn.classList.add('running');
            startBtn.textContent = 'Session läuft …';
            startBtn.disabled = true;
        } else {
            liveView.classList.remove('active');
            startBtn.classList.remove('running');
            startBtn.textContent = startLabel;
            startBtn.disabled = false;
        }
    }

    startBtn.addEventListener('click', () => {
        if (startBtn.disabled) return;
        if (window.pywebview && window.pywebview.api &&
            typeof window.pywebview.api.start_session === 'function') {
            try { window.pywebview.api.start_session(getSessionProfile()); } catch (e) {}
        }
        setRunning(true);
    });

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
                setRunning(false);
            }
        });
    });

    // ── Live-axis sparklines ─────────────────────────────────
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

SESSION_MAIN_HTML = build_session_main_html()
