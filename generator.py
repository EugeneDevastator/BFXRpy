# generator.py
import numpy as np
from numba import njit

SAMPLE_RATE = 44100


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
    # p[32] = WaveTypeB, p[33] = BlendAmt handled externally

    wt = int(wave_type_f)
    if wt < 0:  wt = 0
    if wt > 11: wt = 11

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


def generate_wave_blended(params, wave_type_a, wave_type_b, blend_t):
    """
    Runs generator twice with same params but different wave types, blends output.
    blend_t=0 -> pure wave_type_a, blend_t=1 -> pure wave_type_b.
    """
    p_a = np.array(params, dtype=np.float64)
    p_b = np.array(params, dtype=np.float64)
    p_a[0] = float(wave_type_a)
    p_b[0] = float(wave_type_b)

    raw_a = _generate_wave_jit(p_a)
    raw_b = _generate_wave_jit(p_b)

    len_a = len(raw_a)
    len_b = len(raw_b)
    n     = max(len_a, len_b)

    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        sa = raw_a[i] if i < len_a else 0.0
        sb = raw_b[i] if i < len_b else 0.0
        out[i] = sa + blend_t * (sb - sa)

    peak = np.max(np.abs(out))
    if peak > 1e-9:
        out *= 0.9 / peak

    return (out * 32767.0).astype(np.int16)

