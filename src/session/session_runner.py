"""Session Runner — orchestrates the full generative-session pipeline.

Pipeline (per tick):
  MacroPlan envelopes  ->  MicroRenderer.tick(t)  ->  SafetyGuard.process()
                                                            ->  TCode payload  ->  WS

Live overrides (Pause/Skip/Edge/Boost/Stop) flip flags read by the loop.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .macro import EdgeEvent, MacroPlan
from .macro_planner import MacroPlanner, evaluate_macro_at
from .meso_scheduler import MesoSchedule, MesoScheduler
from .micro_renderer import MicroRenderer
from .profile import SessionProfile
from .safety_guard import SafetyGuard
from .types import AxisName, TCODE_MAP

logger = logging.getLogger("session.runner")


@dataclass
class SessionStatus:
    running: bool
    paused: bool
    t_session_s: float                # elapsed session time (excl. paused time)
    t_total_s: float
    current_phase: str
    next_drop_in_s: Optional[float]
    last_axes: dict[str, float]       # last sent axis values (0..1, keyed by AxisName.value)
    pattern_id: Optional[str]


class SessionRunner:
    """Async orchestrator. start() returns once the session ends or is stopped."""

    def __init__(self, tcode_send: Callable[[dict[str, float], int], "asyncio.Future"],
                 on_status: Optional[Callable[[SessionStatus], None]] = None,
                 dt_s: float = 0.02):
        """
        tcode_send: async fn(axis_values_str_keyed, interval_ms) — your TCodeClient.send
        on_status: optional callback fired ~10 Hz with live status for UI
        dt_s: tick rate (50 Hz default)
        """
        self.tcode_send = tcode_send
        self.on_status = on_status or (lambda s: None)
        self.dt_s = dt_s

        self._stop_flag = False
        self._pause_flag = False
        self._skip_phase_flag = False
        self._edge_now_flag = False
        self._boost_flag = False
        self._panic_flag = False
        self._task: Optional[asyncio.Task] = None

        # Optional learned models — set by SessionBridge before start()
        self._envelope_sampler = None
        self._markov_sampler = None

        # Set during start()
        self.profile: Optional[SessionProfile] = None
        self.plan: Optional[MacroPlan] = None
        self.schedule: Optional[MesoSchedule] = None
        self.renderer: Optional[MicroRenderer] = None
        self.guard: Optional[SafetyGuard] = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, profile: SessionProfile) -> None:
        """Plan the session and run the live loop until end or stop."""
        self.profile = profile

        # Plan & schedule (use learned samplers if injected)
        self.plan = MacroPlanner(
            learned_intensity_sampler=self._envelope_sampler,
        ).plan(profile)
        self.schedule = MesoScheduler(
            markov_sampler=self._markov_sampler,
        ).schedule(profile, self.plan)
        self.renderer = MicroRenderer(profile, self.plan, self.schedule, dt=self.dt_s)
        self.guard = SafetyGuard(profile, t_start=0.0, dt=self.dt_s)

        logger.info("Session start: %s, %.0f min, %d slots, %d edges, %d subwaves",
                    profile.style.value, profile.duration_s / 60,
                    len(self.schedule.slots), len(self.plan.edges), len(self.plan.subwaves))

        # Reset flags
        self._stop_flag = False
        self._pause_flag = False
        self._panic_flag = False

        await self._run_loop()

    async def _run_loop(self) -> None:
        assert self.plan is not None and self.renderer is not None and self.guard is not None

        t_session = 0.0
        t_total = self.plan.total_duration_s()
        last_status_emit = 0.0
        loop_start_real = time.monotonic()
        paused_real_total = 0.0

        while t_session < t_total and not self._stop_flag:
            tick_real_start = time.monotonic()

            # Pause: hold all values, sleep, do not advance t_session
            if self._pause_flag:
                pause_start = time.monotonic()
                await asyncio.sleep(0.05)
                paused_real_total += time.monotonic() - pause_start
                continue

            # Skip phase
            if self._skip_phase_flag:
                self._skip_phase_flag = False
                cur = self.plan.phase_at(t_session)
                t_session = cur.t_end_s + 0.01
                continue

            # Edge-now: inject ad-hoc EdgeEvent
            if self._edge_now_flag:
                self._edge_now_flag = False
                depth = self.guard.caps["max_drop_depth"] * 0.7
                self.plan.edges.append(EdgeEvent(t_s=t_session, depth=depth, recovery_s=20.0))

            # Boost-now: short positive subwave
            if self._boost_flag:
                self._boost_flag = False
                from .macro import SubWave
                self.plan.subwaves.append(SubWave(
                    t_start_s=t_session, period_s=4.0, amplitude=0.2, shape="asym_pulse",
                ))

            # Panic stop: send 0s and exit
            if self._panic_flag:
                self.guard.panic_stop()
                zero_axes = {a: 0.0 for a in AxisName}
                clamped = self.guard.process(t_session, zero_axes)
                await self._send_axes(clamped)
                break

            # Render this tick
            try:
                axes = self.renderer.tick(t_session)
                clamped = self.guard.process(t_session, axes)
                await self._send_axes(clamped)
            except Exception as e:
                logger.exception("Tick render error at t=%.2f: %s", t_session, e)

            # Status emission
            now_real = time.monotonic()
            if now_real - last_status_emit > 0.1:   # ~10 Hz status
                self.on_status(self._build_status(t_session, t_total, clamped))
                last_status_emit = now_real

            # Pace the loop to real time
            t_session += self.dt_s
            elapsed = time.monotonic() - tick_real_start
            sleep_for = max(0.0, self.dt_s - elapsed)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

        # End of session: ramp to 0 over a couple of seconds
        await self._graceful_end()

    async def _graceful_end(self) -> None:
        """Send 5s of decreasing volume to land softly."""
        if self.guard is None:
            return
        for i in range(int(5.0 / self.dt_s)):
            frac = 1.0 - (i / int(5.0 / self.dt_s))
            axes = dict(self.guard.state.last_values)
            axes[AxisName.VOLUME] = axes[AxisName.VOLUME] * frac
            clamped = self.guard.process(self.plan.total_duration_s() + i * self.dt_s, axes)
            try:
                await self._send_axes(clamped)
            except Exception:
                break
            await asyncio.sleep(self.dt_s)
        # Final zeroes
        zero = {a: 0.0 for a in AxisName}
        await self._send_axes(zero)
        logger.info("Session ended cleanly.")

    async def _send_axes(self, axes: dict[AxisName, float]) -> None:
        # Convert AxisName -> TCode string key
        tcode_dict = {TCODE_MAP[a]: v for a, v in axes.items()}
        await self.tcode_send(tcode_dict, int(self.dt_s * 1000))

    def _build_status(self, t_session: float, t_total: float,
                      last_axes: dict[AxisName, float]) -> SessionStatus:
        assert self.plan is not None
        phase = self.plan.phase_at(t_session)
        # next drop
        next_drop = None
        for edge in self.plan.edges:
            if edge.t_s > t_session:
                next_drop = edge.t_s - t_session
                break

        cur_slot = self.schedule.slot_at(t_session) if self.schedule else None
        return SessionStatus(
            running=True,
            paused=self._pause_flag,
            t_session_s=t_session,
            t_total_s=t_total,
            current_phase=phase.name.value,
            next_drop_in_s=next_drop,
            last_axes={a.value: float(v) for a, v in last_axes.items()},
            pattern_id=cur_slot.pattern_id if cur_slot else None,
        )

    # ---- Public override flags (callable from any thread/task) ----

    def pause(self) -> None:
        self._pause_flag = True

    def resume(self) -> None:
        self._pause_flag = False

    def skip_phase(self) -> None:
        self._skip_phase_flag = True

    def edge_now(self) -> None:
        self._edge_now_flag = True

    def boost(self) -> None:
        self._boost_flag = True

    def stop(self) -> None:
        self._stop_flag = True

    def panic_stop(self) -> None:
        self._panic_flag = True
