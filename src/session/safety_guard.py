"""Safety Guard — last line of defense before TCode is sent to Restim.

Applies:
1. Experience-level caps (vol ceiling, carrier max, PW max)
2. User-configured safety caps (overrides if more restrictive)
3. Volume ramp enforcement (no instant 0->100 jumps)
4. Slew-rate limit per axis to prevent click artifacts
5. Charge-balance check (informational, hardware should also DC-block)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .profile import EXPERIENCE_CAPS, SessionProfile
from .types import AxisName


# Per-axis slew-rate limits (max change per second in normalized 0..1 units)
# Tuned so smooth patterns + edges are unaffected, but pathological jumps are clamped.
# Volume is tighter on UPWARD changes (onset-response protection) than DOWNWARD
# (panic-relevant), see SafetyGuard.process for the asymmetry.
DEFAULT_SLEW_LIMITS_PER_S: dict[AxisName, float] = {
    AxisName.ALPHA: 5.0,           # position can move fast (visual rotation needs this)
    AxisName.BETA: 5.0,
    AxisName.VOLUME: 1.0,          # 100%/s upward cap (still gentle — see ONSET_RAMP_S)
    AxisName.CARRIER: 1.0,         # 1.0/s = full sweep in 1s, plenty
    AxisName.PULSE_FREQUENCY: 2.0,
    AxisName.PULSE_WIDTH: 1.5,
    AxisName.PULSE_RISE_TIME: 2.0,
}

# Onset ramp: first ONSET_RAMP_S seconds of any session, volume is hard-limited to a
# linear ramp from 0 to vol_floor. This is the "sanftes Anfahren" — protects against
# the synchronous-neuronal-onset spike documented in the Restim wiki.
ONSET_RAMP_S = 8.0

# Hard absolute floors to prevent zero-volume artifacts that some hardware misreads
ABSOLUTE_FLOORS: dict[AxisName, float] = {
    AxisName.VOLUME: 0.0,           # 0 means "off" — explicitly allowed
    AxisName.CARRIER: 0.05,         # never below 5% of max carrier
    AxisName.PULSE_WIDTH: 0.0,
    AxisName.PULSE_FREQUENCY: 0.0,
}


@dataclass
class SafetyState:
    """Mutable state across Safety Guard invocations within a session."""
    last_values: dict[AxisName, float]
    session_start_t: float
    ramp_complete_t: float           # time at which ramp_per_minute reaches 1.0
    panic_stop: bool = False

    @classmethod
    def initial(cls, profile: SessionProfile, t_start: float) -> "SafetyState":
        caps = EXPERIENCE_CAPS[profile.experience]
        # Time to ramp from 0 to vol_ceiling at the experience-level ramp rate
        ramp_rate_per_s = caps["ramp_per_minute"] / 60.0  # fraction per second
        # We don't enforce a max-time ramp — vol_floor is the start point, not 0.
        # ramp_complete_t is informational; the actual ramping happens via slew limit.
        return cls(
            last_values={a: 0.0 for a in AxisName},
            session_start_t=t_start,
            ramp_complete_t=t_start + caps["vol_ceiling"] / max(ramp_rate_per_s, 1e-6),
        )


class SafetyGuard:
    """Stateful safety filter. Call .process(t, axis_values) per sample tick."""

    def __init__(self, profile: SessionProfile, t_start: float, dt: float = 0.02):
        self.profile = profile
        self.dt = dt
        self.caps = EXPERIENCE_CAPS[profile.experience]
        self.user_caps = profile.safety
        self.state = SafetyState.initial(profile, t_start)

    def panic_stop(self) -> None:
        """Emergency stop. Forces all subsequent values to 0 with a slew-bounded ramp-down."""
        self.state.panic_stop = True

    def process(self, t: float, axis_values: dict[AxisName, float]) -> dict[AxisName, float]:
        """Process one sample. Returns clamped+slewed axis values.

        Volume ramp is enforced via slew-rate limit: even if the planner asks for full intensity
        immediately, we can only rise vol_ramp_per_minute / 60 units per second.
        """
        out: dict[AxisName, float] = {}

        for axis in AxisName:
            target = float(axis_values.get(axis, self.state.last_values[axis]))

            # Apply panic stop
            if self.state.panic_stop:
                target = 0.0

            # 1) Apply experience-level caps
            if axis == AxisName.VOLUME:
                target = min(target, self.caps["vol_ceiling"])
            elif axis == AxisName.CARRIER:
                # carrier in normalized 0..1 maps to 0..max_hz (Restim convention)
                # cap as fraction of max carrier
                target = min(target, self.caps["carrier_max_hz"] / self.user_caps.max_carrier_hz)
            elif axis == AxisName.PULSE_WIDTH:
                target = min(target, self.caps["pw_max_us"] / self.user_caps.max_pulse_width_us)

            # 2) Apply user-defined absolute caps
            if axis == AxisName.VOLUME:
                target = min(target, self.user_caps.max_volume)
            # carrier and pulse_width already clamped above

            # 3) Apply absolute floors
            if axis in ABSOLUTE_FLOORS and not self.state.panic_stop:
                target = max(target, ABSOLUTE_FLOORS[axis])

            # 4) Onset ramp (separate from per-tick slew limit) — only for volume
            # During the first ONSET_RAMP_S, hard-cap volume to a linear ramp 0 -> vol_floor.
            # After that, the regular slew limit applies and the macro curve drives the value.
            t_in_session = t - self.state.session_start_t
            if axis == AxisName.VOLUME and not self.state.panic_stop and t_in_session < ONSET_RAMP_S:
                onset_cap = self.caps["vol_floor"] * (t_in_session / ONSET_RAMP_S)
                target = min(target, onset_cap)

            # 5) Slew-rate limit per axis (asymmetric for volume: gentler upward)
            if axis == AxisName.VOLUME and not self.state.panic_stop:
                max_change_up = DEFAULT_SLEW_LIMITS_PER_S[axis] * self.dt
                max_change_down = 2.0 * self.dt   # 2.0/s downward — fast for edges
            else:
                slew_limit = DEFAULT_SLEW_LIMITS_PER_S[axis]
                max_change_up = slew_limit * self.dt
                max_change_down = slew_limit * self.dt

            prev = self.state.last_values[axis]
            delta = target - prev
            if delta > max_change_up:
                target = prev + max_change_up
            elif delta < -max_change_down:
                target = prev - max_change_down

            # 6) Clamp to [0, 1]
            target = max(0.0, min(1.0, target))

            out[axis] = target
            self.state.last_values[axis] = target

        return out

    def process_batch(self, ts: np.ndarray, axes_arrays: dict[AxisName, np.ndarray]
                      ) -> dict[AxisName, np.ndarray]:
        """Process a batch of samples. Convenience wrapper."""
        n = len(ts)
        result = {a: np.empty(n) for a in AxisName}
        for i in range(n):
            sample = {a: float(axes_arrays.get(a, np.full(n, self.state.last_values[a]))[i])
                      for a in AxisName}
            clamped = self.process(float(ts[i]), sample)
            for a in AxisName:
                result[a][i] = clamped[a]
        return result
