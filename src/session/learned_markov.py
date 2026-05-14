"""Runtime sampler for the learned Pattern-Sequence Markov model.

Trained by `scripts/train_session_models.py`.  See `MarkovSampler.sample_next`
for the inference API; the MesoScheduler accepts an instance of this class as
its `markov_sampler` argument.

Format produced by the trainer:
    {
      "model_type": "stil_phase_markov_v1",
      "n_patterns": int,
      "pattern_ids": [...],
      "phases": ["init", "build", "plateau", "edge", "climax"],
      "min_style_samples": 5,
      "global_transitions": {prev: {next: prob}},
      "by_style_phase": {style: {phase: {prev: {next: prob}}}}
    }

Conditioned cells fall back to `global_transitions` when missing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np


class MarkovSampler:
    """Style+phase conditioned categorical sampler over pattern IDs."""

    def __init__(self, model: dict):
        self.model_type = model.get("model_type")
        self.pattern_ids: list[str] = list(model.get("pattern_ids", []))
        self.phases: list[str] = list(model.get("phases",
                                                ["init", "build", "plateau", "edge", "climax"]))
        self.min_style_samples: int = int(model.get("min_style_samples", 5))
        self._global = model.get("global_transitions", {})
        self._by_style_phase = model.get("by_style_phase", {})
        self._n = len(self.pattern_ids)
        if self._n == 0:
            raise ValueError("MarkovSampler: model has no pattern IDs")
        # Cache numpy arrays per (style, phase, prev) on demand.
        self._arr_cache: dict[tuple[Optional[str], Optional[str], str], np.ndarray] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def sample_next(self, prev_pattern: str, style: str, phase: str,
                    rng: np.random.Generator) -> str:
        """Draw the next pattern ID conditioned on (prev, style, phase)."""
        probs = self._lookup_probs(prev_pattern, style, phase)
        idx = int(rng.choice(self._n, p=probs))
        return self.pattern_ids[idx]

    def top_k(self, prev_pattern: str, style: str, phase: str, k: int = 5
              ) -> list[tuple[str, float]]:
        """Return the top-k next patterns and their probabilities."""
        probs = self._lookup_probs(prev_pattern, style, phase)
        order = np.argsort(probs)[::-1][:k]
        return [(self.pattern_ids[int(i)], float(probs[int(i)])) for i in order]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _lookup_probs(self, prev_pattern: str, style: Optional[str],
                      phase: Optional[str]) -> np.ndarray:
        cache_key = (style, phase, prev_pattern)
        cached = self._arr_cache.get(cache_key)
        if cached is not None:
            return cached

        # 1) Try style x phase x prev
        cell = None
        if style and phase:
            phase_map = self._by_style_phase.get(style, {}).get(phase, {})
            cell = phase_map.get(prev_pattern)

        # 2) Fallback to global[prev]
        if cell is None:
            cell = self._global.get(prev_pattern)

        # 3) Fallback to uniform over the universe
        if cell is None:
            arr = np.full(self._n, 1.0 / self._n, dtype=np.float64)
            self._arr_cache[cache_key] = arr
            return arr

        arr = np.array([float(cell.get(pid, 0.0)) for pid in self.pattern_ids],
                       dtype=np.float64)
        s = arr.sum()
        if s <= 0:
            arr = np.full(self._n, 1.0 / self._n, dtype=np.float64)
        else:
            arr = arr / s
        self._arr_cache[cache_key] = arr
        return arr


def load_markov(model_path: str | Path) -> MarkovSampler:
    """Load a trained Markov model from disk and wrap it in a sampler."""
    path = Path(model_path)
    with open(path, "r", encoding="utf-8") as f:
        model = json.load(f)
    if model.get("model_type") not in {"stil_phase_markov_v1"}:
        raise ValueError(f"Unsupported markov model: {model.get('model_type')}")
    return MarkovSampler(model)
