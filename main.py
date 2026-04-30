# main.py
import threading
import os
import wave
import numpy as np
import pyray as rl

try:
    import tkinter as tk
    def copy_to_clipboard(text):
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
except Exception:
    def copy_to_clipboard(text):
        pass

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
SLIDER_FONT_SIZE = FONT_SIZE - 6

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

    lbl_font = SLIDER_FONT_SIZE
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
    draw_text_f(label, x + size + 8, y + (size - SLIDER_FONT_SIZE) // 2, SLIDER_FONT_SIZE, rl.DARKGRAY)
    if hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return not checked
    return checked


def draw_hslider(x, y, w, h, val, label):
    mx, my = rl.get_mouse_x(), rl.get_mouse_y()
    lw     = measure_text_f(label, SLIDER_FONT_SIZE)
    sx     = x + lw + 8
    sw     = w - lw - 60
    bar_y  = y + SLIDER_FONT_SIZE // 2
    draw_text_f(label, x, y, SLIDER_FONT_SIZE, rl.DARKGRAY)
    filled = int(val * sw)
    rl.draw_rectangle(sx, bar_y, sw, h, rl.Color(200, 200, 200, 255))
    rl.draw_rectangle(sx, bar_y, filled, h, rl.Color(200, 160, 40, 255))
    knob_w = 6
    rl.draw_rectangle(sx + filled - knob_w // 2, bar_y - 4, knob_w, h + 8, rl.BLACK)
    draw_text_f(f"{val:.2f}", sx + sw + 6, bar_y, SLIDER_FONT_SIZE - 4, rl.DARKGRAY)
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

    touching = abs(mx - (bar_x + bar_w // 2)) < 24 and y <= my <= y + total_h
    if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT) and touching:
        blend_t = (my - y) / total_h * 3.0 - 1.0
        if blend_t < -1.0: blend_t = -1.0
        if blend_t >  2.0: blend_t =  2.0

    released = touching and rl.is_mouse_button_released(rl.MouseButton.MOUSE_BUTTON_LEFT)
    return blend_t, released


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


def export_wav(pcm, filepath):
    pcm_int16 = pcm.astype(np.int16)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_int16.tobytes())


def params_to_text(params_l, params_r, blend_t):
    lines = []
    lines.append("# bfxr scene")
    lines.append(f"blend_t={blend_t:.6f}")
    lines.append("")
    lines.append("# PRESET A")
    for i in range(NUM_PARAMS):
        lines.append(f"A.{PARAM_NAMES[i]}={param_display(i, params_l[i])}")
    lines.append("")
    lines.append("# PRESET B")
    for i in range(NUM_PARAMS):
        lines.append(f"B.{PARAM_NAMES[i]}={param_display(i, params_r[i])}")
    return "\n".join(lines) + "\n"


def export_scene_bfxr(params_l, params_r, blend_t, filepath):
    with open(filepath, "w") as f:
        f.write(params_to_text(params_l, params_r, blend_t))


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

def gen_btn_size(label, min_w=100, min_h=40, pad_x=24, pad_y=14, fs=None):
    if fs is None:
        fs = FONT_SIZE - 8
    tw = measure_text_f(label, fs)
    th = fs
    return max(tw + pad_x, min_w), max(th + pad_y, min_h)


def draw_button_sized(x, y, label, color, min_w=100, min_h=40, fs=None):
    if fs is None:
        fs = FONT_SIZE - 8
    bw, bh = gen_btn_size(label, min_w, min_h, fs=fs)
    clicked = draw_button(x, y, bw, bh, label, color)
    return clicked, bw, bh


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
    COLOR_EXPORT = rl.Color(100, 100, 160, 255)
    COLOR_CLIP   = rl.Color(80, 120, 80, 255)

    BTN_GAP = 8
    cx      = CENTER_X
    cw      = CENTER_W

    BTN_FS = FONT_SIZE - 8

    COL1_LABELS = ["PLAY A", "A< BLEND", "A< RND", "A< B", "EXPORT A", "COPY A"]
    col1_sizes  = [gen_btn_size(l, min_w=100, min_h=40, fs=BTN_FS) for l in COL1_LABELS]
    COL1_X      = cx + 4
    col1_w      = max(w for w, _ in col1_sizes)
    col1_x      = cx + 4

    COL3_LABELS = ["PLAY B", "BLEND >B", "RND >B", "A >B", "EXPORT B", "COPY B"]
    col3_sizes  = [gen_btn_size(l, min_w=100, min_h=40, fs=BTN_FS) for l in COL3_LABELS]
    col3_w      = max(w for w, _ in col3_sizes)
    col3_x      = cx + cw - col3_w - 4

    COL2_W      = cx + cw - 8 - col1_x - col1_w - col3_w - 8

    TOP_Y     = PANEL_Y + 10
    CTRL_H    = 32
    ctrl_y    = TOP_Y
    vol_y     = ctrl_y + CTRL_H + 6
    status_y  = vol_y + CTRL_H + 6

    def layout_col(labels, sizes, start_x, start_y, gap):
        rows = []
        cy = start_y
        for label, (w, h) in zip(labels, sizes):
            rows.append((label, start_x, cy, w, h))
            cy += h + gap
        return rows, cy - gap

    col1_rows, col1_end = layout_col(COL1_LABELS, col1_sizes, col1_x, status_y + CTRL_H + 8, BTN_GAP)
    col3_rows, col3_end = layout_col(COL3_LABELS, col3_sizes, col3_x, status_y + CTRL_H + 8, BTN_GAP)

    blend_slider_y1 = status_y + CTRL_H + 8
    max_bottom = max(col1_end, col3_end)
    blend_slider_y2 = max_bottom
    blend_h = blend_slider_y2 - blend_slider_y1

    export_blend_label = "EXPORT BLEND"
    copy_scene_label = "COPY SCENE"
    save_scene_label = "SAVE SCENE (.bfxr)"
    eb_w, eb_h = gen_btn_size(export_blend_label, min_w=100, min_h=40, fs=BTN_FS)
    cs_w, cs_h = gen_btn_size(copy_scene_label, min_w=100, min_h=40, fs=BTN_FS)
    ss_w, ss_h = gen_btn_size(save_scene_label, min_w=100, min_h=40, fs=BTN_FS)
    col2_btn_w = max(eb_w, cs_w, ss_w)
    col2_btn_x = cx + 4 + col1_w + 6 + (COL2_W - 10 - col1_w - col2_btn_w) // 2

    status_msg = ""
    status_msg_timer = 0.0

    while not rl.window_should_close():
        dt = rl.get_frame_time()
        if status_msg_timer > 0:
            status_msg_timer -= dt
            if status_msg_timer <= 0:
                status_msg = ""

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
        play_on_gen   = draw_checkbox(COL1_X, ctrl_y, 26, "Play on Change", play_on_gen)
        global_volume = draw_hslider(COL1_X, vol_y, cw - 16, 10, global_volume, "Vol")
        player.set_volume(global_volume)

        if gen.running:
            draw_text_f(f"Generating {gen.label}...", COL1_X, status_y, SLIDER_FONT_SIZE, rl.Color(180, 140, 0, 255))
        elif player.playing:
            draw_text_f("PLAYING...", COL1_X, status_y, SLIDER_FONT_SIZE, rl.Color(40, 130, 60, 255))
        elif status_msg:
            draw_text_f(status_msg, COL1_X, status_y, SLIDER_FONT_SIZE, rl.Color(40, 100, 180, 255))
        else:
            draw_text_f("---", COL1_X, status_y, SLIDER_FONT_SIZE, rl.GRAY)

        # ── Column 1: A buttons ──
        cy = status_y + CTRL_H + 8
        for label, bx, by, bw, bh in col1_rows:
            if label == "PLAY A":
                if draw_button(bx, cy, bw, bh, label, COLOR_A):
                    gen.start(params_l, "A")
            elif label == "A< BLEND":
                if draw_button(bx, cy, bw, bh, label, COLOR_XFER):
                    blended = clamp_params_to_ui(blend_params(params_l, params_r, blend_t))
                    wt_dom  = dominant_wave_type(blend_t, params_l[0], params_r[0])
                    blended[0] = wt_dom
                    for i in range(NUM_PARAMS): params_l[i] = blended[i]
                    if play_on_gen: gen.start(params_l, "A")
            elif label == "A< RND":
                if draw_button(bx, cy, bw, bh, label, COLOR_RAND):
                    randomize_params(params_l)
                    if play_on_gen: gen.start(params_l, "A")
            elif label == "A< B":
                if draw_button(bx, cy, bw, bh, label, COLOR_COPY):
                    for i in range(NUM_PARAMS): params_l[i] = params_r[i]
                    if play_on_gen: gen.start(params_l, "A")
            elif label == "EXPORT A":
                if draw_button(bx, cy, bw, bh, label, COLOR_EXPORT):
                    p = list(params_l)
                    gen_start_export(p, "A", lambda p: generate_wave(p))
            elif label == "COPY A":
                if draw_button(bx, cy, bw, bh, label, COLOR_CLIP):
                    text = params_to_text(params_l, params_l, 0.0)
                    copy_to_clipboard(text)
                    status_msg = "Copied Preset A to clipboard"
                    status_msg_timer = 2.0
            cy += bh + BTN_GAP

        # ── Column 2: blend slider ──
        blend_t, blend_released = draw_blend_slider(col1_x + col1_w + 6, blend_slider_y1, COL2_W, blend_h, blend_t)

        cy2 = blend_slider_y2 + BTN_GAP
        if draw_button(col2_btn_x, cy2, col2_btn_w, eb_h, "EXPORT BLEND", COLOR_EXPORT):
            gen_start_export_blend(params_l, params_r, blend_t)
        cy2 += eb_h + BTN_GAP
        if draw_button(col2_btn_x, cy2, col2_btn_w, cs_h, "COPY SCENE", COLOR_CLIP):
            text = params_to_text(params_l, params_r, blend_t)
            copy_to_clipboard(text)
            status_msg = "Copied scene to clipboard"
            status_msg_timer = 2.0
        cy2 += cs_h + BTN_GAP
        if draw_button(col2_btn_x, cy2, col2_btn_w, ss_h, "SAVE SCENE (.bfxr)", COLOR_CLIP):
            export_scene_bfxr(params_l, params_r, blend_t, "scene.bfxr")
            status_msg = "Saved scene.bfxr"
            status_msg_timer = 2.0

        blend_btn_y2 = cy2 + ss_h + BTN_GAP
        if draw_button(col2_btn_x, blend_btn_y2, col2_btn_w, eb_h, "PLAY BLEND", COLOR_BLEND):
            blended_p = blend_params(params_l, params_r, blend_t)
            gen.start_blended(blended_p, params_l[0], params_r[0], blend_t, "BLEND")

        if blend_released and play_on_gen:
            blended_p = blend_params(params_l, params_r, blend_t)
            gen.start_blended(blended_p, params_l[0], params_r[0], blend_t, "BLEND")

        # ── Column 3: B buttons ──
        cy = status_y + CTRL_H + 8
        for label, bx, by, bw, bh in col3_rows:
            if label == "PLAY B":
                if draw_button(bx, cy, bw, bh, label, COLOR_B):
                    gen.start(params_r, "B")
            elif label == "BLEND >B":
                if draw_button(bx, cy, bw, bh, label, COLOR_XFER):
                    blended = clamp_params_to_ui(blend_params(params_l, params_r, blend_t))
                    wt_dom  = dominant_wave_type(blend_t, params_l[0], params_r[0])
                    blended[0] = wt_dom
                    for i in range(NUM_PARAMS): params_r[i] = blended[i]
                    if play_on_gen: gen.start(params_r, "B")
            elif label == "RND >B":
                if draw_button(bx, cy, bw, bh, label, COLOR_RAND):
                    randomize_params(params_r)
                    if play_on_gen: gen.start(params_r, "B")
            elif label == "A >B":
                if draw_button(bx, cy, bw, bh, label, COLOR_COPY):
                    for i in range(NUM_PARAMS): params_r[i] = params_l[i]
                    if play_on_gen: gen.start(params_r, "B")
            elif label == "EXPORT B":
                if draw_button(bx, cy, bw, bh, label, COLOR_EXPORT):
                    p = list(params_r)
                    gen_start_export(p, "B", lambda p: generate_wave(p))
            elif label == "COPY B":
                if draw_button(bx, cy, bw, bh, label, COLOR_CLIP):
                    text = params_to_text(params_r, params_r, 1.0)
                    copy_to_clipboard(text)
                    status_msg = "Copied Preset B to clipboard"
                    status_msg_timer = 2.0
            cy += bh + BTN_GAP

        rl.end_drawing()

    player._stop()
    rl.close_audio_device()
    rl.close_window()


_export_gen = None
_export_label = ""
_export_fn = None

def gen_start_export(params, label, gen_fn):
    global _export_gen, _export_label, _export_fn
    if _export_gen is not None and _export_gen.is_alive():
        return
    _export_label = label
    _export_fn = gen_fn
    _export_gen = threading.Thread(target=_do_export, args=(list(params),), daemon=True)
    _export_gen.start()

def gen_start_export_blend(params_l, params_r, blend_t):
    global _export_gen, _export_label
    if _export_gen is not None and _export_gen.is_alive():
        return
    _export_label = "BLEND"
    blended = blend_params(params_l, params_r, blend_t)
    wta = params_l[0]
    wtb = params_r[0]
    def _gen(p):
        return generate_wave_blended(p, wta, wtb, blend_t)
    _export_fn = _gen
    _export_gen = threading.Thread(target=_do_export, args=(list(blended),), daemon=True)
    _export_gen.start()

def _do_export(params):
    global _export_gen, _export_label
    pcm = _export_fn(params)
    fname = f"bfxr_{_export_label.lower()}.wav"
    export_wav(pcm, fname)
    _export_gen = None


if __name__ == "__main__":
    main()
