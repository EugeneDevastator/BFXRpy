import threading
import numpy as np
import pyray as rl

from params import (
    WAVE_NAMES, PARAM_NAMES, NUM_PARAMS,
    make_params, randomize_params, blend_params,
)
from generator import generate_wave, SAMPLE_RATE

SCREEN_W  = 1920
SCREEN_H  = 1080
FONT_SIZE = 42   # 32 * 1.3 ≈ 42
CHUNK     = 4096

# Parameter group separators: (label, start_index, end_index_exclusive)
PARAM_GROUPS = [
    ("Wave",        0,  2),
    ("Envelope",    2,  6),
    ("Frequency",   6, 10),
    ("Vibrato",    10, 12),
    ("Change",     12, 17),
    ("Duty",       17, 19),
    ("Repeat",     19, 20),
    ("Flanger",    20, 22),
    ("Filters",    22, 27),
    ("Bit/Comp",   27, 30),
    ("Overtones",  30, 32),
]

# ── Drawing ────────────────────────────────────────────────────────────────────

def draw_panel(x, y, w, h, params, label):
    rl.draw_rectangle_lines(x, y, w, h, rl.LIGHTGRAY)
    rl.draw_text(label, x + 10, y + 8, FONT_SIZE, rl.WHITE)

    sx    = x + 10
    sw    = w - 140
    row_h = (h - 50) // NUM_PARAMS
    by    = y + 46

    # build a set of indices that start a new group (except first)
    group_starts = set(g[1] for g in PARAM_GROUPS if g[1] > 0)

    for i in range(NUM_PARAMS):
        # separator line before group start
        if i in group_starts:
            sep_y = by + i * row_h - 2
            rl.draw_line(sx, sep_y, sx + sw + 120, sep_y, rl.Color(80, 80, 80, 255))

        sy      = by + i * row_h
        track_y = sy + row_h // 2

        rl.draw_text(PARAM_NAMES[i], sx, sy, FONT_SIZE - 18, rl.GRAY)

        # filled rect slider
        bar_h  = 8
        bar_y  = track_y - bar_h // 2
        filled = int(params[i] * sw)
        rl.draw_rectangle(sx, bar_y, sw, bar_h, rl.DARKGRAY)
        rl.draw_rectangle(sx, bar_y, filled, bar_h, rl.SKYBLUE)
        # knob as bold rect
        knob_w = 6
        knob_h = 18
        knob_x = sx + filled - knob_w // 2
        rl.draw_rectangle(knob_x, bar_y - (knob_h - bar_h) // 2, knob_w, knob_h, rl.WHITE)

        if i == 0:
            wt = int(params[i] * 10.0)
            if wt > 10: wt = 10
            val_str = WAVE_NAMES[wt]
        else:
            val_str = f"{params[i]:.2f}"
        rl.draw_text(val_str, sx + sw + 6, sy, FONT_SIZE - 16, rl.WHITE)

    return sx, sw, by, row_h


def handle_slider_input(mx, my, sx, sw, by, row_h, params):
    if not rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return
    for i in range(NUM_PARAMS):
        track_y = by + i * row_h + row_h // 2
        if abs(my - track_y) < 14 and sx <= mx <= sx + sw:
            t = (mx - sx) / sw
            params[i] = max(0.0, min(1.0, t))


def draw_button(x, y, w, h, label, color):
    mx, my  = rl.get_mouse_x(), rl.get_mouse_y()
    hovered = x <= mx <= x + w and y <= my <= y + h
    col     = rl.color_brightness(color, 0.3) if hovered else color
    rl.draw_rectangle(x, y, w, h, col)
    rl.draw_rectangle_lines(x, y, w, h, rl.WHITE)
    tw = rl.measure_text(label, FONT_SIZE - 4)
    rl.draw_text(label, x + (w - tw) // 2, y + (h - (FONT_SIZE - 4)) // 2, FONT_SIZE - 4, rl.WHITE)
    return hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT)


def draw_checkbox(x, y, size, label, checked):
    mx, my  = rl.get_mouse_x(), rl.get_mouse_y()
    hovered = x <= mx <= x + size and y <= my <= y + size
    rl.draw_rectangle_lines(x, y, size, size, rl.WHITE)
    if checked:
        rl.draw_rectangle(x + 4, y + 4, size - 8, size - 8, rl.ORANGE)
    rl.draw_text(label, x + size + 8, y + (size - (FONT_SIZE - 8)) // 2, FONT_SIZE - 8, rl.WHITE)
    if hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return not checked
    return checked


def draw_hslider(x, y, w, h, val, label):
    """Horizontal filled-rect slider, returns new value."""
    mx, my  = rl.get_mouse_x(), rl.get_mouse_y()
    rl.draw_text(label, x, y, FONT_SIZE - 10, rl.GRAY)
    bar_y = y + FONT_SIZE - 6
    filled = int(val * w)
    rl.draw_rectangle(x, bar_y, w, h, rl.DARKGRAY)
    rl.draw_rectangle(x, bar_y, filled, h, rl.Color(200, 160, 40, 255))
    knob_w = 6
    rl.draw_rectangle(x + filled - knob_w // 2, bar_y - 4, knob_w, h + 8, rl.WHITE)
    rl.draw_text(f"{val:.2f}", x + w + 6, bar_y, FONT_SIZE - 14, rl.WHITE)
    if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
        if abs(my - (bar_y + h // 2)) < 20 and x <= mx <= x + w:
            val = max(0.0, min(1.0, (mx - x) / w))
    return val


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
        self.stream  = rl.load_audio_stream(SAMPLE_RATE, 16, 1)
        rl.set_audio_stream_volume(self.stream, self.volume)
        self.pcm     = pcm
        self.cursor  = 0
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

    def poll(self):
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

    blend_t       = 0.5
    blend_dragging = False
    player        = Player()
    gen           = GenJob()
    play_on_gen   = False
    global_volume = 1.0

    PANEL_W  = 740
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

        pcm = gen.poll()
        if pcm is not None:
            if play_on_gen:
                player.play(pcm)

        mx = rl.get_mouse_x()
        my = rl.get_mouse_y()

        # blend dragger release → autoplay blend
        was_dragging = blend_dragging

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

        # filled rect blend slider (vertical)
        bar_w = 16
        bar_x = bt_x - bar_w // 2
        rl.draw_rectangle(bar_x, bt_y1, bar_w, bt_h, rl.DARKGRAY)
        filled_h = int(blend_t * bt_h)
        rl.draw_rectangle(bar_x, bt_y1, bar_w, filled_h, rl.ORANGE)
        knob_h2 = 10
        knob_y  = bt_y1 + filled_h - knob_h2 // 2
        rl.draw_rectangle(bar_x - 6, knob_y, bar_w + 12, knob_h2, rl.WHITE)
        rl.draw_text(f"{blend_t:.2f}", bt_x + 16, knob_y - 6, FONT_SIZE - 10, rl.WHITE)
        rl.draw_text("A", bt_x - 8, bt_y1 - 28, FONT_SIZE, rl.SKYBLUE)
        rl.draw_text("B", bt_x - 8, bt_y2 + 4,  FONT_SIZE, rl.GREEN)

        if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
            if abs(mx - bt_x) < 24 and bt_y1 <= my <= bt_y2:
                blend_t = max(0.0, min(1.0, (my - bt_y1) / bt_h))
                blend_dragging = True
        else:
            if was_dragging and blend_dragging and play_on_gen:
                gen.start(blend_params(params_l, params_r, blend_t), "BLEND")
            blend_dragging = False

        bx   = cx + 10
        by_b = PANEL_Y + 320

        if draw_button(bx, by_b,       BTN_W, BTN_H, "RANDOMIZE A", RAND_COLOR):
            randomize_params(params_l)
            if play_on_gen:
                gen.start(params_l, "A")
        if draw_button(bx, by_b + 60,  BTN_W, BTN_H, "RANDOMIZE B", RAND_COLOR):
            randomize_params(params_r)
            if play_on_gen:
                gen.start(params_r, "B")
        if draw_button(bx, by_b + 140, BTN_W, BTN_H, "PLAY A",      rl.Color(40,  80, 160, 255)):
            gen.start(params_l, "A")
        if draw_button(bx, by_b + 200, BTN_W, BTN_H, "PLAY B",      rl.Color(40, 130,  60, 255)):
            gen.start(params_r, "B")
        if draw_button(bx, by_b + 260, BTN_W, BTN_H, "PLAY BLEND",  rl.Color(160, 80,  20, 255)):
            gen.start(blend_params(params_l, params_r, blend_t), "BLEND")

        # play on generate checkbox
        play_on_gen = draw_checkbox(bx, by_b + 330, 28, "Play on Generate", play_on_gen)

        # global volume slider
        global_volume = draw_hslider(bx, by_b + 380, BTN_W - 60, 10, global_volume, "Volume")
        player.set_volume(global_volume)

        # status
        status_y = by_b + 440
        if gen.running:
            rl.draw_text(f"Generating {gen.label}...", bx, status_y, FONT_SIZE - 4, rl.YELLOW)
        elif player.playing:
            rl.draw_text("PLAYING...", bx, status_y, FONT_SIZE - 4, rl.GREEN)
        else:
            rl.draw_text("---", bx, status_y, FONT_SIZE - 4, rl.GRAY)

        rl.end_drawing()

    player._stop()
    rl.close_audio_device()
    rl.close_window()


if __name__ == "__main__":
    main()
