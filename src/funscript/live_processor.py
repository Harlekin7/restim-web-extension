import math
from collections import deque

from funscript.converter import ConvertSettings, lerp, clamp, calc_radius


class LiveProcessor:
    """Causal (look-ahead-free) live variant of convert_funscript.

    Receives individual (t_ms, pos) samples and returns a full 7-axis TCode
    dict per sample. Reuses ConvertSettings so the sidebar sliders affect
    both the offline (funscript) and live (theedgy) paths identically.

    Centered rolling windows of the offline converter are replaced with
    backward-only windows; everything else is already causal.
    """

    def __init__(self, settings=None):
        self.settings = settings or ConvertSettings()
        self._history = deque()          # [(t_s, pos)]
        self._volume_history = deque()   # [(t_s, raw_volume)]
        self._volume_envelope = 0.0
        self._last_t_s = None
        self._observed_max_speed = 1e-6
        # Explicit speed envelope (position units/s). Set > 0 to override
        # auto-observation — useful when the input source advertises limits
        # (e.g. theedgy's max speed slider). 0 = auto.
        self.max_speed = 0.0
        self.min_speed = 0.0

    def reset(self):
        self._history.clear()
        self._volume_history.clear()
        self._volume_envelope = 0.0
        self._last_t_s = None
        self._observed_max_speed = 1e-6

    def process(self, t_ms, pos):
        s = self.settings
        t_s = t_ms / 1000.0

        if self._last_t_s is None:
            dt = 0.02
        else:
            dt = max(0.001, t_s - self._last_t_s)
        self._last_t_s = t_s

        self._history.append((t_s, pos))
        max_window = max(
            s.speed_window, s.volume_window, s.boost_window, s.idle_window,
        ) + 0.5
        while self._history and (t_s - self._history[0][0]) > max_window:
            self._history.popleft()

        speed_long = self._causal_movement_rate(s.speed_window)
        if self.max_speed > 0.0:
            lo = max(0.0, self.min_speed)
            hi = max(lo + 1e-6, self.max_speed)
            spd_norm = clamp((speed_long - lo) / (hi - lo), 0.0, 1.0)
        else:
            if speed_long > self._observed_max_speed:
                self._observed_max_speed = speed_long
            spd_norm = min(1.0, speed_long / max(self._observed_max_speed, 1e-6))

        if s.boost_enabled:
            speed_short = self._causal_movement_rate(s.boost_window)
            if speed_long > 1e-6:
                ratio = speed_short / speed_long
            elif speed_short > 1e-6:
                ratio = 10.0
            else:
                ratio = 1.0
            boost = clamp((ratio - 1.0) * s.boost_strength, 0.0, 1.0)
        else:
            boost = 0.0

        effective_spd = clamp(spd_norm + boost * (1.0 - spd_norm), 0.0, 1.0)

        arc_rad = s.arc_degrees * math.pi / 180.0
        theta = (1.0 - pos) * arc_rad
        radius = calc_radius(effective_spd, s)
        direction = -1.0 if s.arc_invert else 1.0
        alpha = 0.5 + radius * math.cos(theta)
        beta = 0.5 + direction * radius * math.sin(theta)

        recent_movement = self._causal_movement_total(s.idle_window)
        is_idle = recent_movement < s.idle_threshold

        if not is_idle:
            fade_rate = dt / s.volume_fade_up if s.volume_fade_up > 0 else 1.0
            self._volume_envelope = min(1.0, self._volume_envelope + fade_rate)
        else:
            fade_rate = dt / s.volume_fade_down if s.volume_fade_down > 0 else 1.0
            self._volume_envelope = max(0.0, self._volume_envelope - fade_rate)

        vol_target = lerp(effective_spd, s.volume_min, s.volume_max)
        vol_raw = lerp(self._volume_envelope, s.volume_min, vol_target)
        car = lerp(effective_spd, s.carrier_freq_min, s.carrier_freq_max)
        pfr_speed = lerp(effective_spd, s.pulse_freq_min, s.pulse_freq_max)
        pfr_pos_norm = (1.0 - pos) if s.position_freq_invert else pos
        pfr_pos = lerp(pfr_pos_norm, s.pulse_freq_min, s.pulse_freq_max)
        pfr = lerp(s.position_freq_influence, pfr_speed, pfr_pos)
        pwi = lerp(effective_spd, s.pulse_width_min, s.pulse_width_max)
        pri = lerp(effective_spd, s.pulse_rise_min, s.pulse_rise_max)

        self._volume_history.append((t_s, vol_raw))
        while self._volume_history and (t_s - self._volume_history[0][0]) > s.volume_window:
            self._volume_history.popleft()
        vol = sum(v for _, v in self._volume_history) / len(self._volume_history)

        return {
            "L0": clamp(alpha, 0.0, 1.0),
            "L1": clamp(beta, 0.0, 1.0),
            "V0": clamp(vol, 0.0, 1.0),
            "C0": clamp(car, 0.0, 1.0),
            "P0": clamp(pfr, 0.0, 1.0),
            "P1": clamp(pwi, 0.0, 1.0),
            "P3": clamp(pri, 0.0, 1.0),
        }

    def _causal_movement_total(self, window_seconds):
        if not self._history:
            return 0.0
        t_now = self._history[-1][0]
        cutoff = t_now - window_seconds
        total = 0.0
        prev_pos = None
        for t, p in self._history:
            if t < cutoff:
                prev_pos = p
                continue
            if prev_pos is not None:
                total += abs(p - prev_pos)
            prev_pos = p
        return total

    def _causal_movement_rate(self, window_seconds):
        if window_seconds <= 1e-9:
            return 0.0
        return self._causal_movement_total(window_seconds) / window_seconds
