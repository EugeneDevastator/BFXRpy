import numpy as np

WAVE_NAMES = ["Square","Saw","Sine","Noise","Triangle","PinkNoise","Tan","Whistle","Breaker","Bitnoise","Buzz"]
NUM_WAVES  = len(WAVE_NAMES)

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
PARAM_DEF = [
    0.0,  0.5,
    0.0,  0.3,  0.0,  0.4,
    0.3,  0.0,  0.0,  0.0,
    0.0,  0.0,
    0.0,  0.0,  0.0,  0.0,  0.0,
    0.0,  0.0,
    0.0,
    0.0,  0.0,
    1.0,  0.0,  0.0,
    0.0,  0.0,
    0.0,  0.0,  0.5,
    0.0,  0.0,
]
NUM_PARAMS = len(PARAM_NAMES)
assert len(PARAM_DEF) == NUM_PARAMS


def make_params():
    return list(PARAM_DEF)


def randomize_params(params):
    for i in range(NUM_PARAMS):
        params[i] = np.random.random()
    params[2]  = np.random.random() * 0.3
    params[22] = 0.5 + np.random.random() * 0.5


def blend_params(pl, pr, t):
    return [pl[i] * (1.0 - t) + pr[i] * t for i in range(NUM_PARAMS)]
