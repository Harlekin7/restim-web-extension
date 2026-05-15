"""Position patterns P1..P15 — alpha/beta micro-renderers.

Each renderer returns 0..1 normalized values for the alpha and/or beta axes.
Patterns target the documented subjective effects from docs/FUNSCRIPT_PATTERNS.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..pattern_base import (
    MasterContext,
    PatternMetadata,
    PatternSlot,
    perlin_like,
    rotating_position,
    slew_smooth,
)
from ..types import AxisName, PatternCategory, PhaseName


# ---------------------------------------------------------------------------
# Helpers local to position patterns
# ---------------------------------------------------------------------------

def _dt_from(t: np.ndarray) -> float:
    if t.size < 2:
        return 0.02
    return float(t[1] - t[0])


def _safe(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0.0, 1.0)


# ---------------------------------------------------------------------------
# P1 — Static Floor
# ---------------------------------------------------------------------------

@dataclass
class PatternP1_StaticFloor:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P1",
        name="Static Floor",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.INIT, PhaseName.PLATEAU),
        style_affinity={
            "sanfter_aufbau": 1.5, "endlos_tease": 1.2,
            "edging": 1.1, "crescendo": 0.6, "beat_drop": 0.3, "ruin": 0.4,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        return {
            AxisName.ALPHA: np.zeros(n),
            AxisName.BETA: np.full(n, 0.5),
        }


# ---------------------------------------------------------------------------
# P2 — Static Center
# ---------------------------------------------------------------------------

@dataclass
class PatternP2_StaticCenter:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P2",
        name="Static Center",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(3.0, 12.0),  # cap shorter — never lingers long
        suitable_phases=(PhaseName.INIT, PhaseName.EDGE),
        style_affinity={  # rare across the board — too sensation-less for most styles
            "endlos_tease": 0.5, "edging": 0.4, "sanfter_aufbau": 0.5,
            "crescendo": 0.2, "beat_drop": 0.1, "ruin": 0.15,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # tiny jitter < 2% to look "alive" but stay centered
        jitter = 0.01 * rng.standard_normal(n)
        a = np.full(n, 0.5) + jitter
        b = np.full(n, 0.5) + 0.01 * rng.standard_normal(n)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P3 — Smooth Cosine Half-Wave (Beat-Lock)
# ---------------------------------------------------------------------------

@dataclass
class PatternP3_CosineBeatLock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P3",
        name="Smooth Cosine Half-Wave",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(4.0, 30.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.8, "crescendo": 1.4, "ruin": 1.3,
            "sanfter_aufbau": 0.6, "endlos_tease": 0.7, "edging": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # Period 2..5s (slow visible motion, not zappy). Higher movement -> faster.
        period = float(slot.parameters.get("period_s", 4.5 - 2.5 * master.movement))
        period = max(1.5, min(6.0, period))
        f = 1.0 / period
        phase0 = float(slot.parameters.get("phase0", rng.uniform(0, 2 * np.pi)))
        a = 0.5 + 0.5 * np.cos(2 * np.pi * f * t_local + phase0)
        # Add a small lagging beta wobble so the rotation traces a tilted figure-8
        # instead of a flat horizontal line through the center.
        b = 0.5 + 0.25 * np.sin(2 * np.pi * f * t_local + phase0 + np.pi / 3)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P4 — Damped Sinus / Ringdown
# ---------------------------------------------------------------------------

@dataclass
class PatternP4_DampedRingdown:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P4",
        name="Damped Sinus Ringdown",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(2.0, 8.0),
        suitable_phases=(PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "ruin": 1.8, "beat_drop": 1.4, "crescendo": 1.2,
            "edging": 1.1, "sanfter_aufbau": 0.4, "endlos_tease": 0.5,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 0.6))
        decay = float(slot.parameters.get("decay_s", 1.5))  # time-constant
        f = 1.0 / period
        env = np.exp(-t_local / max(0.2, decay))
        a = 0.5 + 0.5 * env * np.cos(2 * np.pi * f * t_local)
        b = np.full(n, 0.5)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P5 — Hard Toggle / Square-Wave Slap
# ---------------------------------------------------------------------------

@dataclass
class PatternP5_HardToggle:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P5",
        name="Hard Toggle Slap",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(3.0, 20.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "ruin": 2.0, "beat_drop": 1.7, "crescendo": 1.0,
            "edging": 0.8, "sanfter_aufbau": 0.2, "endlos_tease": 0.3,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # 250..800ms toggle period; stay close to extremes
        lo = float(slot.parameters.get("lo", 0.04))
        hi = float(slot.parameters.get("hi", 0.95))
        period = float(slot.parameters.get("period_s", 0.45))
        period = max(0.2, min(1.0, period))
        # square wave on alpha
        toggle = (np.floor(t_local / period) % 2 == 0).astype(float)
        a = lo + (hi - lo) * toggle
        b = np.full(n, 0.5)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P6 — Slow Drift
# ---------------------------------------------------------------------------

@dataclass
class PatternP6_SlowDrift:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P6",
        name="Slow Drift",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(20.0, 120.0),
        suitable_phases=(PhaseName.INIT, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.8, "sanfter_aufbau": 1.5, "edging": 1.4,
            "crescendo": 0.6, "beat_drop": 0.3, "ruin": 0.4,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # Linear drift with optional random direction
        start = float(slot.parameters.get("start", rng.uniform(0.2, 0.4)))
        end = float(slot.parameters.get("end", rng.uniform(0.6, 0.85)))
        if rng.random() < 0.5:
            start, end = end, start
        a = np.linspace(start, end, n)
        b_start = float(slot.parameters.get("beta_start", 0.5))
        b_end = float(slot.parameters.get("beta_end", 0.5 + 0.1 * (rng.random() - 0.5)))
        b = np.linspace(b_start, b_end, n)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P7 — Pendelschwingung (Beta-Lock)
# ---------------------------------------------------------------------------

@dataclass
class PatternP7_BetaLockPendulum:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P7",
        name="Beta-Lock Pendulum",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "sanfter_aufbau": 1.3, "endlos_tease": 1.4, "edging": 1.3,
            "crescendo": 1.0, "beat_drop": 0.7, "ruin": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 4.0))
        f = 1.0 / max(1.0, period)
        a = 0.5 + 0.5 * np.sin(2 * np.pi * f * t_local)
        # Slow beta drift so the trajectory traces a wide ellipse, not a flat line
        b = 0.5 + 0.30 * np.cos(2 * np.pi * f * 0.5 * t_local)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P8 — Vollkreis-Rotation
# ---------------------------------------------------------------------------

@dataclass
class PatternP8_FullCircleRotation:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P8",
        name="Full Circle Rotation",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(5.0, 90.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "endlos_tease": 1.6, "sanfter_aufbau": 1.3, "crescendo": 1.2,
            "edging": 1.2, "beat_drop": 0.7, "ruin": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        # Period 3..8s — slow visible rotation, scaled by movement (low=slow, high=fast)
        default_period = 7.5 - 4.5 * master.movement
        period = float(slot.parameters.get("period_s", default_period))
        radius = float(slot.parameters.get("radius", 0.5 + 0.4 * master.movement))
        radius = max(0.2, min(1.0, radius))
        f = 1.0 / max(2.0, period)
        phase0 = float(slot.parameters.get("phase0", rng.uniform(0, 2 * np.pi)))
        a, b = rotating_position(t_local, f, radius, phase0)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P9 — Halbkreis-Pendel
# ---------------------------------------------------------------------------

@dataclass
class PatternP9_HalfCircleArc:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P9",
        name="Half Circle Arc",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(5.0, 45.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "sanfter_aufbau": 1.3, "endlos_tease": 1.4, "edging": 1.2,
            "crescendo": 1.1, "beat_drop": 0.7, "ruin": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        period = float(slot.parameters.get("period_s", 5.0))
        f = 1.0 / max(1.5, period)
        a = 0.5 + 0.45 * np.sin(2 * np.pi * f * t_local)
        b = 0.5 + 0.10 * np.cos(2 * np.pi * f * t_local)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P10 — Asymmetrischer Halb-Hub
# ---------------------------------------------------------------------------

@dataclass
class PatternP10_OffsetHalfStroke:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P10",
        name="Asymmetric Half Stroke",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(5.0, 30.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "edging": 1.4, "endlos_tease": 1.3, "sanfter_aufbau": 1.0,
            "crescendo": 0.9, "beat_drop": 0.7, "ruin": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # Pick offset side from rng or parameter
        lo = float(slot.parameters.get("lo", 0.10))
        hi = float(slot.parameters.get("hi", 0.50))
        if slot.parameters.get("side", "low") == "high":
            lo, hi = 0.55, 0.90
        period = float(slot.parameters.get("period_s", 4.0))
        f = 1.0 / max(1.5, period)
        amp = (hi - lo) / 2.0
        mid = (hi + lo) / 2.0
        a = mid + amp * np.sin(2 * np.pi * f * t_local)
        # Wide beta arc so the offset half-stroke doesn't sit on a single horizontal line
        b = 0.5 + 0.30 * np.cos(2 * np.pi * f * t_local + np.pi / 4)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P11 — Mikro-Jitter
# ---------------------------------------------------------------------------

@dataclass
class PatternP11_MicroJitter:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P11",
        name="Micro Jitter",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(3.0, 12.0),  # short bursts only
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={  # niche — only as accent, never as main pattern
            "endlos_tease": 0.7, "edging": 0.7, "ruin": 0.5,
            "crescendo": 0.4, "sanfter_aufbau": 0.4, "beat_drop": 0.3,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        center = float(slot.parameters.get("center", 0.5))
        amp = float(slot.parameters.get("amp", 0.05 + 0.05 * master.movement))
        # high-freq dither + small smoothed component
        noise = perlin_like(t_local, freq_hz=8.0, rng=rng, octaves=3)
        a = center + amp * noise
        b = np.full(n, 0.5) + 0.02 * perlin_like(t_local, freq_hz=4.0, rng=rng, octaves=2)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P12 — Step-Climb
# ---------------------------------------------------------------------------

@dataclass
class PatternP12_StepClimb:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P12",
        name="Step Climb",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(5.0, 30.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.6, "beat_drop": 1.3, "ruin": 1.2,
            "sanfter_aufbau": 0.8, "edging": 1.1, "endlos_tease": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        steps = int(slot.parameters.get("steps", 5))
        steps = max(2, min(8, steps))
        # build step pattern that climbs with small relapses (like 46->59->46->51->71)
        levels = np.linspace(0.3, 0.95, steps)
        # small relapse pattern: insert dips
        seq = []
        for i, lv in enumerate(levels):
            seq.append(lv)
            if i > 0 and i < steps - 1:
                seq.append(lv * 0.85)
        seq = np.array(seq)
        idx = np.clip((t_local / max(t_local[-1], 1e-6) * len(seq)).astype(int), 0, len(seq) - 1)
        a = seq[idx]
        # Couple beta to a slow rotation across the steps so the climb sweeps an arc
        T = max(t_local[-1], 1e-6)
        b = 0.5 + 0.35 * np.sin(np.pi * t_local / T)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P13 — Beta-Buzz auf Alpha-Toggle
# ---------------------------------------------------------------------------

@dataclass
class PatternP13_BetaBuzzAlphaToggle:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P13",
        name="Beta Buzz on Alpha Toggle",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(3.0, 20.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "ruin": 1.7, "beat_drop": 1.5, "crescendo": 1.1,
            "edging": 0.9, "sanfter_aufbau": 0.3, "endlos_tease": 0.5,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        # alpha hard-toggle (slowed from 500ms to 1.5s — was perceptibly jittery)
        toggle_p = float(slot.parameters.get("toggle_period_s", 1.5))
        toggle = (np.floor(t_local / toggle_p) % 2 == 0).astype(float)
        a = 0.04 + 0.91 * toggle
        # beta wobble — 20Hz on position was way too fast (the 50Hz TCode sample
        # rate can't represent it cleanly anyway). Drop to ~2Hz subtle waver.
        buzz_f = float(slot.parameters.get("buzz_hz", 2.0))
        b = 0.5 + 0.30 * np.sin(2 * np.pi * buzz_f * t_local + rng.uniform(0, 2 * np.pi))
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P14 — Rotation mit Frequenzdrift
# ---------------------------------------------------------------------------

@dataclass
class PatternP14_RotationWithDrift:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P14",
        name="Rotation with Frequency Drift",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(20.0, 120.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.5, "crescendo": 1.5, "sanfter_aufbau": 1.2,
            "edging": 1.1, "beat_drop": 0.7, "ruin": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        f0 = float(slot.parameters.get("f_start_hz", 0.15))
        f1 = float(slot.parameters.get("f_end_hz", 0.55))
        radius = float(slot.parameters.get("radius", 0.6))
        # integrate instantaneous frequency to get phase
        T = max(t_local[-1], 1e-6)
        f_inst = f0 + (f1 - f0) * (t_local / T)
        dt = _dt_from(t_local)
        phase = 2 * np.pi * np.cumsum(f_inst) * dt + rng.uniform(0, 2 * np.pi)
        a = 0.5 + radius * 0.5 * np.cos(phase)
        b = 0.5 + radius * 0.5 * np.sin(phase)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# P15 — Position-Phase-Lock zur Beat-Rate
# ---------------------------------------------------------------------------

@dataclass
class PatternP15_BeatPhaseLock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P15",
        name="Beat Phase Lock",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 2.0, "crescendo": 1.4, "ruin": 1.1,
            "edging": 0.8, "sanfter_aufbau": 0.4, "endlos_tease": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        bpm = float(slot.parameters.get("bpm", 90.0))
        # quarter-beat default — half-beat (0.5) at typical BPM was too fast
        ratio = float(slot.parameters.get("beat_ratio", 0.25))
        f = (bpm / 60.0) * ratio
        a = 0.5 + 0.5 * np.cos(2 * np.pi * f * t_local)
        # Beta locked to alpha at +90° so the beat traces a circle
        b = 0.5 + 0.35 * np.sin(2 * np.pi * f * t_local)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# Registry export
# ---------------------------------------------------------------------------

POSITION_PATTERNS = {
    "P1": PatternP1_StaticFloor(),
    "P2": PatternP2_StaticCenter(),
    "P3": PatternP3_CosineBeatLock(),
    "P4": PatternP4_DampedRingdown(),
    "P5": PatternP5_HardToggle(),
    "P6": PatternP6_SlowDrift(),
    "P7": PatternP7_BetaLockPendulum(),
    "P8": PatternP8_FullCircleRotation(),
    "P9": PatternP9_HalfCircleArc(),
    "P10": PatternP10_OffsetHalfStroke(),
    "P11": PatternP11_MicroJitter(),
    "P12": PatternP12_StepClimb(),
    "P13": PatternP13_BetaBuzzAlphaToggle(),
    "P14": PatternP14_RotationWithDrift(),
    "P15": PatternP15_BeatPhaseLock(),
}
