"""Volume patterns V1..V12 — output normalized 0..1 on AxisName.VOLUME."""
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


# ---------------------------------------------------------------------------
# V1 — Linear Slow Build
# ---------------------------------------------------------------------------

@dataclass
class PatternV1_LinearSlowBuild:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V1",
        name="Linear Slow Build",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(30.0, 600.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU),
        style_affinity={
            "sanfter_aufbau": 1.8, "crescendo": 1.6, "edging": 1.0,
            "endlos_tease": 1.1, "beat_drop": 0.5, "ruin": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        start = float(slot.parameters.get("v_start", master.intensity * 0.6))
        end = float(slot.parameters.get("v_end", min(1.0, master.intensity + 0.3)))
        v = np.linspace(start, end, n)
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V2 — Step Plateau Build
# ---------------------------------------------------------------------------

@dataclass
class PatternV2_StepPlateauBuild:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V2",
        name="Step Plateau Build",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(30.0, 300.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "sanfter_aufbau": 1.4, "crescendo": 1.5, "edging": 1.3,
            "endlos_tease": 1.2, "beat_drop": 0.7, "ruin": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        steps = int(slot.parameters.get("steps", 4))
        start = float(slot.parameters.get("v_start", master.intensity * 0.7))
        end = float(slot.parameters.get("v_end", min(1.0, master.intensity + 0.2)))
        levels = np.linspace(start, end, max(2, steps))
        edges = np.linspace(0, n, max(2, steps) + 1).astype(int)
        v = np.empty(n)
        for i in range(len(levels)):
            v[edges[i]:edges[i + 1]] = levels[i]
        # tiny smoothing at step edges
        v = slew_smooth(v, prev_value=v[0], max_change_per_sample=0.05)
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V3 — Frühes Crescendo
# ---------------------------------------------------------------------------

@dataclass
class PatternV3_EarlyCrescendo:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V3",
        name="Early Crescendo",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(30.0, 600.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.7, "beat_drop": 1.4, "ruin": 1.5,
            "sanfter_aufbau": 0.7, "edging": 0.6, "endlos_tease": 0.5,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        start = float(slot.parameters.get("v_start", 0.18))
        peak = float(slot.parameters.get("v_peak", 0.95))
        # 20% time -> peak then plateau
        t_norm = t_local / max(t_local[-1], 1e-6)
        ramp_end = float(slot.parameters.get("ramp_end_norm", 0.20))
        v = np.where(
            t_norm < ramp_end,
            start + (peak - start) * (t_norm / ramp_end),
            peak + 0.02 * np.sin(2 * np.pi * 0.05 * t_local),
        )
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V4 — Spätes Crescendo
# ---------------------------------------------------------------------------

@dataclass
class PatternV4_LateCrescendo:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V4",
        name="Late Crescendo",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(60.0, 900.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "edging": 1.7, "crescendo": 1.4, "endlos_tease": 1.3,
            "sanfter_aufbau": 1.2, "beat_drop": 0.5, "ruin": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_low = float(slot.parameters.get("v_low", 0.55))
        v_peak = float(slot.parameters.get("v_peak", 0.90))
        plateau_end = float(slot.parameters.get("plateau_end_norm", 0.75))
        t_norm = t_local / max(t_local[-1], 1e-6)
        v = np.where(
            t_norm < plateau_end,
            v_low + 0.03 * np.sin(2 * np.pi * 0.03 * t_local),
            v_low + (v_peak - v_low) * ((t_norm - plateau_end) / max(1 - plateau_end, 1e-6)),
        )
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V5 — Konstante Volume-Plateau
# ---------------------------------------------------------------------------

@dataclass
class PatternV5_FlatPlateau:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V5",
        name="Flat Plateau",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(20.0, 600.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.6, "edging": 1.5, "sanfter_aufbau": 1.0,
            "crescendo": 0.6, "beat_drop": 0.5, "ruin": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        level = float(slot.parameters.get("level", master.intensity))
        breath = 0.015 * np.sin(2 * np.pi * 0.07 * t_local + rng.uniform(0, 2 * np.pi))
        v = np.full(n, level) + breath
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V6 — Beat-Drop / Rapid Spike
# ---------------------------------------------------------------------------

@dataclass
class PatternV6_BeatDropSpike:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V6",
        name="Beat Drop Spike",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(8.0, 60.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 2.0, "crescendo": 1.4, "ruin": 1.4,
            "sanfter_aufbau": 0.3, "edging": 0.7, "endlos_tease": 0.5,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        base = float(slot.parameters.get("base", master.intensity * 0.7))
        spike_amp = float(slot.parameters.get("spike_amp", 0.30))
        bpm = float(slot.parameters.get("bpm", 90.0))
        period = 60.0 / max(40.0, bpm)
        # spikes on the beat with short envelope
        v = np.full(n, base)
        beat_times = np.arange(0, t_local[-1] + period, period)
        spike_w = float(slot.parameters.get("spike_width_s", 0.25))
        for bt in beat_times:
            mask = (t_local >= bt) & (t_local < bt + spike_w)
            if np.any(mask):
                phase = (t_local[mask] - bt) / spike_w
                env = np.sin(np.pi * phase)
                v[mask] += spike_amp * env
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V7 — Volume-Drop-and-Hold (Edge)
# ---------------------------------------------------------------------------

@dataclass
class PatternV7_DropAndHold:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V7",
        name="Drop and Hold",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(10.0, 90.0),
        suitable_phases=(PhaseName.EDGE, PhaseName.PLATEAU),
        style_affinity={
            "edging": 2.0, "endlos_tease": 1.4, "ruin": 1.0,
            "sanfter_aufbau": 0.7, "crescendo": 0.6, "beat_drop": 0.8,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        high = float(slot.parameters.get("high", master.intensity))
        low = float(slot.parameters.get("low", max(0.05, master.intensity - 0.40)))
        drop_at = float(slot.parameters.get("drop_at_norm", 0.20))
        T = max(t_local[-1], 1e-6)
        cut = drop_at * T
        v = np.where(t_local < cut, high, low)
        # smooth the cliff a tiny bit
        v = slew_smooth(v, prev_value=v[0], max_change_per_sample=0.10)
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V8 — Sägezahn-Build (Slow Up + Hard Drop)
# ---------------------------------------------------------------------------

@dataclass
class PatternV8_SawtoothBuild:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V8",
        name="Sawtooth Build",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(60.0, 600.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "edging": 1.9, "endlos_tease": 1.2, "ruin": 1.0,
            "crescendo": 1.0, "beat_drop": 0.7, "sanfter_aufbau": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        period = float(slot.parameters.get("period_s", 60.0))
        low = float(slot.parameters.get("low", 0.40))
        high = float(slot.parameters.get("high", 0.95))
        T = max(t_local[-1], 1e-6)
        cycles = max(1.0, T / period)
        # build phase (ramp up) then drop
        v = np.empty(n)
        for i, t in enumerate(t_local):
            phase = (t / period) % 1.0
            if phase < 0.97:
                v[i] = low + (high - low) * (phase / 0.97)
            else:
                # rapid drop in last 3% of period
                drop_p = (phase - 0.97) / 0.03
                v[i] = high - (high - low) * drop_p
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V9 — Two-Level Toggle
# ---------------------------------------------------------------------------

@dataclass
class PatternV9_TwoLevelToggle:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V9",
        name="Two Level Toggle",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(10.0, 120.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.5, "ruin": 1.4, "edging": 1.2,
            "crescendo": 1.0, "endlos_tease": 0.8, "sanfter_aufbau": 0.4,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        lo = float(slot.parameters.get("lo", 0.70))
        hi = float(slot.parameters.get("hi", 1.0))
        period = float(slot.parameters.get("period_s", 4.0))
        toggle = (np.floor(t_local / period) % 2 == 0).astype(float)
        v = lo + (hi - lo) * toggle
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V10 — Audio-rate Volume Modulation
# ---------------------------------------------------------------------------

@dataclass
class PatternV10_AudioRateModulation:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V10",
        name="Audio-Rate Modulation",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(5.0, 120.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "ruin": 1.5, "crescendo": 1.3, "beat_drop": 1.2,
            "edging": 1.1, "endlos_tease": 1.0, "sanfter_aufbau": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        center = float(slot.parameters.get("center", master.intensity))
        amp = float(slot.parameters.get("amp", 0.10))
        # use perlin_like with sample-rate-dependent freq, but cap at Nyquist/4
        dt = _dt_from(t_local)
        max_f = 0.25 / max(dt, 1e-3)
        f = float(slot.parameters.get("freq_hz", min(15.0, max_f)))
        v = center + amp * perlin_like(t_local, freq_hz=f, rng=rng, octaves=3)
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V11 — Histogramm-Spitze bei 100 (Saturation)
# ---------------------------------------------------------------------------

@dataclass
class PatternV11_SaturationStick:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V11",
        name="Saturation Stick",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(15.0, 600.0),
        suitable_phases=(PhaseName.CLIMAX, PhaseName.PLATEAU),
        style_affinity={
            "ruin": 2.0, "crescendo": 1.5, "beat_drop": 1.2,
            "edging": 0.5, "sanfter_aufbau": 0.2, "endlos_tease": 0.3,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        ceil = float(slot.parameters.get("ceiling", 0.98))
        # tiny dips below ceiling, ~60% time at ceiling
        dips = perlin_like(t_local, freq_hz=0.3, rng=rng, octaves=2)
        v = ceil - 0.10 * np.maximum(0.0, -dips)  # only down dips
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# V12 — Volume-Burst-Block
# ---------------------------------------------------------------------------

@dataclass
class PatternV12_BurstBlock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="V12",
        name="Volume Burst Block",
        category=PatternCategory.VOLUME,
        axes_used=(AxisName.VOLUME,),
        duration_range_s=(15.0, 90.0),
        suitable_phases=(PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.6, "ruin": 1.3, "crescendo": 1.1,
            "edging": 1.0, "endlos_tease": 0.8, "sanfter_aufbau": 0.5,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        base = float(slot.parameters.get("base", master.intensity * 0.45))
        peak = float(slot.parameters.get("peak", master.intensity))
        burst_period = float(slot.parameters.get("burst_period_s", 4.0))
        burst_len = float(slot.parameters.get("burst_len_s", 1.5))
        v = np.full(n, base)
        for bt in np.arange(0, t_local[-1] + burst_period, burst_period):
            mask = (t_local >= bt) & (t_local < bt + burst_len)
            if np.any(mask):
                phase = (t_local[mask] - bt) / burst_len
                env = np.sin(np.pi * phase)
                v[mask] = base + (peak - base) * env
        return {AxisName.VOLUME: _safe(v)}


# ---------------------------------------------------------------------------
# Registry export
# ---------------------------------------------------------------------------

VOLUME_PATTERNS = {
    "V1": PatternV1_LinearSlowBuild(),
    "V2": PatternV2_StepPlateauBuild(),
    "V3": PatternV3_EarlyCrescendo(),
    "V4": PatternV4_LateCrescendo(),
    "V5": PatternV5_FlatPlateau(),
    "V6": PatternV6_BeatDropSpike(),
    "V7": PatternV7_DropAndHold(),
    "V8": PatternV8_SawtoothBuild(),
    "V9": PatternV9_TwoLevelToggle(),
    "V10": PatternV10_AudioRateModulation(),
    "V11": PatternV11_SaturationStick(),
    "V12": PatternV12_BurstBlock(),
}
