"""Micro Renderer — renders a stream of axis values from MacroPlan + MesoSchedule.

For each tick:
1. Find the active PatternSlot
2. Sample MasterContext from MacroPlan envelopes
3. Call pattern.render() to get pattern axis output (subset of axes)
4. Fill missing axes with master defaults
5. Crossfade across pattern transitions
6. Apply mixing operator: final = master + (1 - master/cap) * pattern_delta
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .macro import MacroPlan
from .macro_planner import evaluate_macro_at
from .meso_scheduler import MesoSchedule
from .pattern_base import MasterContext, PatternSlot
from .profile import CHARACTER_PRESETS, SessionProfile
from .types import AxisName


def master_to_axis_defaults(master: dict[str, float]) -> dict[AxisName, float]:
    """Convert MacroPlan envelope sample to default per-axis values (when pattern doesn't drive it)."""
    intensity = master["intensity"]
    hardness = master["hardness"]
    sharpness = master["sharpness"]
    movement = master["movement"]

    return {
        AxisName.ALPHA: 0.5,                                # default = center
        AxisName.BETA: 0.5,
        AxisName.VOLUME: intensity,
        AxisName.CARRIER: sharpness,
        # pulse_frequency: positively correlates with intensity (r ≈ 0.5)
        AxisName.PULSE_FREQUENCY: 0.4 + 0.4 * intensity,
        # pulse_width: hardness drives this directly
        AxisName.PULSE_WIDTH: hardness,
        # pulse_rise_time: inversely correlated with hardness
        AxisName.PULSE_RISE_TIME: 1.0 - hardness,
    }


@dataclass
class RenderState:
    last_axes: dict[AxisName, float]
    last_pattern_id: Optional[str] = None
    crossfade_remaining_s: float = 0.0
    crossfade_total_s: float = 0.0
    crossfade_from: Optional[dict[AxisName, float]] = None


class MicroRenderer:
    """Stateful per-tick renderer."""

    def __init__(self, profile: SessionProfile, plan: MacroPlan, schedule: MesoSchedule,
                 catalog: Optional[dict] = None, dt: float = 0.02):
        self.profile = profile
        self.plan = plan
        self.schedule = schedule
        self.dt = dt
        self.char = CHARACTER_PRESETS[profile.character]
        self.crossfade_s = profile.advanced.crossfade_s or self.char["crossfade_s"]

        if catalog is None:
            try:
                from .pattern_catalog import ALL_PATTERNS
                catalog = ALL_PATTERNS
            except Exception:
                catalog = {}
        self.catalog = catalog

        seed = (plan.seed + 31337) & 0x7FFFFFFF
        self.rng = np.random.default_rng(seed)

        defaults = master_to_axis_defaults(evaluate_macro_at(plan, 0.0))
        self.state = RenderState(last_axes=defaults)

    # ---------- batch render of a single slot for offline tests ----------

    def render_slot(self, slot: PatternSlot) -> dict[AxisName, np.ndarray]:
        """Render an entire slot offline. Used for testing patterns standalone."""
        n = max(2, int(round(slot.duration_s / self.dt)))
        t_local = np.linspace(0, slot.duration_s, n)
        t_global = slot.t_start_s + t_local

        master = self._sample_master_at(slot.t_start_s)
        master_at = lambda tg: self._sample_master_at(tg)
        defaults = master_to_axis_defaults(evaluate_macro_at(self.plan, slot.t_start_s))

        pattern_out = self._render_pattern(slot, t_local, master, master_at)

        out: dict[AxisName, np.ndarray] = {}
        for axis in AxisName:
            base = np.array([
                master_to_axis_defaults(evaluate_macro_at(self.plan, float(tg)))[axis]
                for tg in t_global
            ])
            if axis in pattern_out:
                # Mixing: pattern provides axis directly. Multiply by intensity_scale and clamp.
                out[axis] = np.clip(pattern_out[axis] * slot.intensity_scale, 0.0, 1.0)
            else:
                out[axis] = base
        return out

    # ---------- streaming per-tick render ----------

    def tick(self, t_global: float) -> dict[AxisName, float]:
        """Render one sample at global time t. Returns axis values in 0..1."""
        slot = self.schedule.slot_at(t_global)
        master = self._sample_master_at(t_global)
        defaults = master_to_axis_defaults(evaluate_macro_at(self.plan, t_global))

        if slot is None:
            new_axes = defaults
        else:
            t_local = np.array([t_global - slot.t_start_s])
            master_at = lambda tg: self._sample_master_at(tg)
            pattern_out = self._render_pattern(slot, t_local, master, master_at)
            new_axes = {}
            for axis in AxisName:
                if axis in pattern_out:
                    val = float(pattern_out[axis][0]) * slot.intensity_scale
                    new_axes[axis] = max(0.0, min(1.0, val))
                else:
                    new_axes[axis] = defaults[axis]

            # Detect new pattern start → init crossfade
            if slot.pattern_id != self.state.last_pattern_id:
                self.state.crossfade_from = dict(self.state.last_axes)
                self.state.crossfade_remaining_s = self.crossfade_s
                self.state.crossfade_total_s = self.crossfade_s
                self.state.last_pattern_id = slot.pattern_id

        # Apply crossfade
        if self.state.crossfade_remaining_s > 0 and self.state.crossfade_from is not None:
            alpha = 1.0 - (self.state.crossfade_remaining_s / self.state.crossfade_total_s)
            alpha = max(0.0, min(1.0, alpha))
            blended = {}
            for axis in AxisName:
                blended[axis] = (1 - alpha) * self.state.crossfade_from[axis] + alpha * new_axes[axis]
            new_axes = blended
            self.state.crossfade_remaining_s = max(0.0, self.state.crossfade_remaining_s - self.dt)

        self.state.last_axes = new_axes
        return new_axes

    # ---------- helpers ----------

    def _sample_master_at(self, t_global: float) -> MasterContext:
        sample = evaluate_macro_at(self.plan, t_global)
        return MasterContext(
            intensity=sample["intensity"],
            hardness=sample["hardness"],
            sharpness=sample["sharpness"],
            movement=sample["movement"],
        )

    def _render_pattern(self, slot: PatternSlot, t_local: np.ndarray,
                        master: MasterContext, master_at) -> dict[AxisName, np.ndarray]:
        if slot.pattern_id not in self.catalog:
            return {}
        pattern = self.catalog[slot.pattern_id]
        try:
            return pattern.render(t_local, slot, master, master_at, self.rng)
        except Exception as e:
            # Pattern crashed — log and return empty (defaults will fill)
            import logging
            logging.getLogger("session.micro").warning(
                "Pattern %s render failed: %s", slot.pattern_id, e
            )
            return {}
