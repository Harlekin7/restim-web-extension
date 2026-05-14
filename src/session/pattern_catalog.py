"""Pattern catalog — central registry, lookup, and compatibility scoring.

Wraps the 66 atomic patterns from src/session/patterns/* and exposes:

- ``ALL_PATTERNS`` — id -> renderer dict
- ``get_pattern(id)`` — fetch one renderer
- ``patterns_for_phase(phase)`` — filter by macro phase
- ``patterns_for_style(style)`` — filter by session style with affinity weight
- ``compatibility_score(from_id, to_id)`` — heuristic 0..1 transition score

The compatibility score is intentionally heuristic. It blends:
  1. Same/different ``PatternCategory`` (same is usually fine)
  2. Character compatibility (sharp ↔ sharp = good, sharp ↔ smooth = bad)
  3. Phase compatibility (early-arc → mid-arc patterns get a bonus)
  4. Hard contradictions (Hard-Click → Static-Floor) are explicitly penalised
  5. Style affinity overlap (patterns that share a strong style fit cluster)
"""
from __future__ import annotations

from typing import Iterable

from .pattern_base import PatternRenderer
from .patterns import ALL_PATTERNS
from .types import PatternCategory, PhaseName, SessionStyle


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def get_pattern(pattern_id: str) -> PatternRenderer:
    """Fetch a single pattern renderer by its catalog id (e.g. 'P1')."""
    if pattern_id not in ALL_PATTERNS:
        raise KeyError(f"Unknown pattern id: {pattern_id!r}")
    return ALL_PATTERNS[pattern_id]


def all_pattern_ids() -> list[str]:
    return list(ALL_PATTERNS.keys())


def patterns_for_phase(phase: PhaseName) -> list[PatternRenderer]:
    """Return every pattern whose metadata.suitable_phases contains ``phase``."""
    out = []
    for p in ALL_PATTERNS.values():
        if phase in p.metadata.suitable_phases:
            out.append(p)
    return out


def patterns_for_style(
    style: str | SessionStyle,
    min_weight: float = 1.0,
) -> list[tuple[PatternRenderer, float]]:
    """Return patterns sorted by their affinity for ``style``.

    Patterns with no explicit affinity entry default to 1.0.
    Returned items where affinity >= ``min_weight``.
    """
    key = style.value if isinstance(style, SessionStyle) else str(style)
    out = []
    for p in ALL_PATTERNS.values():
        w = float(p.metadata.style_affinity.get(key, 1.0))
        if w >= min_weight:
            out.append((p, w))
    out.sort(key=lambda item: -item[1])
    return out


# ---------------------------------------------------------------------------
# Compatibility scoring — heuristic
# ---------------------------------------------------------------------------

# Characterise each pattern as "soft", "sharp", "neutral" purely from name + id.
# The classification is rough but consistent — used only as one of several signals.
_SHARP_IDS = {
    "P3", "P5", "P13", "P15",
    "V6", "V9", "V11",
    "PW1", "PMix3", "PR4",
    "C5",
    "M2", "M15",
}
_SOFT_IDS = {
    "P1", "P2", "P6", "P11",
    "V1", "V5",
    "PW5", "PR3",
    "PMix2",
    "C1",
    "M5",
}
_BUILD_IDS = {
    "V1", "V2", "V3", "V4",
    "PW2", "PR1", "PF4",
    "C3", "C5",
    "M1", "M11", "M13",
    "P12",
}
_RECOVERY_IDS = {
    "P1", "P2", "P6", "P11",
    "V5", "V7", "V11",
    "PR3", "PMix2",
    "C1",
}


def _character(pid: str) -> str:
    if pid in _SHARP_IDS:
        return "sharp"
    if pid in _SOFT_IDS:
        return "soft"
    return "neutral"


# Hard contradictions — no immediate transition allowed (score floor).
_HARD_CONTRADICTIONS: set[tuple[str, str]] = {
    # going from a hard-click straight into a dead-still floor jars
    ("PMix3", "P1"), ("PMix3", "P2"),
    ("PR4", "PR3"),
    ("V6", "V5"), ("V11", "V5"),
    ("M8", "P1"),
    ("V11", "V1"),
}


def _phase_affinity_overlap(a, b) -> float:
    sa = set(a.metadata.suitable_phases)
    sb = set(b.metadata.suitable_phases)
    if not sa or not sb:
        return 0.5
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / max(1, union)


def _style_affinity_overlap(a, b) -> float:
    keys = set(a.metadata.style_affinity) | set(b.metadata.style_affinity)
    if not keys:
        return 0.5
    sims = []
    for k in keys:
        wa = float(a.metadata.style_affinity.get(k, 1.0))
        wb = float(b.metadata.style_affinity.get(k, 1.0))
        # closer weights = more compatible
        sims.append(1.0 - min(1.0, abs(wa - wb) / 2.0))
    return sum(sims) / len(sims)


def _macro_arc_bonus(from_id: str, to_id: str) -> float:
    """Reward ordered transitions that follow the macro arc Init→Build→Plateau→Edge→Climax."""
    f = ALL_PATTERNS[from_id].metadata
    t = ALL_PATTERNS[to_id].metadata
    arc = [PhaseName.INIT, PhaseName.BUILD, PhaseName.PLATEAU, PhaseName.EDGE, PhaseName.CLIMAX]
    f_score = max((arc.index(p) for p in f.suitable_phases if p in arc), default=-1)
    t_score = min((arc.index(p) for p in t.suitable_phases if p in arc), default=99)
    if t_score >= f_score and t_score - f_score <= 2:
        return 0.10
    if t_score < f_score - 1:
        # going backwards in the arc is mildly penalised
        return -0.05
    return 0.0


def compatibility_score(from_id: str, to_id: str) -> float:
    """Returns 0..1, heuristic score for placing ``to_id`` directly after ``from_id``.

    Higher = better fit. The matrix is asymmetric on purpose — going from
    a build-pattern into a recovery-pattern is fine; the reverse seldom is.
    """
    if from_id not in ALL_PATTERNS or to_id not in ALL_PATTERNS:
        raise KeyError(f"Unknown pattern id pair: {from_id!r} -> {to_id!r}")

    if (from_id, to_id) in _HARD_CONTRADICTIONS:
        return 0.10

    a = ALL_PATTERNS[from_id]
    b = ALL_PATTERNS[to_id]

    # --- Category compatibility ---
    same_cat = a.metadata.category == b.metadata.category
    cat_score = 0.55 if same_cat else 0.50  # cross-category often cooperates

    # --- Character compatibility ---
    ca = _character(from_id)
    cb = _character(to_id)
    if ca == cb:
        char_score = 0.80
    elif "neutral" in (ca, cb):
        char_score = 0.65
    elif {ca, cb} == {"sharp", "soft"}:
        char_score = 0.30
    else:
        char_score = 0.50

    # --- Phase / style overlap ---
    phase_score = _phase_affinity_overlap(a, b)
    style_score = _style_affinity_overlap(a, b)

    # --- Arc bonus ---
    arc_bonus = _macro_arc_bonus(from_id, to_id)

    # Weighted combination
    raw = (
        0.20 * cat_score
        + 0.25 * char_score
        + 0.25 * phase_score
        + 0.20 * style_score
        + 0.10  # base offset, neutralised by arc adjustment below
        + arc_bonus
    )

    # Recovery-after-peak bonus
    if from_id in {"PMix3", "V6", "V11", "PR4"} and to_id in _RECOVERY_IDS:
        raw += 0.08
    # Build-into-build bonus (chained crescendo)
    if from_id in _BUILD_IDS and to_id in _BUILD_IDS:
        raw += 0.06
    # Same character + same category = strong cluster
    if same_cat and ca == cb and ca != "neutral":
        raw += 0.05

    return float(max(0.0, min(1.0, raw)))


# ---------------------------------------------------------------------------
# Convenience exports
# ---------------------------------------------------------------------------

__all__ = [
    "ALL_PATTERNS",
    "all_pattern_ids",
    "get_pattern",
    "patterns_for_phase",
    "patterns_for_style",
    "compatibility_score",
]
