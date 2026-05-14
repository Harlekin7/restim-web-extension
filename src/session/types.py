from __future__ import annotations

from enum import Enum


class SessionStyle(str, Enum):
    SANFTER_AUFBAU = "sanfter_aufbau"
    CRESCENDO = "crescendo"
    BEAT_DROP = "beat_drop"
    EDGING = "edging"
    RUIN = "ruin"
    ENDLOS_TEASE = "endlos_tease"


class SessionTarget(str, Enum):
    CLIMAX = "climax"
    EDGE_HOLD = "edge_hold"
    RUINED = "ruined"
    OPEN_END = "open_end"


class ExperienceLevel(int, Enum):
    BEGINNER = 1
    EINGEWOEHNT = 2
    ERFAHREN = 3
    ROUTINIERT = 4
    PROFI = 5


class Character(str, Enum):
    SANFT = "sanft"
    LEBENDIG = "lebendig"
    SPIELERISCH = "spielerisch"
    WILD = "wild"


class DeviceClass(str, Enum):
    THREE_PHASE_FOC = "3_phase_foc"
    FOUR_PHASE_FOC = "4_phase_foc"
    STEREOSTIM = "stereostim"
    SINGLE_CHANNEL = "single_channel"


class ElectrodePosition(str, Enum):
    EICHEL = "eichel"
    SCHAFT_OBEN = "schaft_oben"
    SCHAFT_UNTEN = "schaft_unten"
    UNTER_HODEN = "unter_hoden"
    DAMM = "damm"
    ANAL_PLUG = "anal_plug"
    PROSTATA = "prostata"
    BRUSTWARZE_L = "brustwarze_l"
    BRUSTWARZE_R = "brustwarze_r"


class AxisName(str, Enum):
    """The 7 TCode axes Restim consumes. Order matches Restim's axis dict."""
    ALPHA = "alpha"
    BETA = "beta"
    VOLUME = "volume"
    CARRIER = "carrier"
    PULSE_FREQUENCY = "pulse_frequency"
    PULSE_WIDTH = "pulse_width"
    PULSE_RISE_TIME = "pulse_rise_time"


TCODE_MAP: dict[AxisName, str] = {
    AxisName.ALPHA: "L0",
    AxisName.BETA: "L1",
    AxisName.VOLUME: "V0",
    AxisName.CARRIER: "C0",
    AxisName.PULSE_FREQUENCY: "P0",
    AxisName.PULSE_WIDTH: "P1",
    AxisName.PULSE_RISE_TIME: "P3",
}


class PhaseName(str, Enum):
    """5-phase macro arc."""
    INIT = "init"
    BUILD = "build"
    PLATEAU = "plateau"
    EDGE = "edge"
    CLIMAX = "climax"


class PatternCategory(str, Enum):
    POSITION = "position"
    VOLUME = "volume"
    PULSE = "pulse"
    CARRIER = "carrier"
    MULTI_AXIS = "multi_axis"
