# params.py
import numpy as np

WAVE_NAMES = [
    "Square","Saw","Sine","Noise","Triangle",
    "PinkNoise","Tan","Whistle","Breaker","Bitnoise","New1","Buzz"
]
NUM_WAVES = len(WAVE_NAMES)  # 12

PARAM_NAMES = [
    "WaveType","Volume",
    "Attack","Sustain","SustPunch","Decay",
    "StartFreq","MinFreq","Slide","DeltaSlide",
    "VibDepth","VibSpeed",
    "ChgAmt","ChgSpd","ChgAmt2","ChgSpd2","ChgRepeat",
    "SqDuty","DutySweep",
    "RepeatSpd",
    "FlngOffset","FlngSweep",
    "LPCutoff","LPCutSweep","LPResonance",
    "HPCutoff","HPCutSweep",
    "BitCrush","BitCrushSwp","Compression",
    "Overtones","OvtoneFalloff",
]

#           min   max   default
PARAM_RANGES = [
    (0,    11,   2.0),   # 0  WaveType
    (0,     1,   0.5),   # 1  Volume
    (0,     1,   0.0),   # 2  Attack
    (0,     1,   0.3),   # 3  Sustain
    (0,     1,   0.0),   # 4  SustPunch
    (0,     1,   0.4),   # 5  Decay
    (0,     1,   0.3),   # 6  StartFreq
    (0,     1,   0.0),   # 7  MinFreq
    (-1,    1,   0.0),   # 8  Slide
    (-1,    1,   0.0),   # 9  DeltaSlide
    (0,     1,   0.0),   # 10 VibDepth
    (0,     1,   0.0),   # 11 VibSpeed
    (-1,    1,   0.0),   # 12 ChgAmt
    (0,     1,   0.0),   # 13 ChgSpd
    (-1,    1,   0.0),   # 14 ChgAmt2
    (0,     1,   0.0),   # 15 ChgSpd2
    (0,     1,   0.0),   # 16 ChgRepeat
    (0,     1,   0.0),   # 17 SqDuty
    (-1,    1,   0.0),   # 18 DutySweep
    (0,     1,   0.0),   # 19 RepeatSpd
    (-1,    1,   0.0),   # 20 FlngOffset
    (-1,    1,   0.0),   # 21 FlngSweep
    (0,     1,   1.0),   # 22 LPCutoff
    (-1,    1,   0.0),   # 23 LPCutSweep
    (0,     1,   0.0),   # 24 LPResonance
    (0,     1,   0.0),   # 25 HPCutoff
    (-1,    1,   0.0),   # 26 HPCutSweep
    (0,     1,   0.0),   # 27 BitCrush
    (-1,    1,   0.0),   # 28 BitCrushSwp
    (0,     1,   0.3),   # 29 Compression
    (0,     1,   0.0),   # 30 Overtones
    (0,     1,   0.0),   # 31 OvtoneFalloff
]

NUM_PARAMS = len(PARAM_NAMES)
assert len(PARAM_RANGES) == NUM_PARAMS

PARAM_DEF = [r[2] for r in PARAM_RANGES]

# Groups: (label, start_index, end_index)  end is exclusive
PARAM_GROUPS = [
    ("Wave",       0,  2),
    ("Envelope",   2,  6),
    ("Frequency",  6, 10),
    ("Vibrato",   10, 12),
    ("Change",    12, 17),
    ("Duty",      17, 19),
    ("Repeat",    19, 20),
    ("Flanger",   20, 22),
    ("Filters",   22, 27),
    ("Bit/Comp",  27, 30),
    ("Overtones", 30, 32),
]


def param_to_t(i, v):
    """Normalize param value to [0,1] for slider drawing."""
    lo, hi, _ = PARAM_RANGES[i]
    return (v - lo) / (hi - lo)


def t_to_param(i, t):
    """Map [0,1] slider position back to param range."""
    lo, hi, _ = PARAM_RANGES[i]
    v = lo + t * (hi - lo)
    if v < lo: v = lo
    if v > hi: v = hi
    return v


def param_display(i, v):
    """Human-readable string for param value."""
    if i == 0:
        wt = int(v)
        if wt < 0: wt = 0
        if wt >= NUM_WAVES: wt = NUM_WAVES - 1
        return WAVE_NAMES[wt]
    return f"{v:.2f}"


def make_params():
    return list(PARAM_DEF)


def clamp_param(i, v):
    lo, hi, _ = PARAM_RANGES[i]
    if v < lo: return lo
    if v > hi: return hi
    return v


def randomize_params(params):
    rng = np.random.default_rng()

    for i in range(NUM_PARAMS):
        lo, hi, _ = PARAM_RANGES[i]
        params[i] = float(rng.uniform(lo, hi))

    params[0] = float(int(rng.uniform(0, NUM_WAVES)))

    if rng.random() < 0.5:
        r = rng.uniform(-1.0, 1.0)
        params[6] = float(r * r)
    else:
        r = rng.uniform(0.0, 0.5)
        params[6] = float(r*r*r + 0.5)

    params[7] = 0.0

    r = rng.uniform(-1.0, 1.0)
    params[8] = float(r**5)

    r = rng.uniform(-1.0, 1.0)
    params[9] = float(r**3)

    if rng.random() < 0.5:
        params[19] = 0.0


def blend_params(pl, pr, t):
    return [pl[i] * (1.0 - t) + pr[i] * t for i in range(NUM_PARAMS)]
