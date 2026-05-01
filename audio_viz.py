import numpy as np
import pyray as rl

def draw_waveform(wave, x, y, w, h):
    """Draw waveform using line rendering. wave is float32 normalized -1..1"""
    if wave is None or len(wave) == 0:
        return

    n = len(wave)
    step = max(1, n // w)

    rl.draw_rectangle(x, y, w, h, rl.RAYWHITE)
    rl.draw_rectangle_lines(x, y, w, h, rl.LIGHTGRAY)

    cy = y + h // 2
    prev_x = x
    prev_y = cy

    for i in range(0, n, step):
        px = x + int((i / n) * w)
        py = cy - int(wave[i] * (h // 2 - 2))
        if i > 0:
            rl.draw_line(prev_x, prev_y, px, py, rl.BLACK)
        prev_x, prev_y = px, py
