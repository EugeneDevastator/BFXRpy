# main.py
import threading
import numpy as np
import pyray as rl

from params import (
    PARAM_NAMES, PARAM_RANGES, PARAM_GROUPS, NUM_PARAMS,
    param_to_t, t_to_param, param_display,
    make_params, randomize_params, blend_params,
    WAVE_NAMES,
)
from generator import generate_wave, generate_wave_blended, SAMPLE_RATE

SCREEN_W  = 1920
SCREEN_H  = 1080
FONT_SIZE = 32
CHUNK     = 4096

_font = None

def get_font():
    return _font if _font is not None else rl.get_font_default()

def measure_text_f(text, size):
    f = get_font()
    v = rl.measure_text_ex(f, text, size, 1)
    return int(v.x)

def draw_text_f(text, x, y, size, color):
    rl.draw_text_ex(get_font(), text, rl.Vector2(x, y), size, 1, color)

_GROUP_STARTS = set(g[1] for g in PARAM_GROUPS if g[1] > 0)


def draw_panel(x, y, w, h, params, label):
    rl.draw_rectangle_lines(x, y, w, h, rl.LIGHTGRAY)
    draw_text_f(label, x + 10, y + 8, FONT_SIZE, rl.DARKGRAY)

    lbl_font = FONT_SIZE - 10
    val_w    = 72
    pad_left = x + 10
    row_h    = (h - 50) // NUM_PARAMS
    by       = y + 46

    max_lbl_w = max(measure_text_f(PARAM_NAMES[i], lbl_font) for i in range(NUM_PARAMS))
    lbl_gap   = 6
    sx        = pad_left + max_lbl_w + lbl_gap
    sw        = (x + w) - sx - val_w - 14

    for i in range(NUM_PARAMS):
        if i in _GROUP_STARTS:
            sep_y = by + i * row_h - 2
            rl.draw_line(pad_left, sep_y,
                         pad_left + max_lbl_w + lbl_gap + sw + val_w + 8, sep_y,
                         rl.Color(180, 180, 180, 255))

        sy      = by + i * row_h
        track_y = sy + row_h // 2

        draw_text_f(PARAM_NAMES[i], pad_left, sy, lbl_font, rl.DARKGRAY)

        bar_h  = 8
        bar_y  = track_y - bar_h // 2
        t      = param_to_t(i, params[i])

        lo, hi, _ = PARAM_RANGES[i]
        rl.draw_rectangle(sx, bar_y, sw, bar_h, rl.Color(200, 200, 200, 255))

        if lo < 0:
            mid_x   = sx + sw // 2
            fill_px = int(t * sw) - sw // 2
            if fill_px >= 0:
                rl.draw_rectangle(mid_x, bar_y, fill_px, bar_h, rl.Color(70, 130, 200, 255))
            else:
                rl.draw_rectangle(mid_x + fill_px, bar_y, -fill_px, bar_h, rl.Color(200, 100, 70, 255))
            rl.draw_line(mid_x, bar_y - 2, mid_x, bar_y + bar_h + 2, rl.DARKGRAY)
        else:
            filled = int(t * sw)
            rl.draw_rectangle(sx, bar_y, filled, bar_h, rl.Color(70, 130, 200, 255))

        knob_w = 6
        knob_h = 18
        knob_x = sx + int(t * sw) - knob_w // 2
        rl.draw_rectangle(knob_x, bar_y - (knob_h - bar_h) // 2, knob_w, knob_h, rl.BLACK)

        val_str = param_display(i, params[i])
        draw_text_f(val_str, sx + sw + 6, sy, lbl_font, rl.DARKGRAY)

    return sx, sw, by, row_h


def handle_slider_input(mx, my, sx, sw, by, row_h, params):
    released = False
    for i in range(NUM_PARAMS):
        track_y = by + i * row_h + row_h // 2
        if abs(my - track_y) < 14 and sx <= mx <= sx + sw:
            if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
                t = (mx - sx) / sw
                if t < 0.0: t = 0.0
                if t > 1.0: t = 1.0
                params[i] = t_to_param(i, t)
            if rl.is_mouse_button_released(rl.MouseButton.MOUSE_BUTTON_LEFT):
                released = True
    return released


def draw_button(x, y, w, h, label, color):
    mx, my  = rl.get_mouse_x(), rl.get_mouse_y()
    hovered = x <= mx <= x + w and y <= my <= y + h
    col     = rl.color_brightness(color, 0.3) if hovered else color
    rl.draw_rectangle(x, y, w, h, col)
    rl.draw_rectangle_lines(x, y, w, h, rl.DARKGRAY)
    fs = FONT_SIZE - 8
    tw = measure_text_f(label, fs)
    draw_text_f(label, x + (w - tw) // 2, y + (h - fs) // 2, fs, rl.WHITE)
    return hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT)


def draw_checkbox(x, y, size, label, checked):
    mx, my  = rl.get_mouse_x(), rl.get_mouse_y()
    hovered = x <= mx <= x + size and y <= my <= y + size
    rl.draw_rectangle_lines(x, y, size, size, rl.DARKGRAY)
    if checked:
        rl.draw_rectangle(x + 4, y + 4, size - 8, size - 8, rl.Color(200, 120, 30, 255))
    draw_text_f(label, x + size + 8, y + (size - (FONT_SIZE - 8)) // 2, FONT_SIZE - 8, rl.DARKGRAY)
    if hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return not checked
    return checked


def draw_hslider(x, y, w, h, val, label):
    mx, my = rl.get_mouse_x(), rl.get_mouse_y()
    lw     = measure_text_f(label, FONT_SIZE - 10)
    sx     = x + lw + 8
    sw     = w - lw - 60
    bar_y  = y + (FONT_SIZE - 10) // 2
    draw_text_f(label, x, y, FONT_SIZE - 10, rl.DARKGRAY)
    filled = int(val * sw)
    rl.draw_rectangle(sx, bar_y, sw, h, rl.Color(200, 200, 200, 255))
    rl.draw_rectangle(sx, bar_y, filled, h, rl.Color(200, 160, 40, 255))
    knob_w = 6
    rl.draw_rectangle(sx + filled - knob_w // 2, bar_y - 4, knob_w, h + 8, rl.BLACK)
    draw_text_f(f"{val:.2f}", sx + sw + 6, bar_y, FONT_SIZE - 14, rl.DARKGRAY)
    if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
        if abs(my - (bar_y + h // 2)) < 20 and sx <= mx <= sx + sw:
            val = (mx - sx) / sw
            if val < 0.0: val = 0.0
            if val > 1.0: val = 1.0
    return val


def draw_blend_slider(x, y, w, h, blend_t):
    mx, my = rl.get_mouse_x(), rl.get_mouse_y()

    seg_h   = h // 3
    total_h = seg_h * 3

    COLOR_EXTRA_A = rl.Color(180, 100, 40,  180)
    COLOR_CORE    = rl.Color(200, 160, 40,  255)
    COLOR_EXTRA_B = rl.Color(100, 180, 40,  180)
    COLOR_TRACK   = rl.Color(200, 200, 200, 255)

    bar_w = 16
    bar_x = x + w // 2 - bar_w // 2

    rl.draw_rectangle(bar_x, y, bar_w, total_h, COLOR_TRACK)

    def t_to_py(t):
        return y + int((t + 1.0) / 3.0 * total_h)

    a_py    = t_to_py(0.0)
    b_py    = t_to_py(1.0)
    knob_py = t_to_py(blend_t)

    if blend_t < 0.0:
        fill_y = knob_py
        fill_h = a_py - knob_py
        rl.draw_rectangle(bar_x, fill_y, bar_w, fill_h, COLOR_EXTRA_A)
    elif blend_t <= 1.0:
        fill_h = knob_py - a_py
        rl.draw_rectangle(bar_x, a_py, bar_w, fill_h, COLOR_CORE)
    else:
        rl.draw_rectangle(bar_x, a_py, bar_w, b_py - a_py, COLOR_CORE)
        rl.draw_rectangle(bar_x, b_py, bar_w, knob_py - b_py, COLOR_EXTRA_B)

    rl.draw_line(bar_x - 8, a_py, bar_x + bar_w + 8, a_py, rl.Color(40, 80, 160, 255))
    rl.draw_line(bar_x - 8, b_py, bar_x + bar_w + 8, b_py, rl.Color(40, 130, 60, 255))

    lbl_fs = FONT_SIZE - 4
    draw_text_f("A", bar_x - 24, a_py - lbl_fs // 2, lbl_fs, rl.Color(40, 80, 160, 255))
    draw_text_f("B", bar_x - 24, b_py - lbl_fs // 2, lbl_fs, rl.Color(40, 130, 60, 255))

    knob_h2 = 10
    rl.draw_rectangle(bar_x - 6, knob_py - knob_h2 // 2, bar_w + 12, knob_h2, rl.BLACK)
    draw_text_f(f"{blend_t:.2f}", bar_x + bar_w + 6, knob_py - lbl_fs // 2, FONT_SIZE - 12, rl.DARKGRAY)

    if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
        if abs(mx - (bar_x + bar_w // 2)) < 24 and y <= my <= y + total_h:
            blend_t = (my - y) / total_h * 3.0 - 1.0
            if blend_t < -1.0: blend_t = -1.0
            if blend_t >  2.0: blend_t =  2.0

    return blend_t


def clamp_params_to_ui(params):
    result = list(params)
    for i in range(NUM_PARAMS):
        lo, hi, _ = PARAM_RANGES[i]
        if result[i] < lo: result[i] = lo
        if result[i] > hi: result[i] = hi
    return result


def dominant_wave_type(blend_t, wt_a, wt_b):
    """Return wave type index of the dominant side."""
    return wt_a if blend_t <= 0.5 else wt_b


# ── Audio ──────────────────────────────────────────────────────────────────────

class Player:
    def __init__(self):
        self.stream  = None
        self.pcm     = None
        self.cursor  = 0
        self.playing = False
        self.volume  = 1.0

    def play(self, pcm):
        self._stop()
        self.stream = rl.load_audio_stream(SAMPLE_RATE, 16, 1)
        rl.set_audio_stream_volume(self.stream, self.volume)
        self.pcm    = pcm
        self.cursor = 0
        self.playing = True
        self._feed()
        rl.play_audio_stream(self.stream)

    def set_volume(self, v):
        self.volume = v
        if self.stream is not None:
            rl.set_audio_stream_volume(self.stream, v)

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
        self.result  = None
        self.running = False
        self.label   = ""
        self._thread = None

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

    # GenJob.start_blended
    def start_blended(self, params, wave_type_a, wave_type_b, blend_t, label):
        if self.running:
            return
        self.result  = None
        self.running = True
        self.label   = label
        p  = list(params)
        wta = wave_type_a
        wtb = wave_type_b
        bt  = blend_t
        def _run():
            self.result  = generate_wave_blended(p, wta, wtb, bt)
            self.running = False
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()


    def poll(self):
        if not self.running and self.result is not None:
            r = self.result
            self.result = None
            return r
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global _font

    rl.init_window(SCREEN_W, SCREEN_H, "bfxr Port")
    rl.set_audio_stream_buffer_size_default(CHUNK)
    rl.init_audio_device()
    rl.set_target_fps(60)

    try:
        _font = rl.load_font_ex("Cadman_Bold.otf", FONT_SIZE * 2, rl.ffi.NULL, 0)
        rl.set_texture_filter(_font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
    except Exception:
        _font = None

    params_l = make_params()
    params_r = make_params()
    params_r[6] = 0.5

    blend_t        = 0.5
    blend_dragging = False
    player         = Player()
    gen            = GenJob()
    play_on_gen    = False
    global_volume  = 1.0

    PANEL_W  = 740
    PANEL_H  = SCREEN_H - 60
    PANEL_Y  = 30
    LEFT_X   = 10
    RIGHT_X  = SCREEN_W - PANEL_W - 10
    CENTER_X = LEFT_X + PANEL_W + 10
    CENTER_W = RIGHT_X - CENTER_X - 10

    COLOR_A    = rl.Color(40,  80, 160, 255)
    COLOR_B    = rl.Color(40, 130,  60, 255)
    COLOR_RAND = rl.Color(120, 60, 160, 255)
    COLOR_COPY = rl.Color(80,  80,  80, 255)
    COLOR_XFER = rl.Color(160, 80,  20, 255)
    COLOR_BLEND= rl.Color(180, 130,  20, 255)

    BTN_H   = 52
    BTN_GAP = 10
    cx      = CENTER_X
    cw      = CENTER_W

    COL_BTN_W   = (cw - 20) * 2 // 5
    COL_BLEND_W = cw - 2 * COL_BTN_W - 20
    COL1_X      = cx + 4
    COL2_X      = COL1_X + COL_BTN_W + 6
    COL3_X      = COL2_X + COL_BLEND_W + 6

    TOP_Y     = PANEL_Y + 10
    CTRL_H    = 36
    ctrl_y    = TOP_Y
    vol_y     = ctrl_y + CTRL_H + 8
    status_y  = vol_y + CTRL_H + 8
    BTN_START = status_y + CTRL_H + 8

    def btn_y(r): return BTN_START + r * (BTN_H + BTN_GAP)

    blend_slider_y1 = BTN_START
    blend_slider_y2 = BTN_START + 4 * (BTN_H + BTN_GAP) - BTN_GAP
    blend_h         = blend_slider_y2 - blend_slider_y1

    while not rl.window_should_close():
        player.update()

        pcm = gen.poll()
        if pcm is not None and play_on_gen:
            player.play(pcm)

        mx = rl.get_mouse_x()
        my = rl.get_mouse_y()
        was_dragging = blend_dragging

        rl.begin_drawing()
        rl.clear_background(rl.Color(240, 240, 240, 255))

        sx_l, sw_l, by_l, rh_l = draw_panel(LEFT_X,  PANEL_Y, PANEL_W, PANEL_H, params_l, "PRESET A")
        sx_r, sw_r, by_r, rh_r = draw_panel(RIGHT_X, PANEL_Y, PANEL_W, PANEL_H, params_r, "PRESET B")

        rel_l = handle_slider_input(mx, my, sx_l, sw_l, by_l, rh_l, params_l)
        rel_r = handle_slider_input(mx, my, sx_r, sw_r, by_r, rh_r, params_r)

        if play_on_gen:
            if rel_l: gen.start(params_l, "A")
            if rel_r: gen.start(params_r, "B")

        # ── Top controls ──
        play_on_gen   = draw_checkbox(COL1_X, ctrl_y, 28, "Play on Change", play_on_gen)
        global_volume = draw_hslider(COL1_X, vol_y, cw - 16, 10, global_volume, "Vol")
        player.set_volume(global_volume)

        if gen.running:
            draw_text_f(f"Generating {gen.label}...", COL1_X, status_y, FONT_SIZE - 4, rl.Color(180, 140, 0, 255))
        elif player.playing:
            draw_text_f("PLAYING...", COL1_X, status_y, FONT_SIZE - 4, rl.Color(40, 130, 60, 255))
        else:
            draw_text_f("---", COL1_X, status_y, FONT_SIZE - 4, rl.GRAY)

        # ── Column 1: A buttons ──
        # PLAY A: pure A, blend=0 means only gen A runs
        if draw_button(COL1_X, btn_y(0), COL_BTN_W, BTN_H, "PLAY A", COLOR_A):
            gen.start(params_l, "A")

        # A< BLEND: copy blended params into A, dominant wave type written
        if draw_button(COL1_X, btn_y(1), COL_BTN_W, BTN_H, "A< BLEND", COLOR_XFER):
            blended = clamp_params_to_ui(blend_params(params_l, params_r, blend_t))
            wt_dom  = dominant_wave_type(blend_t, params_l[0], params_r[0])
            blended[0] = wt_dom
            for i in range(NUM_PARAMS): params_l[i] = blended[i]
            if play_on_gen: gen.start(params_l, "A")

        if draw_button(COL1_X, btn_y(2), COL_BTN_W, BTN_H, "A< RND", COLOR_RAND):
            randomize_params(params_l)
            if play_on_gen: gen.start(params_l, "A")

        if draw_button(COL1_X, btn_y(3), COL_BTN_W, BTN_H, "A< B", COLOR_COPY):
            for i in range(NUM_PARAMS): params_l[i] = params_r[i]
            if play_on_gen: gen.start(params_l, "A")

        # ── Column 2: blend slider ──
        prev_blend_t = blend_t
        blend_t = draw_blend_slider(COL2_X, blend_slider_y1, COL_BLEND_W, blend_h, blend_t)

        # PLAY BLEND button below slider
        blend_btn_y = blend_slider_y2 + BTN_GAP
        if draw_button(COL2_X, blend_btn_y, COL_BLEND_W, BTN_H, "PLAY\nBLEND", COLOR_BLEND):
            blended_p = blend_params(params_l, params_r, blend_t)
            gen.start_blended(blended_p, params_l[0], params_r[0], blend_t, "BLEND")


        dragging_now = rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT)
        if was_dragging and not dragging_now and play_on_gen:
            blended_p = blend_params(params_l, params_r, blend_t)
            gen.start_blended(blended_p, params_l[0], params_r[0], blend_t, "BLEND")

        # ── Column 3: B buttons ──
        # PLAY B: pure B, blend=1 means only gen B runs
        if draw_button(COL3_X, btn_y(0), COL_BTN_W, BTN_H, "PLAY B", COLOR_B):
            gen.start(params_r, "B")

        # BLEND >B: copy blended params into B, dominant wave type written
        if draw_button(COL3_X, btn_y(1), COL_BTN_W, BTN_H, "BLEND >B", COLOR_XFER):
            blended = clamp_params_to_ui(blend_params(params_l, params_r, blend_t))
            wt_dom  = dominant_wave_type(blend_t, params_l[0], params_r[0])
            blended[0] = wt_dom
            for i in range(NUM_PARAMS): params_r[i] = blended[i]
            if play_on_gen: gen.start(params_r, "B")

        if draw_button(COL3_X, btn_y(2), COL_BTN_W, BTN_H, "RND >B", COLOR_RAND):
            randomize_params(params_r)
            if play_on_gen: gen.start(params_r, "B")

        if draw_button(COL3_X, btn_y(3), COL_BTN_W, BTN_H, "A >B", COLOR_COPY):
            for i in range(NUM_PARAMS): params_r[i] = params_l[i]
            if play_on_gen: gen.start(params_r, "B")

        rl.end_drawing()

    player._stop()
    rl.close_audio_device()
    rl.close_window()


if __name__ == "__main__":
    main()
