"""Pipeline test with the learned envelope sampler + Markov pattern model active."""
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from src.session.learned_envelope import load_sampler
from src.session.learned_markov import load_markov
from src.session.macro_planner import MacroPlanner, evaluate_macro_at
from src.session.meso_scheduler import MesoScheduler
from src.session.micro_renderer import MicroRenderer
from src.session.profile import SessionProfile
from src.session.safety_guard import SafetyGuard
from src.session.types import AxisName, Character, ExperienceLevel, SessionStyle


def render_with(profile, env_sampler, markov_sampler, dt=0.05):
    plan = MacroPlanner(learned_intensity_sampler=env_sampler).plan(profile)
    schedule = MesoScheduler(markov_sampler=markov_sampler).schedule(profile, plan)
    renderer = MicroRenderer(profile, plan, schedule, dt=dt)
    guard = SafetyGuard(profile, t_start=0.0, dt=dt)

    n = int(profile.duration_s / dt)
    vol_track = np.empty(n)
    pat_seq = []
    for i in range(n):
        t = i * dt
        axes = renderer.tick(t)
        clamped = guard.process(t, axes)
        vol_track[i] = clamped[AxisName.VOLUME]
        slot = schedule.slot_at(t)
        if slot:
            pat_seq.append(slot.pattern_id)

    return plan, schedule, vol_track, pat_seq


def main():
    print("=" * 72)
    print("Pipeline test WITH learned envelope + Markov samplers")
    print("=" * 72)

    env = load_sampler("data/models/macro_envelope_sampler.json")
    mk = load_markov("data/models/pattern_markov.json")

    for style in SessionStyle:
        profile = SessionProfile(
            style=style,
            duration_s=10 * 60,
            character=Character.LEBENDIG,
            experience=ExperienceLevel.ROUTINIERT,
            seed=20260515,
        )
        # With learned models
        plan_l, sch_l, vol_l, seq_l = render_with(profile, env, mk)
        # Rule-based for comparison
        plan_r, sch_r, vol_r, seq_r = render_with(profile, None, None)

        seg = len(vol_l) // 5
        vol_arc_l = [float(vol_l[i*seg:(i+1)*seg].mean()) for i in range(5)]
        vol_arc_r = [float(vol_r[i*seg:(i+1)*seg].mean()) for i in range(5)]

        unique_l = len(set(seq_l))
        unique_r = len(set(seq_r))

        print(f"\n--- {style.value.upper()} ---")
        print(f"  LEARNED: arc={[f'{v:.2f}' for v in vol_arc_l]}, {len(set(seq_l))} unique patterns, top: {Counter(seq_l).most_common(3)}")
        print(f"  RULE:    arc={[f'{v:.2f}' for v in vol_arc_r]}, {len(set(seq_r))} unique patterns, top: {Counter(seq_r).most_common(3)}")

        # Different sequences? (should be — Markov picks differently)
        diffs = sum(1 for a, b in zip(seq_l, seq_r) if a != b)
        print(f"  Sequence divergence (learned vs rule): {diffs}/{min(len(seq_l), len(seq_r))} positions differ")


if __name__ == "__main__":
    main()
