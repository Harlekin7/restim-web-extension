"""Long-form pipeline check: render 10-min sessions in all 6 styles and report
pattern variety, intensity arcs, and axis statistics. No live Restim connection.
"""
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from src.session.macro_planner import MacroPlanner, evaluate_macro_at
from src.session.meso_scheduler import MesoScheduler
from src.session.micro_renderer import MicroRenderer
from src.session.profile import SensationMix, SessionProfile
from src.session.safety_guard import SafetyGuard
from src.session.types import AxisName, Character, ExperienceLevel, SessionStyle


def render_session(profile: SessionProfile, dt: float = 0.05):
    """Render the entire session offline and return the axis tracks."""
    plan = MacroPlanner().plan(profile)
    schedule = MesoScheduler().schedule(profile, plan)
    renderer = MicroRenderer(profile, plan, schedule, dt=dt)
    guard = SafetyGuard(profile, t_start=0.0, dt=dt)

    n = int(profile.duration_s / dt)
    tracks = {a: np.empty(n) for a in AxisName}
    pattern_track = []

    for i in range(n):
        t = i * dt
        axes = renderer.tick(t)
        clamped = guard.process(t, axes)
        for a in AxisName:
            tracks[a][i] = clamped[a]
        slot = schedule.slot_at(t)
        pattern_track.append(slot.pattern_id if slot else None)

    return plan, schedule, tracks, pattern_track


def report(profile, plan, schedule, tracks, pattern_track):
    name = profile.style.value
    duration_min = profile.duration_s / 60
    print(f"\n--- {name.upper()} ({duration_min:.0f} min, character={profile.character.value}, exp={int(profile.experience)}) ---")

    n_slots = len(schedule.slots)
    pat_counts = Counter(p for p in pattern_track if p)
    unique = len(pat_counts)
    most_common = pat_counts.most_common(5)

    print(f"  Slots: {n_slots}, Unique patterns used: {unique}, Top 5: {most_common}")

    vol = tracks[AxisName.VOLUME]
    car = tracks[AxisName.CARRIER]
    pw = tracks[AxisName.PULSE_WIDTH]
    pr = tracks[AxisName.PULSE_RISE_TIME]
    alpha = tracks[AxisName.ALPHA]

    # Intensity arc (5-phase mean)
    seg_len = len(vol) // 5
    seg_means = [float(vol[i*seg_len:(i+1)*seg_len].mean()) for i in range(5)]
    print(f"  Vol arc:    {[f'{v:.2f}' for v in seg_means]}")
    car_seg = [float(car[i*seg_len:(i+1)*seg_len].mean()) for i in range(5)]
    print(f"  Carrier:    {[f'{v:.2f}' for v in car_seg]}")

    # Local variability (proxy for "lokal lebendig")
    short_var = float(np.std(np.diff(vol[len(vol)//4:3*len(vol)//4])))
    print(f"  Local volume variability (std of dvol/dt in mid-half): {short_var:.4f}")

    # Edge depth: count moments where intensity drops by >0.15 within 10s
    win = int(10.0 / 0.05)
    drops = 0
    for i in range(0, len(vol) - win, win):
        if vol[i:i+win].max() - vol[i:i+win].min() > 0.20:
            drops += 1
    print(f"  Big drops (>0.20 in 10s window): {drops}")

    # Pattern transitions diversity
    transitions = sum(1 for a, b in zip(pattern_track, pattern_track[1:]) if a != b and a is not None and b is not None)
    print(f"  Pattern transitions: {transitions}")


def main():
    print("=" * 72)
    print("Long-form session pipeline test — 10 min per style")
    print("=" * 72)

    for style in SessionStyle:
        profile = SessionProfile(
            style=style,
            duration_s=10 * 60,
            character=Character.LEBENDIG,
            experience=ExperienceLevel.ROUTINIERT,
            sensation=SensationMix(0.5, 0.5, 0.5, 0.6),
            seed=20260515,
        )
        plan, schedule, tracks, ptrack = render_session(profile)
        report(profile, plan, schedule, tracks, ptrack)

    print("\n" + "=" * 72)
    print("Determinism: same seed, two runs of EDGING — slot sequences must match")
    print("=" * 72)
    p = SessionProfile(style=SessionStyle.EDGING, duration_s=5*60, seed=999)
    _, s1, _, _ = render_session(p)
    _, s2, _, _ = render_session(p)
    seq1 = [s.pattern_id for s in s1.slots]
    seq2 = [s.pattern_id for s in s2.slots]
    assert seq1 == seq2, f"Sequences differ! {seq1[:5]} vs {seq2[:5]}"
    print(f"  [OK] Same seed -> identical {len(seq1)}-slot sequence")

    p2 = SessionProfile(style=SessionStyle.EDGING, duration_s=5*60, seed=42)
    _, s3, _, _ = render_session(p2)
    seq3 = [s.pattern_id for s in s3.slots]
    diffs = sum(1 for a, b in zip(seq1, seq3) if a != b)
    print(f"  Different seed -> {diffs}/{min(len(seq1), len(seq3))} slot positions differ")
    assert diffs > 0, "Different seed didn't change anything!"
    print("  [OK] Different seed -> different concrete realization")


if __name__ == "__main__":
    main()
