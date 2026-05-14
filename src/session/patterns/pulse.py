"""Pulse patterns — frequency / width / rise-time and mixed-pulse patterns.

PF1..PF5 — pulse_frequency
PW1..PW5 — pulse_width
PR1..PR4 — pulse_rise_time
PMix1..PMix3 — combined pulse-axis envelopes (Hard-Click / Soft / Triple-Lock)
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
    slew_smooth,
)
from ..types import AxisName, PatternCategory, PhaseName


def _dt_from(t: np.ndarray) -> float:
    if t.size < 2:
        return 0.02
    return float(t[1] - t[0])


def _safe(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0.0, 1.0)


# =============================================================================
# Pulse Frequency Patterns (PF1..PF5)
# =============================================================================

@dataclass
class PatternPF1_SinusPulseFreq:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PF1",
        name="Sinus Pulse-Freq Sync to Position",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY,),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.6, "crescendo": 1.4, "ruin": 1.3,
            "edging": 1.0, "sanfter_aufbau": 0.7, "endlos_tease": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        period = float(slot.parameters.get("period_s", 0.7))
        center = float(slot.parameters.get("center", 0.55 + 0.2 * master.hardness))
        amp = float(slot.parameters.get("amp", 0.20))
        f = 1.0 / max(0.3, period)
        v = center + amp * np.cos(2 * np.pi * f * t_local)
        return {AxisName.PULSE_FREQUENCY: _safe(v)}


@dataclass
class PatternPF2_InversePulseFreq:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PF2",
        name="Inverse Pulse-Freq Pendulum",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY,),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "edging": 1.4, "endlos_tease": 1.2, "sanfter_aufbau": 1.0,
            "crescendo": 0.9, "beat_drop": 0.8, "ruin": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        period = float(slot.parameters.get("period_s", 1.2))
        center = float(slot.parameters.get("center", 0.55))
        amp = float(slot.parameters.get("amp", 0.15))
        f = 1.0 / max(0.3, period)
        v = center - amp * np.sin(2 * np.pi * f * t_local)
        return {AxisName.PULSE_FREQUENCY: _safe(v)}


@dataclass
class PatternPF3_StepSwitchPF:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PF3",
        name="Step-Switch Pulse-Freq Plateaus",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY,),
        duration_range_s=(10.0, 120.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "beat_drop": 1.5, "edging": 1.3, "crescendo": 1.2,
            "ruin": 1.1, "sanfter_aufbau": 0.5, "endlos_tease": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        levels = slot.parameters.get("levels", [0.35, 0.50, 0.80, 1.00])
        levels = np.array(levels, dtype=float)
        dwell = float(slot.parameters.get("dwell_s", 4.0))
        v = np.empty(n)
        for i, t in enumerate(t_local):
            idx = int((t / dwell)) % len(levels)
            v[i] = levels[idx]
        v = slew_smooth(v, prev_value=v[0], max_change_per_sample=0.20)
        return {AxisName.PULSE_FREQUENCY: _safe(v)}


@dataclass
class PatternPF4_SlowBuildPF:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PF4",
        name="Slow Build Pulse-Freq",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY,),
        duration_range_s=(30.0, 600.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU),
        style_affinity={
            "sanfter_aufbau": 1.6, "crescendo": 1.5, "endlos_tease": 1.1,
            "edging": 0.9, "beat_drop": 0.6, "ruin": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_start = float(slot.parameters.get("v_start", 0.30))
        v_end = float(slot.parameters.get("v_end", 0.75))
        v = np.linspace(v_start, v_end, n)
        return {AxisName.PULSE_FREQUENCY: _safe(v)}


@dataclass
class PatternPF5_PulseFreqSpikeDrop:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PF5",
        name="Pulse-Freq Spike & Drop",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY,),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.EDGE, PhaseName.CLIMAX, PhaseName.PLATEAU),
        style_affinity={
            "edging": 1.7, "ruin": 1.4, "beat_drop": 1.5,
            "crescendo": 1.0, "endlos_tease": 1.0, "sanfter_aufbau": 0.4,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        base = float(slot.parameters.get("base", 0.50))
        spike = float(slot.parameters.get("spike", 0.95))
        period = float(slot.parameters.get("period_s", 8.0))
        spike_w = float(slot.parameters.get("spike_w_s", 0.6))
        v = np.full(n, base)
        for bt in np.arange(0, t_local[-1] + period, period):
            mask = (t_local >= bt) & (t_local < bt + spike_w)
            if np.any(mask):
                phase = (t_local[mask] - bt) / spike_w
                env = np.sin(np.pi * phase)
                v[mask] = base + (spike - base) * env
        return {AxisName.PULSE_FREQUENCY: _safe(v)}


# =============================================================================
# Pulse Width Patterns (PW1..PW5)
# =============================================================================

@dataclass
class PatternPW1_SawtoothPW:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PW1",
        name="Pulse-Width Sawtooth Hard-Switch",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_WIDTH,),
        duration_range_s=(5.0, 90.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.8, "ruin": 1.3, "crescendo": 1.2,
            "edging": 0.9, "sanfter_aufbau": 0.4, "endlos_tease": 0.5,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        bpm = float(slot.parameters.get("bpm", 90.0))
        period = 60.0 / max(40.0, bpm)
        lo = float(slot.parameters.get("lo", 0.26))
        hi = float(slot.parameters.get("hi", 0.62))
        toggle = (np.floor(t_local / period) % 2 == 0).astype(float)
        v = lo + (hi - lo) * toggle
        return {AxisName.PULSE_WIDTH: _safe(v)}


@dataclass
class PatternPW2_LinearPWBuild:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PW2",
        name="Linear PW Build",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_WIDTH,),
        duration_range_s=(30.0, 600.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU),
        style_affinity={
            "sanfter_aufbau": 1.6, "crescendo": 1.5, "endlos_tease": 1.1,
            "edging": 0.9, "beat_drop": 0.6, "ruin": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_start = float(slot.parameters.get("v_start", 0.25))
        v_end = float(slot.parameters.get("v_end", 0.50))
        v = np.linspace(v_start, v_end, n)
        return {AxisName.PULSE_WIDTH: _safe(v)}


@dataclass
class PatternPW3_InvLockToPosition:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PW3",
        name="PW Inverse Lock to Position",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_WIDTH,),
        duration_range_s=(5.0, 30.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "edging": 1.3, "endlos_tease": 1.2, "sanfter_aufbau": 1.0,
            "crescendo": 1.1, "beat_drop": 0.9, "ruin": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        # Without true position coupling, simulate negative correlation by
        # following an opposite cosine to a reference position period.
        period = float(slot.parameters.get("period_s", 0.7))
        center = float(slot.parameters.get("center", 0.40))
        amp = float(slot.parameters.get("amp", 0.20))
        f = 1.0 / max(0.3, period)
        v = center - amp * np.cos(2 * np.pi * f * t_local)
        return {AxisName.PULSE_WIDTH: _safe(v)}


@dataclass
class PatternPW4_SmoothPWSweep:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PW4",
        name="Smooth PW Sweep",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_WIDTH,),
        duration_range_s=(5.0, 30.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.EDGE),
        style_affinity={
            "edging": 1.5, "endlos_tease": 1.3, "sanfter_aufbau": 1.2,
            "crescendo": 1.1, "beat_drop": 0.5, "ruin": 0.7,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_start = float(slot.parameters.get("v_start", 0.10))
        v_peak = float(slot.parameters.get("v_peak", 0.85))
        # cosine half-wave: low -> high -> low again
        T = max(t_local[-1], 1e-6)
        env = 0.5 - 0.5 * np.cos(np.pi * 2 * (t_local / T))
        v = v_start + (v_peak - v_start) * env
        return {AxisName.PULSE_WIDTH: _safe(v)}


@dataclass
class PatternPW5_PWPlateauHold:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PW5",
        name="PW Plateau Hold",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_WIDTH,),
        duration_range_s=(60.0, 600.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.5, "edging": 1.4, "sanfter_aufbau": 1.1,
            "crescendo": 0.7, "beat_drop": 0.5, "ruin": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        level = float(slot.parameters.get("level", 0.20))
        v = np.full(n, level) + 0.01 * perlin_like(t_local, freq_hz=0.05, rng=rng, octaves=2)
        return {AxisName.PULSE_WIDTH: _safe(v)}


# =============================================================================
# Pulse Rise-Time Patterns (PR1..PR4)
# =============================================================================

@dataclass
class PatternPR1_FallingRiseTime:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PR1",
        name="Falling Rise-Time Hardening",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_RISE_TIME,),
        duration_range_s=(60.0, 900.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.7, "ruin": 1.4, "sanfter_aufbau": 1.2,
            "beat_drop": 1.1, "edging": 0.9, "endlos_tease": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_start = float(slot.parameters.get("v_start", 0.70))
        v_end = float(slot.parameters.get("v_end", 0.15))
        v = np.linspace(v_start, v_end, n)
        return {AxisName.PULSE_RISE_TIME: _safe(v)}


@dataclass
class PatternPR2_RiseInverseVolume:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PR2",
        name="Pulse-Rise Inverse Volume",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_RISE_TIME,),
        duration_range_s=(10.0, 120.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.5, "ruin": 1.4, "sanfter_aufbau": 1.0,
            "beat_drop": 1.0, "edging": 1.0, "endlos_tease": 0.9,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # Sample master for live tracking; map intensity -> inverse rise.
        # Without per-sample master the slot-start master is used.
        # Use master_at if available.
        rise_at_low = float(slot.parameters.get("rise_at_low_intensity", 0.65))
        rise_at_high = float(slot.parameters.get("rise_at_high_intensity", 0.10))
        v = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            inten = float(mc.intensity)
            v[i] = rise_at_low + (rise_at_high - rise_at_low) * inten
        return {AxisName.PULSE_RISE_TIME: _safe(v)}


@dataclass
class PatternPR3_RiseMidRangeHold:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PR3",
        name="Pulse-Rise Mid-Range Hold",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_RISE_TIME,),
        duration_range_s=(15.0, 600.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.5, "edging": 1.4, "sanfter_aufbau": 1.3,
            "crescendo": 0.8, "beat_drop": 0.7, "ruin": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        center = float(slot.parameters.get("center", 0.38))
        v = np.full(n, center) + 0.02 * perlin_like(t_local, freq_hz=0.1, rng=rng, octaves=2)
        return {AxisName.PULSE_RISE_TIME: _safe(v)}


@dataclass
class PatternPR4_RapidRiseDrop:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PR4",
        name="Rapid Rise-Time Drop",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_RISE_TIME,),
        duration_range_s=(2.0, 15.0),
        suitable_phases=(PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "ruin": 2.0, "beat_drop": 1.5, "crescendo": 1.3,
            "edging": 0.9, "sanfter_aufbau": 0.3, "endlos_tease": 0.4,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_high = float(slot.parameters.get("v_high", 0.70))
        v_low = float(slot.parameters.get("v_low", 0.0))
        drop_at = float(slot.parameters.get("drop_at_norm", 0.30))
        T = max(t_local[-1], 1e-6)
        cut = drop_at * T
        v = np.where(t_local < cut, v_high, v_low)
        return {AxisName.PULSE_RISE_TIME: _safe(v)}


# =============================================================================
# Mixed Pulse Patterns (PMix1..PMix3)
# =============================================================================

@dataclass
class PatternPMix1_TripleAxisLock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PMix1",
        name="Classic 3-Axis Pulse Lock",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY, AxisName.PULSE_WIDTH, AxisName.PULSE_RISE_TIME),
        duration_range_s=(15.0, 600.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.7, "ruin": 1.5, "sanfter_aufbau": 1.2,
            "beat_drop": 1.0, "edging": 0.9, "endlos_tease": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # Drive everything from intensity over the slot
        v_pf = np.empty(n)
        v_pw = np.empty(n)
        v_pr = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            inten = float(mc.intensity)
            hard = float(mc.hardness)
            # PF: 0.30 low -> 0.85 high
            v_pf[i] = 0.30 + (0.55) * max(inten, hard)
            # PW: 0.20 -> 0.65
            v_pw[i] = 0.20 + (0.45) * hard
            # PR: 0.65 -> 0.10
            v_pr[i] = 0.65 - (0.55) * hard
        return {
            AxisName.PULSE_FREQUENCY: _safe(v_pf),
            AxisName.PULSE_WIDTH: _safe(v_pw),
            AxisName.PULSE_RISE_TIME: _safe(v_pr),
        }


@dataclass
class PatternPMix2_SoftPulse:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PMix2",
        name="Soft Pulse (mid PF, low PW, high PR)",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY, AxisName.PULSE_WIDTH, AxisName.PULSE_RISE_TIME),
        duration_range_s=(15.0, 300.0),
        suitable_phases=(PhaseName.INIT, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "sanfter_aufbau": 1.8, "endlos_tease": 1.6, "edging": 1.3,
            "crescendo": 0.7, "beat_drop": 0.4, "ruin": 0.3,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        return {
            AxisName.PULSE_FREQUENCY: np.full(n, 0.50)
                + 0.02 * perlin_like(t_local, 0.15, rng, 2),
            AxisName.PULSE_WIDTH: np.full(n, 0.18)
                + 0.02 * perlin_like(t_local, 0.10, rng, 2),
            AxisName.PULSE_RISE_TIME: np.full(n, 0.55)
                + 0.02 * perlin_like(t_local, 0.10, rng, 2),
        }


@dataclass
class PatternPMix3_HardClick:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="PMix3",
        name="Hard Click (high PF + high PW + low PR)",
        category=PatternCategory.PULSE,
        axes_used=(AxisName.PULSE_FREQUENCY, AxisName.PULSE_WIDTH, AxisName.PULSE_RISE_TIME),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "ruin": 2.0, "beat_drop": 1.7, "crescendo": 1.3,
            "edging": 0.7, "sanfter_aufbau": 0.2, "endlos_tease": 0.4,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        # Slight beat-locked PW twitch
        bpm = float(slot.parameters.get("bpm", 100.0))
        period = 60.0 / max(40.0, bpm)
        twitch = 0.05 * (np.floor(t_local / period) % 2 == 0).astype(float)
        return {
            AxisName.PULSE_FREQUENCY: np.full(n, 0.84) + twitch * 0.5,
            AxisName.PULSE_WIDTH: np.full(n, 0.56) + twitch,
            AxisName.PULSE_RISE_TIME: np.full(n, 0.10) - twitch * 0.5,
        }


# =============================================================================
# Registry export
# =============================================================================

PULSE_PATTERNS = {
    "PF1": PatternPF1_SinusPulseFreq(),
    "PF2": PatternPF2_InversePulseFreq(),
    "PF3": PatternPF3_StepSwitchPF(),
    "PF4": PatternPF4_SlowBuildPF(),
    "PF5": PatternPF5_PulseFreqSpikeDrop(),
    "PW1": PatternPW1_SawtoothPW(),
    "PW2": PatternPW2_LinearPWBuild(),
    "PW3": PatternPW3_InvLockToPosition(),
    "PW4": PatternPW4_SmoothPWSweep(),
    "PW5": PatternPW5_PWPlateauHold(),
    "PR1": PatternPR1_FallingRiseTime(),
    "PR2": PatternPR2_RiseInverseVolume(),
    "PR3": PatternPR3_RiseMidRangeHold(),
    "PR4": PatternPR4_RapidRiseDrop(),
    "PMix1": PatternPMix1_TripleAxisLock(),
    "PMix2": PatternPMix2_SoftPulse(),
    "PMix3": PatternPMix3_HardClick(),
}
