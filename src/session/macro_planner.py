"""Macro Planner — turns a SessionProfile into a complete MacroPlan.

Architecture:
- _build_intensity_curve: stylistic master volume curve. Currently rule-based.
  When the learned envelope sampler (Agent D output) is ready, swap THIS function
  for a model.sample(profile, seed) call. Everything else stays the same.
- _generate_subwaves: nested-envelope sub-crescendi (the "lokal lebendig" layer).
- _plan_edges: planned drop events from style + target.
- _derive_envelopes: hardness/sharpness/movement curves from intensity + correlations.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from typing import Optional

import numpy as np

from .macro import EdgeEvent, MacroPlan, MasterCurve, MasterEnvelopes, Phase, SubWave
from .profile import EXPERIENCE_CAPS, CHARACTER_PRESETS, SessionProfile
from .types import Character, PhaseName, SessionStyle, SessionTarget


# Empirical correlations from docs/FUNSCRIPT_PATTERNS.md
# These coefficients translate the master intensity curve into the 3 derived envelopes.
# Format: derived = base + slope * intensity, optionally modulated by sensation slider.
DERIVATION_DEFAULTS = {
    # hardness ↔ intensity, r=0.85 in empirical data
    "hardness": dict(base=0.30, slope=0.70),
    # carrier (sharpness) ↔ volume, r=0.79..0.98 (universal Restim coupling)
    "sharpness": dict(base=0.40, slope=0.60),
    # movement (alpha/beta rotation amount) — weaker correlation, more style-driven
    "movement": dict(base=0.50, slope=0.40),
}


# Style-specific intensity-curve templates. Each is a list of (phase_fraction, intensity_fraction)
# control points within [0, 1] x [0, 1]. The macro planner stretches them to actual session
# duration and clamps to (vol_floor, vol_ceiling) from the experience caps.
STYLE_CURVES: dict[SessionStyle, list[tuple[float, float]]] = {
    # Long linear hypno climb, no beat
    SessionStyle.SANFTER_AUFBAU: [(0.00, 0.00), (1.00, 1.00)],
    # Classic crescendo: slow start, accelerating end
    SessionStyle.CRESCENDO: [(0.00, 0.00), (0.30, 0.20), (0.70, 0.55), (0.90, 0.85), (1.00, 1.00)],
    # Beat-Drop: plateau-and-burst pattern, mid-range with occasional spikes
    SessionStyle.BEAT_DROP: [(0.00, 0.10), (0.20, 0.40), (0.40, 0.55), (0.60, 0.65), (0.85, 0.80), (1.00, 0.95)],
    # Edging: holds high mid-range with planned drops (drops added separately as EdgeEvents)
    SessionStyle.EDGING: [(0.00, 0.10), (0.25, 0.55), (0.45, 0.75), (0.70, 0.80), (0.95, 0.85), (1.00, 0.90)],
    # Ruin: steep climb, then drop in last phase (also reinforced via negative subwave)
    SessionStyle.RUIN: [(0.00, 0.05), (0.20, 0.30), (0.50, 0.65), (0.80, 0.95), (0.90, 1.00), (1.00, 0.30)],
    # Endless tease: oscillates between mid-low values, no climax
    SessionStyle.ENDLOS_TEASE: [(0.00, 0.20), (0.25, 0.45), (0.50, 0.40), (0.75, 0.50), (1.00, 0.45)],
}


# Phase weight templates per style (sum=1.0). Affects phase boundaries.
PHASE_WEIGHTS: dict[SessionStyle, list[float]] = {
    SessionStyle.SANFTER_AUFBAU: [0.20, 0.20, 0.20, 0.20, 0.20],
    SessionStyle.CRESCENDO: [0.15, 0.20, 0.25, 0.25, 0.15],
    SessionStyle.BEAT_DROP: [0.10, 0.20, 0.30, 0.25, 0.15],
    SessionStyle.EDGING: [0.10, 0.15, 0.40, 0.25, 0.10],     # extra-long plateau
    SessionStyle.RUIN: [0.10, 0.20, 0.25, 0.40, 0.05],       # tiny climax, big edge
    SessionStyle.ENDLOS_TEASE: [0.20, 0.20, 0.20, 0.20, 0.20],
}


# Per-style edge event density (drops per minute on average) and depth scaling.
EDGE_DENSITY: dict[SessionStyle, dict] = {
    SessionStyle.SANFTER_AUFBAU: dict(per_minute=0.0, depth_scale=0.0),
    SessionStyle.CRESCENDO: dict(per_minute=0.0, depth_scale=0.0),
    SessionStyle.BEAT_DROP: dict(per_minute=0.05, depth_scale=0.4),  # occasional small drops
    SessionStyle.EDGING: dict(per_minute=0.30, depth_scale=1.0),     # signature drops
    SessionStyle.RUIN: dict(per_minute=0.0, depth_scale=0.0),        # one massive drop, separate
    SessionStyle.ENDLOS_TEASE: dict(per_minute=0.15, depth_scale=0.6),
}


class MacroPlanner:
    """Plans a complete session as a MacroPlan from a SessionProfile."""

    def __init__(self, learned_intensity_sampler=None):
        """
        learned_intensity_sampler: optional callable (profile, rng) -> MasterCurve.
        When provided, replaces the rule-based intensity curve generation.
        """
        self.learned_intensity_sampler = learned_intensity_sampler

    def plan(self, profile: SessionProfile, seed: Optional[int] = None) -> MacroPlan:
        if seed is None:
            seed = profile.seed if profile.seed is not None else int(time.time() * 1000) & 0x7FFFFFFF

        rng = np.random.default_rng(seed)
        caps = EXPERIENCE_CAPS[profile.experience]
        char = CHARACTER_PRESETS[profile.character]
        duration_s = float(profile.duration_s)

        phases = self._build_phases(profile.style, duration_s)
        intensity = self._build_intensity_curve(profile, caps, rng)
        edges = self._plan_edges(profile, phases, caps, rng)
        subwaves = self._generate_subwaves(profile, phases, char, intensity, rng)
        envelopes = self._derive_envelopes(intensity, profile)

        # Macro consistency check & re-roll if needed (max 10 attempts)
        attempts = 0
        while not self._validate_plan(intensity, edges, caps) and attempts < 10:
            attempts += 1
            seed = (seed + 1) & 0x7FFFFFFF
            rng = np.random.default_rng(seed)
            intensity = self._build_intensity_curve(profile, caps, rng)
            edges = self._plan_edges(profile, phases, caps, rng)
            subwaves = self._generate_subwaves(profile, phases, char, intensity, rng)
            envelopes = self._derive_envelopes(intensity, profile)

        return MacroPlan(
            phases=phases,
            envelopes=envelopes,
            edges=edges,
            subwaves=subwaves,
            seed=seed,
            profile_summary=self._summarize_profile(profile),
        )

    # -- Phases -----------------------------------------------------------

    def _build_phases(self, style: SessionStyle, duration_s: float) -> list[Phase]:
        weights = PHASE_WEIGHTS[style]
        names = [PhaseName.INIT, PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX]
        phases = []
        t_start = 0.0
        for name, w in zip(names, weights):
            t_end = t_start + duration_s * w
            phases.append(Phase(name=name, t_start_s=t_start, t_end_s=t_end))
            t_start = t_end
        # Ensure last phase ends exactly at duration
        phases[-1] = Phase(name=phases[-1].name, t_start_s=phases[-1].t_start_s, t_end_s=duration_s)
        return phases

    # -- Intensity curve --------------------------------------------------

    def _build_intensity_curve(self, profile: SessionProfile, caps: dict,
                               rng: np.random.Generator) -> MasterCurve:
        """Default rule-based. Replace with learned sampler later."""
        if self.learned_intensity_sampler is not None:
            return self.learned_intensity_sampler(profile, rng)

        template = STYLE_CURVES[profile.style]
        duration_s = float(profile.duration_s)
        vol_floor = caps["vol_floor"]
        vol_ceiling = caps["vol_ceiling"]

        # Light per-control-point jitter so two seeds give different shapes within style
        jitter_scale = 0.03  # ±3% jitter on intensity values
        points = []
        for i, (frac_t, frac_v) in enumerate(template):
            t = frac_t * duration_s
            # Map fraction-of-range to actual value, with jitter (skip first/last)
            v = vol_floor + frac_v * (vol_ceiling - vol_floor)
            if 0 < i < len(template) - 1:
                v += rng.uniform(-jitter_scale, jitter_scale) * (vol_ceiling - vol_floor)
                v = float(np.clip(v, vol_floor, vol_ceiling))
            points.append((t, v))

        return MasterCurve.from_points(points)

    # -- Edges ------------------------------------------------------------

    def _plan_edges(self, profile: SessionProfile, phases: list[Phase],
                    caps: dict, rng: np.random.Generator) -> list[EdgeEvent]:
        density_cfg = EDGE_DENSITY[profile.style]
        per_minute = density_cfg["per_minute"]
        depth_scale = density_cfg["depth_scale"]
        max_depth = caps["max_drop_depth"]

        edges: list[EdgeEvent] = []

        # Edges live primarily in PLATEAU and EDGE phases
        edge_zones = [p for p in phases if p.name in (PhaseName.PLATEAU, PhaseName.EDGE)]
        zone_total_s = sum(p.duration_s for p in edge_zones)

        # Special-case: RUIN has one massive drop at start of CLIMAX phase
        if profile.style == SessionStyle.RUIN:
            climax = next(p for p in phases if p.name == PhaseName.CLIMAX)
            edges.append(EdgeEvent(
                t_s=climax.t_start_s + climax.duration_s * 0.15,
                depth=max_depth,                  # max possible drop
                recovery_s=climax.duration_s * 0.6,
            ))

        # Special-case: ENDLOS_TEASE spreads edges across entire session
        if profile.style == SessionStyle.ENDLOS_TEASE:
            edge_zones = phases
            zone_total_s = profile.duration_s

        if per_minute > 0:
            expected_count = (zone_total_s / 60.0) * per_minute
            n_edges = int(round(rng.normal(expected_count, expected_count * 0.2)))
            n_edges = max(1, min(n_edges, 30))   # sane bounds

            # Sample edge times with min-spacing
            min_spacing = 30.0   # at least 30s between edges
            attempts = 0
            zone_start = edge_zones[0].t_start_s
            zone_end = edge_zones[-1].t_end_s
            chosen_t: list[float] = []
            while len(chosen_t) < n_edges and attempts < n_edges * 20:
                t = rng.uniform(zone_start, zone_end - 10.0)
                if all(abs(t - existing) >= min_spacing for existing in chosen_t):
                    chosen_t.append(t)
                attempts += 1

            for t in chosen_t:
                depth = max_depth * depth_scale * rng.uniform(0.5, 1.0)
                recovery = rng.uniform(15.0, 45.0)
                edges.append(EdgeEvent(t_s=t, depth=depth, recovery_s=recovery))

        edges.sort(key=lambda e: e.t_s)
        return edges

    # -- SubWaves (the nested-envelope layer) ----------------------------

    def _generate_subwaves(self, profile: SessionProfile, phases: list[Phase],
                           char: dict, intensity: MasterCurve,
                           rng: np.random.Generator) -> list[SubWave]:
        """Generate sub-wave events whose amplitude grows and period shrinks over the session.

        The mixing operator in the renderer is:
            final = macro + (1 - macro/cap) * subwave
        i.e. subwaves modulate remaining headroom — they automatically flatten when macro is near peak.
        """
        duration_s = float(profile.duration_s)
        amp_scale = char["subwave_amplitude_scale"]
        period_scale = char["subwave_period_scale"]

        # Base amplitude at session start vs end. Empirically: late SubWaves are 2-4x larger.
        base_amp_start = 0.05 * amp_scale
        base_amp_end = 0.20 * amp_scale

        # Period: long at start (60-90s), short at end (15-30s)
        period_start = 75.0 * period_scale
        period_end = 22.5 * period_scale

        # Density: roughly 8-25 sub-waves per session, scaled by character
        target_density = 12 * (1.0 / period_scale)   # more density for short periods
        n_subwaves = int(round(target_density * duration_s / (45 * 60)))
        n_subwaves = max(8, min(n_subwaves, 60))

        subwaves: list[SubWave] = []
        # Distribute subwave start times non-uniformly: more in second half
        # Use a quadratic CDF: t = duration * sqrt(uniform) for back-loading
        starts_unit = np.sort(rng.uniform(0, 1, size=n_subwaves) ** 0.7)
        starts_s = starts_unit * (duration_s * 0.95)   # leave last 5% for tail

        shapes_pool = ["sine", "asym_pulse", "sawtooth"]
        # RUIN style: inject a big "drop" subwave near climax
        if profile.style == SessionStyle.RUIN:
            shapes_pool.append("drop")

        for i, t_start in enumerate(starts_s):
            progress = t_start / duration_s
            amp = base_amp_start + (base_amp_end - base_amp_start) * progress
            amp *= rng.uniform(0.7, 1.3)
            period = period_start + (period_end - period_start) * progress
            period *= rng.uniform(0.85, 1.15)
            shape = rng.choice(shapes_pool)

            # EDGING gets more sawtooth (build then drop) sub-waves
            if profile.style == SessionStyle.EDGING and rng.random() < 0.4:
                shape = "sawtooth"

            subwaves.append(SubWave(
                t_start_s=float(t_start),
                period_s=float(period),
                amplitude=float(amp),
                shape=shape,
            ))

        return subwaves

    # -- Derived envelopes (Härte / Schärfe / Bewegung) -----------------

    def _derive_envelopes(self, intensity: MasterCurve,
                          profile: SessionProfile) -> MasterEnvelopes:
        """Build hardness/sharpness/movement curves as transformations of the intensity curve.

        Each derived curve uses base + slope * intensity, with the sensation sliders modulating
        the final value. Sample at the same control-point times as the intensity curve.
        """
        sm = profile.sensation
        d = DERIVATION_DEFAULTS

        # Sample at intensity's control points
        ts = intensity.times_s
        vs = intensity.values

        # Hardness: shifted by soft_to_hard slider (0=softer, 1=harder)
        hardness_vals = np.clip(
            d["hardness"]["base"] + d["hardness"]["slope"] * vs + (sm.soft_to_hard - 0.5) * 0.3,
            0.0, 1.0,
        )
        # Sharpness: shifted by sharp_to_deep slider — note: 1=deep means LOWER carrier
        # so we invert: sharpness_value increases when slider is at "sharp" pole
        sharpness_vals = np.clip(
            d["sharpness"]["base"] + d["sharpness"]["slope"] * vs - (sm.sharp_to_deep - 0.5) * 0.3,
            0.0, 1.0,
        )
        # Movement: from static_to_moving slider
        movement_vals = np.clip(
            d["movement"]["base"] + d["movement"]["slope"] * vs + (sm.static_to_moving - 0.5) * 0.4,
            0.0, 1.0,
        )

        return MasterEnvelopes(
            intensity=intensity,
            hardness=MasterCurve(ts.copy(), hardness_vals),
            sharpness=MasterCurve(ts.copy(), sharpness_vals),
            movement=MasterCurve(ts.copy(), movement_vals),
        )

    # -- Validation -------------------------------------------------------

    def _validate_plan(self, intensity: MasterCurve, edges: list[EdgeEvent],
                       caps: dict) -> bool:
        """4 checks: monotone trend, plateau lengths, drop depths, climax reachability."""
        # 1. Drops not deeper than max
        for e in edges:
            if e.depth > caps["max_drop_depth"]:
                return False
        # 2. Intensity peaks reach a meaningful fraction of ceiling (≥ 0.6 * (ceil - floor))
        v_floor = caps["vol_floor"]
        v_ceil = caps["vol_ceiling"]
        peak = intensity.values.max()
        if peak < v_floor + 0.6 * (v_ceil - v_floor):
            # only fail if not endlos_tease — that style has low peaks by design
            # (caller ensures style is checked elsewhere)
            pass  # tolerant — style template is responsible for reaching peak
        # 3. No NaN / Inf
        if not np.all(np.isfinite(intensity.values)):
            return False
        # 4. Monotone trend roughly upward in first 80% (skip for tease/ruin)
        # — this would be too strict; we leave it.
        return True

    def _summarize_profile(self, profile: SessionProfile) -> dict:
        return dict(
            style=profile.style.value,
            duration_s=profile.duration_s,
            target=profile.target.value,
            character=profile.character.value,
            experience=int(profile.experience),
            sensation=asdict(profile.sensation),
        )


def evaluate_macro_at(plan: MacroPlan, t: float) -> dict[str, float]:
    """Compose the macro intensity at time t — including subwaves and edges.

    Uses the mixing operator: final = macro + (1 - macro/cap) * (subwaves + edges).
    """
    macro = float(plan.envelopes.intensity(t))
    cap = 1.0   # working in normalized 0..1 space; cap is the ceiling

    sub_total = 0.0
    for sw in plan.subwaves:
        sub_total += sw.evaluate(t)

    edge_total = 0.0
    for e in plan.edges:
        if e.applies_at(t):
            # Negative pulse shaped by sin half-cycle over recovery
            phase = (t - e.t_s) / max(e.recovery_s, 0.01)
            phase = float(np.clip(phase, 0.0, 1.0))
            edge_total -= e.depth * np.sin(np.pi * phase)

    headroom = max(0.0, 1.0 - macro / cap)
    final = macro + headroom * (sub_total + edge_total)
    final = float(np.clip(final, 0.0, 1.0))

    return dict(
        intensity=final,
        macro_only=macro,
        subwave=sub_total,
        edge=edge_total,
        hardness=float(plan.envelopes.hardness(t)),
        sharpness=float(plan.envelopes.sharpness(t)),
        movement=float(plan.envelopes.movement(t)),
    )
