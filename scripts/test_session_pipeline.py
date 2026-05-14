"""End-to-end pipeline test: Profile -> Plan -> Schedule -> Render -> Safety -> TCode-format.

No live Restim connection. Just validates the chain works without exceptions and
produces sensible output.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from src.session.macro_planner import MacroPlanner
from src.session.meso_scheduler import MesoScheduler
from src.session.micro_renderer import MicroRenderer
from src.session.profile import SensationMix, SessionProfile
from src.session.safety_guard import SafetyGuard
from src.session.session_runner import SessionRunner
from src.session.types import AxisName, Character, ExperienceLevel, SessionStyle, SessionTarget
from src.restim.tcode_client import format_tcode


def test_pipeline_offline():
    print("=" * 60)
    print("End-to-end Session Pipeline Test")
    print("=" * 60)

    # Build a 5-min Crescendo for the Erfahren stage
    profile = SessionProfile(
        style=SessionStyle.CRESCENDO,
        duration_s=5 * 60,
        target=SessionTarget.CLIMAX,
        sensation=SensationMix(0.4, 0.6, 0.5, 0.7),
        character=Character.LEBENDIG,
        experience=ExperienceLevel.ERFAHREN,
        seed=2026,
    )

    plan = MacroPlanner().plan(profile)
    schedule = MesoScheduler().schedule(profile, plan)
    print(f"\nPlan:")
    print(f"  Phases:    {[(p.name.value, round(p.duration_s, 1)) for p in plan.phases]}")
    print(f"  SubWaves:  {len(plan.subwaves)}")
    print(f"  Edges:     {len(plan.edges)}")
    print(f"\nSchedule: {len(schedule.slots)} pattern slots")
    if schedule.slots:
        slot_ids = [s.pattern_id for s in schedule.slots[:8]]
        print(f"  First 8 slot pattern IDs: {slot_ids}")
        durs = [s.duration_s for s in schedule.slots]
        print(f"  Slot durations:  min={min(durs):.1f}s  max={max(durs):.1f}s  mean={sum(durs)/len(durs):.1f}s")

    # Render a 30s window to verify renderer + safety produce valid TCode
    renderer = MicroRenderer(profile, plan, schedule, dt=0.02)
    guard = SafetyGuard(profile, t_start=0.0, dt=0.02)

    n_ticks = 30 * 50  # 30s @ 50Hz
    samples_log = []
    for i in range(n_ticks):
        t = i * 0.02
        axes = renderer.tick(t)
        clamped = guard.process(t, axes)
        samples_log.append(clamped)

    # Convert to TCode at last tick
    last_axes_tc = {axis.value: 0.0 for axis in AxisName}
    from src.session.types import TCODE_MAP
    tc_dict = {TCODE_MAP[a]: v for a, v in samples_log[-1].items()}
    tc_string = format_tcode(tc_dict, interval_ms=20)
    print(f"\nLast TCode command (after 30s ramp-up):")
    print(f"  {tc_string}")

    # Sanity stats
    print(f"\nAxis stats over 30s rendering:")
    for axis in AxisName:
        vals = np.array([s[axis] for s in samples_log])
        print(f"  {axis.value:18s}  mean={vals.mean():.3f}  min={vals.min():.3f}  max={vals.max():.3f}")

    # Verify volume ramp at start (onset) — Volume must be 0 at t=0 and rising.
    # We don't check monotonicity over the whole window because Volume-track
    # patterns deliberately introduce local dips/spikes (V-series patterns).
    vol_first = samples_log[0][AxisName.VOLUME]
    vol_after_5s = samples_log[min(len(samples_log)-1, 5*50)][AxisName.VOLUME]
    print(f"\nVolume onset:  t=0s={vol_first:.3f}  t=5s={vol_after_5s:.3f}")
    assert vol_first <= 0.05, "Onset ramp should start near 0"
    assert vol_after_5s > vol_first, "Onset ramp should be rising"
    assert all(0.0 <= s[AxisName.VOLUME] <= 1.0 for s in samples_log), "Volume out of range!"

    print("\n[OK] Pipeline produces valid TCode without errors.")


async def test_runner_dry():
    """Test SessionRunner with a no-op TCode sender, very short duration."""
    print("\n" + "=" * 60)
    print("Session Runner dry-run (5s, no real Restim connection)")
    print("=" * 60)

    sent = []
    async def fake_send(axes_dict, interval_ms):
        sent.append((axes_dict, interval_ms))

    statuses = []
    def on_status(s):
        statuses.append(s)

    profile = SessionProfile(
        style=SessionStyle.SANFTER_AUFBAU,
        duration_s=5,
        seed=11,
    )

    runner = SessionRunner(tcode_send=fake_send, on_status=on_status, dt_s=0.05)
    await runner.start(profile)

    print(f"  Tick count sent: {len(sent)}")
    print(f"  Status updates emitted: {len(statuses)}")
    if sent:
        print(f"  Last TCode payload: {sent[-1][0]}")
    if statuses:
        print(f"  Last status: phase={statuses[-1].current_phase}, t={statuses[-1].t_session_s:.2f}")
    print("[OK] Runner completed without exceptions.")


def main():
    test_pipeline_offline()
    asyncio.run(test_runner_dry())
    print("\n" + "=" * 60)
    print("All pipeline tests passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
