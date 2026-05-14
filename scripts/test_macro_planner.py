"""Smoke-test for the MacroPlanner. Runs all 6 styles, checks plan integrity, prints summary."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from src.session.macro_planner import MacroPlanner, evaluate_macro_at
from src.session.profile import (
    SafetyCaps,
    SensationMix,
    SessionProfile,
)
from src.session.types import (
    Character,
    DeviceClass,
    ExperienceLevel,
    SessionStyle,
    SessionTarget,
)


def test_style(style: SessionStyle, duration_s: int = 30 * 60):
    profile = SessionProfile(
        style=style,
        duration_s=duration_s,
        target=SessionTarget.CLIMAX,
        sensation=SensationMix(0.5, 0.5, 0.5, 0.5),
        character=Character.LEBENDIG,
        experience=ExperienceLevel.ERFAHREN,
        seed=42,
    )

    planner = MacroPlanner()
    plan = planner.plan(profile)

    # Sample the plan over time
    ts = np.linspace(0, duration_s, 200)
    samples = [evaluate_macro_at(plan, float(t)) for t in ts]
    intensities = np.array([s["intensity"] for s in samples])
    macros = np.array([s["macro_only"] for s in samples])
    hardnesses = np.array([s["hardness"] for s in samples])
    sharpnesses = np.array([s["sharpness"] for s in samples])

    print(f"\n=== {style.value.upper()} ({duration_s/60:.0f} min) ===")
    print(f"  Phases:    {[(p.name.value, round(p.duration_s/60, 1)) for p in plan.phases]}")
    print(f"  Edges:     {len(plan.edges)} planned, depths={[round(e.depth, 2) for e in plan.edges[:5]]}")
    print(f"  SubWaves:  {len(plan.subwaves)} total, avg amp={np.mean([s.amplitude for s in plan.subwaves]):.3f}")
    print(f"  Intensity: mean={intensities.mean():.3f}, peak={intensities.max():.3f}, floor={intensities.min():.3f}")
    print(f"  Macro:     mean={macros.mean():.3f}, peak={macros.max():.3f}")
    print(f"  Hardness:  mean={hardnesses.mean():.3f}, range=[{hardnesses.min():.3f}, {hardnesses.max():.3f}]")
    print(f"  Sharpness: mean={sharpnesses.mean():.3f}, range=[{sharpnesses.min():.3f}, {sharpnesses.max():.3f}]")

    # Sanity checks
    assert np.all(np.isfinite(intensities)), "NaN/Inf in intensities"
    assert intensities.min() >= 0 and intensities.max() <= 1, "Intensity out of [0,1]"
    assert hardnesses.min() >= 0 and hardnesses.max() <= 1, "Hardness out of [0,1]"
    return plan, intensities, ts


def test_determinism():
    """Same profile + seed → bit-identical plan. Different seed → different concrete realization."""
    profile = SessionProfile(
        style=SessionStyle.EDGING,
        duration_s=20 * 60,
        seed=12345,
    )
    planner = MacroPlanner()
    p1 = planner.plan(profile, seed=12345)
    p2 = planner.plan(profile, seed=12345)
    p3 = planner.plan(profile, seed=99999)

    assert len(p1.subwaves) == len(p2.subwaves), "Determinism broken (count)"
    for sw1, sw2 in zip(p1.subwaves, p2.subwaves):
        assert abs(sw1.t_start_s - sw2.t_start_s) < 1e-6, "Determinism broken (t)"
        assert abs(sw1.amplitude - sw2.amplitude) < 1e-6, "Determinism broken (amp)"

    assert len(p1.edges) == len(p2.edges), "Edge determinism broken"

    # Different seed → different realization (at least somewhere)
    if len(p1.subwaves) > 0 and len(p3.subwaves) > 0:
        diffs = [abs(s1.t_start_s - s3.t_start_s) for s1, s3 in zip(p1.subwaves, p3.subwaves)
                 if s1 is not None and s3 is not None]
        assert any(d > 1.0 for d in diffs), "Different seed didn't change anything!"

    print("\n[OK] Determinism check passed (same seed = identical, different seed = different)")


def test_experience_caps():
    """Experience level changes the volume ceiling and pulse-width caps."""
    plans = {}
    for level in ExperienceLevel:
        profile = SessionProfile(
            style=SessionStyle.CRESCENDO,
            duration_s=30 * 60,
            experience=level,
            seed=777,
        )
        plan = MacroPlanner().plan(profile)
        plans[level.name] = plan.envelopes.intensity.values.max()

    print("\n=== Experience caps (peak intensity) ===")
    for name, peak in plans.items():
        print(f"  {name:14s}: {peak:.3f}")
    # Higher level should reach higher peak
    assert plans["BEGINNER"] < plans["PROFI"], "Experience caps not enforced!"
    print("[OK] Experience caps enforced")


def main():
    print("=" * 60)
    print("MacroPlanner Smoke Test")
    print("=" * 60)

    for style in SessionStyle:
        test_style(style)

    test_determinism()
    test_experience_caps()

    print("\n" + "=" * 60)
    print("All checks passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
