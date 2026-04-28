SIDEBAR_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<style>
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
        font-size: 12px;
        font-weight: 600;
        padding: 6px 10px;
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
</style>
</head>
<body>

<!-- Site switcher -->
<div class="group">
    <div class="group-title">Website</div>
    <div class="site-switcher">
        <button class="site-btn" data-site="faptap">FapTap</button>
        <button class="site-btn" data-site="theedgy">TheEdgy</button>
    </div>
</div>

<!-- Server -->
<div class="group">
    <div class="group-title">Server</div>
    <div class="status-line">
        <span class="dot" id="server-dot"></span>
        <span class="value" id="server-status">Wird gestartet...</span>
    </div>
</div>

<!-- TheEdgy live settings (only visible on theedgy) -->
<div class="group" id="group-theedgy" style="display:none;">
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

<!-- Funscript -->
<div class="group">
    <div class="group-title">Funscript</div>
    <div class="status-line">
        <span class="label">Status:</span>
        <span class="value" id="script-status">Warte auf Verbindung...</span>
    </div>
    <div class="status-line">
        <span class="label">Aktionen:</span>
        <span class="value" id="script-actions">-</span>
    </div>
    <div class="status-line">
        <span class="label">Dauer:</span>
        <span class="value" id="script-duration">-</span>
    </div>
    <div id="script-preview">Script-Vorschau...</div>
</div>

<!-- ════════ ALLGEMEIN ════════ -->
<div class="group">
    <div class="group-title">Allgemein</div>

    <!-- Arc -->
    <div class="param-row">
        <span class="param-label">Arc Grad</span>
        <input type="range" class="param-range" id="s-arc" min="270" max="360" step="5" value="270">
        <span class="param-val" id="v-arc">270</span>
        <button class="toggle-btn" id="btn-invert" title="Arc invertieren">Inv</button>
    </div>

    <div class="section-sep"></div>

    <!-- Speed -->
    <div class="param-row">
        <span class="param-label">Speed Window</span>
        <input type="number" class="param-input" id="s-speed-win" min="1" max="30" step="0.5" value="5.0">
        <span class="param-val">s</span>
    </div>
    <div class="param-row">
        <span class="param-label">Min Radius</span>
        <input type="range" class="param-range" id="s-min-rad" min="0.05" max="0.5" step="0.05" value="0.1">
        <span class="param-val" id="v-min-rad">0.10</span>
    </div>
    <div class="param-row">
        <span class="param-label">Speed Thr.</span>
        <input type="range" class="param-range" id="s-speed-thr" min="0.1" max="1.0" step="0.05" value="0.5">
        <span class="param-val" id="v-speed-thr">0.50</span>
    </div>

    <div class="section-sep"></div>

    <!-- Volume -->
    <div class="param-row">
        <span class="param-label">Vol Min</span>
        <input type="number" class="param-input" id="s-vol-min" min="0" max="1" step="0.01" value="0.20">
    </div>
    <div class="param-row">
        <span class="param-label">Vol Max</span>
        <input type="number" class="param-input" id="s-vol-max" min="0" max="1" step="0.01" value="0.95">
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
        <button class="toggle-btn" id="btn-boost" title="Burst-Erkennung">Aus</button>
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
        <input type="range" class="param-range" id="s-pos-freq" min="0" max="1" step="0.05" value="0">
        <span class="param-val" id="v-pos-freq">0.00</span>
        <button class="toggle-btn" id="btn-pos-freq-inv" title="Position invertieren">Inv</button>
    </div>
</div>

<!-- ════════ PULSE SETTINGS ════════ -->
<div class="group">
    <div class="group-title">Pulse Settings</div>

    <!-- Carrier Freq: 0-1 in Restim (skaliert intern) -->
    <div class="param-row">
        <span class="param-label">CarFreq Min</span>
        <input type="range" class="param-range" id="s-car-min" min="0" max="0.8" step="0.05" value="0.4">
        <span class="param-val" id="v-car-min">0.40</span>
    </div>
    <div class="param-row">
        <span class="param-label">CarFreq Max</span>
        <input type="range" class="param-range" id="s-car-max" min="0.2" max="1.0" step="0.05" value="0.95">
        <span class="param-val" id="v-car-max">0.95</span>
    </div>

    <div class="section-sep"></div>

    <!-- Pulse Freq -->
    <div class="param-row">
        <span class="param-label">PulseF Min</span>
        <input type="range" class="param-range" id="s-pf-min" min="0" max="0.8" step="0.05" value="0.3">
        <span class="param-val" id="v-pf-min">0.30</span>
    </div>
    <div class="param-row">
        <span class="param-label">PulseF Max</span>
        <input type="range" class="param-range" id="s-pf-max" min="0.2" max="1.0" step="0.05" value="0.9">
        <span class="param-val" id="v-pf-max">0.90</span>
    </div>

    <div class="section-sep"></div>

    <!-- Pulse Width -->
    <div class="param-row">
        <span class="param-label">PulseW Min</span>
        <input type="range" class="param-range" id="s-pw-min" min="0" max="0.5" step="0.05" value="0.1">
        <span class="param-val" id="v-pw-min">0.10</span>
    </div>
    <div class="param-row">
        <span class="param-label">PulseW Max</span>
        <input type="range" class="param-range" id="s-pw-max" min="0.1" max="1.0" step="0.05" value="0.5">
        <span class="param-val" id="v-pw-max">0.50</span>
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

<!-- Log -->
<div class="group">
    <div class="group-title">Log</div>
    <div id="log"></div>
</div>

<script>
    // ── Toggle states ─────────────────────────────────────────
    var arcInverted = false;
    document.getElementById('btn-invert').addEventListener('click', function() {
        arcInverted = !arcInverted;
        this.className = 'toggle-btn' + (arcInverted ? ' active' : '');
        notifySettingsChanged();
    });

    var boostEnabled = false;
    document.getElementById('btn-boost').addEventListener('click', function() {
        boostEnabled = !boostEnabled;
        this.className = 'toggle-btn' + (boostEnabled ? ' active' : '');
        this.textContent = boostEnabled ? 'An' : 'Aus';
        document.getElementById('boost-settings').style.display = boostEnabled ? 'flex' : 'none';
        document.getElementById('boost-settings2').style.display = boostEnabled ? 'flex' : 'none';
        notifySettingsChanged();
    });

    var posFreqInverted = false;
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

    // ── Site switcher ─────────────────────────────────────────
    var currentSite = 'faptap';
    document.querySelectorAll('.site-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var site = btn.getAttribute('data-site');
            if (site === currentSite) return;
            if (window.pywebview && window.pywebview.api && window.pywebview.api.set_site) {
                window.pywebview.api.set_site(site).then(function(ok) {
                    if (ok) setActiveSite(site);
                });
            }
        });
    });

    function setActiveSite(site) {
        currentSite = site;
        document.querySelectorAll('.site-btn').forEach(function(b) {
            b.classList.toggle('active', b.getAttribute('data-site') === site);
        });
        document.getElementById('group-theedgy').style.display =
            (site === 'theedgy') ? 'block' : 'none';
    }

    // ── Collect all settings ──────────────────────────────────
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
                btn.textContent = boostEnabled ? 'An' : 'Aus';
                document.getElementById('boost-settings').style.display = boostEnabled ? 'flex' : 'none';
                document.getElementById('boost-settings2').style.display = boostEnabled ? 'flex' : 'none';
            } else if (m.type === 'pos-freq-toggle') {
                posFreqInverted = !!data[key];
                document.getElementById(m.id).className =
                    'toggle-btn' + (posFreqInverted ? ' active' : '');
            } else {
                var el = document.getElementById(m.id);
                el.value = data[key];
                // Update display label for sliders
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
                document.getElementById('script-status').textContent = 'Leeres Script';
                return;
            }
            var durMs = actions[count - 1].at;
            var mins = Math.floor(durMs / 60000);
            var secs = Math.floor((durMs % 60000) / 1000);
            var el = document.getElementById('script-status');
            el.textContent = 'Script empfangen!';
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
                lines.push('  ... (' + (count - 15) + ' weitere) ...');
            }
            document.getElementById('script-preview').textContent = lines.join('\\n');
        } catch(e) {
            appendLog('Parse-Fehler: ' + e.message);
        }
    }
</script>
</body>
</html>
"""
