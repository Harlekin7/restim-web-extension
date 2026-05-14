"""Multi-axis composite patterns M1..M15.

These patterns drive 2+ axes simultaneously with explicit coupling.
M3 / M5 / M6 / M7 require sub-channels (-prostate, -stereostim, e1..e4) and
are emitted on the *available* primary axes only — secondary channels are
consumed by downstream multi-channel renderers.
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


def _dt_from(t: np.ndarray) -> float:
    if t.size < 2:
        return 0.02
    return float(t[1] - t[0])


def _safe(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0.0, 1.0)


# ---------------------------------------------------------------------------
# M1 — Triple-Sync Build (Volume + Carrier + PulseWidth)
# ---------------------------------------------------------------------------

@dataclass
class PatternM1_TripleSyncBuild:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M1",
        name="Triple Sync Build (Vol+Car+PW)",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.VOLUME, AxisName.CARRIER, AxisName.PULSE_WIDTH),
        duration_range_s=(60.0, 1200.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.9, "sanfter_aufbau": 1.4, "ruin": 1.4,
            "beat_drop": 1.0, "edging": 0.9, "endlos_tease": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_start = float(slot.parameters.get("v_start", 0.40))
        v_end = float(slot.parameters.get("v_end", 0.95))
        c_start = float(slot.parameters.get("c_start", 0.55))
        c_end = float(slot.parameters.get("c_end", 0.88))
        pw_start = float(slot.parameters.get("pw_start", 0.20))
        pw_end = float(slot.parameters.get("pw_end", 0.55))
        return {
            AxisName.VOLUME: _safe(np.linspace(v_start, v_end, n)),
            AxisName.CARRIER: _safe(np.linspace(c_start, c_end, n)),
            AxisName.PULSE_WIDTH: _safe(np.linspace(pw_start, pw_end, n)),
        }


# ---------------------------------------------------------------------------
# M2 — Position-Pulse-Frequency Lock
# ---------------------------------------------------------------------------

@dataclass
class PatternM2_PositionPulseFreqLock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M2",
        name="Position ↔ Pulse-Freq Lock",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA, AxisName.PULSE_FREQUENCY),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.7, "crescendo": 1.4, "ruin": 1.2,
            "edging": 0.9, "sanfter_aufbau": 0.6, "endlos_tease": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 0.8))
        f = 1.0 / max(0.3, period)
        wave = 0.5 + 0.5 * np.cos(2 * np.pi * f * t_local)
        return {
            AxisName.ALPHA: _safe(wave),
            AxisName.BETA: np.full(n, 0.5),
            AxisName.PULSE_FREQUENCY: _safe(0.40 + 0.45 * wave),
        }


# ---------------------------------------------------------------------------
# M3 — Mirror Prostate Channel (alpha-prostate = -alpha)
# Renders inverted alpha on the alpha primary if no sub-channel is registered.
# ---------------------------------------------------------------------------

@dataclass
class PatternM3_MirrorProstate:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M3",
        name="Mirror Prostate Channel",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 120.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        required_caps={"prostate_channel": True},
        style_affinity={
            "endlos_tease": 1.2, "edging": 1.2, "crescendo": 1.0,
            "ruin": 1.0, "sanfter_aufbau": 1.0, "beat_drop": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 1.0))
        f = 1.0 / max(0.3, period)
        # wave for primary alpha
        a = 0.5 + 0.45 * np.sin(2 * np.pi * f * t_local)
        # mirrored counterpart appears in beta-driven layout if main hardware
        # only has alpha/beta; we expose it as small inverse beta jitter
        b = 1.0 - a
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# M4 — Parallel Prostate Channel
# ---------------------------------------------------------------------------

@dataclass
class PatternM4_ParallelProstate:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M4",
        name="Parallel Prostate Channel",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 120.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        required_caps={"prostate_channel": True},
        style_affinity={
            "crescendo": 1.2, "ruin": 1.2, "sanfter_aufbau": 1.0,
            "edging": 1.0, "endlos_tease": 1.0, "beat_drop": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 1.0))
        f = 1.0 / max(0.3, period)
        a = 0.5 + 0.45 * np.sin(2 * np.pi * f * t_local)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(np.copy(a))}


# ---------------------------------------------------------------------------
# M5 — Secondary-Volume-Floor (Stereostim, never below 50%)
# ---------------------------------------------------------------------------

@dataclass
class PatternM5_SecondaryVolumeFloor:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M5",
        name="Secondary Volume Floor",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(15.0, 600.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        required_caps={"stereostim_channel": True},
        style_affinity={
            "endlos_tease": 1.3, "edging": 1.2, "crescendo": 1.2,
            "sanfter_aufbau": 1.1, "beat_drop": 1.0, "ruin": 1.1,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        floor = float(slot.parameters.get("floor", 0.50))
        v = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            v[i] = max(floor, float(mc.intensity))
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# M6 — 4-Phasen Round Robin (E1-E4 simulated on alpha/beta vector)
# ---------------------------------------------------------------------------

@dataclass
class PatternM6_FourPhaseRoundRobin:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M6",
        name="4-Phase Round Robin",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA),
        duration_range_s=(10.0, 120.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        required_caps={"four_phase": True},
        style_affinity={
            "endlos_tease": 1.5, "crescendo": 1.2, "ruin": 1.1,
            "edging": 1.1, "sanfter_aufbau": 1.0, "beat_drop": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 1.6))
        radius = float(slot.parameters.get("radius", 0.85))
        f = 1.0 / max(0.4, period)
        # 4-phase: rotating around the unit circle hits each electrode in turn
        a, b = rotating_position(t_local, f, radius, 0.0)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b)}


# ---------------------------------------------------------------------------
# M7 — E1 Position Coupling
# ---------------------------------------------------------------------------

@dataclass
class PatternM7_E1PositionCoupling:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M7",
        name="E1 Position Coupling",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA, AxisName.PULSE_FREQUENCY),
        duration_range_s=(10.0, 120.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        required_caps={"four_phase": True},
        style_affinity={
            "crescendo": 1.3, "edging": 1.1, "endlos_tease": 1.1,
            "sanfter_aufbau": 1.0, "beat_drop": 1.0, "ruin": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 1.0))
        f = 1.0 / max(0.3, period)
        wave = 0.5 + 0.5 * np.sin(2 * np.pi * f * t_local)
        return {
            AxisName.ALPHA: _safe(wave),
            AxisName.BETA: _safe(1.0 - 0.5 * wave),
            AxisName.PULSE_FREQUENCY: _safe(0.40 + 0.40 * wave),
        }


# ---------------------------------------------------------------------------
# M8 — Volume Drives Everything
# ---------------------------------------------------------------------------

@dataclass
class PatternM8_VolumeDrivesEverything:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M8",
        name="Volume Drives Everything",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.VOLUME, AxisName.CARRIER, AxisName.PULSE_FREQUENCY,
                   AxisName.PULSE_WIDTH, AxisName.PULSE_RISE_TIME),
        duration_range_s=(30.0, 1200.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.7, "ruin": 1.4, "sanfter_aufbau": 1.3,
            "beat_drop": 1.0, "edging": 0.9, "endlos_tease": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v = np.empty(n); c = np.empty(n); pf = np.empty(n)
        pw = np.empty(n); pr = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            inten = float(mc.intensity)
            v[i] = inten
            c[i] = 0.50 + 0.40 * inten
            pf[i] = 0.40 + 0.45 * inten
            pw[i] = 0.20 + 0.50 * inten
            pr[i] = 0.65 - 0.55 * inten
        return {
            AxisName.VOLUME: _safe(v),
            AxisName.CARRIER: _safe(c),
            AxisName.PULSE_FREQUENCY: _safe(pf),
            AxisName.PULSE_WIDTH: _safe(pw),
            AxisName.PULSE_RISE_TIME: _safe(pr),
        }


# ---------------------------------------------------------------------------
# M9 — Position-Independent Volume
# ---------------------------------------------------------------------------

@dataclass
class PatternM9_PositionIndependentVolume:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M9",
        name="Position-Independent Volume",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA, AxisName.VOLUME),
        duration_range_s=(20.0, 600.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.5, "edging": 1.4, "sanfter_aufbau": 1.2,
            "crescendo": 0.9, "beat_drop": 0.7, "ruin": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # rotate position slowly; volume independently builds with random walk
        period = float(slot.parameters.get("period_s", 4.0))
        f = 1.0 / max(0.5, period)
        a = 0.5 + 0.45 * np.cos(2 * np.pi * f * t_local + rng.uniform(0, 2*np.pi))
        b = 0.5 + 0.45 * np.sin(2 * np.pi * f * t_local + rng.uniform(0, 2*np.pi))
        v = np.full(n, master.intensity) + 0.05 * perlin_like(t_local, 0.05, rng, 2)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b), AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# M10 — Inverse Volume vs Alpha
# ---------------------------------------------------------------------------

@dataclass
class PatternM10_InverseVolumeAlpha:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M10",
        name="Inverse Volume vs Alpha",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.VOLUME),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "edging": 1.4, "ruin": 1.2, "endlos_tease": 1.1,
            "crescendo": 0.8, "beat_drop": 1.0, "sanfter_aufbau": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 1.5))
        f = 1.0 / max(0.5, period)
        a = 0.5 + 0.45 * np.sin(2 * np.pi * f * t_local)
        v = master.intensity * (1.0 - 0.4 * a)
        return {AxisName.ALPHA: _safe(a), AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# M11 — Pulse-Rise–Frequency Anti-Lock
# ---------------------------------------------------------------------------

@dataclass
class PatternM11_PulseRiseFreqAntiLock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M11",
        name="Pulse-Rise / Carrier Anti-Lock",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.CARRIER, AxisName.PULSE_RISE_TIME),
        duration_range_s=(15.0, 600.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.5, "ruin": 1.4, "sanfter_aufbau": 1.2,
            "beat_drop": 1.0, "edging": 0.9, "endlos_tease": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        c = np.empty(n); pr = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            sharp = float(mc.sharpness)
            c[i] = 0.50 + 0.40 * sharp
            pr[i] = 0.65 - 0.55 * sharp
        return {AxisName.CARRIER: _safe(c), AxisName.PULSE_RISE_TIME: _safe(pr)}


# ---------------------------------------------------------------------------
# M12 — Carrier-Position Modulation
# ---------------------------------------------------------------------------

@dataclass
class PatternM12_CarrierPositionMod:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M12",
        name="Carrier-Position Modulation",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA, AxisName.CARRIER),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.5, "crescendo": 1.3, "ruin": 1.2,
            "edging": 1.0, "endlos_tease": 0.9, "sanfter_aufbau": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 1.0))
        f = 1.0 / max(0.4, period)
        a = 0.5 + 0.45 * np.cos(2 * np.pi * f * t_local)
        b = np.full(n, 0.5)
        c_center = float(slot.parameters.get("c_center", 0.70))
        c = c_center + 0.15 * np.sin(2 * np.pi * f * t_local)
        return {AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b), AxisName.CARRIER: _safe(c)}


# ---------------------------------------------------------------------------
# M13 — Pulse-Width Frequency Co-Lock
# ---------------------------------------------------------------------------

@dataclass
class PatternM13_PWFreqCoLock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M13",
        name="Pulse-Width / Carrier Co-Lock",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.PULSE_WIDTH, AxisName.CARRIER),
        duration_range_s=(15.0, 300.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.4, "ruin": 1.2, "sanfter_aufbau": 1.1,
            "beat_drop": 1.0, "edging": 0.9, "endlos_tease": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        pw = np.empty(n); c = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            inten = float(mc.intensity)
            sharp = float(mc.sharpness)
            x = 0.5 * (inten + sharp)
            pw[i] = 0.20 + 0.50 * x
            c[i] = 0.50 + 0.40 * x
        return {AxisName.PULSE_WIDTH: _safe(pw), AxisName.CARRIER: _safe(c)}


# ---------------------------------------------------------------------------
# M14 — Independent Position vs Pulse
# ---------------------------------------------------------------------------

@dataclass
class PatternM14_IndependentPosVsPulse:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M14",
        name="Independent Position vs Pulse",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.ALPHA, AxisName.BETA, AxisName.PULSE_FREQUENCY, AxisName.PULSE_WIDTH),
        duration_range_s=(15.0, 120.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.5, "edging": 1.3, "sanfter_aufbau": 1.0,
            "crescendo": 0.9, "beat_drop": 0.7, "ruin": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # Position rotates fast; pulse axes drift slowly via OU-like perlin.
        period = float(slot.parameters.get("period_s", 0.9))
        f = 1.0 / max(0.4, period)
        ph = rng.uniform(0, 2*np.pi)
        a = 0.5 + 0.45 * np.cos(2*np.pi*f*t_local + ph)
        b = 0.5 + 0.45 * np.sin(2*np.pi*f*t_local + ph)
        pf = 0.55 + 0.15 * perlin_like(t_local, 0.10, rng, 2)
        pw = 0.40 + 0.10 * perlin_like(t_local, 0.07, rng, 2)
        return {
            AxisName.ALPHA: _safe(a), AxisName.BETA: _safe(b),
            AxisName.PULSE_FREQUENCY: _safe(pf), AxisName.PULSE_WIDTH: _safe(pw),
        }


# ---------------------------------------------------------------------------
# M15 — Phase Lead/Lag between Volume and PulseFreq
# ---------------------------------------------------------------------------

@dataclass
class PatternM15_PhaseLeadLag:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="M15",
        name="Phase Lead/Lag (Vol ↔ PF)",
        category=PatternCategory.MULTI_AXIS,
        axes_used=(AxisName.VOLUME, AxisName.PULSE_FREQUENCY),
        duration_range_s=(15.0, 300.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "crescendo": 1.4, "edging": 1.2, "endlos_tease": 1.1,
            "ruin": 1.0, "sanfter_aufbau": 1.0, "beat_drop": 1.1,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 6.0))
        lag_s = float(slot.parameters.get("lag_s", 1.2))
        f = 1.0 / max(1.0, period)
        center = float(master.intensity)
        v = center + 0.15 * np.sin(2*np.pi*f*t_local)
        pf = 0.55 + 0.20 * np.sin(2*np.pi*f*(t_local - lag_s))
        return {AxisName.VOLUME: _safe(v), AxisName.PULSE_FREQUENCY: _safe(pf)}


# ---------------------------------------------------------------------------
# Registry export
# ---------------------------------------------------------------------------

MULTI_AXIS_PATTERNS = {
    "M1": PatternM1_TripleSyncBuild(),
    "M2": PatternM2_PositionPulseFreqLock(),
    "M3": PatternM3_MirrorProstate(),
    "M4": PatternM4_ParallelProstate(),
    "M5": PatternM5_SecondaryVolumeFloor(),
    "M6": PatternM6_FourPhaseRoundRobin(),
    "M7": PatternM7_E1PositionCoupling(),
    "M8": PatternM8_VolumeDrivesEverything(),
    "M9": PatternM9_PositionIndependentVolume(),
    "M10": PatternM10_InverseVolumeAlpha(),
    "M11": PatternM11_PulseRiseFreqAntiLock(),
    "M12": PatternM12_CarrierPositionMod(),
    "M13": PatternM13_PWFreqCoLock(),
    "M14": PatternM14_IndependentPosVsPulse(),
    "M15": PatternM15_PhaseLeadLag(),
}
