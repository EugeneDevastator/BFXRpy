import pyray as rl
import numpy as np
from numba import njit
import threading

SCREEN_W    = 1920
SCREEN_H    = 1080
FONT_SIZE   = 32
SAMPLE_RATE = 44100
CHUNK       = 4096

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


@njit(cache=True)
def _generate_wave_jit(p):
    wave_type_f  = p[0]
    master_vol   = p[1]
    attack_t     = p[2]
    sustain_t    = p[3]
    sust_punch   = p[4]
    decay_t      = p[5]
    start_freq   = p[6]
    min_freq     = p[7]
    slide        = p[8]
    delta_slide  = p[9]
    vib_depth    = p[10]
    vib_speed    = p[11]
    chg_amt      = p[12]
    chg_spd      = p[13]
    chg_amt2     = p[14]
    chg_spd2     = p[15]
    chg_repeat   = p[16]
    sq_duty      = p[17]
    duty_sweep   = p[18]
    repeat_spd   = p[19]
    flng_offset  = p[20]
    flng_sweep   = p[21]
    lp_cutoff    = p[22]
    lp_cut_sweep = p[23]
    lp_res       = p[24]
    hp_cutoff    = p[25]
    hp_cut_sweep = p[26]
    bit_crush    = p[27]
    bit_crush_sw = p[28]
    compression  = p[29]
    overtones    = p[30]
    ot_falloff   = p[31]

    wave_type = int(wave_type_f * 10.0)
    if wave_type > 10: wave_type = 10
    wtype_map = (0,1,2,3,4,5,6,7,8,9,11)
    wt = wtype_map[wave_type]

    mv2 = master_vol * master_vol

    env0 = int(attack_t  * attack_t  * 100000.0)
    env1 = int(sustain_t * sustain_t * 100000.0)
    env2 = int(decay_t   * decay_t   * 100000.0) + 10
    total = env0 + env1 + env2
    min_len = int(0.18 * 44100)
    if total < min_len:
        scale = min_len / max(total, 1)
        env0  = int(env0 * scale)
        env1  = int(env1 * scale)
        env2  = int(env2 * scale)
        total = env0 + env1 + env2

    period     = 100.0 / (start_freq * start_freq + 0.001)
    max_period = 100.0 / (min_freq   * min_freq   + 0.001) if min_freq > 0.0 else 1e9

    sl  = 1.0 - slide * slide * slide * 0.01
    dsl = -delta_slide * delta_slide * delta_slide * 0.000001

    sq_d = 0.5 - sq_duty * 0.5
    dsq  = -duty_sweep * 0.00005

    vib_phase = 0.0
    vib_spd   = vib_speed * vib_speed * 0.01
    vib_amp   = vib_depth * 0.5

    if chg_amt > 0.0:  ca  = 1.0 - chg_amt  * chg_amt  * 0.9
    else:              ca  = 1.0 + chg_amt  * chg_amt  * 10.0
    if chg_amt2 > 0.0: ca2 = 1.0 - chg_amt2 * chg_amt2 * 0.9
    else:              ca2 = 1.0 + chg_amt2 * chg_amt2 * 10.0

    if chg_spd  == 1.0: cl  = 0
    else:               cl  = int((1.0 - chg_spd)  * (1.0 - chg_spd)  * 20000) + 32
    if chg_spd2 == 1.0: cl2 = 0
    else:               cl2 = int((1.0 - chg_spd2) * (1.0 - chg_spd2) * 20000) + 32

    chg_period      = int(((1.0 - chg_repeat) + 0.1) / 1.1 * 20000) + 32
    cl  = int(cl  * ((1.0 - chg_repeat + 0.1) / 1.1))
    cl2 = int(cl2 * ((1.0 - chg_repeat + 0.1) / 1.1))

    if repeat_spd == 0.0: repeat_limit = 0
    else:                 repeat_limit = int((1.0 - repeat_spd) * (1.0 - repeat_spd) * 20000) + 32

    flng_off  = flng_offset * flng_offset * 1020.0
    if flng_offset < 0.0: flng_off = -flng_off
    flng_doff = flng_sweep * flng_sweep * flng_sweep * 0.2
    use_flng  = (flng_offset != 0.0 or flng_sweep != 0.0)

    lp_cut   = lp_cutoff * lp_cutoff * lp_cutoff * 0.1
    lp_dcut  = 1.0 + lp_cut_sweep * 0.0001
    lp_damp  = 5.0 / (1.0 + lp_res * lp_res * 20.0) * (0.01 + lp_cut)
    if lp_damp > 0.8: lp_damp = 0.8
    lp_damp  = 1.0 - lp_damp
    lp_on    = (lp_cutoff != 1.0)
    use_filt = (lp_cutoff != 1.0 or hp_cutoff != 0.0)

    hp_cut  = hp_cutoff * hp_cutoff * 0.1
    hp_dcut = 1.0 + hp_cut_sweep * 0.0003

    bc_freq  = 1.0 - (max(bit_crush, 1e-9) ** (1.0/3.0))
    bc_sweep = -bit_crush_sw * 0.000015
    bc_phase = 0.0
    bc_last  = 0.0

    comp_factor = 1.0 / (1.0 + 4.0 * compression)

    ot_count = int(overtones * 10)

    noise_buf = np.zeros(32)
    for n in range(32):
        noise_buf[n] = np.random.uniform(-1.0, 1.0)

    pb0 = 0.0; pb1 = 0.0; pb2 = 0.0; pb3 = 0.0
    pb4 = 0.0; pb5 = 0.0; pb6 = 0.0
    pink_buf = np.zeros(32)
    for n in range(32):
        w = np.random.uniform(-1.0, 1.0)
        pb0 = 0.99886*pb0 + w*0.0555179
        pb1 = 0.99332*pb1 + w*0.0750759
        pb2 = 0.96900*pb2 + w*0.1538520
        pb3 = 0.86650*pb3 + w*0.3104856
        pb4 = 0.55000*pb4 + w*0.5329522
        pb5 = -0.7616*pb5 - w*0.0168980
        pink_buf[n] = (pb0+pb1+pb2+pb3+pb4+pb5+pb6+w*0.5362)*0.11
        pb6 = w * 0.115926

    lores_buf = np.zeros(32)
    lores_buf[0] = np.random.uniform(-1.0, 1.0)
    for n in range(1, 32):
        if n % 8 == 0:
            lores_buf[n] = np.random.uniform(-1.0, 1.0)
        else:
            lores_buf[n] = lores_buf[n-1]

    flng_buf = np.zeros(1024)
    flng_pos = 0
    flng_int = int(abs(flng_off)) & 1023

    lp_pos  = 0.0
    lp_dpos = 0.0
    hp_pos  = 0.0

    one_bit_state = 1 << 14
    one_bit_noise = 0.0
    buzz_state    = 1 << 14
    buzz_val      = 0.0

    phase     = 0
    env_stage = 0
    env_time  = 0
    env_vol   = 0.0
    env_cur   = env0
    oe0 = 1.0 / env0 if env0 > 0 else 0.0
    oe1 = 1.0 / env1 if env1 > 0 else 0.0
    oe2 = 1.0 / env2 if env2 > 0 else 0.0

    chg_time        = 0; chg_reached  = False
    chg_time2       = 0; chg_reached2 = False
    chg_period_time = 0
    repeat_time     = 0
    muted           = False

    start_period = period
    start_sl     = sl
    start_dsl    = dsl
    start_sq_d   = sq_d
    start_dsq    = dsq

    out = np.zeros(total, dtype=np.float32)
    finished = False

    for i in range(total):
        if finished:
            break

        if repeat_limit > 0:
            repeat_time += 1
            if repeat_time >= repeat_limit:
                repeat_time     = 0
                period          = start_period
                sl              = start_sl
                dsl             = start_dsl
                sq_d            = start_sq_d
                dsq             = start_dsq
                chg_time        = 0; chg_reached  = False
                chg_time2       = 0; chg_reached2 = False
                chg_period_time = 0

        chg_period_time += 1
        if chg_period_time >= chg_period:
            chg_period_time = 0
            chg_time = 0; chg_time2 = 0
            if chg_reached:
                period /= ca;  chg_reached  = False
            if chg_reached2:
                period /= ca2; chg_reached2 = False

        if not chg_reached:
            chg_time += 1
            if cl == 0 or chg_time >= cl:
                chg_reached = True
                period *= ca

        if not chg_reached2:
            chg_time2 += 1
            if cl2 == 0 or chg_time2 >= cl2:
                chg_reached2 = True
                period *= ca2

        sl     += dsl
        period *= sl
        if period > max_period:
            period = max_period
            if min_freq > 0.0:
                muted = True

        period_temp = period
        if vib_amp > 0.0:
            vib_phase  += vib_spd
            period_temp = period * (1.0 + np.sin(vib_phase) * vib_amp)

        period_int = int(period_temp)
        if period_int < 8: period_int = 8

        if wt == 0:
            sq_d += dsq
            if sq_d < 0.0: sq_d = 0.0
            if sq_d > 0.5: sq_d = 0.5

        env_time += 1
        if env_time > env_cur:
            env_time   = 0
            env_stage += 1
            if env_stage == 1: env_cur = env1
            elif env_stage == 2: env_cur = env2

        if env_stage == 0:
            env_vol = env_time * oe0
        elif env_stage == 1:
            env_vol = 1.0 + (1.0 - env_time * oe1) * 2.0 * sust_punch
        elif env_stage == 2:
            env_vol = 1.0 - env_time * oe2
        else:
            env_vol  = 0.0
            finished = True

        if use_flng:
            flng_off += flng_doff
            flng_int  = int(abs(flng_off))
            if flng_int > 1023: flng_int = 1023

        if use_filt:
            hp_cut *= hp_dcut
            if hp_cut < 0.00001: hp_cut = 0.00001
            if hp_cut > 0.1:     hp_cut = 0.1

        supersample = 0.0

        for j in range(8):
            phase += 1
            if phase >= period_int:
                phase -= period_int
                if wt == 3:
                    for n in range(32):
                        noise_buf[n] = np.random.uniform(-1.0, 1.0)
                elif wt == 5:
                    for n in range(32):
                        w = np.random.uniform(-1.0, 1.0)
                        pb0 = 0.99886*pb0 + w*0.0555179
                        pb1 = 0.99332*pb1 + w*0.0750759
                        pb2 = 0.96900*pb2 + w*0.1538520
                        pb3 = 0.86650*pb3 + w*0.3104856
                        pb4 = 0.55000*pb4 + w*0.5329522
                        pb5 = -0.7616*pb5 - w*0.0168980
                        pink_buf[n] = (pb0+pb1+pb2+pb3+pb4+pb5+pb6+w*0.5362)*0.11
                        pb6 = w * 0.115926
                elif wt == 6:
                    for n in range(32):
                        if n % 8 == 0:
                            lores_buf[n] = np.random.uniform(-1.0, 1.0)
                        else:
                            lores_buf[n] = lores_buf[n-1]
                elif wt == 9:
                    fb = ((one_bit_state >> 1) & 1) ^ (one_bit_state & 1)
                    one_bit_state = (one_bit_state >> 1) | (fb << 14)
                    one_bit_noise = float(~one_bit_state & 1) - 0.5
                elif wt == 11:
                    fb = ((buzz_state >> 3) & 1) ^ (buzz_state & 1)
                    buzz_state = (buzz_state >> 1) | (fb << 14)
                    buzz_val   = float(~buzz_state & 1) - 0.5

            sample  = 0.0
            ot_str  = 1.0
            for k in range(ot_count + 1):
                tp = (phase * (k + 1)) % period_int
                cur_wt = wt
                if cur_wt == 10:
                    cur_wt = int(phase / 4) % 10

                if cur_wt == 0:
                    sample += ot_str * (0.5 if (tp / period_int) < sq_d else -0.5)
                elif cur_wt == 1:
                    sample += ot_str * (1.0 - (tp / period_int) * 2.0)
                elif cur_wt == 2:
                    pos = tp / period_int
                    if pos > 0.5: pos = (pos - 1.0) * 6.28318531
                    else:         pos = pos * 6.28318531
                    if pos < 0.0: ts = 1.27323954*pos + 0.405284735*pos*pos
                    else:         ts = 1.27323954*pos - 0.405284735*pos*pos
                    if ts < 0.0:  sv = 0.225*(ts*-ts - ts) + ts
                    else:         sv = 0.225*(ts*ts  - ts) + ts
                    sample += ot_str * sv
                elif cur_wt == 3:
                    idx = int(tp * 32 / period_int) % 32
                    sample += ot_str * noise_buf[idx]
                elif cur_wt == 4:
                    sample += ot_str * (abs(1.0 - (tp / period_int) * 2.0) - 1.0)
                elif cur_wt == 5:
                    idx = int(tp * 32 / period_int) % 32
                    sample += ot_str * pink_buf[idx]
                elif cur_wt == 6:
                    v = tp / period_int
                    arg = 3.14159265 * v
                    if arg > 1.56: arg = 1.56
                    sample += ot_str * np.tan(arg)
                elif cur_wt == 7:
                    pos = tp / period_int
                    if pos > 0.5: pos = (pos-1.0)*6.28318531
                    else:         pos = pos*6.28318531
                    if pos < 0.0: ts = 1.27323954*pos+0.405284735*pos*pos
                    else:         ts = 1.27323954*pos-0.405284735*pos*pos
                    if ts < 0.0:  sv = 0.225*(ts*-ts-ts)+ts
                    else:         sv = 0.225*(ts*ts-ts)+ts
                    v = 0.75 * sv
                    pos2 = ((tp*20) % period_int) / period_int
                    if pos2 > 0.5: pos2 = (pos2-1.0)*6.28318531
                    else:          pos2 = pos2*6.28318531
                    if pos2 < 0.0: ts2 = 1.27323954*pos2+0.405284735*pos2*pos2
                    else:          ts2 = 1.27323954*pos2-0.405284735*pos2*pos2
                    if ts2 < 0.0:  sv2 = 0.225*(ts2*-ts2-ts2)+ts2
                    else:          sv2 = 0.225*(ts2*ts2-ts2)+ts2
                    v += 0.25 * sv2
                    sample += ot_str * v
                elif cur_wt == 8:
                    amp = tp / period_int
                    sample += ot_str * (abs(1.0 - amp*amp*2.0) - 1.0)
                elif cur_wt == 9:
                    sample += ot_str * one_bit_noise
                elif cur_wt == 11:
                    sample += ot_str * buzz_val

                ot_str *= (1.0 - ot_falloff)

            if use_filt:
                lp_old  = lp_pos
                lp_cut *= lp_dcut
                if lp_cut < 0.0:   lp_cut = 0.0
                if lp_cut > 0.1:   lp_cut = 0.1
                if lp_on:
                    lp_dpos += (sample - lp_pos) * lp_cut
                    lp_dpos *= lp_damp
                else:
                    lp_pos  = sample
                    lp_dpos = 0.0
                lp_pos += lp_dpos
                hp_pos += lp_pos - lp_old
                hp_pos *= (1.0 - hp_cut)
                sample  = hp_pos

            if use_flng:
                flng_buf[flng_pos & 1023] = sample
                sample  += flng_buf[(flng_pos - flng_int + 1024) & 1023]
                flng_pos = (flng_pos + 1) & 1023

            supersample += sample

        if supersample >  8.0: supersample =  8.0
        if supersample < -8.0: supersample = -8.0
        supersample = mv2 * env_vol * supersample * 0.125

        bc_phase += bc_freq
        if bc_phase > 1.0:
            bc_phase = 0.0
            bc_last  = supersample
        bc_freq = bc_freq + bc_sweep
        if bc_freq < 0.0: bc_freq = 0.0
        if bc_freq > 1.0: bc_freq = 1.0
        supersample = bc_last

        if supersample > 0.0:
            supersample =  supersample ** comp_factor
        elif supersample < 0.0:
            supersample = -((-supersample) ** comp_factor)

        if muted:
            supersample = 0.0

        out[i] = supersample

    peak = 0.0
    for i in range(len(out)):
        v = out[i]
        if v < 0.0: v = -v
        if v > peak: peak = v

    if peak > 1e-9:
        scale = 0.9 / peak
        for i in range(len(out)):
            out[i] *= scale

    return out


def generate_wave(params):
    p = np.array(params, dtype=np.float64)
    raw = _generate_wave_jit(p)
    return (raw * 32767.0).astype(np.int16)


# ── Drawing ────────────────────────────────────────────────────────────────────

def draw_panel(x, y, w, h, params, label):
    rl.draw_rectangle_lines(x, y, w, h, rl.LIGHTGRAY)
    rl.draw_text(label, x + 10, y + 8, FONT_SIZE, rl.WHITE)

    sx    = x + 10
    sw    = w - 100
    row_h = (h - 50) // NUM_PARAMS
    by    = y + 46

    for i in range(NUM_PARAMS):
        sy      = by + i * row_h
        track_y = sy + row_h // 2
        rl.draw_text(PARAM_NAMES[i], sx, sy, 18, rl.GRAY)
        rl.draw_rectangle(sx, track_y, sw, 4, rl.DARKGRAY)
        t_val  = params[i]
        knob_x = int(sx + t_val * sw)
        rl.draw_circle(knob_x, track_y + 2, 7, rl.SKYBLUE)
        if i == 0:
            wt = int(params[i] * 10.0)
            if wt > 10: wt = 10
            val_str = WAVE_NAMES[wt]
        else:
            val_str = f"{params[i]:.2f}"
        rl.draw_text(val_str, sx + sw + 4, sy, 16, rl.WHITE)

    return sx, sw, by, row_h


def handle_slider_input(mx, my, sx, sw, by, row_h, params):
    if not rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return
    for i in range(NUM_PARAMS):
        track_y = by + i * row_h + row_h // 2 + 2
        if abs(my - track_y) < 12 and sx <= mx <= sx + sw:
            t = (mx - sx) / sw
            params[i] = max(0.0, min(1.0, t))


def draw_button(x, y, w, h, label, color):
    mx, my  = rl.get_mouse_x(), rl.get_mouse_y()
    hovered = x <= mx <= x + w and y <= my <= y + h
    col     = rl.color_brightness(color, 0.3) if hovered else color
    rl.draw_rectangle(x, y, w, h, col)
    rl.draw_rectangle_lines(x, y, w, h, rl.WHITE)
    tw = rl.measure_text(label, FONT_SIZE - 4)
    rl.draw_text(label, x + (w - tw) // 2, y + (h - (FONT_SIZE-4)) // 2, FONT_SIZE - 4, rl.WHITE)
    return hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT)


# ── Audio ──────────────────────────────────────────────────────────────────────

class Player:
    def __init__(self):
        self.stream  = None
        self.pcm     = None
        self.cursor  = 0
        self.playing = False

    def play(self, pcm):
        self._stop()
        self.stream  = rl.load_audio_stream(SAMPLE_RATE, 16, 1)
        self.pcm     = pcm
        self.cursor  = 0
        self.playing = True
        self._feed()
        rl.play_audio_stream(self.stream)

    def update(self):
        if not self.playing or self.stream is None:
            return
        if rl.is_audio_stream_processed(self.stream):
            self._feed()

    def _feed(self):
        remaining = len(self.pcm) - self.cursor
        if remaining <= 0:
            self._stop(); return
        count = min(CHUNK, remaining)
        chunk = np.ascontiguousarray(self.pcm[self.cursor:self.cursor + count])
        if count < CHUNK:
            chunk = np.concatenate([chunk, np.zeros(CHUNK - count, dtype=np.int16)])
        buf = rl.ffi.cast("short *", rl.ffi.from_buffer(chunk))
        rl.update_audio_stream(self.stream, buf, CHUNK)
        self.cursor += count

    def _stop(self):
        if self.stream is not None:
            rl.stop_audio_stream(self.stream)
            rl.unload_audio_stream(self.stream)
            self.stream = None
        self.playing = False


# ── Async generation ───────────────────────────────────────────────────────────

class GenJob:
    def __init__(self):
        self.result   = None   # np.int16 array when done
        self.running  = False
        self.label    = ""
        self._thread  = None

    def start(self, params, label):
        if self.running:
            return
        self.result  = None
        self.running = True
        self.label   = label
        p = list(params)
        def _run():
            self.result  = generate_wave(p)
            self.running = False
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def poll(self):
        """Returns pcm array if ready, else None."""
        if not self.running and self.result is not None:
            r = self.result
            self.result = None
            return r
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    rl.init_window(SCREEN_W, SCREEN_H, "bfxr Port")
    rl.set_audio_stream_buffer_size_default(CHUNK)
    rl.init_audio_device()
    rl.set_target_fps(60)

    params_l = make_params()
    params_r = make_params()
    params_r[6] = 0.5

    blend_t = 0.5
    player  = Player()
    gen     = GenJob()

    PANEL_W  = 760
    PANEL_H  = SCREEN_H - 60
    PANEL_Y  = 30
    LEFT_X   = 10
    RIGHT_X  = SCREEN_W - PANEL_W - 10
    CENTER_X = LEFT_X + PANEL_W + 10
    CENTER_W = RIGHT_X - CENTER_X - 10

    RAND_COLOR = rl.Color(120, 60, 160, 255)
    BTN_H      = 48
    BTN_W      = CENTER_W - 20

    while not rl.window_should_close():
        player.update()

        # pick up finished generation and play it
        pcm = gen.poll()
        if pcm is not None:
            player.play(pcm)

        mx = rl.get_mouse_x()
        my = rl.get_mouse_y()

        rl.begin_drawing()
        rl.clear_background(rl.Color(30, 30, 30, 255))

        sx_l, sw_l, by_l, rh_l = draw_panel(LEFT_X,  PANEL_Y, PANEL_W, PANEL_H, params_l, "PRESET A")
        sx_r, sw_r, by_r, rh_r = draw_panel(RIGHT_X, PANEL_Y, PANEL_W, PANEL_H, params_r, "PRESET B")

        handle_slider_input(mx, my, sx_l, sw_l, by_l, rh_l, params_l)
        handle_slider_input(mx, my, sx_r, sw_r, by_r, rh_r, params_r)

        cx = CENTER_X
        cw = CENTER_W

        lbl = "BLEND"
        rl.draw_text(lbl, cx + (cw - rl.measure_text(lbl, FONT_SIZE)) // 2, PANEL_Y, FONT_SIZE, rl.WHITE)

        bt_x  = cx + cw // 2
        bt_y1 = PANEL_Y + 44
        bt_y2 = PANEL_Y + 300
        bt_h  = bt_y2 - bt_y1
        rl.draw_rectangle(bt_x - 3, bt_y1, 6, bt_h, rl.DARKGRAY)
        knob_y = int(bt_y1 + blend_t * bt_h)
        rl.draw_circle(bt_x, knob_y, 12, rl.ORANGE)
        rl.draw_text(f"{blend_t:.2f}", bt_x + 16, knob_y - 12, FONT_SIZE - 6, rl.WHITE)
        rl.draw_text("A", bt_x - 8, bt_y1 - 28, FONT_SIZE, rl.SKYBLUE)
        rl.draw_text("B", bt_x - 8, bt_y2 + 4,  FONT_SIZE, rl.GREEN)

        if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
            if abs(mx - bt_x) < 20 and bt_y1 <= my <= bt_y2:
                blend_t = max(0.0, min(1.0, (my - bt_y1) / bt_h))

        bx   = cx + 10
        by_b = PANEL_Y + 320

        if draw_button(bx, by_b,       BTN_W, BTN_H, "RANDOMIZE A",  RAND_COLOR):
            randomize_params(params_l)
        if draw_button(bx, by_b + 60,  BTN_W, BTN_H, "RANDOMIZE B",  RAND_COLOR):
            randomize_params(params_r)
        if draw_button(bx, by_b + 140, BTN_W, BTN_H, "PLAY A",       rl.Color(40,  80, 160, 255)):
            gen.start(params_l, "A")
        if draw_button(bx, by_b + 200, BTN_W, BTN_H, "PLAY B",       rl.Color(40, 130,  60, 255)):
            gen.start(params_r, "B")
        if draw_button(bx, by_b + 260, BTN_W, BTN_H, "PLAY BLEND",   rl.Color(160, 80,  20, 255)):
            gen.start(blend_params(params_l, params_r, blend_t), "BLEND")

        if gen.running:
            status = f"Generating {gen.label}..."
            rl.draw_text(status, bx, by_b + 330, FONT_SIZE - 4, rl.YELLOW)
        elif player.playing:
            rl.draw_text("PLAYING...", bx, by_b + 330, FONT_SIZE - 4, rl.GREEN)
        else:
            rl.draw_text("---", bx, by_b + 330, FONT_SIZE - 4, rl.GRAY)

        rl.end_drawing()

    player._stop()
    rl.close_audio_device()
    rl.close_window()


if __name__ == "__main__":
    main()
