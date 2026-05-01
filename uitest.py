"""
imgui_raylib.py — Experimental ImGui-style UI with dynamic layouts in pyray/raylib.

Architecture:
  - UIContext   : per-frame state (mouse, hot/active ids, draw calls)
  - Components  : stateless functions that read UIContext and emit draw calls
  - Layout      : Panel tree that resolves rects at render time, scales with window
  - App         : wires everything together
"""

import pyray as rl
from dataclasses import dataclass, field
from typing import Callable, Optional
import textwrap

# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
@dataclass
class Theme:
    bg:          rl.Color = field(default_factory=lambda: rl.Color(22, 22, 30, 255))
    panel_bg:    rl.Color = field(default_factory=lambda: rl.Color(32, 32, 44, 255))
    panel_border:rl.Color = field(default_factory=lambda: rl.Color(60, 60, 80, 255))

    btn_idle:    rl.Color = field(default_factory=lambda: rl.Color(55, 55, 75, 255))
    btn_hover:   rl.Color = field(default_factory=lambda: rl.Color(80, 80, 110, 255))
    btn_active:  rl.Color = field(default_factory=lambda: rl.Color(110, 90, 200, 255))
    btn_text:    rl.Color = field(default_factory=lambda: rl.Color(220, 220, 235, 255))

    slider_bg:   rl.Color = field(default_factory=lambda: rl.Color(40, 40, 58, 255))
    slider_fill: rl.Color = field(default_factory=lambda: rl.Color(110, 90, 200, 255))
    slider_grab: rl.Color = field(default_factory=lambda: rl.Color(180, 160, 255, 255))

    text_fg:     rl.Color = field(default_factory=lambda: rl.Color(210, 210, 230, 255))
    text_dim:    rl.Color = field(default_factory=lambda: rl.Color(130, 130, 160, 255))
    text_cursor: rl.Color = field(default_factory=lambda: rl.Color(180, 160, 255, 255))
    editor_bg:   rl.Color = field(default_factory=lambda: rl.Color(18, 18, 26, 255))
    editor_border_active: rl.Color = field(default_factory=lambda: rl.Color(110, 90, 200, 255))
    editor_border_idle:   rl.Color = field(default_factory=lambda: rl.Color(55, 55, 75, 255))

    font_size:   int = 16
    pad:         int = 8
    rounding:    float = 4.0

THEME = Theme()

# ─────────────────────────────────────────────
#  UI CONTEXT  (per-frame immediate-mode state)
# ─────────────────────────────────────────────
class UIContext:
    def __init__(self):
        self.hot_id: Optional[str] = None      # hovered this frame
        self.active_id: Optional[str] = None   # mouse-down on this
        self.focus_id: Optional[str] = None    # keyboard focus

        # Mouse
        self.mx: int = 0
        self.my: int = 0
        self.mouse_down: bool = False
        self.mouse_pressed: bool = False
        self.mouse_released: bool = False

        # Keyboard chars typed this frame (for text editor)
        self.chars: list[int] = []
        self.key_pressed: list[int] = []

    def update(self):
        mp = rl.get_mouse_position()
        self.mx, self.my = int(mp.x), int(mp.y)
        self.mouse_down     = rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT)
        self.mouse_pressed  = rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT)
        self.mouse_released = rl.is_mouse_button_released(rl.MouseButton.MOUSE_BUTTON_LEFT)

        self.chars = []
        while True:
            c = rl.get_char_pressed()
            if c == 0:
                break
            self.chars.append(c)

        self.key_pressed = []
        WATCHED = [
            rl.KeyboardKey.KEY_BACKSPACE, rl.KeyboardKey.KEY_ENTER,
            rl.KeyboardKey.KEY_LEFT, rl.KeyboardKey.KEY_RIGHT,
            rl.KeyboardKey.KEY_UP, rl.KeyboardKey.KEY_DOWN,
            rl.KeyboardKey.KEY_HOME, rl.KeyboardKey.KEY_END,
            rl.KeyboardKey.KEY_DELETE, rl.KeyboardKey.KEY_TAB,
        ]
        for k in WATCHED:
            if rl.is_key_pressed(k) or rl.is_key_pressed_repeat(k):
                self.key_pressed.append(k)

    def hovering(self, x, y, w, h) -> bool:
        return x <= self.mx < x + w and y <= self.my < y + h

CTX = UIContext()

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def draw_rect_rounded(x, y, w, h, color, radius=THEME.rounding):
    rec = rl.Rectangle(x, y, w, h)
    rl.draw_rectangle_rounded(rec, radius / max(w, h, 1), 6, color)

def draw_rect_rounded_lines(x, y, w, h, color, thick=1.0, radius=THEME.rounding):
    rec = rl.Rectangle(x, y, w, h)
    rl.draw_rectangle_rounded_lines_ex(rec, radius / max(w, h, 1), 6, thick, color)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ─────────────────────────────────────────────
#  COMPONENTS  (stateless imgui-style)
# ─────────────────────────────────────────────

def button(uid: str, label: str, x: int, y: int, w: int, h: int) -> bool:
    """Returns True on click."""
    hovered = CTX.hovering(x, y, w, h)
    if hovered:
        CTX.hot_id = uid
    if CTX.mouse_pressed and hovered:
        CTX.active_id = uid
    clicked = CTX.mouse_released and CTX.active_id == uid and hovered

    if CTX.active_id == uid:
        col = THEME.btn_active
    elif CTX.hot_id == uid:
        col = THEME.btn_hover
    else:
        col = THEME.btn_idle

    draw_rect_rounded(x, y, w, h, col)
    draw_rect_rounded_lines(x, y, w, h, THEME.panel_border, thick=1.0)

    fs = THEME.font_size
    tw = rl.measure_text(label, fs)
    tx = x + (w - tw) // 2
    ty = y + (h - fs) // 2
    rl.draw_text(label, tx, ty, fs, THEME.btn_text)

    if clicked:
        CTX.active_id = None
    return clicked


def slider(uid: str, x: int, y: int, w: int, h: int,
           value: float, lo: float = 0.0, hi: float = 1.0,
           label: str = "") -> float:
    """Returns updated float value."""
    track_y = y + h // 2 - 3
    track_h = 6
    grab_r = 8

    hovered = CTX.hovering(x, y, w, h)
    if hovered:
        CTX.hot_id = uid
    if CTX.mouse_pressed and hovered:
        CTX.active_id = uid
        CTX.focus_id = uid

    if CTX.active_id == uid:
        t = clamp((CTX.mx - x - grab_r) / max(w - grab_r * 2, 1), 0.0, 1.0)
        value = lo + t * (hi - lo)
    if CTX.mouse_released and CTX.active_id == uid:
        CTX.active_id = None

    t = clamp((value - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    fill_w = int(t * (w - grab_r * 2))
    grab_x = x + grab_r + fill_w

    # Track background
    rl.draw_rectangle(x + grab_r, track_y, w - grab_r * 2, track_h, THEME.slider_bg)
    # Fill
    if fill_w > 0:
        rl.draw_rectangle(x + grab_r, track_y, fill_w, track_h, THEME.slider_fill)
    # Grab
    grab_col = THEME.slider_grab if (CTX.active_id == uid or CTX.hot_id == uid) else THEME.slider_fill
    rl.draw_circle(grab_x, y + h // 2, grab_r, grab_col)
    rl.draw_circle_lines(grab_x, y + h // 2, grab_r, THEME.panel_border)

    # Value label
    val_str = f"{value:.2f}"
    if label:
        val_str = f"{label}: {value:.2f}"
    fs = THEME.font_size - 2
    rl.draw_text(val_str, x, y, fs, THEME.text_dim)

    return value


# ── Text Editor State (lives outside component, passed in) ──────────────────
@dataclass
class TextEditorState:
    text: str = ""
    cursor: int = 0      # byte offset in text
    scroll_line: int = 0

    def insert(self, ch: str):
        self.text = self.text[:self.cursor] + ch + self.text[self.cursor:]
        self.cursor += len(ch)

    def backspace(self):
        if self.cursor > 0:
            self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
            self.cursor -= 1

    def delete_fwd(self):
        if self.cursor < len(self.text):
            self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]

    def lines(self):
        return self.text.split("\n")

    def cursor_line_col(self):
        before = self.text[:self.cursor]
        line = before.count("\n")
        col  = len(before) - (before.rfind("\n") + 1)
        return line, col

    def move_cursor(self, delta: int):
        self.cursor = clamp(self.cursor + delta, 0, len(self.text))

    def move_to_line_start(self):
        before = self.text[:self.cursor]
        nl = before.rfind("\n")
        self.cursor = nl + 1

    def move_to_line_end(self):
        after = self.text[self.cursor:]
        nl = after.find("\n")
        self.cursor = self.cursor + (nl if nl != -1 else len(after))


def text_editor(uid: str, state: TextEditorState,
                x: int, y: int, w: int, h: int,
                placeholder: str = "Type here…") -> TextEditorState:
    """Multiline text editor. Returns (possibly mutated) state."""
    fs = THEME.font_size
    line_h = fs + 4
    pad = THEME.pad

    hovered = CTX.hovering(x, y, w, h)
    if CTX.mouse_pressed and hovered:
        CTX.focus_id = uid
    if CTX.mouse_pressed and not hovered:
        if CTX.focus_id == uid:
            CTX.focus_id = None

    focused = (CTX.focus_id == uid)
    border_col = THEME.editor_border_active if focused else THEME.editor_border_idle

    # Background
    draw_rect_rounded(x, y, w, h, THEME.editor_bg)
    draw_rect_rounded_lines(x, y, w, h, border_col, thick=1.5)

    # Clip drawing to inner area (raylib scissor)
    inner_x = x + pad
    inner_y = y + pad
    inner_w = w - pad * 2
    inner_h = h - pad * 2

    rl.begin_scissor_mode(inner_x, inner_y, inner_w, inner_h)

    lines = state.lines()
    cur_line, cur_col = state.cursor_line_col()

    # Auto-scroll so cursor is visible
    visible_lines = max(1, inner_h // line_h)
    if cur_line < state.scroll_line:
        state.scroll_line = cur_line
    elif cur_line >= state.scroll_line + visible_lines:
        state.scroll_line = cur_line - visible_lines + 1

    if state.text == "" and not focused:
        rl.draw_text(placeholder, inner_x, inner_y, fs, THEME.text_dim)
    else:
        for i, line in enumerate(lines):
            vy = inner_y + (i - state.scroll_line) * line_h
            if vy + line_h < inner_y or vy > inner_y + inner_h:
                continue
            rl.draw_text(line, inner_x, vy, fs, THEME.text_fg)

            # Draw cursor
            if focused and i == cur_line:
                cx_offset = rl.measure_text(line[:cur_col], fs)
                cx = inner_x + cx_offset
                cy = vy
                blink = (int(rl.get_time() * 2) % 2 == 0)
                if blink:
                    rl.draw_rectangle(cx, cy, 2, line_h, THEME.text_cursor)

    rl.end_scissor_mode()

    # Keyboard handling when focused
    if focused:
        K = rl.KeyboardKey
        for k in CTX.key_pressed:
            if k == K.KEY_BACKSPACE:
                state.backspace()
            elif k == K.KEY_DELETE:
                state.delete_fwd()
            elif k == K.KEY_ENTER:
                state.insert("\n")
            elif k == K.KEY_LEFT:
                state.move_cursor(-1)
            elif k == K.KEY_RIGHT:
                state.move_cursor(1)
            elif k == K.KEY_HOME:
                state.move_to_line_start()
            elif k == K.KEY_END:
                state.move_to_line_end()
            elif k == K.KEY_UP:
                ln, col = state.cursor_line_col()
                if ln > 0:
                    ls = state.lines()
                    new_line = ln - 1
                    new_col  = min(col, len(ls[new_line]))
                    state.cursor = sum(len(l) + 1 for l in ls[:new_line]) + new_col
            elif k == K.KEY_DOWN:
                ln, col = state.cursor_line_col()
                ls = state.lines()
                if ln < len(ls) - 1:
                    new_line = ln + 1
                    new_col  = min(col, len(ls[new_line]))
                    state.cursor = sum(len(l) + 1 for l in ls[:new_line]) + new_col

        for ch in CTX.chars:
            state.insert(chr(ch))

    # Status bar (line/col)
    if focused:
        ln, col = state.cursor_line_col()
        status = f"Ln {ln+1}  Col {col+1}  |  {len(lines)} lines"
        sw = rl.measure_text(status, fs - 4)
        rl.draw_text(status, x + w - sw - pad, y + h - fs, fs - 4, THEME.text_dim)

    return state


# ─────────────────────────────────────────────
#  LAYOUT ENGINE
# ─────────────────────────────────────────────

class Panel:
    """
    A node in a layout tree.
    direction: "h" (horizontal) | "v" (vertical) | "leaf"
    weights:   relative size fractions for children
    gap:       pixels between children
    padding:   inner padding
    """
    def __init__(self, direction="v", children=None, weights=None,
                 gap=6, padding=8, label="", draw_bg=True):
        self.direction = direction
        self.children: list["Panel"] = children or []
        self.weights: list[float] = weights or ([1.0] * len(children)) if children else []
        self.gap = gap
        self.padding = padding
        self.label = label
        self.draw_bg = draw_bg

        # Resolved rect (set each frame by resolve)
        self.x = self.y = self.w = self.h = 0

        # Leaf render callback: fn(x, y, w, h)
        self.render_fn: Optional[Callable] = None

    def leaf(self, fn: Callable) -> "Panel":
        self.direction = "leaf"
        self.render_fn = fn
        return self

    def resolve(self, x: int, y: int, w: int, h: int):
        """Recursively assign rects to all panels."""
        self.x, self.y, self.w, self.h = x, y, w, h

        if self.direction == "leaf" or not self.children:
            return

        inner_x = x + self.padding
        inner_y = y + self.padding + (THEME.font_size + 4 if self.label else 0)
        inner_w = w - self.padding * 2
        inner_h = h - self.padding * 2 - (THEME.font_size + 4 if self.label else 0)

        n = len(self.children)
        ws = self.weights if len(self.weights) == n else [1.0] * n
        total_w = sum(ws)
        gaps_total = self.gap * (n - 1)

        if self.direction == "h":
            avail = inner_w - gaps_total
            cursor = inner_x
            for i, child in enumerate(self.children):
                cw = int(avail * ws[i] / total_w)
                child.resolve(cursor, inner_y, cw, inner_h)
                cursor += cw + self.gap
        else:  # "v"
            avail = inner_h - gaps_total
            cursor = inner_y
            for i, child in enumerate(self.children):
                ch = int(avail * ws[i] / total_w)
                child.resolve(inner_x, cursor, inner_w, ch)
                cursor += ch + self.gap

    def draw(self):
        if self.draw_bg:
            draw_rect_rounded(self.x, self.y, self.w, self.h, THEME.panel_bg)
            draw_rect_rounded_lines(self.x, self.y, self.w, self.h, THEME.panel_border)

        if self.label:
            rl.draw_text(self.label,
                         self.x + self.padding,
                         self.y + self.padding,
                         THEME.font_size - 2,
                         THEME.text_dim)

        if self.direction == "leaf" and self.render_fn:
            self.render_fn(self.x + self.padding,
                           self.y + self.padding,
                           self.w - self.padding * 2,
                           self.h - self.padding * 2)

        for child in self.children:
            child.draw()


# ─────────────────────────────────────────────
#  APPLICATION STATE
# ─────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.slider_a: float = 0.42
        self.slider_b: float = 0.75
        self.slider_c: float = 0.20
        self.editor_main = TextEditorState(
            text="Welcome, Captain.\n\nThis is a multiline text editor.\nUse arrow keys, backspace, enter.\nAll rendered with pyray/raylib.\n\nThe layout scales with the window."
        )
        self.editor_log = TextEditorState(text="[LOG] System ready.\n")
        self.btn_clicks = 0
        self.btn_label = "Fire Engines"
        self.last_action = "—"

STATE = AppState()

# ─────────────────────────────────────────────
#  LEAF RENDER FUNCTIONS  (use STATE & CTX)
# ─────────────────────────────────────────────

def render_controls(x, y, w, h):
    pad = THEME.pad
    btn_h = 32
    slider_h = 36
    spacing = 10
    fs = THEME.font_size

    cy = y

    # Button
    lbl = f"{STATE.btn_label}  [{STATE.btn_clicks}]"
    bw = min(w, 220)
    if button("btn_main", lbl, x, cy, bw, btn_h):
        STATE.btn_clicks += 1
        STATE.last_action = f"Fired! (x{STATE.btn_clicks})"
        STATE.editor_log.text += f"[ACTION] {STATE.last_action}\n"
        STATE.editor_log.cursor = len(STATE.editor_log.text)

    cy += btn_h + spacing

    # Second button
    bw2 = min(w, 140)
    if button("btn_reset", "Reset Log", x, cy, bw2, btn_h):
        STATE.editor_log.text = "[LOG] Log cleared.\n"
        STATE.editor_log.cursor = len(STATE.editor_log.text)
        STATE.last_action = "Log cleared"

    cy += btn_h + spacing + 4

    # Sliders
    STATE.slider_a = slider("sl_a", x, cy, w, slider_h,
                             STATE.slider_a, 0.0, 1.0, "Speed")
    cy += slider_h + spacing

    STATE.slider_b = slider("sl_b", x, cy, w, slider_h,
                             STATE.slider_b, 0.0, 100.0, "Thrust")
    cy += slider_h + spacing

    STATE.slider_c = slider("sl_c", x, cy, w, slider_h,
                             STATE.slider_c, -1.0, 1.0, "Trim")
    cy += slider_h + spacing

    # Status line
    status = f"Last: {STATE.last_action}"
    rl.draw_text(status, x, cy, fs - 2, THEME.text_dim)


def render_main_editor(x, y, w, h):
    text_editor("ed_main", STATE.editor_main, x, y, w, h,
                placeholder="Main editor…")


def render_log_editor(x, y, w, h):
    text_editor("ed_log", STATE.editor_log, x, y, w, h,
                placeholder="Log output…")


def render_info(x, y, w, h):
    fs = THEME.font_size - 2
    lines = [
        "IMGUI + RAYLIB",
        f"FPS: {rl.get_fps()}",
        f"Speed:  {STATE.slider_a:.2f}",
        f"Thrust: {STATE.slider_b:.1f}",
        f"Trim:   {STATE.slider_c:+.2f}",
        "",
        "Window scales layout.",
        "Click panels to focus.",
    ]
    for i, l in enumerate(lines):
        col = THEME.text_fg if i > 0 else THEME.slider_grab
        rl.draw_text(l, x, y + i * (fs + 5), fs, col)


# ─────────────────────────────────────────────
#  BUILD LAYOUT TREE
# ─────────────────────────────────────────────

def build_layout() -> Panel:
    # Leaf panels
    controls = Panel(label="CONTROLS", draw_bg=True).leaf(render_controls)
    info     = Panel(label="STATUS",   draw_bg=True).leaf(render_info)
    main_ed  = Panel(label="EDITOR",   draw_bg=True).leaf(render_main_editor)
    log_ed   = Panel(label="LOG",      draw_bg=True).leaf(render_log_editor)

    # Left column: controls on top, info below
    left_col = Panel(direction="v",
                     children=[controls, info],
                     weights=[3.0, 1.5],
                     gap=6, padding=0, draw_bg=False)

    # Right column: main editor top, log below
    right_col = Panel(direction="v",
                      children=[main_ed, log_ed],
                      weights=[2.5, 1.0],
                      gap=6, padding=0, draw_bg=False)

    # Root: left | right
    root = Panel(direction="h",
                 children=[left_col, right_col],
                 weights=[1.0, 1.8],
                 gap=8, padding=10, draw_bg=False)
    return root


# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────

def main():
    rl.init_window(1100, 720, "imgui-raylib experiment")
    rl.set_window_state(rl.ConfigFlags.FLAG_WINDOW_RESIZABLE)
    rl.set_target_fps(60)

    layout = build_layout()

    while not rl.window_should_close():
        # Update context
        CTX.update()

        # Reset hot each frame
        CTX.hot_id = None

        # Resolve layout to current window size
        W = rl.get_screen_width()
        H = rl.get_screen_height()
        layout.resolve(0, 0, W, H)

        # Draw
        rl.begin_drawing()
        rl.clear_background(THEME.bg)

        layout.draw()

        rl.end_drawing()

    rl.close_window()


if __name__ == "__main__":
    main()