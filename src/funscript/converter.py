import math


class ConvertSettings:
    """All configurable parameters for funscript → TCode conversion."""

    def __init__(self):
        # Arc conversion
        self.arc_degrees = 270.0        # 270-360, arc coverage
        self.arc_invert = False         # invertiert die Laufrichtung
        self.points_per_second = 25     # output sample rate

        # Speed-responsive radius
        self.speed_window = 5.0         # rolling window in seconds
        self.min_radius = 0.1           # radius at speed=0 (0.0-0.5)
        self.speed_threshold = 0.5      # speed fraction for max radius

        # Speed → parameter mappings (min at speed=0, max at speed=1)
        self.volume_min = 0.20
        self.volume_max = 0.95
        self.carrier_freq_min = 0.40
        self.carrier_freq_max = 0.95
        self.pulse_freq_min = 0.30
        self.pulse_freq_max = 0.90
        self.pulse_width_min = 0.10
        self.pulse_width_max = 0.50
        self.pulse_rise_min = 0.00
        self.pulse_rise_max = 0.80

        # Boost: hebt schnelle Bewegungen in langsamen Passagen hervor
        self.boost_enabled = False
        self.boost_window = 0.5         # Sekunden: kurzes Fenster fuer Burst-Erkennung
        self.boost_strength = 1.0       # Staerke des Boost-Effekts (0-3)

        # Position → Pulse Freq Einfluss
        # 0 = Pulse Freq rein speed-basiert (bisher), 1 = Pulse Freq folgt der Position
        self.position_freq_influence = 0.0
        self.position_freq_invert = False

        # Volume smoothing + fade
        self.volume_window = 3.0        # Sekunden: separates Glaettungsfenster fuer Volume
        self.volume_fade_down = 1.0     # Sekunden bis Volume auf min faded
        self.volume_fade_up = 0.3       # Sekunden bis Volume wieder auf Soll
        self.idle_window = 0.5          # Sekunden: Fenster fuer Stillstand-Erkennung
        self.idle_threshold = 0.01      # Positions-Aenderung unter der = Stillstand


def convert_funscript(funscript_data, settings=None):
    """Convert a funscript to pre-processed TCode axes.

    Returns dict with keys: times_ms, L0, L1, V0, C0, P0, P1, P3
    Each value is a list of floats (0.0-1.0).
    """
    if settings is None:
        settings = ConvertSettings()

    actions = funscript_data.get("actions", [])
    if len(actions) < 2:
        return None

    # Normalize actions: time in seconds, position 0.0-1.0
    raw_times = [a["at"] / 1000.0 for a in actions]
    raw_pos = [a["pos"] / 100.0 for a in actions]

    # Remap position range: actual min/max → 0.0-1.0
    pos_min = min(raw_pos)
    pos_max = max(raw_pos)
    pos_range = pos_max - pos_min
    if pos_range > 1e-6:
        raw_pos = [(p - pos_min) / pos_range for p in raw_pos]
    else:
        raw_pos = [0.5] * len(raw_pos)

    total_duration = raw_times[-1]

    # Generate output sample points
    dt = 1.0 / settings.points_per_second
    sample_count = int(total_duration * settings.points_per_second) + 1
    sample_times = [i * dt for i in range(sample_count)]

    # Interpolate position at each sample point
    positions = [lerp_at(sample_times[i], raw_times, raw_pos)
                 for i in range(sample_count)]

    # Calculate speed at each sample point
    speeds = calculate_speed(sample_times, positions, settings.speed_window)

    # Calculate boost: short-window speed vs long-window speed ratio (raw, unnormalized)
    if settings.boost_enabled:
        speeds_short = calculate_speed(
            sample_times, positions, settings.boost_window
        )
        boost_factors = []
        for i in range(sample_count):
            context = speeds[i]  # long window = context
            instant = speeds_short[i]  # short window = instant
            if context > 1e-6:
                ratio = instant / context
            elif instant > 1e-6:
                ratio = 10.0  # movement from silence = big burst
            else:
                ratio = 1.0
            # ratio > 1 = faster than context = burst
            boost = clamp((ratio - 1.0) * settings.boost_strength, 0.0, 1.0)
            boost_factors.append(boost)
    else:
        boost_factors = [0.0] * sample_count

    # Normalize speed to 0-1
    max_speed = max(speeds) if speeds else 1.0
    if max_speed < 1e-9:
        max_speed = 1.0
    norm_speeds = [s / max_speed for s in speeds]

    # Convert to all axes
    arc_rad = settings.arc_degrees * math.pi / 180.0

    times_ms = []
    alpha_vals = []
    beta_vals = []
    volume_vals = []
    carrier_vals = []
    pulse_freq_vals = []
    pulse_width_vals = []
    pulse_rise_vals = []

    # Volume fade state
    volume_envelope = 0.0  # 0=silent, 1=full

    for i in range(sample_count):
        t = sample_times[i]
        pos = positions[i]
        spd = norm_speeds[i]
        boost = boost_factors[i]

        # Boost: push effective speed towards 1.0 during bursts
        effective_spd = clamp(spd + boost * (1.0 - spd), 0.0, 1.0)

        # Arc conversion: position → angle → alpha/beta
        theta = (1.0 - pos) * arc_rad
        radius = calc_radius(effective_spd, settings)
        direction = -1.0 if settings.arc_invert else 1.0
        alpha = 0.5 + radius * math.cos(theta)
        beta = 0.5 + direction * radius * math.sin(theta)

        # Idle detection: check actual position movement over short window
        idle_samples = min(i, int(settings.idle_window * settings.points_per_second))
        recent_movement = 0.0
        for j in range(idle_samples):
            recent_movement += abs(positions[i - j] - positions[i - j - 1])
        is_idle = recent_movement < settings.idle_threshold

        # Volume envelope: fade down bei Stillstand, fade up bei Bewegung
        if not is_idle:
            fade_rate = dt / settings.volume_fade_up if settings.volume_fade_up > 0 else 1.0
            volume_envelope = min(1.0, volume_envelope + fade_rate)
        else:
            fade_rate = dt / settings.volume_fade_down if settings.volume_fade_down > 0 else 1.0
            volume_envelope = max(0.0, volume_envelope - fade_rate)

        # Speed → parameter mappings (mit Boost und Volume-Envelope)
        vol_target = lerp(effective_spd, settings.volume_min, settings.volume_max)
        vol = lerp(volume_envelope, settings.volume_min, vol_target)
        car = lerp(effective_spd, settings.carrier_freq_min, settings.carrier_freq_max)
        pfr_speed = lerp(effective_spd, settings.pulse_freq_min, settings.pulse_freq_max)
        pfr_pos = (1.0 - pos) if settings.position_freq_invert else pos
        pfr = lerp(settings.position_freq_influence, pfr_speed, pfr_pos)
        pwi = lerp(effective_spd, settings.pulse_width_min, settings.pulse_width_max)
        pri = lerp(effective_spd, settings.pulse_rise_min, settings.pulse_rise_max)

        times_ms.append(int(t * 1000))
        alpha_vals.append(clamp(alpha, 0.0, 1.0))
        beta_vals.append(clamp(beta, 0.0, 1.0))
        volume_vals.append(clamp(vol, 0.0, 1.0))
        carrier_vals.append(clamp(car, 0.0, 1.0))
        pulse_freq_vals.append(clamp(pfr, 0.0, 1.0))
        pulse_width_vals.append(clamp(pwi, 0.0, 1.0))
        pulse_rise_vals.append(clamp(pri, 0.0, 1.0))

    # Separate Volume smoothing: moving average over volume_window
    vol_win_samples = max(1, int(settings.volume_window * settings.points_per_second))
    volume_vals = smooth(volume_vals, vol_win_samples)

    return {
        "times_ms": times_ms,
        "L0": alpha_vals,
        "L1": beta_vals,
        "V0": volume_vals,
        "C0": carrier_vals,
        "P0": pulse_freq_vals,
        "P1": pulse_width_vals,
        "P3": pulse_rise_vals,
    }


# ── Helpers ────────────────────────────────────────────────────────

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(t, a, b):
    """Linear interpolation: t=0→a, t=1→b."""
    return a + (b - a) * t


def smooth(values, window):
    """Centered moving average. Preserves list length."""
    if window <= 1:
        return values
    n = len(values)
    half = window // 2
    result = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        result.append(sum(values[lo:hi]) / (hi - lo))
    return result


def lerp_at(t, times, values):
    """Interpolate value at time t from sorted (times, values) arrays."""
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]

    # Binary search for interval
    lo, hi = 0, len(times) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if times[mid] <= t:
            lo = mid
        else:
            hi = mid

    dt = times[hi] - times[lo]
    if dt < 1e-9:
        return values[lo]
    frac = (t - times[lo]) / dt
    return values[lo] + (values[hi] - values[lo]) * frac


def calculate_speed(times, positions, window_seconds):
    """Calculate speed using a CENTERED rolling window.

    Looks half backward and half forward, eliminating lag.
    Returns unnormalized speed at each sample point.
    """
    half_window = window_seconds / 2.0
    n = len(times)
    speeds = []
    for i in range(n):
        t_now = times[i]
        total_movement = 0.0

        # Look backward (half window)
        j = i
        while j > 0 and times[j] > t_now - half_window:
            total_movement += abs(positions[j] - positions[j - 1])
            j -= 1

        # Look forward (half window)
        j = i + 1
        while j < n and times[j] < t_now + half_window:
            total_movement += abs(positions[j] - positions[j - 1])
            j += 1

        speeds.append(total_movement / window_seconds)
    return speeds


def calc_radius(speed_normalized, settings):
    """Speed-responsive radius: faster = larger radius."""
    if speed_normalized >= settings.speed_threshold:
        scale = 1.0
    else:
        t = speed_normalized / settings.speed_threshold if settings.speed_threshold > 0 else 0
        scale = settings.min_radius + (1.0 - settings.min_radius) * t
    return 0.5 * scale
