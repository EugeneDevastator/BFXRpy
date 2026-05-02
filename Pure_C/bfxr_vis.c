#include "bfxr_vis.h"
#include "bfxr_fft.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define SPECTRO_W 512
#define SPECTRO_H 256
#define N_FFT 1024
#define OVERLAP 0.75f

// Gradient stops: (t, r, g, b)
static const float GRADIENT[][4] = {
    {0.0f, 0,   0,   0},
    {0.6f, 32,  64,  128},
    {1.0f, 255, 255, 255},
};

// Texture cache
static Texture2D spectro_tex = {0};
static unsigned long long last_wave_hash = 0;

static unsigned long long simple_hash(const void* data, int len) {
    unsigned long long hash = 5381;
    const unsigned char* p = (const unsigned char*)data;
    for (int i = 0; i < len; i++) {
        hash = ((hash << 5) + hash) + p[i];
    }
    return hash;
}

static void compute_spectrogram(const BfxrWave* wave, float* spectro, int spectro_w, int spectro_h) {
    int n = wave->num_samples;
    if (n == 0) return;

    int hop = (int)(N_FFT * (1.0f - OVERLAP));
    if (hop < 1) hop = 1;

    // Number of frequency bins from FFT (0 to Nyquist)
    int num_bins_fft = N_FFT / 2 + 1;

    // Number of time frames
    int num_frames = (n - N_FFT) / hop + 1;
    if (num_frames <= 0) return;

    // Hann window
    float* window = (float*)malloc(N_FFT * sizeof(float));
    for (int i = 0; i < N_FFT; i++) {
        window[i] = 0.5f * (1.0f - cosf(2.0f * M_PI * i / (N_FFT - 1)));
    }

    // Working buffer for FFT (complex)
    complex float* fft_buf = (complex float*)malloc(N_FFT * sizeof(complex float));

    // First pass: compute power dB to find min/max for normalization
    float pmin = 1e9f, pmax = -1e9f;
    float* power_db = (float*)malloc(num_frames * num_bins_fft * sizeof(float));

    for (int frame = 0; frame < num_frames; frame++) {
        int start = frame * hop;

        // Fill buffer with windowed samples
        for (int i = 0; i < N_FFT; i++) {
            if (start + i < n) {
                fft_buf[i] = (float)wave->samples[start + i] / 32767.0f * window[i];
            } else {
                fft_buf[i] = 0;
            }
        }

        bfxr_fft(fft_buf, N_FFT);

        // Get magnitude for first N_FFT/2+1 bins (0 to Nyquist)
        for (int bin = 0; bin < num_bins_fft; bin++) {
            float real = crealf(fft_buf[bin]);
            float imag = cimagf(fft_buf[bin]);
            float mag = sqrtf(real * real + imag * imag);
            float db = 20.0f * log10f(mag + 1e-9f);
            power_db[frame * num_bins_fft + bin] = db;
            if (db < pmin) pmin = db;
            if (db > pmax) pmax = db;
        }
    }

    // Second pass: normalize and fill spectro output with proper frequency mapping
    float range = pmax - pmin + 1e-9f;
    for (int frame = 0; frame < num_frames && frame < spectro_w; frame++) {
        for (int display_bin = 0; display_bin < spectro_h; display_bin++) {
            // Map display bin to FFT bin (invert so low freq at bottom like Python)
            int fft_bin = (num_bins_fft - 1) - (display_bin * num_bins_fft / spectro_h);
            if (fft_bin < 0) fft_bin = 0;
            if (fft_bin >= num_bins_fft) fft_bin = num_bins_fft - 1;

            float v = (power_db[frame * num_bins_fft + fft_bin] - pmin) / range;
            if (v < 0) v = 0;
            if (v > 1) v = 1;
            spectro[frame * spectro_h + display_bin] = v;
        }
    }

    free(power_db);
    free(fft_buf);
    free(window);
}

void vis_draw_waveform(const BfxrWave* wave, int x, int y, int w, int h) {
    if (!wave || wave->num_samples == 0) return;

    DrawRectangle(x, y, w, h, RAYWHITE);
    DrawRectangleLines(x, y, w, h, LIGHTGRAY);

    int n = wave->num_samples;
    int step = (n > w) ? n / w : 1;
    int cy = y + h / 2;

    Vector2 prev = {x, cy};
    for (int i = 0; i < n; i += step) {
        int px = x + (int)((float)i / n * w);
        int py = cy - (int)(wave->samples[i] / 32767.0f * (h / 2 - 2));
        if (i > 0) {
            DrawLineV(prev, (Vector2){px, py}, BLACK);
        }
        prev = (Vector2){px, py};
    }
}

void vis_draw_spectrogram_full(const BfxrWave* wave, int x, int y, int w, int h) {
    if (!wave || wave->num_samples == 0) return;

    unsigned long long hash = simple_hash(wave->samples, wave->num_samples * sizeof(int16_t));

    if (hash != last_wave_hash || spectro_tex.id == 0) {
        last_wave_hash = hash;
        if (spectro_tex.id) UnloadTexture(spectro_tex);

        float* spectro = (float*)malloc(SPECTRO_W * SPECTRO_H * sizeof(float));
        if (!spectro) return;
        memset(spectro, 0, SPECTRO_W * SPECTRO_H * sizeof(float));
        compute_spectrogram(wave, spectro, SPECTRO_W, SPECTRO_H);

        unsigned char* rgba = (unsigned char*)malloc(SPECTRO_W * SPECTRO_H * 4);
        if (!rgba) { free(spectro); return; }

        for (int frame = 0; frame < SPECTRO_W; frame++) {
            for (int bin = 0; bin < SPECTRO_H; bin++) {
                int src_idx = frame * SPECTRO_H + bin;
                int dst_idx = frame * SPECTRO_H + bin;

                float v = spectro[src_idx];
                if (v < 0) v = 0;
                if (v > 1) v = 1;

                int stop = 0;
                for (int s = 0; s < 3; s++) {
                    if (v >= GRADIENT[s][0]) stop = s;
                }

                float t = 0;
                if (stop < 2) {
                    t = (v - GRADIENT[stop][0]) / (GRADIENT[stop+1][0] - GRADIENT[stop][0]);
                }

                rgba[dst_idx*4 + 0] = (unsigned char)(GRADIENT[stop][1] + t * (GRADIENT[stop+1][1] - GRADIENT[stop][1]));
                rgba[dst_idx*4 + 1] = (unsigned char)(GRADIENT[stop][2] + t * (GRADIENT[stop+1][2] - GRADIENT[stop][2]));
                rgba[dst_idx*4 + 2] = (unsigned char)(GRADIENT[stop][3] + t * (GRADIENT[stop+1][3] - GRADIENT[stop][3]));
                rgba[dst_idx*4 + 3] = 255;
            }
        }

        Image img = {.data = rgba, .width = SPECTRO_W, .height = SPECTRO_H, .mipmaps = 1, .format = PIXELFORMAT_UNCOMPRESSED_R8G8B8A8};
        spectro_tex = LoadTextureFromImage(img);

        free(rgba);
        free(spectro);
    }

    if (spectro_tex.id) {
        DrawTexturePro(spectro_tex,
            (Rectangle){0, 0, (float)spectro_tex.width, (float)spectro_tex.height},
            (Rectangle){x, y, (float)w, (float)h},
            (Vector2){0, 0}, 0.0f, WHITE);
    }
}

void vis_clear_cache(void) {
    if (spectro_tex.id) {
        UnloadTexture(spectro_tex);
        spectro_tex.id = 0;
    }
    last_wave_hash = 0;
}
