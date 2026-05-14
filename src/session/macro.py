from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .types import PhaseName


@dataclass
class Phase:
    name: PhaseName
    t_start_s: float
    t_end_s: float

    @property
    def duration_s(self) -> float:
        return self.t_end_s - self.t_start_s


@dataclass
class EdgeEvent:
    """Planned edge / drop. Negative SubWave injected into Master-Intensität."""
    t_s: float
    depth: float          # 0..1 — fraction of current intensity to drop
    recovery_s: float     # how long to recover back

    def applies_at(self, t: float) -> bool:
        return self.t_s <= t <= (self.t_s + self.recovery_s)


@dataclass
class SubWave:
    """A 30-90s mini-crescendo riding on the macro trend."""
    t_start_s: float
    period_s: float
    amplitude: float      # in [-1, 1], multiplied by remaining headroom in mixer
    shape: str = "sine"   # "sine" | "asym_pulse" | "sawtooth" | "drop"

    def evaluate(self, t: float) -> float:
        if not (self.t_start_s <= t <= self.t_start_s + self.period_s):
            return 0.0
        phase = (t - self.t_start_s) / self.period_s  # 0..1
        if self.shape == "sine":
            return self.amplitude * np.sin(np.pi * phase)
        if self.shape == "asym_pulse":
            # rapid build, slow tail
            return self.amplitude * (4 * phase * (1 - phase) ** 1.5)
        if self.shape == "sawtooth":
            # slow build, sharp drop
            return self.amplitude * (1 - abs(2 * phase - 1))
        if self.shape == "drop":
            # negative subwave for edges
            return -abs(self.amplitude) * np.sin(np.pi * phase)
        return 0.0


@dataclass
class MasterCurve:
    """A piecewise-linear curve from control points, sample-able at any t."""
    times_s: np.ndarray   # shape (N,)
    values: np.ndarray    # shape (N,), in 0..1

    def __call__(self, t: float | np.ndarray) -> float | np.ndarray:
        return np.interp(t, self.times_s, self.values)

    @classmethod
    def linear(cls, t_start: float, t_end: float, v_start: float, v_end: float) -> "MasterCurve":
        return cls(np.array([t_start, t_end]), np.array([v_start, v_end]))

    @classmethod
    def from_points(cls, points: list[tuple[float, float]]) -> "MasterCurve":
        pts = sorted(points, key=lambda p: p[0])
        return cls(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))


@dataclass
class MasterEnvelopes:
    """The 4 master driving envelopes. intensity is editable in UI; the others derive from it."""
    intensity: MasterCurve     # Volume master, drives everything
    hardness: MasterCurve      # Pulse-Hardening (PW + inverse Rise) — derived from intensity
    sharpness: MasterCurve     # Carrier — derived from intensity (r≈0.9 in empirical data)
    movement: MasterCurve      # alpha/beta rotation amount — derived from intensity + style

    def at(self, t: float) -> dict[str, float]:
        return {
            "intensity": float(self.intensity(t)),
            "hardness": float(self.hardness(t)),
            "sharpness": float(self.sharpness(t)),
            "movement": float(self.movement(t)),
        }


@dataclass
class MacroPlan:
    """Output of the Macro Planner. Deterministic from (SessionProfile, seed)."""
    phases: list[Phase]
    envelopes: MasterEnvelopes
    edges: list[EdgeEvent]
    subwaves: list[SubWave]
    seed: int
    profile_summary: dict          # snapshot of profile for logging

    def phase_at(self, t: float) -> Phase:
        for p in self.phases:
            if p.t_start_s <= t <= p.t_end_s:
                return p
        return self.phases[-1]

    def total_duration_s(self) -> float:
        return self.phases[-1].t_end_s
