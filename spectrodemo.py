import pyray as rl
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
import sys

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

def power_to_rgba(power_norm):
    freq_bins, time_frames = power_norm.shape
    v = power_norm[::-1, :].astype(np.float32)
    r = np.zeros_like(v); g = np.zeros_like(v); b = np.zeros_like(v)

    m = v < 0.25;  t = v / 0.25
    g[m] = t[m]; b[m] = 1.0

    m = (v >= 0.25) & (v < 0.5); t = (v - 0.25) / 0.25
    g[m] = 1.0; b[m] = 1.0 - t[m]

    m = (v >= 0.5) & (v < 0.75); t = (v - 0.5) / 0.25
    r[m] = t[m]; g[m] = 1.0

    m = v >= 0.75; t = (v - 0.75) / 0.25
    r[m] = 1.0; g[m] = 1.0 - t[m]

    rgba = np.stack([
        (r * 255).astype(np.uint8),
        (g * 255).astype(np.uint8),
        (b * 255).astype(np.uint8),
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
    # rgba must stay alive — it's referenced by ffi buffer, not copied here
    img.data = rl.ffi.cast("void *", rl.ffi.from_buffer(rgba))

    tex = rl.load_texture_from_image(img)
    return tex

def draw_spectro(tex, x, y, w, h):
    src = rl.Rectangle(0, 0, float(tex.width), float(tex.height))
    dst = rl.Rectangle(float(x), float(y), float(w), float(h))
    rl.draw_texture_pro(tex, src, dst, rl.Vector2(0, 0), 0.0, rl.WHITE)

def main():
    wav_path = sys.argv[1] if len(sys.argv) > 1 else "audio.wav"
    print(f"Computing spectrogram: {wav_path}")
    power_norm = compute_spectrogram(wav_path)
    print(f"Shape: {power_norm.shape}")
    rgba = power_to_rgba(power_norm)  # kept alive through build_texture call

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
