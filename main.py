# main.py
import threading
import os
import wave
import itertools
import glob
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
    def paste_from_clipboard():
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text
except Exception:
    def copy_to_clipboard(text):
        pass
    def paste_from_clipboard():
        return None

from params import (
    PARAM_NAMES, PARAM_RANGES, PARAM_GROUPS, NUM_PARAMS,
    param_to_t, t_to_param, param_display,
    make_params, randomize_params, blend_params,
    WAVE_NAMES,
)
from generator import generate_wave, generate_wave_blended, SAMPLE_RATE
import dialogs
import ui_components as ui
from tag_manager import estimate_tags, save_tags, find_matching_tags, generate_novel_params

SCREEN_W  = 1920
SCREEN_H  = 1080
CHUNK     = 4096


def clamp_params_to_ui(params):
    result = list(params)
    for i in range(NUM_PARAMS):
        lo, hi, _ = PARAM_RANGES[i]
        if result[i] < lo: result[i] = lo
        if result[i] > hi: result[i] = hi
    return result


def dominant_wave_type(blend_t, wt_a, wt_b):
    return wt_a if blend_t <= 0.5 else wt_b


EXPORT_DIR = "export"

def ensure_export_dir():
    if not os.path.isdir(EXPORT_DIR):
        os.makedirs(EXPORT_DIR, exist_ok=True)

def unique_export_path(base_name, ext):
    ensure_export_dir()
    pattern = os.path.join(EXPORT_DIR, f"{base_name}_*.{ext}")
    existing = glob.glob(pattern)
    max_n = 0
    prefix = f"{base_name}_"
    for f in existing:
        name = os.path.basename(f)
        num_part = name[len(prefix):].rsplit(".", 1)[0]
        if num_part.isdigit():
            n = int(num_part)
            if n > max_n:
                max_n = n
    new_num = max_n + 1
    return os.path.join(EXPORT_DIR, f"{base_name}_{new_num:04d}.{ext}")

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


def parse_scene_text(text, params_l, params_r):
    blend_t = 0.5
    name_to_idx = {n: i for i, n in enumerate(PARAM_NAMES)}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key == "blend_t":
                try:
                    blend_t = float(val)
                except ValueError:
                    pass
            elif key.startswith("A.") or key.startswith("B."):
                side = key[0]
                pname = key[2:]
                if pname in name_to_idx:
                    idx = name_to_idx[pname]
                    try:
                        target = params_l if side == "A" else params_r
                        target[idx] = float(val)
                    except ValueError:
                        pass
    return blend_t


def export_scene_bfxr(params_l, params_r, blend_t, filepath):
    with open(filepath, "w") as f:
        f.write(params_to_text(params_l, params_r, blend_t))

def export_scene_to_export(params_l, params_r, blend_t):
    fname = unique_export_path("scene", "bfxr")
    export_scene_bfxr(params_l, params_r, blend_t, fname)
    return fname

def gen_start_export_with_dialog(params, label, gen_func):
    """Export WAV using file dialog."""
    path = dialogs.get_save_wav_file(default_name=f"bfxr_{label.lower()}.wav")
    if not path:
        return None
    pcm = np.array(gen_func(params), dtype=np.float32)
    maxv = np.max(np.abs(pcm)) if len(pcm) > 0 else 0.0
    if maxv > 0.0:
        pcm = pcm / maxv
    pcm_int16 = (pcm * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_int16.tobytes())
    return os.path.basename(path)


def load_scene_bfxr(filepath, params_l, params_r):
    with open(filepath, "r") as f:
        text = f.read()
    return parse_scene_text(text, params_l, params_r)


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


# ── Export status ──────────────────────────────────────────────────────────────

_export_gen = None
_export_label = ""
_export_fn = None
_export_done_msg = None
_export_done_time = 0.0

def gen_start_export(params, label, gen_fn):
    global _export_gen, _export_label, _export_fn, _export_done_msg
    if _export_gen is not None and _export_gen.is_alive():
        return
    _export_done_msg = None
    _export_label = label
    _export_fn = gen_fn
    _export_gen = threading.Thread(target=_do_export, args=(list(params),), daemon=True)
    _export_gen.start()

def gen_start_export_blend(params_l, params_r, blend_t):
    global _export_gen, _export_label, _export_fn, _export_done_msg
    if _export_gen is not None and _export_gen.is_alive():
        return
    _export_done_msg = None
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
    global _export_gen, _export_label, _export_done_msg, _export_done_time
    import time
    t0 = time.time()
    pcm = _export_fn(params)
    fname = unique_export_path(f"bfxr_{_export_label.lower()}", "wav")
    export_wav(pcm, fname)
    dur = time.time() - t0
    n_samples = len(pcm)
    audio_dur = n_samples / SAMPLE_RATE
    _export_done_msg = f"Exported {fname}: {audio_dur:.2f}s audio, {n_samples} samples, {dur:.1f}s gen"
    _export_done_time = 5.0
    _export_gen = None

def poll_export_status():
    global _export_done_msg, _export_done_time
    if _export_done_msg and _export_done_time > 0:
        msg = _export_done_msg
        _export_done_time -= 1.0 / 60.0
        if _export_done_time <= 0:
            _export_done_msg = None
        return msg
    return None


# ── JIT warmup ─────────────────────────────────────────────────────────────────

_warmup_thread = None
_warmup_done = False

def start_warmup(params):
    global _warmup_thread, _warmup_done
    _warmup_done = False
    p = list(params)
    def _run():
        global _warmup_done
        _ = generate_wave(p)
        _warmup_done = True
    _warmup_thread = threading.Thread(target=_run, daemon=True)
    _warmup_thread.start()


# ── Main ───────────────────────────────────────────────────────────────────────

def gen_btn_size(label, min_w=100, min_h=40, pad_x=24, pad_y=14, fs=None):
    if fs is None:
        fs = ui.FONT_SIZE - 8
    tw = ui.measure_text_f(label, fs)
    th = fs
    return max(tw + pad_x, min_w), max(th + pad_y, min_h)


def compute_layout(sw, sh):
    PANEL_W  = max(sw // 3 - 10, 300)
    PANEL_H  = sh - 60
    PANEL_Y  = 30
    LEFT_X   = 10
    RIGHT_X  = sw - PANEL_W - 10
    CENTER_X = LEFT_X + PANEL_W + 10
    CENTER_W = max(RIGHT_X - CENTER_X - 10, 200)
    return PANEL_W, PANEL_H, PANEL_Y, LEFT_X, RIGHT_X, CENTER_X, CENTER_W


def main():
    global _font

    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_RESIZABLE)
    rl.init_window(SCREEN_W, SCREEN_H, "bfxr Port")
    rl.set_audio_stream_buffer_size_default(CHUNK)
    rl.init_audio_device()
    rl.set_target_fps(60)

    try:
        _font = rl.load_font_ex("Cadman_Bold.otf", ui.FONT_SIZE * 2, rl.ffi.NULL, 0)
        rl.set_texture_filter(_font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
        ui._font = _font
    except Exception:
        _font = None
        ui._font = None

    params_l = make_params()
    params_r = make_params()
    params_r[6] = 0.5

    blend_t        = 0.5
    blend_dragging = False
    player         = Player()
    gen            = GenJob()
    play_on_gen    = False
    global_volume  = 1.0

    start_warmup(params_l)

    # ensure export directory exists on startup
    ensure_export_dir()

    COLOR_A    = rl.Color(40,  80, 160, 255)
    COLOR_B    = rl.Color(40, 130,  60, 255)
    COLOR_RAND = rl.Color(120, 60, 160, 255)
    COLOR_COPY = rl.Color(80,  80,  80, 255)
    COLOR_XFER = rl.Color(160, 80,  20, 255)
    COLOR_BLEND= rl.Color(180, 130,  20, 255)
    COLOR_EXPORT = rl.Color(100, 100, 160, 255)
    COLOR_CLIP   = rl.Color(80, 120, 80, 255)
    COLOR_TAG    = rl.Color(80, 120, 160, 255)

    # Text editors for parameter tags
    tag_editor_a = ui.TextEditor()
    tag_editor_b = ui.TextEditor()
    tag_editor_blend = ui.TextEditor()
    tag_editor_a.set_text("")
    tag_editor_b.set_text("")
    tag_editor_blend.set_text("")

    COL1_LABELS = ["PLAY A", "A< BLEND", "A< RND", "A< B", "NOVEL A", "EXPORT A", "COPY A"]
    COL3_LABELS = ["PLAY B", "BLEND >B", "RND >B", "A >B", "EXPORT B", "COPY B"]
    COL2_LABELS = ["EXPORT BLEND"]
    SCENE_BTN_LABELS = ["SAVE SCENE (.bfxr)", "LOAD SCENE", "COPY SCENE", "PASTE SCENE"]

    UNIFIED_BTN_W = 180
    UNIFIED_BTN_H = 44

    status_msg = ""
    status_msg_timer = 0.0
    frame_count = 0

    while not rl.window_should_close():
        dt = rl.get_frame_time()
        frame_count += 1
        sw = rl.get_screen_width()
        sh = rl.get_screen_height()

        if status_msg_timer > 0:
            status_msg_timer -= dt
            if status_msg_timer <= 0:
                status_msg = ""

        export_msg = poll_export_status()
        if export_msg:
            status_msg = export_msg
            status_msg_timer = export_msg and 5.0 or 0

        player.update()

        pcm = gen.poll()
        if pcm is not None and play_on_gen:
            player.play(pcm)

        PANEL_W, PANEL_H, PANEL_Y, LEFT_X, RIGHT_X, CENTER_X, CENTER_W = compute_layout(sw, sh)

        BTN_GAP = 8
        cx = CENTER_X
        cw = CENTER_W

        col1_x = cx + 4
        col3_x = cx + cw - UNIFIED_BTN_W - 4
        col2_x = col1_x + UNIFIED_BTN_W + 12

        CTRL_H    = 32
        ctrl_y    = PANEL_Y + 10
        vol_y     = ctrl_y + CTRL_H + 6
        status_y  = vol_y + CTRL_H + 6

        BTN_START = status_y + CTRL_H + 10

        def layout_col_unified(labels, start_x, start_y, gap, w=UNIFIED_BTN_W, h=UNIFIED_BTN_H):
            rows = []
            cy = start_y
            for label in labels:
                rows.append((label, start_x, cy, w, h))
                cy += h + gap
            return rows, cy - gap

        col1_rows, col1_end = layout_col_unified(COL1_LABELS, col1_x, BTN_START, BTN_GAP)
        col3_rows, col3_end = layout_col_unified(COL3_LABELS, col3_x, BTN_START, BTN_GAP)

        # blend slider: 1/3 of screen height, PLAY BLEND above slider
        play_blend_y = BTN_START
        blend_slider_y1 = play_blend_y + UNIFIED_BTN_H + BTN_GAP
        blend_h = max(int(sh * 1.0 / 3.0), 120)
        col2_rows, col2_end = layout_col_unified(COL2_LABELS, col2_x, blend_slider_y1 + blend_h + BTN_GAP, BTN_GAP)

        # Scene buttons in 2x2 grid below blend slider
        scene_grid_y = blend_slider_y1 + blend_h + BTN_GAP
        gx = col2_x
        gy = scene_grid_y
        gw = UNIFIED_BTN_W
        gh = UNIFIED_BTN_H
        gap = BTN_GAP
        # 2x2 grid positions
        scene_positions = [
            (gx,           gy,           gw, gh, "SAVE SCENE (.bfxr)"),
            (gx + gw + gap, gy,           gw, gh, "LOAD SCENE"),
            (gx,           gy + gh + gap, gw, gh, "COPY SCENE"),
            (gx + gw + gap, gy + gh + gap, gw, gh, "PASTE SCENE"),
        ]

        mx = rl.get_mouse_x()
        my = rl.get_mouse_y()

        rl.begin_drawing()
        rl.clear_background(rl.Color(240, 240, 240, 255))

        sx_l, sw_l, by_l, rh_l = ui.draw_panel(LEFT_X,  PANEL_Y, PANEL_W, PANEL_H, params_l, "PRESET A")
        sx_r, sw_r, by_r, rh_r = ui.draw_panel(RIGHT_X, PANEL_Y, PANEL_W, PANEL_H, params_r, "PRESET B")

        rel_l = ui.handle_slider_input(mx, my, sx_l, sw_l, by_l, rh_l, params_l)
        rel_r = ui.handle_slider_input(mx, my, sx_r, sw_r, by_r, rh_r, params_r)

        if play_on_gen:
            if rel_l: gen.start(params_l, "A")
            if rel_r: gen.start(params_r, "B")

        # ── Top controls ──
        top_w = cw
        play_on_gen   = ui.checkbox(cx, ctrl_y, 26, "Play on Change", play_on_gen)
        global_volume = ui.hslider(cx, vol_y, top_w, 10, global_volume, "Vol")
        player.set_volume(global_volume)

        if not _warmup_done:
            ui.draw_text_f("Warming up audio engine...", cx, status_y, ui.SLIDER_FONT_SIZE, rl.Color(0, 120, 200, 255))
        elif gen.running:
            ui.draw_text_f(f"Generating {gen.label}...", cx, status_y, ui.SLIDER_FONT_SIZE, rl.Color(180, 140, 0, 255))
        elif player.playing:
            ui.draw_text_f("PLAYING...", cx, status_y, ui.SLIDER_FONT_SIZE, rl.Color(40, 130, 60, 255))
        elif status_msg:
            ui.draw_text_f(status_msg, cx, status_y, ui.SLIDER_FONT_SIZE, rl.Color(40, 100, 180, 255))
        else:
            ui.draw_text_f("---", cx, status_y, ui.SLIDER_FONT_SIZE, rl.GRAY)

        # ── Column 1: A buttons ──
        cy = BTN_START
        for label, bx, by, bw, bh in col1_rows:
            if label == "PLAY A":
                if ui.button(bx, cy, bw, bh, label, COLOR_A):
                    gen.start(params_l, "A")
            elif label == "A< BLEND":
                if ui.button(bx, cy, bw, bh, label, COLOR_XFER):
                    blended = clamp_params_to_ui(blend_params(params_l, params_r, blend_t))
                    wt_dom  = dominant_wave_type(blend_t, params_l[0], params_r[0])
                    blended[0] = wt_dom
                    for i in range(NUM_PARAMS): params_l[i] = blended[i]
                    if play_on_gen: gen.start(params_l, "A")
            elif label == "A< RND":
                if ui.button(bx, cy, bw, bh, label, COLOR_RAND):
                    randomize_params(params_l)
                    if play_on_gen: gen.start(params_l, "A")
            elif label == "A< B":
                if ui.button(bx, cy, bw, bh, label, COLOR_COPY):
                    for i in range(NUM_PARAMS): params_l[i] = params_r[i]
                    if play_on_gen: gen.start(params_l, "A")
            elif label == "NOVEL A":
                if ui.button(bx, cy, bw, bh, label, COLOR_RAND):
                    novel = generate_novel_params()
                    for i in range(NUM_PARAMS): params_l[i] = novel[i]
                    status_msg = "Generated novel params for A"
                    status_msg_timer = 2.0
                    if play_on_gen: gen.start(params_l, "A")
            elif label == "EXPORT A":
                if ui.button(bx, cy, bw, bh, label, COLOR_EXPORT):
                    p = list(params_l)
                    result = gen_start_export_with_dialog(p, "A", lambda p: generate_wave(p))
                    if result:
                        status_msg = f"Exported {result}"
                        status_msg_timer = 2.0
                    else:
                        status_msg = "Export cancelled"
                        status_msg_timer = 2.0
            elif label == "COPY A":
                if ui.button(bx, cy, bw, bh, label, COLOR_CLIP):
                    text = params_to_text(params_l, params_l, 0.0)
                    copy_to_clipboard(text)
                    status_msg = "Copied Preset A to clipboard"
                    status_msg_timer = 2.0
            cy += bh + BTN_GAP

        # ── Column 2: PLAY BLEND above slider, then slider, then other buttons ──
        play_blend_pressed = ui.button(col2_x, play_blend_y, UNIFIED_BTN_W, UNIFIED_BTN_H, "PLAY BLEND", COLOR_BLEND)
        if play_blend_pressed:
            blended_p = blend_params(params_l, params_r, blend_t)
            gen.start_blended(blended_p, params_l[0], params_r[0], blend_t, "BLEND")

        blend_t, blend_released = ui.blend_slider(col2_x, blend_slider_y1, UNIFIED_BTN_W, blend_h, blend_t)

        # Draw scene buttons in 2x2 grid
        for bx, by, bw, bh, label in scene_positions:
            if label == "SAVE SCENE (.bfxr)":
                if ui.button(bx, by, bw, bh, label, COLOR_CLIP):
                    path = dialogs.get_save_scene_file()
                    if path:
                        text = params_to_text(params_l, params_r, blend_t)
                        with open(path, "w") as f:
                            f.write(text)
                        status_msg = f"Saved {os.path.basename(path)}"
                        status_msg_timer = 2.0
                    else:
                        status_msg = "Save cancelled"
                        status_msg_timer = 2.0
            elif label == "LOAD SCENE":
                if ui.button(bx, by, bw, bh, label, COLOR_CLIP):
                    path = dialogs.get_load_scene_file()
                    if path:
                        with open(path, "r") as f:
                            text = f.read()
                        bt = parse_scene_text(text, params_l, params_r)
                        blend_t = bt
                        status_msg = f"Loaded {os.path.basename(path)}"
                        status_msg_timer = 2.0
                    else:
                        status_msg = "Load cancelled"
                        status_msg_timer = 2.0
            elif label == "COPY SCENE":
                if ui.button(bx, by, bw, bh, label, COLOR_CLIP):
                    text = params_to_text(params_l, params_r, blend_t)
                    copy_to_clipboard(text)
                    status_msg = "Copied scene to clipboard"
                    status_msg_timer = 2.0
            elif label == "PASTE SCENE":
                if ui.button(bx, by, bw, bh, label, COLOR_CLIP):
                    clip = paste_from_clipboard()
                    if clip:
                        bt = parse_scene_text(clip, params_l, params_r)
                        blend_t = bt
                        status_msg = "Pasted scene from clipboard"
                        status_msg_timer = 2.0
                    else:
                        status_msg = "Clipboard empty or unavailable"
                        status_msg_timer = 2.0

        # Also handle blend_released for play_on_gen
        if blend_released and play_on_gen:
            blended_p = blend_params(params_l, params_r, blend_t)
            gen.start_blended(blended_p, params_l[0], params_r[0], blend_t, "BLEND")

        # ── Column 3: B buttons ──
        cy = BTN_START
        for label, bx, by, bw, bh in col3_rows:
            if label == "PLAY B":
                if ui.button(bx, cy, bw, bh, label, COLOR_B):
                    gen.start(params_r, "B")
            elif label == "BLEND >B":
                if ui.button(bx, cy, bw, bh, label, COLOR_XFER):
                    blended = clamp_params_to_ui(blend_params(params_l, params_r, blend_t))
                    wt_dom  = dominant_wave_type(blend_t, params_l[0], params_r[0])
                    blended[0] = wt_dom
                    for i in range(NUM_PARAMS): params_r[i] = blended[i]
                    if play_on_gen: gen.start(params_r, "B")
            elif label == "RND >B":
                if ui.button(bx, cy, bw, bh, label, COLOR_RAND):
                    randomize_params(params_r)
                    if play_on_gen: gen.start(params_r, "B")
            elif label == "A >B":
                if ui.button(bx, cy, bw, bh, label, COLOR_COPY):
                    for i in range(NUM_PARAMS): params_r[i] = params_l[i]
                    if play_on_gen: gen.start(params_r, "B")
            elif label == "EXPORT B":
                if ui.button(bx, cy, bw, bh, label, COLOR_EXPORT):
                    p = list(params_r)
                    gen_start_export(p, "B", lambda p: generate_wave(p))
            elif label == "COPY B":
                if ui.button(bx, cy, bw, bh, label, COLOR_CLIP):
                    text = params_to_text(params_r, params_r, 1.0)
                    copy_to_clipboard(text)
                    status_msg = "Copied Preset B to clipboard"
                    status_msg_timer = 2.0
            cy += bh + BTN_GAP

        # ── Bottom: Tag editors (below scene buttons) ──
        # Calculate position below scene buttons
        scene_bottom = gy + 2 * gh + BTN_GAP  # 2 rows of scene buttons + gap between them
        tag_y = scene_bottom + 20  # 20px gap after scene buttons
        tag_w = 260
        tag_h = 120  # 4 lines
        tag_gap = 20
        bottom_center_x = sw // 2

        # Line 1: A and B side by side
        line1_y = tag_y
        line1_w = tag_w * 2 + tag_gap
        start_x = (sw - line1_w) // 2

        ui.draw_text_f("A Tags:", start_x, line1_y - 20, ui.SLIDER_FONT_SIZE, rl.DARKGRAY)
        ui.draw_text_f("B Tags:", start_x + tag_w + tag_gap, line1_y - 20, ui.SLIDER_FONT_SIZE, rl.DARKGRAY)

        tag_editor_a.update()
        tag_editor_a.draw(start_x, line1_y, tag_w, tag_h, dark=False)
        tag_editor_b.update()
        tag_editor_b.draw(start_x + tag_w + tag_gap, line1_y, tag_w, tag_h, dark=False)

        # Bigger buttons below A
        btn_y = line1_y + tag_h + 4
        btn_w = tag_w // 2 - 4
        btn_h = 26

        if ui.button(start_x, btn_y, btn_w, btn_h, "Save A", COLOR_TAG):
            tag_a = tag_editor_a.get_text().strip()
            save_tags("A", params_l, tag_a)
            status_msg = "Saved A tags: " + tag_a
            status_msg_timer = 2.0
        if ui.button(start_x + btn_w + 8, btn_y, btn_w, btn_h, "Est A", COLOR_TAG):
            matches = find_matching_tags(params_l, params_l[0])
            if matches:
                best_tags, best_score = matches[0]
                tag_editor_a.set_text(best_tags)
                status_msg = f"Est A (match: {best_score:.0%}): {best_tags}"
            else:
                status_msg = "No matches in database"
            status_msg_timer = 3.0

        # Bigger buttons below B
        if ui.button(start_x + tag_w + tag_gap, btn_y, btn_w, btn_h, "Save B", COLOR_TAG):
            tag_b = tag_editor_b.get_text().strip()
            save_tags("B", params_r, tag_b)
            status_msg = "Saved B tags: " + tag_b
            status_msg_timer = 2.0
        if ui.button(start_x + tag_w + tag_gap + btn_w + 8, btn_y, btn_w, btn_h, "Est B", COLOR_TAG):
            matches = find_matching_tags(params_r, params_r[0])
            if matches:
                best_tags, best_score = matches[0]
                tag_editor_b.set_text(best_tags)
                status_msg = f"Est B (match: {best_score:.0%}): {best_tags}"
            else:
                status_msg = "No matches in database"
            status_msg_timer = 3.0

        # Line 2: Blend centered below
        line2_y = btn_y + btn_h + 20
        blend_x = bottom_center_x - tag_w // 2

        ui.draw_text_f("Blend Tags:", blend_x, line2_y - 20, ui.SLIDER_FONT_SIZE, rl.DARKGRAY)
        tag_editor_blend.update()
        tag_editor_blend.draw(blend_x, line2_y, tag_w, tag_h, dark=False)

        btn_y2 = line2_y + tag_h + 4
        if ui.button(blend_x, btn_y2, btn_w, btn_h, "Save Bl", COLOR_TAG):
            tag_bl = tag_editor_blend.get_text().strip()
            save_tags("BLEND", blend_params(params_l, params_r, blend_t), tag_bl, blend_t)
            status_msg = "Saved Blend tags: " + tag_bl
            status_msg_timer = 2.0
        if ui.button(blend_x + btn_w + 8, btn_y2, btn_w, btn_h, "Est Bl", COLOR_TAG):
            blended = blend_params(params_l, params_r, blend_t)
            dom_wt = params_l[0] if blend_t <= 0.5 else params_r[0]
            matches = find_matching_tags(blended, dom_wt)
            if matches:
                best_tags, best_score = matches[0]
                tag_editor_blend.set_text(best_tags)
                status_msg = f"Est Bl (match: {best_score:.0%}): {best_tags}"
            else:
                status_msg = "No matches in database"
            status_msg_timer = 3.0

        rl.end_drawing()

    player._stop()
    rl.close_audio_device()
    rl.close_window()


if __name__ == "__main__":
    main()
