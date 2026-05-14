"""Micro Renderer — renders 7 axes per tick from the multi-track MesoSchedule.

For each tick:
  1. Find the active PatternSlot per track (Position / Volume / Pulse / Carrier
     / Multi-Axis overlay).
  2. Sample MasterContext from MacroPlan envelopes.
  3. Render each track's active pattern.
  4. Merge with priority: Multi-Axis overlay > category-specific tracks > master defaults.
  5. Per-axis crossfade across pattern transitions (each track keeps its own
     crossfade state so a Position swap doesn't smear Volume).

Position is ALWAYS driven by an active Position-pattern — "Static" is one of
those patterns (P1 Static-Floor), not a default fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .macro import MacroPlan
from .macro_planner import evaluate_macro_at
from .meso_scheduler import (
    ALWAYS_ACTIVE_TRACKS,
    MesoSchedule,
    TRACK_CARRIER,
    TRACK_MULTI_AXIS,
    TRACK_POSITION,
    TRACK_PULSE,
    TRACK_VOLUME,
)
from .pattern_base import MasterContext, PatternSlot
from .profile import CHARACTER_PRESETS, SessionProfile
from .types import AxisName


def master_to_axis_defaults(master: dict[str, float]) -> dict[AxisName, float]:
    """Master-derived per-axis defaults. Used only as fallback if no track
    pattern provides a value (which should not happen for the always-active
    tracks Position/Volume/Pulse/Carrier)."""
    intensity = master["intensity"]
    hardness = master["hardness"]
    sharpness = master["sharpness"]
    return {
        AxisName.ALPHA: 0.5,
        AxisName.BETA: 0.5,
        AxisName.VOLUME: intensity,
        AxisName.CARRIER: sharpness,
        AxisName.PULSE_FREQUENCY: 0.4 + 0.4 * intensity,
        AxisName.PULSE_WIDTH: hardness,
        AxisName.PULSE_RISE_TIME: 1.0 - hardness,
    }


# Which axes does each track "own"? Used to limit cross-track interference.
_TRACK_AXES: dict[str, set[AxisName]] = {
    TRACK_POSITION: {AxisName.ALPHA, AxisName.BETA},
    TRACK_VOLUME:   {AxisName.VOLUME},
    TRACK_PULSE:    {AxisName.PULSE_FREQUENCY, AxisName.PULSE_WIDTH, AxisName.PULSE_RISE_TIME},
    TRACK_CARRIER:  {AxisName.CARRIER},
    # Multi-axis overlay can touch any axis — we don't restrict its outputs.
    TRACK_MULTI_AXIS: set(AxisName),
}


# How much of the master.intensity range a pattern is allowed to modulate
# the Volume axis around. Values are "modulation depth": pattern_out=0 maps to
# master*(1-depth), pattern_out=1 maps to master*1.0. So depth=0.2 means
# Volume stays within ±20% of the macro envelope's current value, no matter
# what the pattern outputs. Lower = subtler.
# E-stim users notice volume changes very strongly, so we keep this tight.
VOLUME_MOD_DEPTH_BY_TRACK: dict[str, float] = {
    TRACK_VOLUME:     0.20,   # V-patterns: subtle ripple around the macro arc
    TRACK_MULTI_AXIS: 0.35,   # M-patterns: a bit more freedom for synced moves
}


@dataclass
class _TrackState:
    last_pattern_id: Optional[str] = None
    last_axes: dict[AxisName, float] = field(default_factory=dict)
    crossfade_remaining_s: float = 0.0
    crossfade_total_s: float = 0.0
    crossfade_from: Optional[dict[AxisName, float]] = None


class MicroRenderer:
    """Stateful per-tick renderer with multi-track merging."""

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

        # One state per track (always-active + multi-axis overlay)
        self._states: dict[str, _TrackState] = {
            t: _TrackState() for t in (*ALWAYS_ACTIVE_TRACKS, TRACK_MULTI_AXIS)
        }

        # Initial axis values come from master defaults at t=0
        self._last_merged: dict[AxisName, float] = master_to_axis_defaults(
            evaluate_macro_at(plan, 0.0)
        )

    # ─────────────────────── streaming per-tick render ────────────────────

    def tick(self, t_global: float) -> dict[AxisName, float]:
        """Render one sample at global time t. Returns the 7 axis values in 0..1."""
        master = self._sample_master_at(t_global)
        defaults = master_to_axis_defaults(evaluate_macro_at(self.plan, t_global))

        # Start with master defaults — these only "win" for axes no track touches.
        merged: dict[AxisName, float] = dict(defaults)

        # Render the always-active tracks first; multi-axis comes last as overlay.
        for track in (*ALWAYS_ACTIVE_TRACKS, TRACK_MULTI_AXIS):
            slot = self.schedule.slot_at(t_global, track=track)
            track_out = self._render_track_at(track, slot, t_global, master)
            if not track_out:
                continue
            # Multi-axis overlay overrides any axis it returns.
            # Always-active tracks only return values for their owned axes — apply directly.
            for axis, val in track_out.items():
                merged[axis] = max(0.0, min(1.0, val))

        self._last_merged = merged
        return merged

    def _render_track_at(self, track: str, slot: Optional[PatternSlot],
                         t_global: float, master: MasterContext) -> dict[AxisName, float]:
        """Render the active pattern for one track and apply per-track crossfade.
        Returns axis-name -> value mapping (only for axes the pattern actually drives).

        Volume axis output is *modulated by* master.intensity rather than overriding
        it: pattern-Output × intensity = final Volume. This keeps the global macro
        envelope in charge of the overall arc while V-patterns give it local shape."""
        st = self._states[track]
        owned = _TRACK_AXES[track]

        if slot is None:
            # No active slot. For multi-axis this is the normal "no overlay" case.
            # For always-active tracks this means a gap — return empty dict; merger
            # will use master defaults for those axes.
            st.last_pattern_id = None
            return {}

        # Render the pattern at this single tick.
        t_local = np.array([t_global - slot.t_start_s])
        master_at = lambda tg: self._sample_master_at(tg)
        raw_out = self._call_pattern(slot, t_local, master, master_at)

        # Build the axis dict — restrict to the track's owned axes (for category tracks)
        # so a Position-pattern that returns extra axes (rare) doesn't smear things.
        new_axes: dict[AxisName, float] = {}
        for axis in (raw_out.keys() if track == TRACK_MULTI_AXIS else owned):
            if axis in raw_out:
                v = float(raw_out[axis][0]) * slot.intensity_scale
                # Volume: bounded modulation around master.intensity. Patterns can
                # only nudge Volume within ±depth of the macro envelope, so the
                # global arc stays in charge. Subjective volume swings are huge
                # in e-stim — small ripple is plenty.
                if axis == AxisName.VOLUME:
                    depth = VOLUME_MOD_DEPTH_BY_TRACK.get(track, 0.20)
                    pattern_factor = (1.0 - depth) + depth * float(np.clip(v, 0.0, 1.0))
                    v = master.intensity * pattern_factor
                new_axes[axis] = max(0.0, min(1.0, v))

        # Detect new pattern → initialise crossfade
        if slot.pattern_id != st.last_pattern_id:
            if st.last_axes:
                st.crossfade_from = dict(st.last_axes)
                st.crossfade_remaining_s = self.crossfade_s
                st.crossfade_total_s = self.crossfade_s
            st.last_pattern_id = slot.pattern_id

        # Apply crossfade (blend per-axis between previous and new pattern outputs)
        if st.crossfade_remaining_s > 0 and st.crossfade_from is not None:
            alpha = 1.0 - (st.crossfade_remaining_s / max(st.crossfade_total_s, 1e-6))
            alpha = max(0.0, min(1.0, alpha))
            for axis in list(new_axes.keys()):
                prev = st.crossfade_from.get(axis, new_axes[axis])
                new_axes[axis] = (1 - alpha) * prev + alpha * new_axes[axis]
            st.crossfade_remaining_s = max(0.0, st.crossfade_remaining_s - self.dt)

        st.last_axes = dict(new_axes)
        return new_axes

    # ─────────────────────── batch (offline) render ───────────────────────

    def render_slot(self, slot: PatternSlot) -> dict[AxisName, np.ndarray]:
        """Render a single slot offline — used by tests/debugging."""
        n = max(2, int(round(slot.duration_s / self.dt)))
        t_local = np.linspace(0, slot.duration_s, n)
        t_global = slot.t_start_s + t_local

        master = self._sample_master_at(slot.t_start_s)
        master_at = lambda tg: self._sample_master_at(tg)
        pattern_out = self._call_pattern(slot, t_local, master, master_at)

        out: dict[AxisName, np.ndarray] = {}
        for axis in AxisName:
            base = np.array([
                master_to_axis_defaults(evaluate_macro_at(self.plan, float(tg)))[axis]
                for tg in t_global
            ])
            if axis in pattern_out:
                out[axis] = np.clip(pattern_out[axis] * slot.intensity_scale, 0.0, 1.0)
            else:
                out[axis] = base
        return out

    # ─────────────────────── helpers ──────────────────────────────────────

    def _sample_master_at(self, t_global: float) -> MasterContext:
        sample = evaluate_macro_at(self.plan, t_global)
        return MasterContext(
            intensity=sample["intensity"],
            hardness=sample["hardness"],
            sharpness=sample["sharpness"],
            movement=sample["movement"],
        )

    def _call_pattern(self, slot: PatternSlot, t_local: np.ndarray,
                      master: MasterContext, master_at) -> dict[AxisName, np.ndarray]:
        if slot.pattern_id not in self.catalog:
            return {}
        pattern = self.catalog[slot.pattern_id]
        try:
            return pattern.render(t_local, slot, master, master_at, self.rng)
        except Exception as e:
            import logging
            logging.getLogger("session.micro").warning(
                "Pattern %s render failed: %s", slot.pattern_id, e
            )
            return {}
