import pyray as rl
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
import sys

SAMPLE_RATE = 44100

# --- GRADIENT STOPS: (value 0..1, R, G, B) ---
GRADIENT = [
    (0.0,  0,   0,   0),
    (0.5,  255, 0,   0),
    (1.0,  255, 255, 255),
]

# Texture cache for spectrogram reuse (keyed by wave data hash)
_tex_cache = {}  # hash(wave.tobytes()) -> texture

def _wave_hash(wave):
    """Compute hash of wave data for caching"""
    return hash(wave.tobytes())

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

def compute_spectrogram_from_wave(wave, n_fft=2048, overlap=0.75):
    """Compute spectrogram from in-memory wave data (float32, -1..1)"""
    if wave is None or len(wave) == 0:
        return None

    # Ensure float32 normalized
    if wave.dtype != np.float32:
        data = wave.astype(np.float32) / 32767.0
    else:
        data = wave

    data = data / (np.max(np.abs(data)) + 1e-9)

    hop = int(n_fft * (1 - overlap))
    _, _, Zxx = stft(data, fs=SAMPLE_RATE, nperseg=n_fft, noverlap=n_fft - hop, window='hann')
    power_db = 20 * np.log10(np.abs(Zxx) + 1e-9)
    pmin, pmax = power_db.min(), power_db.max()
    return ((power_db - pmin) / (pmax - pmin + 1e-9)).astype(np.float32)

def compute_spectrogram(wav_path, n_fft=2048, overlap=0.75):
    sr, data = wavfile.read(wav_path)
    if data.ndim > 1:
        data = data[:, 0]
    data = data.astype(np.float32)
    data /= np.max(np.abs(data)) + 1e-9
    hop = int(n_fft * (1 - overlap))
    _, _, Zxx = stft(data, fs=sr, nperseg=n_fft, noverlap=n_fft - hop, window='hann')
    power_db = 20 * np.log10(np.abs(Zxx) + 1e-9)
    pmin, pmax = power_db.min(), power_db.max()
    return ((power_db - pmin) / (pmax - pmin + 1e-9)).astype(np.float32)

def apply_gradient(v):
    stops = GRADIENT
    r = np.zeros_like(v); g = np.zeros_like(v); b = np.zeros_like(v)
    for i in range(len(stops) - 1):
        t0, r0, g0, b0 = stops[i]
        t1, r1, g1, b1 = stops[i + 1]
        mask = (v >= t0) & (v <= t1)
        t = (v[mask] - t0) / (t1 - t0)
        r[mask] = r0 + t * (r1 - r0)
        g[mask] = g0 + t * (g1 - g0)
        b[mask] = b0 + t * (b1 - b0)
    return r, g, b

def power_to_rgba(power_norm):
    freq_bins, time_frames = power_norm.shape
    v = power_norm[::-1, :].astype(np.float32)
    r, g, b = apply_gradient(v)
    rgba = np.stack([
        r.astype(np.uint8),
        g.astype(np.uint8),
        b.astype(np.uint8),
        np.full((freq_bins, time_frames), 255, dtype=np.uint8)
    ], axis=-1)
    return np.ascontiguousarray(rgba)

def build_texture(rgba):
    h, w = rgba.shape[:2]
    img = rl.Image()
    img.width = w
    img.height = h
    img.mipmaps = 1
    img.format = rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8
    img.data = rl.ffi.cast("void *", rl.ffi.from_buffer(rgba))
    return rl.load_texture_from_image(img)

def draw_spectro(tex, x, y, w, h, tint=rl.WHITE):
    src = rl.Rectangle(0, 0, float(tex.width), float(tex.height))
    dst = rl.Rectangle(float(x), float(y), float(w), float(h))
    rl.draw_texture_pro(tex, src, dst, rl.Vector2(0, 0), 0.0, tint)

def clear_texture_cache():
    """Clear cached textures. Call on cleanup."""
    global _tex_cache, _waveform_tex_cache, _waveform_wave_id
    for tex in _tex_cache.values():
        if tex:
            rl.unload_texture(tex)
    _tex_cache.clear()
    if _waveform_tex_cache:
        rl.unload_texture(_waveform_tex_cache)
    _waveform_tex_cache = None
    _waveform_wave_id = None

def main():
    wav_path = sys.argv[1] if len(sys.argv) > 1 else "audio.wav"
    print(f"Computing spectrogram: {wav_path}")
    power_norm = compute_spectrogram(wav_path)
    rgba = power_to_rgba(power_norm)

    rl.init_window(1920, 1080, "Spectrogram Viewer")
    rl.set_target_fps(60)

    tex = build_texture(rgba)
    MARGIN = 60

    while not rl.window_should_close():
        rl.begin_drawing()
        rl.clear_background(rl.Color(30, 30, 30, 255))
        draw_spectro(tex, MARGIN, MARGIN, 1920 - MARGIN * 2, 1080 - MARGIN * 2 - 50)
        rl.draw_text("SPECTROGRAM", MARGIN, 1080 - MARGIN, 32, rl.RAYWHITE)
        rl.draw_text(wav_path, 500, 1080 - MARGIN, 24, rl.GRAY)
        rl.end_drawing()

    rl.unload_texture(tex)
    rl.close_window()

if __name__ == "__main__":
    main()
