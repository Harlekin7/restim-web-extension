"""Session-graph component (uPlot-based).

Renders the macro envelope graph used to configure a Session-mode session:

- 4 lines: Master-Intensität (editable), Härte / Schärfe / Bewegung
  (auto-derived from Master).
- Half-transparent variability bands per line, scaled by the active
  character preset.
- SubWaves visualised on the Master-line (mock — visual only, real
  SubWave shape comes later from the macro planner).
- Phase sectors as background bands (Init / Build / Plateau / Edge / Climax).
- Drop-markers (◯) — drag to move, click to delete, click on empty
  area = add new drop.
- Hover tooltip showing live values of all 4 lines.
- Quick-presets above the chart.

Public API:
    build_session_graph_html(profile_json: str) -> str

`profile_json` is the serialised SessionProfile (see session.profile).
The component emits change-events back to Python through:
    pywebview.api.update_session_envelope(envelope_json_str)

`envelope_json_str` payload shape::
    {
      "master_points": [{"t": <0..1>, "v": <0..1>}, ...],
      "drops":         [{"t": <0..1>, "depth": <0..1>}, ...],
    }
The Python bridge for this method is added separately.
"""
from __future__ import annotations


def build_session_graph_html(profile_json: str) -> str:
    """Return an HTML fragment that renders the session graph.

    `profile_json` must be a JSON-serialised SessionProfile. The JS reads
    the relevant fields (style, character, duration_s, target) to set
    initial defaults; everything else is ignored.
    """
    # The JS embeds profile_json verbatim — caller is responsible for
    # passing a valid JSON string. We do not double-encode.
    return _GRAPH_TEMPLATE.replace("__PROFILE_JSON__", profile_json or "{}")


_GRAPH_TEMPLATE = r"""
<!-- uPlot is loaded by the host page (sidebar_html.py) before this fragment. -->

<style>
.sg-wrap {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 10px;
    margin-top: 8px;
    margin-bottom: 8px;
}
.sg-presets {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}
.sg-preset-btn {
    background: #2d2d2d;
    border: 1px solid #3e3e3e;
    color: #aaa;
    font-size: 10px;
    padding: 4px 8px;
    border-radius: 3px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}
.sg-preset-btn:hover { background: #3a3a3a; color: #ccc; }
.sg-preset-btn.danger { color: #c66; }
.sg-preset-btn.danger:hover { background: #3a2222; }

.sg-canvas-wrap {
    position: relative;
    width: 100%;
    height: 230px;
    background: #141414;
    border-radius: 4px;
    overflow: hidden;
}
.sg-canvas-wrap .uplot {
    width: 100% !important;
    background: transparent;
}
.sg-canvas-wrap .uplot .u-axis {
    color: #777;
}
.sg-overlay {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
}
.sg-tooltip {
    position: absolute;
    background: rgba(20,20,20,0.94);
    border: 1px solid #444;
    color: #ddd;
    font-family: Consolas, monospace;
    font-size: 10px;
    padding: 4px 6px;
    border-radius: 3px;
    pointer-events: none;
    display: none;
    z-index: 10;
    white-space: nowrap;
}
.sg-tooltip .tt-row { display: flex; gap: 6px; }
.sg-tooltip .tt-key  { color: #888; }
.sg-legend {
    display: flex;
    gap: 12px;
    margin-top: 6px;
    font-size: 10px;
    color: #aaa;
}
.sg-legend .lg { display: flex; align-items: center; gap: 4px; }
.sg-legend .sw {
    display: inline-block;
    width: 14px;
    height: 3px;
    border-radius: 2px;
}
.sg-hint {
    color: #666;
    font-size: 10px;
    margin-top: 6px;
    text-align: center;
}
</style>

<div class="sg-wrap">
    <div class="sg-presets">
        <button class="sg-preset-btn" data-preset="sanfter_build">Sanfter Build</button>
        <button class="sg-preset-btn" data-preset="steiler_crescendo">Steiler Crescendo</button>
        <button class="sg-preset-btn" data-preset="1_edge">1 Edge</button>
        <button class="sg-preset-btn" data-preset="3_edges">3 Edges</button>
        <button class="sg-preset-btn" data-preset="tease_loop">Tease-Loop</button>
        <button class="sg-preset-btn danger" data-preset="reset">Reset</button>
    </div>
    <div class="sg-canvas-wrap" id="sg-canvas-wrap">
        <div id="sg-uplot"></div>
        <canvas class="sg-overlay" id="sg-overlay"></canvas>
        <div class="sg-tooltip" id="sg-tooltip"></div>
    </div>
    <div class="sg-legend">
        <span class="lg"><span class="sw" style="background:#7af"></span>Master</span>
        <span class="lg"><span class="sw" style="background:#fb4"></span>Härte</span>
        <span class="lg"><span class="sw" style="background:#5a8"></span>Schärfe</span>
        <span class="lg"><span class="sw" style="background:#c6c"></span>Bewegung</span>
        <span class="lg" style="margin-left:auto">◯ Drop</span>
    </div>
    <div class="sg-hint">Drag points · Click line to add · Click point to delete · Click between points to add a Drop</div>
</div>

<script>
(() => {
    'use strict';

    // ── Inputs ────────────────────────────────────────────────────
    let profile = {};
    try { profile = JSON.parse(`__PROFILE_JSON__`); } catch (e) { profile = {}; }

    const N_SAMPLES = 120;          // resolution along time axis
    const COLORS = {
        master:    '#7af',
        haerte:    '#fb4',
        schaerfe:  '#5a8',
        bewegung:  '#c6c',
    };
    const CHAR_BANDS = {            // ±band-width per character
        sanft: 0.05, lebendig: 0.10, spielerisch: 0.15, wild: 0.20,
    };
    const PHASE_DEFS = [
        { name: 'Init',    color: 'rgba(120,160,255,0.05)', ratio: 0.10 },
        { name: 'Build',   color: 'rgba(120,200,255,0.07)', ratio: 0.30 },
        { name: 'Plateau', color: 'rgba(255,200,120,0.07)', ratio: 0.30 },
        { name: 'Edge',    color: 'rgba(255,120,120,0.08)', ratio: 0.20 },
        { name: 'Climax',  color: 'rgba(220,80,200,0.10)',  ratio: 0.10 },
    ];

    // ── State ─────────────────────────────────────────────────────
    // Master stützpunkte: monotone t in [0,1], v in [0,1].
    let masterPts = stylePreset(profile.style || 'sanfter_aufbau');
    let drops    = defaultDrops(profile.style || 'sanfter_aufbau', profile.target);
    let character = profile.character || 'lebendig';
    let bandWidth = CHAR_BANDS[character] ?? 0.10;

    // Drag state for stützpunkte
    let dragIdx = -1;          // index in masterPts being dragged
    let dragKind = null;       // 'pt' | 'drop'
    let dragDropIdx = -1;
    let suppressClick = false; // set true after a drag so the click doesn't delete

    // ── Helpers ───────────────────────────────────────────────────
    function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

    function stylePreset(style) {
        // Returns [{t,v}] anchor points 0..1.
        switch (style) {
            case 'crescendo':
                return [{t:0,v:0.25},{t:0.4,v:0.55},{t:0.75,v:0.80},{t:1.0,v:0.95}];
            case 'beat_drop':
                return [{t:0,v:0.30},{t:0.30,v:0.65},{t:0.65,v:0.65},{t:1.0,v:0.90}];
            case 'edging':
                return [{t:0,v:0.30},{t:0.25,v:0.75},{t:0.50,v:0.50},
                        {t:0.75,v:0.80},{t:1.0,v:0.65}];
            case 'ruin':
                return [{t:0,v:0.30},{t:0.5,v:0.70},{t:0.85,v:0.95},{t:1.0,v:0.10}];
            case 'endlos_tease':
                return [{t:0,v:0.30},{t:0.33,v:0.55},{t:0.66,v:0.40},{t:1.0,v:0.55}];
            case 'sanfter_aufbau':
            default:
                return [{t:0,v:0.30},{t:0.5,v:0.55},{t:1.0,v:0.85}];
        }
    }

    function defaultDrops(style, target) {
        if (style === 'edging' || target === 'edge_hold') {
            return [{t:0.30, depth:0.30},{t:0.55, depth:0.30},{t:0.80, depth:0.35}];
        }
        if (style === 'ruin' || target === 'ruined') return [{t:0.93, depth:0.85}];
        if (style === 'endlos_tease') return [{t:0.4,depth:0.25},{t:0.75,depth:0.25}];
        return [];
    }

    // Auto-derive Härte/Schärfe/Bewegung from Master at given v.
    function derive(v) {
        return {
            haerte:   clamp(0.30 + 0.70 * v, 0, 1),   // r≈0.85
            schaerfe: clamp(0.40 + 0.60 * v, 0, 1),   // r≈0.90
            bewegung: clamp(0.50 + 0.40 * v, 0, 1),
        };
    }

    // Linear interp between stützpunkte at given t (0..1).
    function masterAt(t) {
        if (masterPts.length === 0) return 0;
        if (t <= masterPts[0].t) return masterPts[0].v;
        if (t >= masterPts[masterPts.length-1].t) return masterPts[masterPts.length-1].v;
        for (let i = 1; i < masterPts.length; i++) {
            const a = masterPts[i-1], b = masterPts[i];
            if (t >= a.t && t <= b.t) {
                const f = (t - a.t) / Math.max(1e-9, (b.t - a.t));
                return a.v + (b.v - a.v) * f;
            }
        }
        return masterPts[masterPts.length-1].v;
    }

    // SubWave overlay: small wavy oscillation that grows in amplitude
    // and shrinks in period over the session — a visual mock per the
    // nested-envelope description. Real subwave shape comes from the
    // macro planner later.
    function subwaveAt(t, masterV) {
        const amp = 0.04 + 0.06 * t;          // grows from 0.04 → 0.10
        const periods = 6 + 8 * t;            // increasing freq
        const headroom = Math.max(0, 1 - masterV); // less wiggle near cap
        return amp * headroom * Math.sin(2 * Math.PI * periods * t);
    }

    // Build the 5 series arrays (xs, master, haerte, schaerfe, bewegung).
    function buildSeries() {
        const xs       = new Array(N_SAMPLES);
        const master   = new Array(N_SAMPLES);
        const haerte   = new Array(N_SAMPLES);
        const schaerfe = new Array(N_SAMPLES);
        const bewegung = new Array(N_SAMPLES);
        for (let i = 0; i < N_SAMPLES; i++) {
            const t = i / (N_SAMPLES - 1);
            const m = masterAt(t);
            const mv = clamp(m + subwaveAt(t, m), 0, 1);
            const d = derive(mv);
            xs[i] = t;
            master[i]   = mv;
            haerte[i]   = d.haerte;
            schaerfe[i] = d.schaerfe;
            bewegung[i] = d.bewegung;
        }
        return [xs, master, haerte, schaerfe, bewegung];
    }

    // ── uPlot setup ───────────────────────────────────────────────
    const wrap = document.getElementById('sg-canvas-wrap');
    const target = document.getElementById('sg-uplot');
    const overlay = document.getElementById('sg-overlay');
    const tooltip = document.getElementById('sg-tooltip');

    // Wait for uPlot to be available; the sidebar loads it before this script.
    if (typeof uPlot === 'undefined') {
        wrap.innerHTML = '<div style="color:#c66;padding:20px;font-size:11px;text-align:center;">uPlot not loaded — graph unavailable.</div>';
        return;
    }

    // Phase-sector hook (drawn under series).
    const phaseHook = (u) => {
        const ctx = u.ctx;
        const left = u.bbox.left, top = u.bbox.top;
        const width = u.bbox.width, height = u.bbox.height;
        ctx.save();
        let acc = 0;
        for (const ph of PHASE_DEFS) {
            const x0 = left + width * acc;
            const w  = width * ph.ratio;
            ctx.fillStyle = ph.color;
            ctx.fillRect(x0, top, w, height);
            // label
            ctx.fillStyle = 'rgba(180,180,180,0.45)';
            ctx.font = '10px Segoe UI';
            ctx.textBaseline = 'top';
            ctx.fillText(ph.name, x0 + 4, top + 4);
            acc += ph.ratio;
        }
        ctx.restore();
    };

    // Variability-band hook: draws ±bandWidth around each line.
    const bandHook = (u) => {
        const ctx = u.ctx;
        ctx.save();
        const seriesIdx = [1, 2, 3, 4];
        const colors = ['rgba(120,170,255,0.10)','rgba(255,180,70,0.07)',
                        'rgba(90,170,140,0.07)','rgba(200,110,200,0.07)'];
        for (let s = 0; s < seriesIdx.length; s++) {
            const sIdx = seriesIdx[s];
            const ys = u.data[sIdx];
            ctx.beginPath();
            for (let i = 0; i < ys.length; i++) {
                const x = u.valToPos(u.data[0][i], 'x', true);
                const yTop = u.valToPos(clamp(ys[i] + bandWidth, 0, 1), 'y', true);
                if (i === 0) ctx.moveTo(x, yTop); else ctx.lineTo(x, yTop);
            }
            for (let i = ys.length - 1; i >= 0; i--) {
                const x = u.valToPos(u.data[0][i], 'x', true);
                const yBot = u.valToPos(clamp(ys[i] - bandWidth, 0, 1), 'y', true);
                ctx.lineTo(x, yBot);
            }
            ctx.closePath();
            ctx.fillStyle = colors[s];
            ctx.fill();
        }
        ctx.restore();
    };

    // Draw stützpunkte + drop-markers on top using the overlay canvas.
    function drawOverlay(u) {
        const dpr = window.devicePixelRatio || 1;
        overlay.width  = wrap.clientWidth  * dpr;
        overlay.height = wrap.clientHeight * dpr;
        overlay.style.width  = wrap.clientWidth  + 'px';
        overlay.style.height = wrap.clientHeight + 'px';
        const ctx = overlay.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, wrap.clientWidth, wrap.clientHeight);

        // Stützpunkte
        for (const p of masterPts) {
            const x = u.valToPos(p.t, 'x');
            const y = u.valToPos(p.v, 'y');
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fillStyle = COLORS.master;
            ctx.fill();
            ctx.strokeStyle = '#1a1a1a';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }
        // Drop markers
        for (const d of drops) {
            const x = u.valToPos(d.t, 'x');
            const y = u.valToPos(masterAt(d.t) - d.depth * 0.5, 'y');
            ctx.beginPath();
            ctx.arc(x, y, 7, 0, Math.PI * 2);
            ctx.strokeStyle = '#e66';
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.fillStyle = 'rgba(230,100,100,0.18)';
            ctx.fill();
        }
    }

    function makePlot() {
        const data = buildSeries();
        const opts = {
            width: wrap.clientWidth,
            height: wrap.clientHeight,
            padding: [10, 10, 22, 30],
            cursor: { show: true, x: true, y: false, drag: { x: false, y: false } },
            legend: { show: false },
            scales: {
                x: { time: false, range: [0, 1] },
                y: { range: [0, 1] },
            },
            axes: [
                {
                    stroke: '#888',
                    grid: { stroke: 'rgba(255,255,255,0.04)' },
                    values: (u, vals) => vals.map(v => Math.round(v*100) + '%'),
                },
                {
                    stroke: '#888',
                    grid: { stroke: 'rgba(255,255,255,0.04)' },
                    values: (u, vals) => vals.map(v => Math.round(v*100) + ''),
                },
            ],
            series: [
                {},
                { label: 'Master',   stroke: COLORS.master,   width: 2.6 },
                { label: 'Härte',    stroke: COLORS.haerte,   width: 1.2 },
                { label: 'Schärfe',  stroke: COLORS.schaerfe, width: 1.2 },
                { label: 'Bewegung', stroke: COLORS.bewegung, width: 1.2 },
            ],
            hooks: {
                drawClear: [phaseHook],
                draw:      [bandHook, (u) => drawOverlay(u)],
                setSize:   [(u) => drawOverlay(u)],
                setCursor: [(u) => onCursor(u)],
            },
        };
        return new uPlot(opts, data, target);
    }

    let plot = makePlot();

    function refresh() {
        plot.setData(buildSeries());
        // setData triggers redraw; overlay redrawn via draw hook.
    }

    // ── Cursor / tooltip ──────────────────────────────────────────
    function onCursor(u) {
        const idx = u.cursor.idx;
        if (idx == null || idx < 0) {
            tooltip.style.display = 'none';
            return;
        }
        const xs = u.data[0];
        const t = xs[idx];
        const m = u.data[1][idx];
        const h = u.data[2][idx];
        const s = u.data[3][idx];
        const b = u.data[4][idx];
        tooltip.innerHTML =
            '<div class="tt-row"><span class="tt-key">t</span><span>' +
                Math.round(t * 100) + '%</span></div>' +
            '<div class="tt-row"><span class="tt-key" style="color:'+COLORS.master+'">M</span><span>' +
                Math.round(m * 100) + '%</span></div>' +
            '<div class="tt-row"><span class="tt-key" style="color:'+COLORS.haerte+'">H</span><span>' +
                Math.round(h * 100) + '%</span></div>' +
            '<div class="tt-row"><span class="tt-key" style="color:'+COLORS.schaerfe+'">S</span><span>' +
                Math.round(s * 100) + '%</span></div>' +
            '<div class="tt-row"><span class="tt-key" style="color:'+COLORS.bewegung+'">B</span><span>' +
                Math.round(b * 100) + '%</span></div>';
        tooltip.style.display = 'block';
        const px = u.cursor.left + 12;
        const py = u.cursor.top  + 12;
        tooltip.style.left = px + 'px';
        tooltip.style.top  = py + 'px';
    }

    // ── Mouse interaction ─────────────────────────────────────────
    function clientToData(evt) {
        const rect = wrap.getBoundingClientRect();
        const x = evt.clientX - rect.left;
        const y = evt.clientY - rect.top;
        const t = clamp(plot.posToVal(x, 'x'), 0, 1);
        const v = clamp(plot.posToVal(y, 'y'), 0, 1);
        return { x, y, t, v };
    }

    function findHitPoint(t, v) {
        const tol = 0.025; // ~2.5% in t space ≈ 12px on a 480px-wide chart
        let best = -1, bestD = Infinity;
        for (let i = 0; i < masterPts.length; i++) {
            const p = masterPts[i];
            const dt = (p.t - t);
            const dv = (p.v - v);
            const d = dt*dt + dv*dv;
            if (d < bestD && Math.abs(dt) < tol && Math.abs(dv) < 0.05) {
                bestD = d; best = i;
            }
        }
        return best;
    }

    function findHitDrop(t, v) {
        const tol = 0.030;
        for (let i = 0; i < drops.length; i++) {
            const d = drops[i];
            const m = masterAt(d.t);
            if (Math.abs(d.t - t) < tol && Math.abs((m - d.depth*0.5) - v) < 0.07) {
                return i;
            }
        }
        return -1;
    }

    wrap.addEventListener('mousedown', (evt) => {
        if (evt.button !== 0) return;
        const { t, v } = clientToData(evt);
        const ptIdx = findHitPoint(t, v);
        if (ptIdx >= 0) {
            dragKind = 'pt';
            dragIdx = ptIdx;
            suppressClick = false;
            evt.preventDefault();
            return;
        }
        const dropIdx = findHitDrop(t, v);
        if (dropIdx >= 0) {
            dragKind = 'drop';
            dragDropIdx = dropIdx;
            suppressClick = false;
            evt.preventDefault();
            return;
        }
    });

    window.addEventListener('mousemove', (evt) => {
        if (!dragKind) return;
        const { t, v } = clientToData(evt);
        suppressClick = true;
        if (dragKind === 'pt') {
            const p = masterPts[dragIdx];
            // Endpoints stay at t=0 / t=1
            if (dragIdx === 0) p.t = 0;
            else if (dragIdx === masterPts.length - 1) p.t = 1;
            else {
                const left  = masterPts[dragIdx-1].t + 1e-3;
                const right = masterPts[dragIdx+1].t - 1e-3;
                p.t = clamp(t, left, right);
            }
            p.v = clamp(v, 0, 1);
            refresh();
            emit();
        } else if (dragKind === 'drop') {
            const d = drops[dragDropIdx];
            d.t = clamp(t, 0.02, 0.98);
            refresh();
            emit();
        }
    });

    window.addEventListener('mouseup', () => {
        dragKind = null;
        dragIdx = -1;
        dragDropIdx = -1;
    });

    // Click handling: add new point/drop, or delete existing.
    wrap.addEventListener('click', (evt) => {
        if (suppressClick) { suppressClick = false; return; }
        const { t, v } = clientToData(evt);
        // Click on a point → delete (unless it's an endpoint).
        const ptIdx = findHitPoint(t, v);
        if (ptIdx >= 0) {
            if (ptIdx !== 0 && ptIdx !== masterPts.length - 1) {
                masterPts.splice(ptIdx, 1);
                refresh(); emit();
            }
            return;
        }
        // Click on a drop → delete.
        const dropIdx = findHitDrop(t, v);
        if (dropIdx >= 0) {
            drops.splice(dropIdx, 1);
            refresh(); emit();
            return;
        }
        // Otherwise: shift-click or default = add Master point near line.
        const lineV = masterAt(t);
        const onLine = Math.abs(v - lineV) < 0.07;
        if (evt.shiftKey || !onLine) {
            // Empty area (or shift) → add Drop here.
            drops.push({ t: clamp(t, 0.02, 0.98), depth: 0.30 });
            drops.sort((a,b) => a.t - b.t);
        } else {
            // On the line → add stützpunkt.
            masterPts.push({ t, v });
            masterPts.sort((a,b) => a.t - b.t);
        }
        refresh(); emit();
    });

    // ── Quick-presets ─────────────────────────────────────────────
    document.querySelectorAll('.sg-preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = btn.getAttribute('data-preset');
            switch (p) {
                case 'sanfter_build':
                    masterPts = [{t:0,v:0.30},{t:0.5,v:0.55},{t:1,v:0.85}];
                    drops = [];
                    break;
                case 'steiler_crescendo':
                    masterPts = [{t:0,v:0.20},{t:0.6,v:0.55},{t:0.9,v:0.85},{t:1,v:0.97}];
                    drops = [];
                    break;
                case '1_edge':
                    masterPts = [{t:0,v:0.30},{t:0.45,v:0.78},{t:0.55,v:0.45},{t:1,v:0.90}];
                    drops = [{t:0.50, depth:0.40}];
                    break;
                case '3_edges':
                    masterPts = [{t:0,v:0.25},{t:0.25,v:0.75},{t:0.40,v:0.55},
                                 {t:0.60,v:0.80},{t:0.75,v:0.55},{t:0.90,v:0.85},{t:1,v:0.95}];
                    drops = [{t:0.30,depth:0.30},{t:0.65,depth:0.30},{t:0.80,depth:0.35}];
                    break;
                case 'tease_loop':
                    masterPts = [{t:0,v:0.30},{t:0.33,v:0.55},{t:0.66,v:0.40},{t:1,v:0.55}];
                    drops = [{t:0.40,depth:0.25},{t:0.75,depth:0.25}];
                    break;
                case 'reset':
                    masterPts = stylePreset(profile.style || 'sanfter_aufbau');
                    drops = defaultDrops(profile.style || 'sanfter_aufbau', profile.target);
                    break;
            }
            refresh();
            emit();
        });
    });

    // ── Resize handling ───────────────────────────────────────────
    let resizeTimer = null;
    new ResizeObserver(() => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            plot.setSize({ width: wrap.clientWidth, height: wrap.clientHeight });
        }, 50);
    }).observe(wrap);

    // ── Outbound: notify backend ──────────────────────────────────
    let emitTimer = null;
    function emit() {
        clearTimeout(emitTimer);
        emitTimer = setTimeout(() => {
            const payload = JSON.stringify({
                master_points: masterPts.map(p => ({ t: p.t, v: p.v })),
                drops:         drops.map(d => ({ t: d.t, depth: d.depth })),
            });
            if (window.pywebview && window.pywebview.api &&
                typeof window.pywebview.api.update_session_envelope === 'function') {
                try { window.pywebview.api.update_session_envelope(payload); } catch (e) {}
            }
            // Also broadcast for any in-page listeners (e.g. live-cursor view).
            window.dispatchEvent(new CustomEvent('sg-envelope', { detail: payload }));
        }, 80);
    }

    // ── Public hooks for sidebar wiring ───────────────────────────
    window.__sessionGraph = {
        setCharacter: (c) => {
            character = c;
            bandWidth = CHAR_BANDS[c] ?? 0.10;
            refresh();
        },
        setStyle: (s) => {
            profile.style = s;
            masterPts = stylePreset(s);
            drops = defaultDrops(s, profile.target);
            refresh();
            emit();
        },
        setTarget: (t) => {
            profile.target = t;
            refresh();
        },
        setLiveCursor: (t) => {
            // t in [0,1] — paint a vertical cursor on the overlay.
            if (t == null) return;
            const x = plot.valToPos(clamp(t, 0, 1), 'x');
            const ctx = overlay.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            // Re-draw stützpunkte/drops (cheap), then cursor on top.
            drawOverlay(plot);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.2;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, wrap.clientHeight);
            ctx.stroke();
            ctx.setLineDash([]);
        },
        getEnvelope: () => ({
            master_points: masterPts.map(p => ({ t: p.t, v: p.v })),
            drops:         drops.map(d => ({ t: d.t, depth: d.depth })),
        }),
    };

    // Fire an initial emit so backend sees the default envelope.
    emit();
})();
</script>
"""
