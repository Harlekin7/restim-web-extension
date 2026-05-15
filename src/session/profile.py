from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .types import (
    Character,
    DeviceClass,
    ElectrodePosition,
    ExperienceLevel,
    SessionStyle,
    SessionTarget,
)


@dataclass
class SensationMix:
    """Four sliders 0..1 driving signal character. 0 = left pole, 1 = right pole."""
    sharp_to_deep: float = 0.5
    granular_to_smooth: float = 0.5
    soft_to_hard: float = 0.5
    static_to_moving: float = 0.5


@dataclass
class Electrode:
    position: ElectrodePosition
    is_common: bool = False
    size_cm2: float = 9.0


@dataclass
class HardwareProfile:
    device_class: DeviceClass = DeviceClass.THREE_PHASE_FOC
    electrodes: list[Electrode] = field(default_factory=list)


# Experience-level caps. Single source of truth — referenced by safety_guard, macro_planner, micro_renderer.
EXPERIENCE_CAPS: dict[ExperienceLevel, dict] = {
    ExperienceLevel.BEGINNER: dict(
        vol_floor=0.20, vol_ceiling=0.70,
        carrier_max_hz=1000, pw_max_us=150,
        ramp_per_minute=0.01, max_drop_depth=0.25,
    ),
    ExperienceLevel.EINGEWOEHNT: dict(
        vol_floor=0.25, vol_ceiling=0.80,
        carrier_max_hz=1300, pw_max_us=200,
        ramp_per_minute=0.02, max_drop_depth=0.35,
    ),
    ExperienceLevel.ERFAHREN: dict(
        vol_floor=0.30, vol_ceiling=0.85,
        carrier_max_hz=1600, pw_max_us=250,
        ramp_per_minute=0.03, max_drop_depth=0.45,
    ),
    ExperienceLevel.ROUTINIERT: dict(
        vol_floor=0.35, vol_ceiling=0.92,
        carrier_max_hz=1800, pw_max_us=300,
        ramp_per_minute=0.04, max_drop_depth=0.55,
    ),
    ExperienceLevel.PROFI: dict(
        vol_floor=0.40, vol_ceiling=1.00,
        carrier_max_hz=2200, pw_max_us=400,
        ramp_per_minute=0.05, max_drop_depth=0.70,
    ),
}


# Character presets. Drive meso scheduler + micro renderer stochastics.
# Slot durations + crossfades raised across the board after live feedback
# that pattern transitions felt jittery. Crossfades now overlap more of
# each slot so the listener spends most of the time in a smooth blend.
CHARACTER_PRESETS: dict[Character, dict] = {
    Character.SANFT: dict(
        band_width=0.05,
        pattern_pool_size=10,
        surprises_per_minute=0.0,
        pattern_duration_s=(20.0, 40.0),
        crossfade_s=4.0,
        subwave_amplitude_scale=0.6,
        subwave_period_scale=1.5,
    ),
    Character.LEBENDIG: dict(
        band_width=0.10,
        pattern_pool_size=25,
        surprises_per_minute=0.20,  # 1 per 5 min
        pattern_duration_s=(12.0, 22.0),
        crossfade_s=3.0,
        subwave_amplitude_scale=1.0,
        subwave_period_scale=1.0,
    ),
    Character.SPIELERISCH: dict(
        band_width=0.15,
        pattern_pool_size=40,
        surprises_per_minute=0.5,  # 1 per 2 min
        pattern_duration_s=(8.0, 16.0),
        crossfade_s=2.0,
        subwave_amplitude_scale=1.2,
        subwave_period_scale=0.7,
    ),
    Character.WILD: dict(
        band_width=0.20,
        pattern_pool_size=999,  # unlimited
        surprises_per_minute=1.0,
        pattern_duration_s=(5.0, 12.0),
        crossfade_s=2.5,
        subwave_amplitude_scale=1.5,
        subwave_period_scale=0.5,
        allow_pattern_overshoot=True,
    ),
}


@dataclass
class SafetyCaps:
    """Hard absolute limits, applied AFTER experience caps. User-overridable in expert tab."""
    max_volume: float = 1.00
    min_volume: float = 0.0           # Volume floor — patterns/edges can't pull Volume below this.
                                      # Onset ramp still starts at 0 and ramps up to this floor.
    max_carrier_hz: float = 2200.0
    max_pulse_width_us: float = 400.0
    min_volume_ramp_s: float = 5.0


@dataclass
class AdvancedSettings:
    """Expert-tab overrides. None = use defaults from style/character."""
    pattern_repeat_lockout_s: Optional[float] = None
    crossfade_s: Optional[float] = None
    pattern_pool: Optional[list[str]] = None  # None = derived from character
    subwave_count: Optional[int] = None


@dataclass
class SessionProfile:
    """Top-level user-configured profile. Deterministic input to MacroPlanner."""

    # Required basics
    style: SessionStyle = SessionStyle.SANFTER_AUFBAU
    duration_s: int = 45 * 60
    target: SessionTarget = SessionTarget.CLIMAX

    sensation: SensationMix = field(default_factory=SensationMix)
    character: Character = Character.LEBENDIG
    experience: ExperienceLevel = ExperienceLevel.EINGEWOEHNT
    hardware: HardwareProfile = field(default_factory=HardwareProfile)

    safety: SafetyCaps = field(default_factory=SafetyCaps)
    advanced: AdvancedSettings = field(default_factory=AdvancedSettings)

    seed: Optional[int] = None  # None => fresh random per session start

    def caps(self) -> dict:
        return EXPERIENCE_CAPS[self.experience]

    def character_settings(self) -> dict:
        return CHARACTER_PRESETS[self.character]

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "SessionProfile":
        data = json.loads(raw)
        # Re-enum the values
        data["style"] = SessionStyle(data["style"])
        data["target"] = SessionTarget(data["target"])
        data["character"] = Character(data["character"])
        data["experience"] = ExperienceLevel(int(data["experience"]))
        sm = data.pop("sensation", {})
        data["sensation"] = SensationMix(**sm)
        hw = data.pop("hardware", {})
        electrodes = [
            Electrode(position=ElectrodePosition(e["position"]), is_common=e.get("is_common", False),
                      size_cm2=e.get("size_cm2", 9.0))
            for e in hw.get("electrodes", [])
        ]
        data["hardware"] = HardwareProfile(
            device_class=DeviceClass(hw.get("device_class", DeviceClass.THREE_PHASE_FOC.value)),
            electrodes=electrodes,
        )
        data["safety"] = SafetyCaps(**data.pop("safety", {}))
        data["advanced"] = AdvancedSettings(**data.pop("advanced", {}))
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "SessionProfile":
        return cls.from_json(path.read_text(encoding="utf-8"))
