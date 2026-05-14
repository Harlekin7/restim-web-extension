"""Meso Scheduler — selects pattern slots over the session timeline.

Strategy:
- Walk forward in time. At each step, pick a pattern duration (from character settings)
  and a pattern (weighted by phase, style affinity, compatibility with previous, recency).
- Keeps a recency window to avoid same-pattern repeats.
- Optionally injects "surprise" patterns at character-defined density.
- Runs in advance to produce a full PatternSlot list (cheap to replan after Skip/Pause).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .macro import MacroPlan
from .pattern_base import PatternMetadata, PatternSlot
from .profile import CHARACTER_PRESETS, SessionProfile
from .types import Character, PhaseName, SessionStyle


@dataclass
class MesoSchedule:
    slots: list[PatternSlot]

    def slot_at(self, t: float) -> Optional[PatternSlot]:
        for s in self.slots:
            if s.t_start_s <= t <= s.t_end_s:
                return s
        return None

    def slots_in_range(self, t_start: float, t_end: float) -> list[PatternSlot]:
        return [s for s in self.slots if not (s.t_end_s < t_start or s.t_start_s > t_end)]


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
        rng = np.random.default_rng(seed if seed is not None else plan.seed)
        char = CHARACTER_PRESETS[profile.character]
        dur_min, dur_max = char["pattern_duration_s"]
        pool_size = char["pattern_pool_size"]
        surprises_per_min = char["surprises_per_minute"]
        adv_pool = profile.advanced.pattern_pool

        # Style-filtered, character-pool-limited active set
        active_pool = self._build_active_pool(profile.style, pool_size, adv_pool, rng)
        if not active_pool:
            # Fallback: use all if catalog is empty (mock/test path)
            return MesoSchedule(slots=[])

        slots: list[PatternSlot] = []
        recency_q: list[str] = []
        recency_lockout = profile.advanced.pattern_repeat_lockout_s or (dur_max * 1.5)

        t = 0.0
        total_duration = plan.total_duration_s()

        while t < total_duration:
            phase = plan.phase_at(t).name
            slot_dur = float(rng.uniform(dur_min, dur_max))
            slot_dur = min(slot_dur, total_duration - t)
            if slot_dur < 0.5:
                break

            # Surprise injection
            is_surprise = rng.random() < (surprises_per_min * slot_dur / 60.0)

            # If a learned Markov is available, use it for the bulk of selections.
            # We still fall back to the heuristic picker for surprise mode (Markov is
            # by definition the average behaviour — surprises are explicit deviations)
            # and when prev_id is None (no Markov context yet).
            prev_id = slots[-1].pattern_id if slots else None
            if self.markov_sampler is not None and prev_id is not None and not is_surprise:
                pattern_id = self.markov_sampler.sample_next(
                    prev_pattern=prev_id,
                    style=profile.style.value,
                    phase=phase.value,
                    rng=rng,
                )
                # Markov may pick a pattern that's not in the active pool — accept anyway,
                # since Markov has already been trained on real-world style affinity.
            else:
                pattern_id = self._pick_pattern(
                    pool=active_pool,
                    phase=phase,
                    style=profile.style,
                    last_id=prev_id,
                    recency=recency_q,
                    recency_lockout_dur_units=recency_lockout / max(slot_dur, 1e-6),
                    rng=rng,
                    surprise_mode=is_surprise,
                )

            if pattern_id is None:
                # No suitable pattern — skip a small amount of time and retry
                t += 0.5
                continue

            slot = PatternSlot(
                t_start_s=t,
                t_end_s=t + slot_dur,
                pattern_id=pattern_id,
                intensity_scale=float(rng.uniform(0.85, 1.15) if is_surprise else 1.0),
            )
            slots.append(slot)

            recency_q.append(pattern_id)
            if len(recency_q) > 8:   # last 8 patterns
                recency_q.pop(0)

            t += slot_dur

        return MesoSchedule(slots=slots)

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
