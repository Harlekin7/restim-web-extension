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
    ou_process,
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
        # very slow noise — 8Hz felt jittery, 0.4Hz reads as gentle drift
        noise = perlin_like(t_local, freq_hz=0.4, rng=rng, octaves=2)
        a = center + amp * noise
        b = np.full(n, 0.5) + 0.02 * perlin_like(t_local, freq_hz=0.3, rng=rng, octaves=2)
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
# P16 / P17 / P18 — Hold a single electrode (Neutral / Left / Right pole)
# ---------------------------------------------------------------------------
# In Restim's three-phase phase diagram the electrodes sit at 120° apart
# on the unit circle around (0.5, 0.5). The standard mapping is:
#   Neutral pole (often glans):   (1.000, 0.500)   — pure +alpha
#   Left pole:                    (0.250, 0.933)   — 120° CCW
#   Right pole:                   (0.250, 0.067)   — 120° CW
# These three patterns *hold* the stim concentrated on one electrode for
# the duration of the slot, with only a tiny breathing motion so it doesn't
# read as completely frozen.

_NEUTRAL_POLE = (1.00, 0.50)
_LEFT_POLE    = (0.25, 0.93)
_RIGHT_POLE   = (0.25, 0.07)


def _hold_pole(t_local: np.ndarray, pole: tuple[float, float],
               breath_amp: float, breath_hz: float,
               rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Hold near a target pole with a slow tangential 'breathing' motion."""
    cx, cy = pole
    # Perpendicular breathing: lay it tangential to the radius from the center.
    # Direction from center (0.5,0.5) to pole:
    rx, ry = cx - 0.5, cy - 0.5
    norm = max((rx * rx + ry * ry) ** 0.5, 1e-6)
    rx, ry = rx / norm, ry / norm
    # Tangent vector (90° CCW)
    tx, ty = -ry, rx
    phase0 = float(rng.uniform(0, 2 * np.pi))
    breath = breath_amp * np.sin(2 * np.pi * breath_hz * t_local + phase0)
    a = cx + tx * breath
    b = cy + ty * breath
    return _safe(a), _safe(b)


@dataclass
class PatternP16_HoldNeutral:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P16",
        name="Hold Neutral Pole",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 45.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "edging": 1.7, "endlos_tease": 1.6, "sanfter_aufbau": 1.5,
            "crescendo": 1.4, "ruin": 1.3, "beat_drop": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        a, b = _hold_pole(t_local, _NEUTRAL_POLE, breath_amp=0.04, breath_hz=0.20, rng=rng)
        return {AxisName.ALPHA: a, AxisName.BETA: b}


@dataclass
class PatternP17_HoldLeft:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P17",
        name="Hold Left Pole",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 45.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "edging": 1.7, "endlos_tease": 1.6, "sanfter_aufbau": 1.5,
            "crescendo": 1.4, "ruin": 1.3, "beat_drop": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        a, b = _hold_pole(t_local, _LEFT_POLE, breath_amp=0.04, breath_hz=0.20, rng=rng)
        return {AxisName.ALPHA: a, AxisName.BETA: b}


@dataclass
class PatternP18_HoldRight:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P18",
        name="Hold Right Pole",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 45.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "edging": 1.7, "endlos_tease": 1.6, "sanfter_aufbau": 1.5,
            "crescendo": 1.4, "ruin": 1.3, "beat_drop": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        a, b = _hold_pole(t_local, _RIGHT_POLE, breath_amp=0.04, breath_hz=0.20, rng=rng)
        return {AxisName.ALPHA: a, AxisName.BETA: b}


# ---------------------------------------------------------------------------
# P19 — Triadic Step Cycle (slow walk through all three electrode poles)
# ---------------------------------------------------------------------------

@dataclass
class PatternP19_TriadicStepCycle:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P19",
        name="Triadic Step Cycle",
        category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(15.0, 90.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.8, "edging": 1.7, "sanfter_aufbau": 1.6,
            "crescendo": 1.4, "ruin": 1.2, "beat_drop": 1.1,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        # Hold each pole for ~6s, smoothly transition over ~2s
        hold_s = float(slot.parameters.get("hold_s", 6.0))
        trans_s = float(slot.parameters.get("transition_s", 2.0))
        order = slot.parameters.get("order", None)
        poles = [_NEUTRAL_POLE, _LEFT_POLE, _RIGHT_POLE]
        if order is None:
            # Random rotation direction so successive slots differ
            if rng.random() < 0.5:
                poles = [_NEUTRAL_POLE, _LEFT_POLE, _RIGHT_POLE]
            else:
                poles = [_NEUTRAL_POLE, _RIGHT_POLE, _LEFT_POLE]

        cycle_len = hold_s + trans_s
        a_out = np.empty_like(t_local)
        b_out = np.empty_like(t_local)
        for i, t in enumerate(t_local):
            phase_in_cycle = t % (cycle_len * len(poles))
            pole_idx = int(phase_in_cycle // cycle_len)
            local_t = phase_in_cycle - pole_idx * cycle_len
            cur_pole = poles[pole_idx]
            next_pole = poles[(pole_idx + 1) % len(poles)]
            if local_t < hold_s:
                a_out[i] = cur_pole[0]
                b_out[i] = cur_pole[1]
            else:
                # smooth ease-in-out between cur and next
                u = (local_t - hold_s) / max(trans_s, 1e-6)
                u = 0.5 - 0.5 * np.cos(np.pi * u)  # smoothstep
                a_out[i] = cur_pole[0] * (1 - u) + next_pole[0] * u
                b_out[i] = cur_pole[1] * (1 - u) + next_pole[1] * u
        return {AxisName.ALPHA: _safe(a_out), AxisName.BETA: _safe(b_out)}


# =====================================================================
# Restim-derived patterns (ports from references/restim/qt_ui/patterns/threephase/)
# Convention: Restim returns (x, y) in [-1, +1] around a center; we map to
#             alpha = 0.5 + 0.5*x, beta = 0.5 + 0.5*y
# =====================================================================

def _to_unit(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert Restim's [-1,+1] coords to our [0,1] alpha/beta."""
    return _safe(0.5 + 0.5 * x), _safe(0.5 + 0.5 * y)


@dataclass
class PatternP20_RestimCircle:
    """Smooth full circle (port of Restim's CirclePattern)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P20", name="Restim Circle", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 60.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"endlos_tease": 1.4, "sanfter_aufbau": 1.4, "edging": 1.3,
                        "crescendo": 1.2, "ruin": 1.0, "beat_drop": 0.9},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.4 + 0.4 * master.movement))
        amp = float(slot.parameters.get("amplitude", 0.6 + 0.3 * master.movement))
        phase0 = rng.uniform(0, 2 * np.pi)
        x = amp * np.cos(velocity * t_local + phase0)
        y = amp * np.sin(velocity * t_local + phase0)
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP21_FigureEight:
    """Figure-8 (port of Restim's FigureEightPattern)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P21", name="Figure 8", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 45.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"endlos_tease": 1.5, "edging": 1.4, "sanfter_aufbau": 1.3,
                        "crescendo": 1.2, "ruin": 1.0, "beat_drop": 1.0},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.5 + 0.4 * master.movement))
        amp = float(slot.parameters.get("amplitude", 0.7))
        ang = velocity * t_local + rng.uniform(0, 2 * np.pi)
        y = np.sin(ang) * amp
        x = 0.5 * np.sin(2 * ang) * amp
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP22_MicroCircles:
    """Tiny circles drifting around inside the unit (port of MicroCirclesPattern)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P22", name="Micro Circles", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 60.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"edging": 1.6, "endlos_tease": 1.5, "sanfter_aufbau": 1.3,
                        "ruin": 1.0, "crescendo": 0.9, "beat_drop": 0.7},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.5))
        circle_r = float(slot.parameters.get("circle_radius", 0.18))
        t = velocity * t_local
        # Slow drift of the micro-circle origin
        ox = 0.4 * np.sin(t * 0.1) + 0.3 * np.sin(t * 0.07)
        oy = 0.3 * np.cos(t * 0.08) + 0.2 * np.cos(t * 0.12)
        # Small circular motion around the drifting origin (but not too fast)
        size_mod = 0.8 + 0.4 * np.sin(t * 0.3)
        cx = circle_r * np.cos(t * 1.3) * size_mod
        cy = circle_r * np.sin(t * 1.3) * size_mod
        x = ox + cx
        y = oy + cy
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP23_TriPhasePanning:
    """Triphase panning (port of PanningPattern1) — sweeps along the 120° arc."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P23", name="Tri-Phase Panning", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 60.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"endlos_tease": 1.6, "sanfter_aufbau": 1.5, "edging": 1.4,
                        "crescendo": 1.2, "beat_drop": 1.0, "ruin": 1.0},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.15 + 0.15 * master.movement))
        amp = float(slot.parameters.get("amplitude", 0.85))
        t = velocity * t_local + rng.uniform(0, 2 * np.pi)
        base = np.sin(2 * np.pi * t) * (np.pi * 120 / 180)  # ~±2.09 rad sweep
        x = np.cos(base) * amp
        y = np.sin(base) * amp
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP24_VerticalOscillation:
    """Slow alpha sweep + faster beta wobble (port of VerticalOscillation)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P24", name="Vertical Oscillation", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 40.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"crescendo": 1.4, "edging": 1.3, "endlos_tease": 1.2,
                        "ruin": 1.2, "sanfter_aufbau": 1.0, "beat_drop": 1.1},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.4))
        t = velocity * t_local
        x = np.sin(2 * np.pi * 0.25 * t) * 0.85          # slow main motion
        y = 0.20 * np.sin(2 * np.pi * 1.5 * t)           # gentle wobble (was 5Hz)
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP25_DeepThrob:
    """Deep slow throb (port of DeepThrobPattern, simplified)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P25", name="Deep Throb", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(15.0, 90.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"edging": 1.6, "endlos_tease": 1.5, "sanfter_aufbau": 1.4,
                        "crescendo": 1.1, "ruin": 1.1, "beat_drop": 0.7},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.4))
        t = velocity * t_local * 0.4
        cycle = (t * 0.8) % (2 * np.pi)
        # Smooth raised-cosine throb
        intensity = np.where(cycle < np.pi,
                             np.sin(cycle / np.pi * np.pi) ** 2,
                             (1.0 - (cycle - np.pi) / np.pi) ** 2)
        x = -0.20 + 1.10 * intensity  # extends from a bit negative to ~+0.9
        y = 0.10 * np.sin(t * 0.6) + 0.05 * np.sin(t * 1.1)
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP26_RoseCurve:
    """5-petal rose (port of RoseCurvePattern)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P26", name="Rose Curve", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(15.0, 90.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"endlos_tease": 1.6, "edging": 1.4, "crescendo": 1.3,
                        "sanfter_aufbau": 1.2, "ruin": 1.0, "beat_drop": 0.8},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.25 + 0.15 * master.movement))
        n = float(slot.parameters.get("petals", 5))
        amp = float(slot.parameters.get("amplitude", 0.8))
        theta = velocity * t_local + rng.uniform(0, 2 * np.pi)
        r = np.abs(np.cos(n * theta))
        x = r * np.cos(theta) * amp
        y = r * np.sin(theta) * amp
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP27_RandomWalk:
    """Bounded random walk with center-pull (port of RandomWalkPattern)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P27", name="Random Walk", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 45.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"endlos_tease": 1.4, "edging": 1.3, "ruin": 1.2,
                        "sanfter_aufbau": 1.1, "crescendo": 1.0, "beat_drop": 0.6},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.4))
        n = len(t_local)
        # Generate via OU process for smooth bounded random walk
        x = ou_process(n, dt=_dt_from(t_local), mean=0.0, sigma=0.5 * velocity,
                       theta=0.4, rng=rng) * 0.7
        y = ou_process(n, dt=_dt_from(t_local), mean=0.0, sigma=0.5 * velocity,
                       theta=0.4, rng=rng) * 0.7
        x = np.clip(x, -1.0, 1.0)
        y = np.clip(y, -1.0, 1.0)
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP28_Spirograph:
    """Inner-circle inside outer-circle (Restim Spirograph, simplified)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P28", name="Spirograph", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(15.0, 90.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"endlos_tease": 1.5, "edging": 1.3, "sanfter_aufbau": 1.2,
                        "crescendo": 1.1, "beat_drop": 0.9, "ruin": 1.0},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.3))
        R = float(slot.parameters.get("R", 0.6))
        r = float(slot.parameters.get("r", 0.20))
        d = float(slot.parameters.get("d", 0.25))
        t = velocity * t_local + rng.uniform(0, 2 * np.pi)
        x = (R - r) * np.cos(t) + d * np.cos((R - r) / r * t)
        y = (R - r) * np.sin(t) - d * np.sin((R - r) / r * t)
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP29_TremorCircle:
    """Circle with small tremor on top (port of TremorCirclePattern)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P29", name="Tremor Circle", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 40.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"edging": 1.4, "ruin": 1.3, "endlos_tease": 1.2,
                        "crescendo": 1.1, "beat_drop": 1.0, "sanfter_aufbau": 0.8},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.4))
        amp = float(slot.parameters.get("amplitude", 0.55))
        t = velocity * t_local + rng.uniform(0, 2 * np.pi)
        cx = amp * np.cos(t)
        cy = amp * np.sin(t)
        # Tiny tremor (~3Hz, 3% amplitude)
        tx = 0.03 * np.sin(2 * np.pi * 3.0 * t_local)
        ty = 0.03 * np.cos(2 * np.pi * 3.0 * t_local + 1.0)
        x = cx + tx
        y = cy + ty
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x, y)))


@dataclass
class PatternP30_WShape:
    """W-shape sweep (port of WShapePattern)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P30", name="W-Shape Sweep", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 40.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"crescendo": 1.5, "beat_drop": 1.4, "ruin": 1.3,
                        "edging": 1.0, "endlos_tease": 0.9, "sanfter_aufbau": 0.8},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        velocity = float(slot.parameters.get("velocity", 0.4))
        amp = float(slot.parameters.get("amplitude", 0.85))
        t = (velocity * t_local) % (4 * np.pi)
        # Triangular sawtooth on alpha + sweep on beta
        x = 1.0 - (np.abs(((t / (2 * np.pi) * 4) % 4) - 2) - 0)  # tent function
        y = np.sin(t * 0.5) * 0.6
        return dict(zip([AxisName.ALPHA, AxisName.BETA], _to_unit(x * amp, y * amp)))


# =====================================================================
# Edge-of-pole patterns: small angular oscillations *at* an electrode
# These are exactly what the user asked for: "directly at the edge of one
# electrode, just a few degrees left/right oscillation". The stim stays
# clearly *on* one pole but micro-modulates around it.
# =====================================================================

def _polar_at_pole(pole: tuple[float, float], radial: float, angular_offset: float
                   ) -> tuple[float, float]:
    """Return (x_unit, y_unit) at offset (radial, angular) from a pole.

    pole is given in our [0,1] coords. The angular_offset rotates the radial
    direction around the center (0.5, 0.5)."""
    cx, cy = pole[0] - 0.5, pole[1] - 0.5
    pole_angle = np.arctan2(cy, cx)
    pole_r = (cx * cx + cy * cy) ** 0.5
    new_r = pole_r + radial
    new_angle = pole_angle + angular_offset
    x = 0.5 + new_r * np.cos(new_angle)
    y = 0.5 + new_r * np.sin(new_angle)
    return x, y


@dataclass
class PatternP31_EdgeWobbleNeutral:
    """Tiny ±5° angular wobble *on* the Neutral electrode."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P31", name="Edge Wobble Neutral", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 40.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"edging": 1.7, "endlos_tease": 1.6, "sanfter_aufbau": 1.4,
                        "crescendo": 1.3, "ruin": 1.2, "beat_drop": 1.0},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        # 5° = 0.087 rad. Multiplied by master.movement so Wandernd-slider matters.
        wobble_amp = float(slot.parameters.get("wobble_rad",
                                               np.deg2rad(3.0 + 7.0 * master.movement)))
        velocity = float(slot.parameters.get("velocity", 0.25 + 0.20 * master.movement))
        offset = wobble_amp * np.sin(2 * np.pi * velocity * t_local)
        # vectorised polar offset around Neutral pole
        cx, cy = _NEUTRAL_POLE[0] - 0.5, _NEUTRAL_POLE[1] - 0.5
        pole_r = (cx * cx + cy * cy) ** 0.5
        pole_angle = np.arctan2(cy, cx)
        new_angle = pole_angle + offset
        x = 0.5 + pole_r * np.cos(new_angle)
        y = 0.5 + pole_r * np.sin(new_angle)
        return {AxisName.ALPHA: _safe(x), AxisName.BETA: _safe(y)}


@dataclass
class PatternP32_EdgeWobbleLeft:
    """Tiny ±5° angular wobble *on* the Left electrode."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P32", name="Edge Wobble Left", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 40.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"edging": 1.7, "endlos_tease": 1.6, "sanfter_aufbau": 1.4,
                        "crescendo": 1.3, "ruin": 1.2, "beat_drop": 1.0},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        wobble_amp = float(slot.parameters.get("wobble_rad",
                                               np.deg2rad(3.0 + 7.0 * master.movement)))
        velocity = float(slot.parameters.get("velocity", 0.25 + 0.20 * master.movement))
        offset = wobble_amp * np.sin(2 * np.pi * velocity * t_local)
        cx, cy = _LEFT_POLE[0] - 0.5, _LEFT_POLE[1] - 0.5
        pole_r = (cx * cx + cy * cy) ** 0.5
        pole_angle = np.arctan2(cy, cx)
        new_angle = pole_angle + offset
        x = 0.5 + pole_r * np.cos(new_angle)
        y = 0.5 + pole_r * np.sin(new_angle)
        return {AxisName.ALPHA: _safe(x), AxisName.BETA: _safe(y)}


@dataclass
class PatternP33_EdgeWobbleRight:
    """Tiny ±5° angular wobble *on* the Right electrode."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P33", name="Edge Wobble Right", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(8.0, 40.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"edging": 1.7, "endlos_tease": 1.6, "sanfter_aufbau": 1.4,
                        "crescendo": 1.3, "ruin": 1.2, "beat_drop": 1.0},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        wobble_amp = float(slot.parameters.get("wobble_rad",
                                               np.deg2rad(3.0 + 7.0 * master.movement)))
        velocity = float(slot.parameters.get("velocity", 0.25 + 0.20 * master.movement))
        offset = wobble_amp * np.sin(2 * np.pi * velocity * t_local)
        cx, cy = _RIGHT_POLE[0] - 0.5, _RIGHT_POLE[1] - 0.5
        pole_r = (cx * cx + cy * cy) ** 0.5
        pole_angle = np.arctan2(cy, cx)
        new_angle = pole_angle + offset
        x = 0.5 + pole_r * np.cos(new_angle)
        y = 0.5 + pole_r * np.sin(new_angle)
        return {AxisName.ALPHA: _safe(x), AxisName.BETA: _safe(y)}


@dataclass
class PatternP34_TwoPoleTease:
    """Slow oscillation between two adjacent poles, never touching the third."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P34", name="Two-Pole Tease", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 60.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={"edging": 1.7, "endlos_tease": 1.6, "sanfter_aufbau": 1.3,
                        "crescendo": 1.2, "ruin": 1.0, "beat_drop": 0.9},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        # Pick two of the three poles randomly (per slot, deterministically via rng)
        pair_idx = int(rng.integers(0, 3))
        pairs = [(_NEUTRAL_POLE, _LEFT_POLE),
                 (_LEFT_POLE, _RIGHT_POLE),
                 (_RIGHT_POLE, _NEUTRAL_POLE)]
        p1, p2 = pairs[pair_idx]
        # Slow ease-in-out between p1 and p2
        velocity = float(slot.parameters.get("velocity", 0.10 + 0.10 * master.movement))
        u = 0.5 - 0.5 * np.cos(2 * np.pi * velocity * t_local)
        x = p1[0] * (1 - u) + p2[0] * u
        y = p1[1] * (1 - u) + p2[1] * u
        return {AxisName.ALPHA: _safe(x), AxisName.BETA: _safe(y)}


@dataclass
class PatternP35_PoleEdgeSlide:
    """Slow linear slide along the edge of one pole (radial in/out + slight angular drift)."""
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="P35", name="Pole Edge Slide", category=PatternCategory.POSITION,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 50.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={"edging": 1.6, "endlos_tease": 1.5, "sanfter_aufbau": 1.3,
                        "crescendo": 1.2, "ruin": 1.1, "beat_drop": 0.9},
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        # pick a pole at random for this slot
        pole = (_NEUTRAL_POLE, _LEFT_POLE, _RIGHT_POLE)[int(rng.integers(0, 3))]
        velocity = float(slot.parameters.get("velocity", 0.15))
        # Radial in/out: pole-edge to ~70% of pole distance and back
        cx, cy = pole[0] - 0.5, pole[1] - 0.5
        pole_r = (cx * cx + cy * cy) ** 0.5
        pole_angle = np.arctan2(cy, cx)
        slide_u = 0.5 - 0.5 * np.cos(2 * np.pi * velocity * t_local)  # 0..1
        r = pole_r * (0.55 + 0.45 * slide_u)
        # Mild angular wander ±2°
        ang = pole_angle + np.deg2rad(2.0) * np.sin(2 * np.pi * velocity * 0.7 * t_local)
        x = 0.5 + r * np.cos(ang)
        y = 0.5 + r * np.sin(ang)
        return {AxisName.ALPHA: _safe(x), AxisName.BETA: _safe(y)}


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
    "P16": PatternP16_HoldNeutral(),
    "P17": PatternP17_HoldLeft(),
    "P18": PatternP18_HoldRight(),
    "P19": PatternP19_TriadicStepCycle(),
    # Restim-derived
    "P20": PatternP20_RestimCircle(),
    "P21": PatternP21_FigureEight(),
    "P22": PatternP22_MicroCircles(),
    "P23": PatternP23_TriPhasePanning(),
    "P24": PatternP24_VerticalOscillation(),
    "P25": PatternP25_DeepThrob(),
    "P26": PatternP26_RoseCurve(),
    "P27": PatternP27_RandomWalk(),
    "P28": PatternP28_Spirograph(),
    "P29": PatternP29_TremorCircle(),
    "P30": PatternP30_WShape(),
    # Edge-of-pole micro-targeting
    "P31": PatternP31_EdgeWobbleNeutral(),
    "P32": PatternP32_EdgeWobbleLeft(),
    "P33": PatternP33_EdgeWobbleRight(),
    "P34": PatternP34_TwoPoleTease(),
    "P35": PatternP35_PoleEdgeSlide(),
}
