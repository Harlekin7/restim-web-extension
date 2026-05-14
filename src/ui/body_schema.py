"""Body-Schema component for electrode placement.

Renders a schematic male anatomy SVG with click-points for the positions
defined in `session.types.ElectrodePosition`. Active electrodes are
highlighted, can be marked as `Common` and sized small/medium/large.

The schema is intentionally low-detail / clinical-diagram style — anatomical
labels rather than figurative drawing.

Public API:
    build_body_schema_html(electrodes: list[dict] | None) -> str

`electrodes` is a list of dicts of the shape::
    {"position": "<ElectrodePosition value>", "is_common": bool, "size": "small"|"medium"|"large"}

Returns a self-contained HTML fragment (no <html>/<body>) suitable for
embedding inside the sidebar. JS communicates electrode-changes back to
the parent through the `window.__bodySchemaOnChange(list)` callback hook,
which the sidebar wires up to `pywebview.api.set_session_profile(...)`.
"""
from __future__ import annotations

import json
from typing import Optional


# Click-points in SVG user units. The SVG viewBox is 200x420.
# Coordinates were placed by hand to roughly match a schematic
# torso + genital diagram. They are NOT anatomically precise,
# only functional for selection.
ELECTRODE_POINTS: list[dict] = [
    # Upper body
    {"id": "brustwarze_l", "label": "Brustwarze L",  "x":  78, "y":  60},
    {"id": "brustwarze_r", "label": "Brustwarze R",  "x": 122, "y":  60},
    # Penis (vertical schematic shaft, glans at bottom)
    {"id": "schaft_oben",  "label": "Schaft oben",   "x": 100, "y": 215},
    {"id": "schaft_unten", "label": "Schaft unten",  "x": 100, "y": 260},
    {"id": "eichel",       "label": "Eichel",        "x": 100, "y": 300},
    # Below scrotum
    {"id": "unter_hoden",  "label": "Unter Hoden",   "x": 100, "y": 335},
    # Perineum
    {"id": "damm",         "label": "Damm",          "x": 100, "y": 360},
    # Anal area
    {"id": "anal_plug",    "label": "Anal Plug",     "x": 100, "y": 388},
    {"id": "prostata",     "label": "Prostata",      "x": 130, "y": 388},
]

# Default presets per device class — pre-selected electrode spots.
# Keys map to `DeviceClass` enum values.
HARDWARE_PRESETS: dict[str, list[dict]] = {
    "3_phase_foc": [
        {"position": "eichel",       "is_common": True,  "size": "medium"},
        {"position": "schaft_oben",  "is_common": False, "size": "medium"},
        {"position": "unter_hoden",  "is_common": False, "size": "medium"},
    ],
    "4_phase_foc": [
        {"position": "eichel",       "is_common": True,  "size": "medium"},
        {"position": "schaft_oben",  "is_common": False, "size": "medium"},
        {"position": "schaft_unten", "is_common": False, "size": "medium"},
        {"position": "unter_hoden",  "is_common": False, "size": "medium"},
    ],
    "stereostim": [
        {"position": "schaft_oben",  "is_common": False, "size": "medium"},
        {"position": "unter_hoden",  "is_common": False, "size": "medium"},
    ],
    "single_channel": [
        {"position": "schaft_oben",  "is_common": False, "size": "medium"},
        {"position": "unter_hoden",  "is_common": False, "size": "medium"},
    ],
}


def build_body_schema_html(electrodes: Optional[list[dict]] = None) -> str:
    """Render the body-schema HTML.

    Returns a fragment containing:
      - SVG anatomy with click-points
      - electrode-list under the SVG with per-electrode controls
        (common-toggle and size-picker)
      - JS that exposes `window.__bodySchema` with helpers
        `set(list)`, `get()`, `setHardwarePreset(deviceClass)`.
    """
    initial = electrodes or HARDWARE_PRESETS["3_phase_foc"]
    initial_json = json.dumps(initial)
    points_json = json.dumps(ELECTRODE_POINTS)
    presets_json = json.dumps(HARDWARE_PRESETS)
    return _BODY_SCHEMA_TEMPLATE.format(
        initial_json=initial_json,
        points_json=points_json,
        presets_json=presets_json,
    )


# NOTE: Curly braces in CSS / JS are doubled `{{` / `}}` so str.format works.
_BODY_SCHEMA_TEMPLATE = r"""
<style>
.body-schema-wrap {{
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px;
    margin-top: 4px;
}}
.body-schema-svg {{
    display: block;
    margin: 0 auto;
    width: 180px;
    height: 380px;
    background: #141414;
    border-radius: 4px;
}}
.body-schema-svg .anat {{
    fill: none;
    stroke: #555;
    stroke-width: 1.2;
}}
.body-schema-svg .anat-fill {{
    fill: #1f1f1f;
    stroke: #555;
    stroke-width: 1.2;
}}
.body-schema-svg .pt {{
    fill: #2a2a2a;
    stroke: #555;
    stroke-width: 1.4;
    cursor: pointer;
    transition: fill 0.12s, stroke 0.12s;
}}
.body-schema-svg .pt:hover {{
    fill: #3a3a3a;
    stroke: #7af;
}}
.body-schema-svg .pt.active {{
    fill: #5a8;
    stroke: #6b9;
}}
.body-schema-svg .pt.active.common {{
    fill: #fb4;
    stroke: #fc6;
}}
.body-schema-svg .pt-label {{
    fill: #888;
    font-size: 8px;
    font-family: 'Segoe UI', Tahoma, sans-serif;
    pointer-events: none;
}}
.electrode-list {{
    margin-top: 8px;
    font-size: 11px;
}}
.electrode-row {{
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 4px;
    border-bottom: 1px solid #2a2a2a;
}}
.electrode-row:last-child {{ border-bottom: none; }}
.electrode-name {{
    flex: 1;
    color: #ccc;
}}
.electrode-name.common::before {{
    content: '★ ';
    color: #fb4;
    font-weight: 600;
}}
.electrode-row select {{
    background: #1a1a1a;
    border: 1px solid #444;
    color: #ccc;
    font-size: 10px;
    padding: 1px 3px;
    border-radius: 3px;
}}
.electrode-mini-btn {{
    background: #333;
    border: 1px solid #444;
    color: #aaa;
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
    cursor: pointer;
}}
.electrode-mini-btn.active {{
    background: #fb4;
    border-color: #fc6;
    color: #111;
}}
.electrode-empty {{
    color: #666;
    font-style: italic;
    padding: 4px 0;
    text-align: center;
}}
</style>

<div class="body-schema-wrap">
    <svg class="body-schema-svg" viewBox="0 0 200 420" xmlns="http://www.w3.org/2000/svg">
        <!-- Schematic torso (rectangle with rounded shoulders) -->
        <path class="anat-fill" d="M 55 30 Q 70 18 100 18 Q 130 18 145 30 L 150 180 Q 130 195 100 195 Q 70 195 50 180 Z"/>
        <!-- Hip / pelvis line -->
        <path class="anat-fill" d="M 50 180 L 50 230 Q 70 245 100 245 Q 130 245 150 230 L 150 180 Z"/>
        <!-- Penis schematic (vertical shape) -->
        <path class="anat-fill" d="M 88 200 L 88 285 Q 88 315 100 315 Q 112 315 112 285 L 112 200 Z"/>
        <!-- Glans -->
        <ellipse class="anat-fill" cx="100" cy="305" rx="14" ry="13"/>
        <!-- Scrotum (rough) -->
        <ellipse class="anat-fill" cx="100" cy="335" rx="22" ry="16"/>
        <!-- Perineum line -->
        <line class="anat" x1="78" y1="358" x2="122" y2="358"/>
        <!-- Anal indicator -->
        <circle class="anat-fill" cx="100" cy="385" r="11"/>

        <!-- Click-points + labels rendered by JS -->
        <g id="bs-points"></g>
        <g id="bs-labels"></g>
    </svg>
    <div class="electrode-list" id="electrode-list"></div>
</div>

<script>
(() => {{
    const POINTS = {points_json};
    const PRESETS = {presets_json};
    let electrodes = {initial_json};

    const ptGroup = document.getElementById('bs-points');
    const lblGroup = document.getElementById('bs-labels');
    const listEl = document.getElementById('electrode-list');

    // Build click-points
    POINTS.forEach(pt => {{
        const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', pt.x);
        c.setAttribute('cy', pt.y);
        c.setAttribute('r', 5);
        c.setAttribute('class', 'pt');
        c.setAttribute('data-id', pt.id);
        c.addEventListener('click', () => togglePoint(pt.id));
        ptGroup.appendChild(c);

        // Label, offset to the side that has more space.
        const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        const right = pt.x > 100;
        lbl.setAttribute('x', pt.x + (right ? 10 : -10));
        lbl.setAttribute('y', pt.y + 3);
        lbl.setAttribute('text-anchor', right ? 'start' : 'end');
        lbl.setAttribute('class', 'pt-label');
        lbl.textContent = pt.label;
        lblGroup.appendChild(lbl);
    }});

    function togglePoint(id) {{
        const idx = electrodes.findIndex(e => e.position === id);
        if (idx >= 0) {{
            electrodes.splice(idx, 1);
        }} else {{
            // First electrode added becomes Common by default if none yet.
            const hasCommon = electrodes.some(e => e.is_common);
            electrodes.push({{
                position: id,
                is_common: !hasCommon,
                size: 'medium',
            }});
        }}
        render();
        notify();
    }}

    function render() {{
        // Update SVG point classes
        ptGroup.querySelectorAll('.pt').forEach(el => {{
            const id = el.getAttribute('data-id');
            const e = electrodes.find(x => x.position === id);
            el.classList.toggle('active', !!e);
            el.classList.toggle('common', !!(e && e.is_common));
            el.setAttribute('r', e ? (e.size === 'large' ? 7 : e.size === 'small' ? 4 : 5.5) : 5);
        }});
        // Render electrode list
        listEl.innerHTML = '';
        if (electrodes.length === 0) {{
            const d = document.createElement('div');
            d.className = 'electrode-empty';
            d.textContent = 'No electrodes — click the body-schema to add.';
            listEl.appendChild(d);
            return;
        }}
        electrodes.forEach((e, i) => {{
            const pt = POINTS.find(p => p.id === e.position);
            const row = document.createElement('div');
            row.className = 'electrode-row';

            const name = document.createElement('span');
            name.className = 'electrode-name' + (e.is_common ? ' common' : '');
            name.textContent = (pt ? pt.label : e.position);
            row.appendChild(name);

            const cBtn = document.createElement('button');
            cBtn.className = 'electrode-mini-btn' + (e.is_common ? ' active' : '');
            cBtn.textContent = 'Common';
            cBtn.title = 'Mark as the shared/Common electrode';
            cBtn.addEventListener('click', () => {{
                // Only one Common allowed at a time.
                electrodes.forEach((x, j) => {{ x.is_common = (j === i) ? !x.is_common : false; }});
                render();
                notify();
            }});
            row.appendChild(cBtn);

            const sel = document.createElement('select');
            ['small', 'medium', 'large'].forEach(s => {{
                const o = document.createElement('option');
                o.value = s; o.textContent = s;
                if (e.size === s) o.selected = true;
                sel.appendChild(o);
            }});
            sel.addEventListener('change', () => {{
                e.size = sel.value;
                render();
                notify();
            }});
            row.appendChild(sel);

            const rmBtn = document.createElement('button');
            rmBtn.className = 'electrode-mini-btn';
            rmBtn.textContent = '×';
            rmBtn.title = 'Remove electrode';
            rmBtn.addEventListener('click', () => {{
                electrodes.splice(i, 1);
                render();
                notify();
            }});
            row.appendChild(rmBtn);

            listEl.appendChild(row);
        }});
    }}

    function notify() {{
        if (typeof window.__bodySchemaOnChange === 'function') {{
            try {{ window.__bodySchemaOnChange(electrodes.map(e => ({{...e}}))); }} catch (err) {{}}
        }}
    }}

    window.__bodySchema = {{
        get: () => electrodes.map(e => ({{...e}})),
        set: (list) => {{ electrodes = (list || []).map(e => ({{...e}})); render(); notify(); }},
        setHardwarePreset: (cls) => {{
            const preset = PRESETS[cls];
            if (preset) {{
                electrodes = preset.map(e => ({{...e}}));
                render();
                notify();
            }}
        }},
    }};

    render();
}})();
</script>
"""
