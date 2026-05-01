import pyray as rl
from params import PARAM_NAMES, PARAM_RANGES, PARAM_GROUPS, NUM_PARAMS, param_to_t, t_to_param, param_display

FONT_SIZE = 32
SLIDER_FONT_SIZE = FONT_SIZE - 6

_font = None

def get_font():
    global _font
    if _font is None:
        _font = rl.get_font_default()
    return _font

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

    max_lbl_w = max([measure_text_f(PARAM_NAMES[i], lbl_font) for i in range(NUM_PARAMS)])
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


def button(x, y, w, h, label, color):
    mx, my  = rl.get_mouse_x(), rl.get_mouse_y()
    hovered = x <= mx <= x + w and y <= my <= y + h
    col     = rl.color_brightness(color, 0.3) if hovered else color
    rl.draw_rectangle(x, y, w, h, col)
    rl.draw_rectangle_lines(x, y, w, h, rl.DARKGRAY)
    fs = FONT_SIZE - 2
    tw = measure_text_f(label, fs)
    draw_text_f(label, x + (w - tw) // 2, y + (h - fs) // 2, fs, rl.RAYWHITE)
    return hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT)


def checkbox(x, y, size, label, checked):
    mx, my = rl.get_mouse_x(), rl.get_mouse_y()
    hovered = x <= mx <= x + size and y <= my <= y + size
    rl.draw_rectangle_lines(x, y, size, size, rl.DARKGRAY)
    if checked:
        rl.draw_rectangle(x + 4, y + 4, size - 8, size - 8, rl.Color(200, 120, 30, 255))
    draw_text_f(label, x + size + 8, y + (size - SLIDER_FONT_SIZE) // 2, SLIDER_FONT_SIZE, rl.DARKGRAY)
    if hovered and rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return not checked
    return checked


def hslider(x, y, w, h, val, label):
    mx, my = rl.get_mouse_x(), rl.get_mouse_y()
    lw     = measure_text_f(label, SLIDER_FONT_SIZE)
    sx     = x + lw + 8
    sw     = max(w - lw - 60, 40)
    bar_y  = y + SLIDER_FONT_SIZE // 2
    draw_text_f(label, x, y, SLIDER_FONT_SIZE, rl.DARKGRAY)
    filled = int(val * sw)
    rl.draw_rectangle(sx, bar_y, sw, h, rl.Color(200, 200, 200, 255))
    rl.draw_rectangle(sx, bar_y, filled, h, rl.Color(200, 160, 40, 255))
    knob_w = 6
    rl.draw_rectangle(sx + filled - knob_w // 2, bar_y - 4, knob_w, h + 8, rl.BLACK)
    draw_text_f("%.2f" % val, sx + sw + 6, bar_y, SLIDER_FONT_SIZE - 4, rl.DARKGRAY)
    if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
        if abs(my - (bar_y + h // 2)) < 20 and sx <= mx <= sx + sw:
            val = (mx - sx) / sw
            if val < 0.0: val = 0.0
            if val > 1.0: val = 1.0
    return val


def blend_slider(x, y, w, h, blend_t):
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
    draw_text_f("%.2f" % blend_t, bar_x + bar_w + 6, knob_py - lbl_fs // 2, FONT_SIZE - 12, rl.DARKGRAY)

    touching = abs(mx - (bar_x + bar_w // 2)) < 24 and y <= my <= y + total_h
    if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT) and touching:
        blend_t = (my - y) / total_h * 3.0 - 1.0
        if blend_t < -1.0: blend_t = -1.0
        if blend_t >  2.0: blend_t =  2.0

    released = touching and rl.is_mouse_button_released(rl.MouseButton.MOUSE_BUTTON_LEFT)
    return blend_t, released


class TextEditor:
    def __init__(self):
        self.lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.scroll_y = 0
        self.active = False
        self._tick = 0

    def draw(self, x, y, w, h, font_size=None):
        if font_size is None:
            font_size = SLIDER_FONT_SIZE

        self._tick += 1
        mx, my = rl.get_mouse_x(), rl.get_mouse_y()

        rl.draw_rectangle(x, y, w, h, rl.Color(40, 40, 40, 255))
        rl.draw_rectangle_lines(x, y, w, h, rl.LIGHTGRAY)

        line_h = font_size + 4
        max_lines = max(1, h // line_h)

        self.cursor_line = max(0, min(self.cursor_line, len(self.lines) - 1))
        self.cursor_col = max(0, min(self.cursor_col, len(self.lines[self.cursor_line])))

        if self.cursor_line < self.scroll_y:
            self.scroll_y = self.cursor_line
        elif self.cursor_line >= self.scroll_y + max_lines:
            self.scroll_y = self.cursor_line - max_lines + 1

        for i in range(self.scroll_y, min(len(self.lines), self.scroll_y + max_lines)):
            line_y = y + 4 + (i - self.scroll_y) * line_h
            text = self.lines[i]
            is_active = (i == self.cursor_line and self.active)

            if is_active:
                cursor_x = x + 4 + measure_text_f(text[:self.cursor_col], font_size)
                rl.draw_rectangle(x + 4, int(line_y), int(w - 8), int(line_h - 2), rl.Color(60, 60, 100, 255))
                if (self._tick // 20) % 2 == 0:
                    rl.draw_rectangle(int(cursor_x), int(line_y + 2), 2, int(font_size), rl.RAYWHITE)

            draw_text_f(text, x + 4, int(line_y), font_size, rl.RAYWHITE)

        if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
            if x <= mx <= x + w and y <= my <= y + h:
                self.active = True
                rel_y = my - y - 4
                clicked_line = self.scroll_y + rel_y // line_h
                if 0 <= clicked_line < len(self.lines):
                    self.cursor_line = clicked_line
                    line_text = self.lines[self.cursor_line]
                    rel_x = mx - x - 4
                    best_col = 0
                    best_dist = 9999
                    for c in range(len(line_text) + 1):
                        cx = measure_text_f(line_text[:c], font_size)
                        if abs(cx - rel_x) < best_dist:
                            best_dist = abs(cx - rel_x)
                            best_col = c
                    self.cursor_col = best_col
            else:
                self.active = False

    def update(self):
        if not self.active:
            return

        if rl.is_key_pressed(rl.KeyboardKey.KEY_RIGHT):
            self._move_right()
        elif rl.is_key_down(rl.KeyboardKey.KEY_RIGHT) and self._tick % 4 == 0:
            self._move_right()
        elif rl.is_key_pressed(rl.KeyboardKey.KEY_LEFT):
            self._move_left()
        elif rl.is_key_down(rl.KeyboardKey.KEY_LEFT) and self._tick % 4 == 0:
            self._move_left()
        elif rl.is_key_pressed(rl.KeyboardKey.KEY_UP):
            self._move_up()
        elif rl.is_key_down(rl.KeyboardKey.KEY_UP) and self._tick % 4 == 0:
            self._move_up()
        elif rl.is_key_pressed(rl.KeyboardKey.KEY_DOWN):
            self._move_down()
        elif rl.is_key_down(rl.KeyboardKey.KEY_DOWN) and self._tick % 4 == 0:
            self._move_down()
        elif rl.is_key_pressed(rl.KeyboardKey.KEY_BACKSPACE):
            self._backspace()
        elif rl.is_key_down(rl.KeyboardKey.KEY_BACKSPACE) and self._tick % 4 == 0:
            self._backspace()
        elif rl.is_key_pressed(rl.KeyboardKey.KEY_DELETE):
            self._delete()
        elif rl.is_key_down(rl.KeyboardKey.KEY_DELETE) and self._tick % 4 == 0:
            self._delete()

        if rl.is_key_pressed(rl.KeyboardKey.KEY_ENTER):
            self._insert_newline()
        elif rl.is_key_pressed(rl.KeyboardKey.KEY_TAB):
            self._insert_text("    ")

        char = rl.get_char_pressed()
        while char != 0:
            if 32 <= char < 127:
                self._insert_char(chr(char))
            char = rl.get_char_pressed()

    def _insert_char(self, ch):
        line = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = line[:self.cursor_col] + ch + line[self.cursor_col:]
        self.cursor_col += 1

    def _insert_text(self, text):
        for ch in text:
            self._insert_char(ch)

    def _insert_newline(self):
        line = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = line[:self.cursor_col]
        self.lines.insert(self.cursor_line + 1, line[self.cursor_col:])
        self.cursor_line += 1
        self.cursor_col = 0

    def _move_right(self):
        line = self.lines[self.cursor_line]
        if self.cursor_col < len(line):
            self.cursor_col += 1
        elif self.cursor_line < len(self.lines) - 1:
            self.cursor_line += 1
            self.cursor_col = 0

    def _move_left(self):
        if self.cursor_col > 0:
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = len(self.lines[self.cursor_line])

    def _move_up(self):
        if self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))

    def _move_down(self):
        if self.cursor_line < len(self.lines) - 1:
            self.cursor_line += 1
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))

    def _backspace(self):
        if self.cursor_col > 0:
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col-1] + line[self.cursor_col:]
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            prev_line = self.lines[self.cursor_line - 1]
            cur_line = self.lines[self.cursor_line]
            self.cursor_col = len(prev_line)
            self.lines[self.cursor_line - 1] = prev_line + cur_line
            self.lines.pop(self.cursor_line)
            self.cursor_line -= 1

    def _delete(self):
        line = self.lines[self.cursor_line]
        if self.cursor_col < len(line):
            self.lines[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col+1:]
        elif self.cursor_line < len(self.lines) - 1:
            next_line = self.lines[self.cursor_line + 1]
            self.lines[self.cursor_line] = line + next_line
            self.lines.pop(self.cursor_line + 1)

    def get_text(self):
        return "\n".join(self.lines)

    def set_text(self, text):
        self.lines = text.split("\n") if text else [""]
        self.cursor_line = 0
        self.cursor_col = 0
