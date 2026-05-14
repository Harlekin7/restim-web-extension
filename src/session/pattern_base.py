from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np

from .types import AxisName, PatternCategory, PhaseName


@dataclass
class MasterContext:
    """Per-sample context passed to a pattern renderer.

    Values come from MacroPlan.envelopes evaluated at the sample's time.
    Patterns multiply or add to these — they don't replace them.
    """
    intensity: float    # 0..1, master volume target
    hardness: float     # 0..1, drives PW and inverse Rise
    sharpness: float    # 0..1, drives Carrier
    movement: float     # 0..1, drives alpha/beta rotation amount


@dataclass
class PatternSlot:
    """One scheduled occurrence of a pattern in the session timeline."""
    t_start_s: float
    t_end_s: float
    pattern_id: str
    intensity_scale: float = 1.0     # how strong relative to master (0..2)
    parameters: dict = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return self.t_end_s - self.t_start_s


@dataclass
class PatternMetadata:
    """Static metadata for a pattern, used by Meso scheduler for filtering."""
    id: str
    name: str
    category: PatternCategory
    axes_used: tuple[AxisName, ...]
    duration_range_s: tuple[float, float]    # min,max sensible duration
    suitable_phases: tuple[PhaseName, ...]   # phases where this pattern fits
    required_caps: dict = field(default_factory=dict)  # e.g. {"min_intensity": 0.3}
    style_affinity: dict = field(default_factory=dict) # style -> weight 0..2


# Renderer signature. Each pattern in pattern_catalog.py implements this.
#
# Args:
#   t_local_s: shape (N,), time in seconds RELATIVE to slot start (0 .. slot.duration_s)
#   slot: the PatternSlot scheduled
#   master: MasterContext sampled at the SLOT START (callers can re-evaluate per sample if needed)
#   master_at: callable t_global -> MasterContext, for patterns that need master to track
#   rng: numpy Generator, seeded by session seed + slot index
#
# Returns:
#   dict mapping AxisName -> np.ndarray of shape (N,), values in 0..1
#   Patterns may return only a subset of axes; the renderer fills missing with master defaults.
PatternRenderFn = Callable[
    [np.ndarray, "PatternSlot", MasterContext, Callable[[float], MasterContext], np.random.Generator],
    dict[AxisName, np.ndarray],
]


class PatternRenderer(Protocol):
    metadata: PatternMetadata
    render: PatternRenderFn


# --- Helpers patterns can use ---


def slew_smooth(values: np.ndarray, prev_value: float, max_change_per_sample: float) -> np.ndarray:
    """Limit absolute change per sample. Used for smoothing pattern outputs."""
    out = np.empty_like(values)
    cur = prev_value
    for i, v in enumerate(values):
        delta = np.clip(v - cur, -max_change_per_sample, max_change_per_sample)
        cur = cur + delta
        out[i] = cur
    return out


def perlin_like(t: np.ndarray, freq_hz: float, rng: np.random.Generator, octaves: int = 3) -> np.ndarray:
    """Cheap smooth noise via summed cosines with random phases. Range ≈ -1..1."""
    out = np.zeros_like(t, dtype=float)
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        phase = rng.uniform(0, 2 * np.pi)
        out += amp * np.cos(2 * np.pi * freq_hz * (2 ** o) * t + phase)
        norm += amp
        amp *= 0.5
    return out / norm


def ou_process(n: int, dt: float, mean: float, sigma: float, theta: float,
               rng: np.random.Generator, x0: float | None = None) -> np.ndarray:
    """Ornstein-Uhlenbeck mean-reverting noise. Smooth, bounded, seeded."""
    x = np.empty(n, dtype=float)
    x[0] = mean if x0 is None else x0
    sqrt_dt = np.sqrt(dt)
    eps = rng.standard_normal(n)
    for i in range(1, n):
        x[i] = x[i-1] + theta * (mean - x[i-1]) * dt + sigma * sqrt_dt * eps[i]
    return x


def rotating_position(t: np.ndarray, freq_hz: float, radius: float,
                      phase0: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Returns (alpha, beta) trajectories rotating on the unit circle at freq_hz, scaled by radius."""
    omega = 2 * np.pi * freq_hz
    alpha = 0.5 + radius * 0.5 * np.cos(omega * t + phase0)
    beta = 0.5 + radius * 0.5 * np.sin(omega * t + phase0)
    return alpha, beta


def static_value(n: int, value: float) -> np.ndarray:
    return np.full(n, value, dtype=float)
