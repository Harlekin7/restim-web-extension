"""Runtime loader for the learned macro intensity envelope sampler.

Trained by `scripts/train_session_models.py`.  The returned callable is meant
to be passed to `MacroPlanner(learned_intensity_sampler=...)`.

Format produced by the trainer:
    {
      "model_type": "per_style_meanstd_v1",
      "trained_on_sessions": int,
      "n_resample_points": 100,
      "control_points": 7,
      "styles": {
        "<style>": {
          "n_samples": int,
          "mean_curve_100pts": [...],
          "std_curve_100pts": [...],
          "control_point_indices": [...],
          "is_fallback": bool
        },
        ...
      }
    }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np

from .macro import MasterCurve
from .profile import EXPERIENCE_CAPS, SessionProfile


def _coerce_style(profile: SessionProfile) -> str:
    """Style enum -> canonical lowercase string used in the model."""
    raw = getattr(profile.style, "value", profile.style)
    return str(raw)


def _sample_for_profile(model: dict, profile: SessionProfile,
                        rng: np.random.Generator) -> MasterCurve:
    style = _coerce_style(profile)
    styles_cfg = model["styles"]
    cfg = styles_cfg.get(style)
    if cfg is None:
        # Hard fallback: sanfter_aufbau is always present (template fallback).
        cfg = styles_cfg["sanfter_aufbau"]

    mean = np.asarray(cfg["mean_curve_100pts"], dtype=np.float64)
    std = np.asarray(cfg["std_curve_100pts"], dtype=np.float64)
    cp_idx = cfg["control_point_indices"]
    n = mean.shape[0]

    # Sample 100-point curve; clip to [0,1] before scaling to caps.
    noise = rng.normal(0.0, 1.0, size=mean.shape)
    sampled = np.clip(mean + noise * std, 0.0, 1.0)

    # Scale to experience-level intensity caps (vol_floor..vol_ceiling).
    caps = EXPERIENCE_CAPS[profile.experience]
    vol_floor = float(caps["vol_floor"])
    vol_ceiling = float(caps["vol_ceiling"])
    scaled = vol_floor + sampled * (vol_ceiling - vol_floor)

    duration_s = float(profile.duration_s)
    points: list[tuple[float, float]] = []
    for idx in cp_idx:
        t = (idx / max(n - 1, 1)) * duration_s
        points.append((float(t), float(scaled[idx])))
    if not points:
        points = [(0.0, vol_floor), (duration_s, vol_ceiling)]
    return MasterCurve.from_points(points)


def load_sampler(model_path: str | Path
                 ) -> Callable[[SessionProfile, np.random.Generator], MasterCurve]:
    """Return a sampler callable that the MacroPlanner injects."""
    path = Path(model_path)
    with open(path, "r", encoding="utf-8") as f:
        model = json.load(f)
    if model.get("model_type") not in {"per_style_meanstd_v1"}:
        raise ValueError(f"Unsupported macro envelope model: {model.get('model_type')}")

    def _sampler(profile: SessionProfile, rng: np.random.Generator) -> MasterCurve:
        return _sample_for_profile(model, profile, rng)

    # Make introspection easier
    _sampler.model_type = model.get("model_type")
    _sampler.trained_on_sessions = model.get("trained_on_sessions")
    return _sampler
