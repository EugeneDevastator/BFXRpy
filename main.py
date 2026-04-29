import threading
import numpy as np
import pyray as rl

from params import (
    WAVE_NAMES, PARAM_NAMES, NUM_PARAMS,
    make_params, randomize_params, blend_params,
)
from generator import generate_wave, SAMPLE_RATE

SCREEN_W = 1920
SCREEN_H = 1080
FONT_SIZE = 32
CHUNK     = 4096


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
    rl.draw_text(label, x + (w - tw) // 2, y + (h - (FONT_SIZE - 4)) // 2, FONT_SIZE - 4, rl.WHITE)
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

        if draw_button(bx, by_b,       BTN_W, BTN_H, "RANDOMIZE A", RAND_COLOR):
            randomize_params(params_l)
        if draw_button(bx, by_b + 60,  BTN_W, BTN_H, "RANDOMIZE B", RAND_COLOR):
            randomize_params(params_r)
        if draw_button(bx, by_b + 140, BTN_W, BTN_H, "PLAY A",      rl.Color(40,  80, 160, 255)):
            gen.start(params_l, "A")
        if draw_button(bx, by_b + 200, BTN_W, BTN_H, "PLAY B",      rl.Color(40, 130,  60, 255)):
            gen.start(params_r, "B")
        if draw_button(bx, by_b + 260, BTN_W, BTN_H, "PLAY BLEND",  rl.Color(160, 80,  20, 255)):
            gen.start(blend_params(params_l, params_r, blend_t), "BLEND")

        if gen.running:
            rl.draw_text(f"Generating {gen.label}...", bx, by_b + 330, FONT_SIZE - 4, rl.YELLOW)
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
