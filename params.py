import numpy as np

WAVE_NAMES = [
    "Square","Saw","Sine","Noise","Triangle",
    "PinkNoise","Tan","Whistle","Breaker","Bitnoise","New1","Buzz"
]
NUM_WAVES = len(WAVE_NAMES)  # 12

# Index mapping matches generator.py p[] array order
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

#          min   max   default
PARAM_RANGES = [
    (0,    11,   2.0),   # 0  WaveType      (integer 0-11, stored as float)
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

    # WaveType: integer 0-11
    params[0] = float(int(rng.uniform(0, NUM_WAVES)))

    # StartFreq: match AS randomize distribution
    if rng.random() < 0.5:
        r = rng.uniform(-1.0, 1.0)
        params[6] = float(r * r)          # pow(rand*2-1, 2)
    else:
        r = rng.uniform(0.0, 0.5)
        params[6] = float(r*r*r + 0.5)   # pow(rand*0.5, 3) + 0.5

    # MinFreq: AS randomize sets to 0
    params[7] = 0.0

    # Slide: AS uses pow(rand*2-1, 5)
    r = rng.uniform(-1.0, 1.0)
    params[8] = float(r**5)

    # DeltaSlide: AS uses pow(rand*2-1, 3)
    r = rng.uniform(-1.0, 1.0)
    params[9] = float(r**3)

    # RepeatSpd: 50% chance of zero
    if rng.random() < 0.5:
        params[19] = 0.0


def blend_params(pl, pr, t):
    return [pl[i] * (1.0 - t) + pr[i] * t for i in range(NUM_PARAMS)]
