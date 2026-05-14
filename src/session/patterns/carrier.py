"""Carrier patterns C1..C5 — frequency (carrier) axis."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..pattern_base import (
    MasterContext,
    PatternMetadata,
    PatternSlot,
    perlin_like,
    slew_smooth,
)
from ..types import AxisName, PatternCategory, PhaseName


def _safe(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0.0, 1.0)


# ---------------------------------------------------------------------------
# C1 — Static Carrier
# ---------------------------------------------------------------------------

@dataclass
class PatternC1_StaticCarrier:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="C1",
        name="Static Carrier",
        category=PatternCategory.CARRIER,
        axes_used=(AxisName.CARRIER,),
        duration_range_s=(15.0, 1800.0),
        suitable_phases=(PhaseName.INIT, PhaseName.PLATEAU, PhaseName.EDGE),
        style_affinity={
            "endlos_tease": 1.4, "edging": 1.3, "sanfter_aufbau": 1.2,
            "crescendo": 0.7, "beat_drop": 0.5, "ruin": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        level = float(slot.parameters.get("level", 0.50 + 0.20 * master.sharpness))
        v = np.full(n, level) + 0.005 * perlin_like(t_local, 0.05, rng, 2)
        return {AxisName.CARRIER: _safe(v)}


# ---------------------------------------------------------------------------
# C2 — Carrier-Volume Lockstep (live tracks master.intensity for sharpness)
# ---------------------------------------------------------------------------

@dataclass
class PatternC2_CarrierVolumeLockstep:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="C2",
        name="Carrier-Volume Lockstep",
        category=PatternCategory.CARRIER,
        axes_used=(AxisName.CARRIER,),
        duration_range_s=(15.0, 1800.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.6, "ruin": 1.4, "sanfter_aufbau": 1.3,
            "beat_drop": 1.1, "edging": 1.0, "endlos_tease": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_lo = float(slot.parameters.get("c_low", 0.50))
        v_hi = float(slot.parameters.get("c_high", 0.95))
        v = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            inten = float(mc.intensity)
            v[i] = v_lo + (v_hi - v_lo) * inten
        return {AxisName.CARRIER: _safe(v)}


# ---------------------------------------------------------------------------
# C3 — Linear Carrier Sweep
# ---------------------------------------------------------------------------

@dataclass
class PatternC3_LinearCarrierSweep:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="C3",
        name="Linear Carrier Sweep",
        category=PatternCategory.CARRIER,
        axes_used=(AxisName.CARRIER,),
        duration_range_s=(60.0, 1200.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.CLIMAX),
        style_affinity={
            "crescendo": 1.7, "sanfter_aufbau": 1.4, "ruin": 1.3,
            "beat_drop": 0.9, "edging": 0.8, "endlos_tease": 1.0,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_start = float(slot.parameters.get("v_start", 0.45))
        v_end = float(slot.parameters.get("v_end", 0.85))
        v = np.linspace(v_start, v_end, n)
        return {AxisName.CARRIER: _safe(v)}


# ---------------------------------------------------------------------------
# C4 — Carrier Drop on Volume Peak
# ---------------------------------------------------------------------------

@dataclass
class PatternC4_CarrierDropOnPeak:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="C4",
        name="Carrier Drop on Volume Peak",
        category=PatternCategory.CARRIER,
        axes_used=(AxisName.CARRIER,),
        duration_range_s=(5.0, 60.0),
        suitable_phases=(PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "ruin": 1.4, "edging": 1.3, "beat_drop": 1.2,
            "crescendo": 0.9, "endlos_tease": 0.8, "sanfter_aufbau": 0.5,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        base = float(slot.parameters.get("base", 0.80))
        drop_to = float(slot.parameters.get("drop_to", 0.45))
        v = np.empty(n)
        t0 = slot.t_start_s
        for i, t in enumerate(t_local):
            mc = master_at(t0 + float(t)) if master_at is not None else master
            inten = float(mc.intensity)
            # at peak intensity, drop carrier
            v[i] = base + (drop_to - base) * (inten ** 2)
        return {AxisName.CARRIER: _safe(v)}


# ---------------------------------------------------------------------------
# C5 — Carrier Sweep Block (short ramp 2-10s)
# ---------------------------------------------------------------------------

@dataclass
class PatternC5_CarrierSweepBlock:
    metadata: PatternMetadata = field(default_factory=lambda: PatternMetadata(
        id="C5",
        name="Carrier Sweep Block",
        category=PatternCategory.CARRIER,
        axes_used=(AxisName.CARRIER,),
        duration_range_s=(2.0, 30.0),
        suitable_phases=(PhaseName.BUILD, PhaseName.EDGE, PhaseName.CLIMAX),
        style_affinity={
            "beat_drop": 1.5, "crescendo": 1.3, "ruin": 1.2,
            "edging": 1.0, "endlos_tease": 0.9, "sanfter_aufbau": 0.6,
        },
    ))

    @staticmethod
    def render(t_local, slot, master, master_at, rng):
        n = len(t_local)
        v_start = float(slot.parameters.get("v_start", 0.55))
        v_end = float(slot.parameters.get("v_end", 0.90))
        # mild ease in/out
        t_norm = t_local / max(t_local[-1], 1e-6)
        eased = 0.5 - 0.5 * np.cos(np.pi * t_norm)
        v = v_start + (v_end - v_start) * eased
        return {AxisName.CARRIER: _safe(v)}


# ---------------------------------------------------------------------------
# Registry export
# ---------------------------------------------------------------------------

CARRIER_PATTERNS = {
    "C1": PatternC1_StaticCarrier(),
    "C2": PatternC2_CarrierVolumeLockstep(),
    "C3": PatternC3_LinearCarrierSweep(),
    "C4": PatternC4_CarrierDropOnPeak(),
    "C5": PatternC5_CarrierSweepBlock(),
}
