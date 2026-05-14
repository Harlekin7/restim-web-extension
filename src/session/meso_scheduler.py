"""Meso Scheduler — selects pattern slots over the session timeline.

Multi-track architecture: each pattern category runs on its own independent
track, so a Position pattern is ALWAYS active alongside the active Volume,
Pulse, Carrier patterns. "Static" (P1) is just one Position pattern among 15,
not a default fallback.

Tracks:
 - position    (always active — Position-patterns drive alpha/beta)
 - volume      (always active — Volume-patterns drive volume)
 - pulse       (always active — Pulse-patterns drive pulse_freq/width/rise)
 - carrier     (always active — Carrier-patterns drive carrier)
 - multi_axis  (optional overlay — Multi-Axis-patterns can override several axes;
                gaps between slots = no overlay, the per-track patterns drive)

For each track:
 - Walk forward in time. At each step, pick a pattern duration (from character
   settings) and a pattern from the category-filtered pool (weighted by phase,
   style affinity, compat with previous, recency).
 - Optionally inject "surprise" patterns at character-defined density.

Runs in advance to produce a full per-track schedule (cheap to replan after
Skip/Pause).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .macro import MacroPlan
from .pattern_base import PatternMetadata, PatternSlot
from .profile import CHARACTER_PRESETS, SessionProfile
from .types import AxisName, Character, PatternCategory, PhaseName, SessionStyle


# Track names. Each track holds an independent slot sequence.
TRACK_POSITION = "position"
TRACK_VOLUME = "volume"
TRACK_PULSE = "pulse"
TRACK_CARRIER = "carrier"
TRACK_MULTI_AXIS = "multi_axis"

# Map track -> categories that feed it.
_TRACK_CATEGORIES: dict[str, tuple[PatternCategory, ...]] = {
    TRACK_POSITION:    (PatternCategory.POSITION,),
    TRACK_VOLUME:      (PatternCategory.VOLUME,),
    TRACK_PULSE:       (PatternCategory.PULSE,),
    TRACK_CARRIER:     (PatternCategory.CARRIER,),
    TRACK_MULTI_AXIS:  (PatternCategory.MULTI_AXIS,),
}

# Tracks that must be filled across the entire session (no idle gaps allowed).
ALWAYS_ACTIVE_TRACKS = (TRACK_POSITION, TRACK_VOLUME, TRACK_PULSE, TRACK_CARRIER)

# Multi-axis is an optional overlay — present only on a fraction of total time.
MULTI_AXIS_COVERAGE_DEFAULT = 0.30   # ~30% of session time


@dataclass
class MesoSchedule:
    """Multi-track schedule. `tracks[track_name]` holds an ordered list of slots
    for that track. The legacy `slots` field is kept as a flattened view for
    backward compatibility with old callers/tests."""

    tracks: dict[str, list[PatternSlot]] = field(default_factory=dict)

    @property
    def slots(self) -> list[PatternSlot]:
        out: list[PatternSlot] = []
        for s_list in self.tracks.values():
            out.extend(s_list)
        out.sort(key=lambda s: s.t_start_s)
        return out

    def slot_at(self, t: float, track: Optional[str] = None) -> Optional[PatternSlot]:
        """If track is given, returns the slot active on that track at time t.
        Without track, returns the first matching slot (legacy behaviour)."""
        if track is not None:
            for s in self.tracks.get(track, []):
                if s.t_start_s <= t <= s.t_end_s:
                    return s
            return None
        for s_list in self.tracks.values():
            for s in s_list:
                if s.t_start_s <= t <= s.t_end_s:
                    return s
        return None

    def slots_in_range(self, t_start: float, t_end: float,
                       track: Optional[str] = None) -> list[PatternSlot]:
        if track is not None:
            return [s for s in self.tracks.get(track, [])
                    if not (s.t_end_s < t_start or s.t_start_s > t_end)]
        return [s for s in self.slots
                if not (s.t_end_s < t_start or s.t_start_s > t_end)]


# Type aliases for clarity (catalog is provided by pattern_catalog at runtime)
PatternRegistry = dict[str, "PatternRendererProtocol"]


class MesoScheduler:
    """Lazily-imported pattern catalog so Meso can be loaded standalone in tests.

    Optional `markov_sampler` overrides the default heuristic pattern selection
    once the trained model from Agent D is available. The sampler is expected
    to expose `sample_next(prev_pattern, style, phase, rng) -> str` and a list
    of valid pattern IDs `pattern_ids`.
    """

    def __init__(self, catalog: Optional[PatternRegistry] = None,
                 markov_sampler=None):
        if catalog is None:
            try:
                from .pattern_catalog import ALL_PATTERNS
                catalog = ALL_PATTERNS
            except Exception:
                catalog = {}
        self.catalog = catalog
        self.markov_sampler = markov_sampler

    def schedule(self, profile: SessionProfile, plan: MacroPlan,
                 seed: Optional[int] = None) -> MesoSchedule:
        """Build a multi-track schedule. Each always-active track is filled
        contiguously across the session duration. Multi-axis is sparser."""
        seed_val = seed if seed is not None else plan.seed
        rng = np.random.default_rng(seed_val)
        total_duration = plan.total_duration_s()

        tracks: dict[str, list[PatternSlot]] = {}

        # Always-active tracks: Position, Volume, Pulse, Carrier
        for i, track_name in enumerate(ALWAYS_ACTIVE_TRACKS):
            # Use a different seed per track so they don't all pick the same patterns
            track_rng = np.random.default_rng(seed_val + 1000 * i + 7)
            tracks[track_name] = self._schedule_track(
                track_name=track_name,
                profile=profile,
                plan=plan,
                rng=track_rng,
                total_duration=total_duration,
                require_full_coverage=True,
            )

        # Optional multi-axis overlay: sparser, with explicit gaps
        ma_rng = np.random.default_rng(seed_val + 9999)
        tracks[TRACK_MULTI_AXIS] = self._schedule_track(
            track_name=TRACK_MULTI_AXIS,
            profile=profile,
            plan=plan,
            rng=ma_rng,
            total_duration=total_duration,
            require_full_coverage=False,
            target_coverage=MULTI_AXIS_COVERAGE_DEFAULT,
        )

        return MesoSchedule(tracks=tracks)

    def _schedule_track(self, track_name: str, profile: SessionProfile,
                        plan: MacroPlan, rng: np.random.Generator,
                        total_duration: float,
                        require_full_coverage: bool,
                        target_coverage: float = 1.0) -> list[PatternSlot]:
        """Schedule one track. If require_full_coverage, fills the entire timeline.
        Otherwise inserts patterns at random gaps until target_coverage is reached."""
        char = CHARACTER_PRESETS[profile.character]
        dur_min, dur_max = char["pattern_duration_s"]
        pool_size = char["pattern_pool_size"]
        surprises_per_min = char["surprises_per_minute"]
        adv_pool = profile.advanced.pattern_pool

        # Filter the global pool to this track's categories
        allowed_cats = _TRACK_CATEGORIES[track_name]
        active_pool = self._build_active_pool_for_categories(
            profile.style, pool_size, adv_pool, allowed_cats, rng,
        )
        if not active_pool:
            return []

        slots: list[PatternSlot] = []
        recency_q: list[str] = []
        recency_lockout = profile.advanced.pattern_repeat_lockout_s or (dur_max * 1.5)

        if require_full_coverage:
            t = 0.0
            while t < total_duration:
                phase = plan.phase_at(t).name
                slot_dur = float(rng.uniform(dur_min, dur_max))
                slot_dur = min(slot_dur, total_duration - t)
                if slot_dur < 0.5:
                    break

                is_surprise = rng.random() < (surprises_per_min * slot_dur / 60.0)
                prev_id = slots[-1].pattern_id if slots else None

                pattern_id = self._select_pattern(
                    active_pool, phase, profile.style, prev_id, recency_q,
                    recency_lockout, slot_dur, rng, is_surprise,
                )
                if pattern_id is None:
                    t += 0.5
                    continue

                slots.append(PatternSlot(
                    t_start_s=t, t_end_s=t + slot_dur,
                    pattern_id=pattern_id,
                    intensity_scale=float(rng.uniform(0.85, 1.15) if is_surprise else 1.0),
                ))
                recency_q.append(pattern_id)
                if len(recency_q) > 8:
                    recency_q.pop(0)
                t += slot_dur
        else:
            # Sparse mode: pick non-overlapping intervals up to target_coverage
            target_total_s = total_duration * target_coverage
            covered = 0.0
            attempts = 0
            while covered < target_total_s and attempts < 200:
                attempts += 1
                slot_dur = float(rng.uniform(dur_min, dur_max))
                # candidate start in [0, total_duration - slot_dur]
                if slot_dur >= total_duration:
                    break
                t = float(rng.uniform(0, total_duration - slot_dur))
                # Reject if overlaps any existing slot
                if any(not (s.t_end_s + 5.0 < t or s.t_start_s > t + slot_dur + 5.0)
                       for s in slots):
                    continue
                phase = plan.phase_at(t).name
                prev_id = slots[-1].pattern_id if slots else None
                pattern_id = self._select_pattern(
                    active_pool, phase, profile.style, prev_id, recency_q,
                    recency_lockout, slot_dur, rng, False,
                )
                if pattern_id is None:
                    continue
                slots.append(PatternSlot(
                    t_start_s=t, t_end_s=t + slot_dur,
                    pattern_id=pattern_id,
                ))
                covered += slot_dur
                recency_q.append(pattern_id)
                if len(recency_q) > 4:
                    recency_q.pop(0)
            slots.sort(key=lambda s: s.t_start_s)

        return slots

    def _select_pattern(self, pool, phase, style, prev_id, recency_q,
                        recency_lockout, slot_dur, rng, is_surprise) -> Optional[str]:
        """Wraps Markov + heuristic picker."""
        if self.markov_sampler is not None and prev_id is not None and not is_surprise:
            pattern_id = self.markov_sampler.sample_next(
                prev_pattern=prev_id,
                style=style.value,
                phase=phase.value,
                rng=rng,
            )
            # Verify Markov pick is in our pool — if not, fall back to heuristic
            if pattern_id and any(m.id == pattern_id for m in pool):
                return pattern_id

        return self._pick_pattern(
            pool=pool,
            phase=phase,
            style=style,
            last_id=prev_id,
            recency=recency_q,
            recency_lockout_dur_units=recency_lockout / max(slot_dur, 1e-6),
            rng=rng,
            surprise_mode=is_surprise,
        )

    def _build_active_pool_for_categories(
        self, style: SessionStyle, pool_size: int,
        advanced_pool: Optional[list[str]],
        allowed_categories: tuple[PatternCategory, ...],
        rng: np.random.Generator,
    ) -> list[PatternMetadata]:
        if advanced_pool is not None:
            ids = advanced_pool
        else:
            ids = list(self.catalog.keys())

        # Filter by category first
        all_metas = [
            self.catalog[pid].metadata for pid in ids
            if pid in self.catalog
            and self.catalog[pid].metadata.category in allowed_categories
        ]
        if not all_metas:
            return []

        weighted = [(m, m.style_affinity.get(style.value, 1.0)) for m in all_metas]
        weighted.sort(key=lambda x: x[1], reverse=True)
        cut = min(len(weighted), max(pool_size, 5))
        return [m for m, _ in weighted[:cut]]

    def _build_active_pool(self, style: SessionStyle, pool_size: int,
                           advanced_pool: Optional[list[str]],
                           rng: np.random.Generator) -> list[PatternMetadata]:
        if advanced_pool is not None:
            ids = advanced_pool
        else:
            ids = list(self.catalog.keys())

        all_metas = [self.catalog[pid].metadata for pid in ids if pid in self.catalog]
        if not all_metas:
            return []

        # Weight by style affinity, sort, take top pool_size
        weighted = [(m, m.style_affinity.get(style.value, 1.0)) for m in all_metas]
        weighted.sort(key=lambda x: x[1], reverse=True)
        # If pool_size huge (Wild=999), keep all
        cut = min(len(weighted), max(pool_size, 5))
        active = [m for m, _ in weighted[:cut]]
        return active

    def _pick_pattern(self, pool: list[PatternMetadata], phase: PhaseName,
                      style: SessionStyle, last_id: Optional[str],
                      recency: list[str], recency_lockout_dur_units: float,
                      rng: np.random.Generator, surprise_mode: bool) -> Optional[str]:
        if not pool:
            return None

        # Compatibility scores
        try:
            from .pattern_catalog import compatibility_score
        except Exception:
            compatibility_score = lambda a, b: 0.7   # neutral fallback

        weights = []
        for m in pool:
            w = 1.0
            # Phase suitability
            if phase in m.suitable_phases:
                w *= 2.0
            elif m.suitable_phases:   # has restrictions, current phase not in them
                w *= 0.3
            # Style affinity
            w *= max(0.05, m.style_affinity.get(style.value, 1.0))
            # Compatibility with last
            if last_id is not None:
                w *= max(0.1, compatibility_score(last_id, m.id))
            # Recency penalty
            if m.id in recency:
                idx = recency.index(m.id)
                penalty = 0.1 + (0.9 * idx / max(len(recency), 1))
                w *= penalty

            weights.append(w)

        weights = np.array(weights, dtype=float)
        if weights.sum() <= 0:
            return rng.choice([m.id for m in pool])

        # Surprise mode: invert weights (pick from less-likely candidates)
        if surprise_mode:
            weights = (weights.max() + 0.01) - weights
            weights = np.maximum(weights, 0.01)

        weights = weights / weights.sum()
        idx = int(rng.choice(len(pool), p=weights))
        return pool[idx].id
