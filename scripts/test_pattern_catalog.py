"""Smoke-test for the pattern catalog.

For every registered pattern this script:
  - constructs a 5-second slot
  - renders it at 50 Hz
  - validates that all returned arrays are in [0,1] and free of NaN/Inf
  - prints a per-pattern table: id | category | axes | min/max/mean

Run from project root::

  python -m scripts.test_pattern_catalog

or as a script::

  python scripts/test_pattern_catalog.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

# Allow running as plain script from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.session.pattern_base import MasterContext, PatternSlot
from src.session.pattern_catalog import ALL_PATTERNS, all_pattern_ids, compatibility_score


SAMPLE_RATE_HZ = 50.0
DURATION_S = 5.0


def mock_master(t_global: float) -> MasterContext:
    """Toy master envelope: linear ramp 0.4 → 0.85 over 1 hour."""
    progress = max(0.0, min(1.0, t_global / 3600.0))
    inten = 0.40 + 0.45 * progress
    return MasterContext(
        intensity=inten,
        hardness=0.30 + 0.55 * progress,
        sharpness=0.50 + 0.40 * progress,
        movement=0.40 + 0.40 * progress,
    )


def main() -> int:
    n = int(SAMPLE_RATE_HZ * DURATION_S)
    t_local = np.linspace(0.0, DURATION_S, n, endpoint=False)
    rng_master = np.random.default_rng(42)

    print(f"Running pattern catalog smoke-test "
          f"({len(ALL_PATTERNS)} patterns, {DURATION_S}s @ {SAMPLE_RATE_HZ}Hz)")
    print()

    header = (
        f"{'id':<6} {'category':<11} {'axes':<46} "
        f"{'min':>5} {'max':>5} {'mean':>5} {'time_ms':>7} {'status':<6}"
    )
    print(header)
    print("-" * len(header))

    failures = []
    timings_ms = []

    for pid in all_pattern_ids():
        renderer = ALL_PATTERNS[pid]
        slot = PatternSlot(
            t_start_s=10.0,
            t_end_s=10.0 + DURATION_S,
            pattern_id=pid,
            intensity_scale=1.0,
            parameters={},
        )
        master = mock_master(slot.t_start_s)
        rng = np.random.default_rng(np.frombuffer(pid.encode(), dtype=np.uint8).sum())

        t0 = time.perf_counter()
        try:
            out = renderer.render(t_local, slot, master, mock_master, rng)
        except Exception as exc:  # pragma: no cover -- diagnostic path
            print(f"{pid:<6} ERROR during render: {exc}")
            failures.append((pid, str(exc)))
            continue
        dt_ms = (time.perf_counter() - t0) * 1000.0
        timings_ms.append(dt_ms)

        axes_str = ",".join(a.value for a in out.keys())
        all_min = min(float(np.min(arr)) for arr in out.values())
        all_max = max(float(np.max(arr)) for arr in out.values())
        all_mean = float(np.mean([float(np.mean(arr)) for arr in out.values()]))

        # validation
        ok = True
        for axis, arr in out.items():
            if arr.shape != (n,):
                failures.append((pid, f"axis {axis.value} bad shape {arr.shape}"))
                ok = False
            if np.any(~np.isfinite(arr)):
                failures.append((pid, f"axis {axis.value} contains NaN/Inf"))
                ok = False
            if np.any(arr < -1e-9) or np.any(arr > 1.0 + 1e-9):
                failures.append((pid, f"axis {axis.value} out of [0,1]: "
                                       f"min={float(np.min(arr)):.3f}, "
                                       f"max={float(np.max(arr)):.3f}"))
                ok = False
        status = "OK" if ok else "FAIL"

        print(f"{pid:<6} {renderer.metadata.category.value:<11} {axes_str:<46} "
              f"{all_min:>5.2f} {all_max:>5.2f} {all_mean:>5.2f} "
              f"{dt_ms:>7.2f} {status:<6}")

    print()
    print(f"Renders: {len(timings_ms)}, "
          f"avg={np.mean(timings_ms):.2f} ms, "
          f"p95={np.percentile(timings_ms, 95):.2f} ms, "
          f"max={np.max(timings_ms):.2f} ms")

    # quick compatibility-matrix sanity
    print()
    print("Compatibility-matrix spot checks:")
    pairs = [
        ("P1", "P3"), ("P3", "P5"), ("PMix3", "P1"),
        ("V1", "V3"), ("V6", "V5"), ("PR4", "PR3"),
        ("M1", "M8"), ("M8", "PMix2"), ("PMix1", "PMix2"),
    ]
    for a, b in pairs:
        s = compatibility_score(a, b)
        print(f"  {a:>5} -> {b:<5}: {s:.2f}")

    if failures:
        print()
        print(f"FAILURES ({len(failures)}):")
        for pid, msg in failures:
            print(f"  {pid}: {msg}")
        return 1

    print()
    print("All patterns rendered successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
