"""Micro-pattern catalog — 66 atomic Restim stimulation patterns.

Pattern IDs follow the docs/FUNSCRIPT_PATTERNS.md taxonomy:
  P1..P15        Position
  V1..V12        Volume
  PF1..PF5, PW1..PW5, PR1..PR4, PMix1..PMix3   Pulse
  C1..C5         Carrier
  M1..M15        Multi-axis
"""
from __future__ import annotations

from .position import POSITION_PATTERNS
from .volume import VOLUME_PATTERNS
from .pulse import PULSE_PATTERNS
from .carrier import CARRIER_PATTERNS
from .multi_axis import MULTI_AXIS_PATTERNS


ALL_PATTERNS: dict = {}
ALL_PATTERNS.update(POSITION_PATTERNS)
ALL_PATTERNS.update(VOLUME_PATTERNS)
ALL_PATTERNS.update(PULSE_PATTERNS)
ALL_PATTERNS.update(CARRIER_PATTERNS)
ALL_PATTERNS.update(MULTI_AXIS_PATTERNS)


__all__ = [
    "ALL_PATTERNS",
    "POSITION_PATTERNS",
    "VOLUME_PATTERNS",
    "PULSE_PATTERNS",
    "CARRIER_PATTERNS",
    "MULTI_AXIS_PATTERNS",
]
