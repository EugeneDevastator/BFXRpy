#include "os_util.h"
#include <sys/stat.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include "bfxr_params.h"
#include "bfxr_generator.h"
#include "bfxr_wav.h"
#include "bfxr_file.h"
#include "bfxr_ui.h"
#include "bfxr_vis.h"
#include "bfxr_config.h"
#include "raylib.h"

// For tracking parameter changes
static double prev_params_l[NUM_PARAMS] = {0};
static double prev_params_r[NUM_PARAMS] = {0};

// Forward declaration for simple_hash
unsigned long long simple_hash(const void* data, int len);
#include "bfxr_config.h"


#define SCREEN_WIDTH 1200
#define SCREEN_HEIGHT 800
#define FONT_SIZE 32
#define SLIDER_FONT_SIZE (FONT_SIZE - 6)
#define UNIFIED_BTN_W 180
#define UNIFIED_BTN_H 44
#define BTN_GAP 6

static Font _font = {0};

// Match Python's GenJob class
typedef struct {
    BfxrWave result;
    int running;
    int done;
    char label[64];
    pthread_t thread;
    int should_stop;
    double params[NUM_PARAMS];
    int wave_type_a;
    int wave_type_b;
    double blend_t;
    int is_blend;
} GenJob;

static GenJob gen_job = {0};

// Clone params
void clone_params(const double src[NUM_PARAMS], double dst[NUM_PARAMS]) {
    memcpy(dst, src, sizeof(double) * NUM_PARAMS);
}

// Thread function for wave generation
static void* generate_thread(void* arg) {
    GenJob* job = (GenJob*)arg;
    job->running = 1;
    job->done = 0;

    if (job->is_blend) {
        job->result = bfxr_generate_wave_blended(job->params, job->wave_type_a, job->wave_type_b, job->blend_t);
    } else {
        job->result = bfxr_generate_wave(job->params);
    }

    job->done = 1;
    job->running = 0;
    return NULL;
}

void start_generation(GenJob* job, const double params[NUM_PARAMS], int which_unused, const char* label) {
    (void)which_unused;
    if (job->running) return;

    memcpy(job->params, params, sizeof(double) * NUM_PARAMS);
    job->is_blend = 0;
    strncpy(job->label, label, sizeof(job->label)-1);
    job->should_stop = 0;

    pthread_create(&job->thread, NULL, generate_thread, job);
    pthread_detach(job->thread);
}

void start_generation_blended(GenJob* job, const double blended[NUM_PARAMS], int wt_a, int wt_b, double blend_t, const char* label) {
    if (job->running) return;

    memcpy(job->params, blended, sizeof(double) * NUM_PARAMS);
    job->wave_type_a = wt_a;
    job->wave_type_b = wt_b;
    job->blend_t = blend_t;
    job->is_blend = 1;
    strncpy(job->label, label, sizeof(job->label)-1);
    job->should_stop = 0;

    pthread_create(&job->thread, NULL, generate_thread, job);
    pthread_detach(job->thread);
}

// Poll for completed generation - matching Python's gen.poll()
BfxrWave poll_generation(GenJob* job, const char** label) {
    if (job->done && job->result.num_samples > 0) {
        BfxrWave wave = job->result;
        *label = job->label;
        job->result.num_samples = 0;
        job->result.samples = NULL;
        job->done = 0;
        return wave;
    }
    *label = NULL;
    return (BfxrWave){0};
}

typedef struct {
    double params_l[NUM_PARAMS];
    double params_r[NUM_PARAMS];
    double blend_t;
    int sound_loaded;
    Sound sound;
    char status[256];
    BfxrWave last_wave;
    int wave_valid;
    int play_on_gen;
    float global_volume;
    int rel_l;
    int rel_r;
    // For async generation
    BfxrWave pending_wave;
    int pending_play;
    const char* pending_label;
    BfxrConfig config;
} AppState;

int handle_slider_input(int mx, int my, int sx, int sw, int by, int row_h, double params[NUM_PARAMS]) {
    int released = 0;
    for (int i = 0; i < NUM_PARAMS; i++) {
        int track_y = by + i * row_h + row_h / 2;
        if (fabs((double)my - track_y) < 14 && mx >= sx && mx <= sx + sw) {
            if (IsMouseButtonDown(MOUSE_BUTTON_LEFT)) {
                double t = (double)(mx - sx) / sw;
                if (t < 0.0) t = 0.0;
                if (t > 1.0) t = 1.0;
                params[i] = t_to_param(i, t);
            }
            if (IsMouseButtonReleased(MOUSE_BUTTON_LEFT)) {
                released = 1;
            }
        }
    }
    return released;
}

void draw_panel(int x, int y, int w, int h, double params[NUM_PARAMS], const char* label, int* out_sx, int* out_sw, int* out_by, int* out_row_h) {
    DrawRectangleLines(x, y, w, h, LIGHTGRAY);
    DrawTextEx(_font, label, (Vector2){x + 10, y + 8}, FONT_SIZE, 1, DARKGRAY);

    int lbl_font = SLIDER_FONT_SIZE;
    int val_w = 72;
    int pad_left = x + 10;
    int row_h = (h - 50) / NUM_PARAMS;
    int by = y + 46;

    int max_lbl_w = 0;
    for (int i = 0; i < NUM_PARAMS; i++) {
        int tw = MeasureTextEx(_font, PARAM_NAMES[i], lbl_font, 1).x;
        if (tw > max_lbl_w) max_lbl_w = tw;
    }
    int lbl_gap = 6;
    int sx = pad_left + max_lbl_w + lbl_gap;
    int sw = (x + w) - sx - val_w - 14;

    for (int i = 0; i < NUM_PARAMS; i++) {
        int sy = by + i * row_h;

        DrawTextEx(_font, PARAM_NAMES[i], (Vector2){pad_left, sy}, lbl_font, 1, DARKGRAY);

        int bar_y = sy + row_h / 2 - 4;
        double t = params_to_t(i, params[i]);

        DrawRectangle(sx, bar_y, sw, 8, (Color){200, 200, 200, 255});

        if (PARAM_RANGES[i].min < 0) {
            int mid_x = sx + sw / 2;
            int fill_px = (int)(t * sw) - sw / 2;
            if (fill_px >= 0) {
                DrawRectangle(mid_x, bar_y, fill_px, 8, (Color){70, 130, 200, 255});
            } else {
                DrawRectangle(mid_x + fill_px, bar_y, -fill_px, 8, (Color){200, 100, 70, 255});
            }
            DrawLine(mid_x, bar_y - 2, mid_x, bar_y + 10, DARKGRAY);
        } else {
            int filled = (int)(t * sw);
            if (filled > 0) {
                DrawRectangle(sx, bar_y, filled, 8, (Color){70, 130, 200, 255});
            }
        }

        int knob_w = 6;
        int knob_h = 18;
        int knob_x = sx + (int)(t * sw) - knob_w / 2;
        DrawRectangle(knob_x, bar_y - (knob_h - 8) / 2, knob_w, knob_h, BLACK);

        const char* val_str = params_display(i, params[i]);
        DrawTextEx(_font, val_str, (Vector2){sx + sw + 6, sy}, lbl_font, 1, DARKGRAY);
    }

    if (out_sx) *out_sx = sx;
    if (out_sw) *out_sw = sw;
    if (out_by) *out_by = by;
    if (out_row_h) *out_row_h = row_h;
}

double draw_blend_slider(int x, int y, int w, int h, double blend_t, int* released) {
    int mx = GetMouseX();
    int my = GetMouseY();

    int seg_h = h / 3;
    int total_h = seg_h * 3;

    Color COLOR_EXTRA_A = {180, 100, 40, 180};
    Color COLOR_CORE = {200, 160, 40, 255};
    Color COLOR_EXTRA_B = {100, 180, 40, 180};
    Color COLOR_TRACK = {200, 200, 200, 255};

    int bar_w = 16;
    int bar_x = x + w / 2 - bar_w / 2;

    DrawRectangle(bar_x, y, bar_w, total_h, COLOR_TRACK);

    int a_py = y + seg_h;
    int b_py = y + 2 * seg_h;
    int knob_py = y + (int)((blend_t + 1.0) / 3.0 * total_h);

    if (blend_t < 0.0) {
        DrawRectangle(bar_x, knob_py, bar_w, a_py - knob_py, COLOR_EXTRA_A);
    } else if (blend_t <= 1.0) {
        DrawRectangle(bar_x, a_py, bar_w, knob_py - a_py, COLOR_CORE);
    } else {
        DrawRectangle(bar_x, a_py, bar_w, b_py - a_py, COLOR_CORE);
        DrawRectangle(bar_x, b_py, bar_w, knob_py - b_py, COLOR_EXTRA_B);
    }

    DrawLine(bar_x - 8, a_py, bar_x + bar_w + 8, a_py, (Color){40, 80, 160, 255});
    DrawLine(bar_x - 8, b_py, bar_x + bar_w + 8, b_py, (Color){40, 130, 60, 255});

    int lbl_fs = FONT_SIZE - 4;
    DrawTextEx(_font, "A", (Vector2){bar_x - 24, a_py - lbl_fs / 2}, lbl_fs, 1, (Color){40, 80, 160, 255});
    DrawTextEx(_font, "B", (Vector2){bar_x - 24, b_py - lbl_fs / 2}, lbl_fs, 1, (Color){40, 130, 60, 255});

    int knob_h2 = 10;
    DrawRectangle(bar_x - 6, knob_py - knob_h2 / 2, bar_w + 12, knob_h2, BLACK);
    DrawTextEx(_font, TextFormat("%.2f", blend_t), (Vector2){bar_x + bar_w + 6, knob_py - lbl_fs / 2}, lbl_fs, 1, DARKGRAY);

    int touching = (abs(mx - (bar_x + bar_w / 2)) < 24) && my >= y && my <= y + total_h;
    if (IsMouseButtonDown(MOUSE_BUTTON_LEFT) && touching) {
        blend_t = (double)(my - y) / total_h * 3.0 - 1.0;
        if (blend_t < -1.0) blend_t = -1.0;
        if (blend_t > 2.0) blend_t = 2.0;
    }

    if (released) {
        *released = touching && IsMouseButtonReleased(MOUSE_BUTTON_LEFT);
    }

    return blend_t;
}

void load_and_play_wave(AppState* state, BfxrWave wave, const char* label) {
    if (state->sound_loaded) {
        UnloadSound(state->sound);
        state->sound_loaded = 0;
    }

    Wave w;
    w.data = wave.samples;
    w.frameCount = wave.num_samples;
    w.sampleRate = 44100;
    w.sampleSize = 16;
    w.channels = 1;

    state->sound = LoadSoundFromWave(w);
    state->sound_loaded = 1;
    SetSoundVolume(state->sound, state->global_volume);
    PlaySound(state->sound);

    if (state->wave_valid) {
        bfxr_wave_free(&state->last_wave);
    }
    state->last_wave = wave;
    state->wave_valid = 1;

    snprintf(state->status, sizeof(state->status), "Playing %s: %d samples", label, wave.num_samples);
}

int main(void) {
    // Create Export directory - best effort, ignore errors
    os_mkdir("Export");

	SetConfigFlags(FLAG_WINDOW_RESIZABLE);
	InitWindow(800, 600, "bfxrc");  // dummy size first

	int monitor = GetCurrentMonitor();
	int sw = GetMonitorWidth(monitor);
	int sh = GetMonitorHeight(monitor);

	SetWindowPosition(0, 0);
	SetWindowSize(sw, sh);
	SetTargetFPS(60);
	InitAudioDevice();

    // Set spectrogram gradient from config

    _font = LoadFontEx("Cadman_Bold.otf", FONT_SIZE * 2, 0, 0);
    if (_font.texture.id == 0) {
        _font = GetFontDefault();
    } else {
        SetTextureFilter(_font.texture, TEXTURE_FILTER_BILINEAR);
    }

    AppState state;
    params_make_default(state.params_l);
    params_make_default(state.params_r);
    state.params_r[6] = 0.5;
    state.blend_t = 0.5;
    state.sound_loaded = 0;
    state.sound = (Sound){0};
    state.wave_valid = 0;
    memset(&state.last_wave, 0, sizeof(BfxrWave));
    state.play_on_gen = 1;
    state.global_volume = 1.0f;
    state.rel_l = 0;
    state.rel_r = 0;
    state.pending_wave = (BfxrWave){0};
    state.pending_play = 0;
    state.pending_label = NULL;
    // Load config
    config_load(&state.config);
    state.play_on_gen = state.config.autoplay;
    state.global_volume = state.config.volume;

    // Set spectrogram gradient from config
    vis_set_gradient(state.config.grad_t, state.config.grad_r, state.config.grad_g, state.config.grad_b);

    // Load last scene
    config_load_scene(state.params_l, state.params_r, &state.blend_t);

    // Initialize previous params for change detection
    memcpy(prev_params_l, state.params_l, sizeof(double) * NUM_PARAMS);
    memcpy(prev_params_r, state.params_r, sizeof(double) * NUM_PARAMS);

    strcpy(state.status, "Ready");

    // Generate initial visualizations for loaded scene
    if (state.play_on_gen) {
        memcpy(state.params_l, state.params_l, sizeof(double) * NUM_PARAMS);
        start_generation(&gen_job, state.params_l, 0, "A");
    }

    // Initialize generation job
    gen_job.running = 0;
    gen_job.done = 0;
    gen_job.result = (BfxrWave){0};

    while (!WindowShouldClose()) {
        int sw = GetScreenWidth();
        int sh = GetScreenHeight();
        int mx = GetMouseX();
        int my = GetMouseY();

        // Check for completed generation (matching Python's gen.poll())
        if (gen_job.done) {
            const char* label = NULL;
            BfxrWave wave = poll_generation(&gen_job, &label);
            if (wave.num_samples > 0) {
                load_and_play_wave(&state, wave, label);
            }
        }

        // Compute layout matching Python
        int PANEL_W = (sw / 3 - 10) > 300 ? (sw / 3 - 10) : 300;
        int PANEL_H = sh - 60;
        int PANEL_Y = 30;
        int LEFT_X = 10;
        int RIGHT_X = sw - PANEL_W - 10;
        int CENTER_X = LEFT_X + PANEL_W + 10;
        int CENTER_W = RIGHT_X - CENTER_X - 10;

        int cx = CENTER_X;
        int cw = CENTER_W;

        int col1_x = cx + 4;
        int col3_x = cx + cw - UNIFIED_BTN_W - 4;
        int col2_x = col1_x + UNIFIED_BTN_W + 8;

        int CTRL_H = 28;
        int ctrl_y = PANEL_Y + 8;
        int vol_y = ctrl_y + CTRL_H + 4;
        int status_y = vol_y + CTRL_H + 4;

        int BTN_START = status_y + CTRL_H + 8;

        int blend_slider_y1 = BTN_START + UNIFIED_BTN_H + BTN_GAP;
        int blend_h = (int)(sh * 0.25) > 100 ? (int)(sh * 0.25) : 100;

        int col2_start_y = blend_slider_y1 + blend_h + BTN_GAP;

        int gx = col2_x;
        int gy = col2_start_y;
        int gw = UNIFIED_BTN_W;
        int gh = UNIFIED_BTN_H;
        int gap = BTN_GAP;

        // Handle slider input
        int sx_l, sw_l, by_l, row_h_l;
        int sx_r, sw_r, by_r, row_h_r;

        draw_panel(LEFT_X, PANEL_Y, PANEL_W, PANEL_H, state.params_l, "PRESET A", &sx_l, &sw_l, &by_l, &row_h_l);
        state.rel_l = handle_slider_input(mx, my, sx_l, sw_l, by_l, row_h_l, state.params_l);

        draw_panel(RIGHT_X, PANEL_Y, PANEL_W, PANEL_H, state.params_r, "PRESET B", &sx_r, &sw_r, &by_r, &row_h_r);
        state.rel_r = handle_slider_input(mx, my, sx_r, sw_r, by_r, row_h_r, state.params_r);

        // Start generation on slider change (like blend slider)
        if (state.play_on_gen && !gen_job.running) {
            int l_changed = 0, r_changed = 0;
            for (int i = 0; i < NUM_PARAMS; i++) {
                if (state.params_l[i] != prev_params_l[i]) l_changed = 1;
                if (state.params_r[i] != prev_params_r[i]) r_changed = 1;
            }
            if (l_changed) {
                start_generation(&gen_job, state.params_l, 0, "A");
                memcpy(prev_params_l, state.params_l, sizeof(double) * NUM_PARAMS);
                snprintf(state.status, sizeof(state.status), "Generating A...");
            }
            if (r_changed) {
                start_generation(&gen_job, state.params_r, 1, "B");
                memcpy(prev_params_r, state.params_r, sizeof(double) * NUM_PARAMS);
                snprintf(state.status, sizeof(state.status), "Generating B...");
            }
        } else if (!state.play_on_gen) {
            // Still track changes even when not playing
            memcpy(prev_params_l, state.params_l, sizeof(double) * NUM_PARAMS);
            memcpy(prev_params_r, state.params_r, sizeof(double) * NUM_PARAMS);
        }

        double old_blend_t = state.blend_t;
        int blend_released = 0;
        state.blend_t = draw_blend_slider(col2_x, blend_slider_y1, UNIFIED_BTN_W, blend_h, state.blend_t, &blend_released);

        // Autoplay on blend slider movement if autoplay is on
        if (state.play_on_gen && state.blend_t != old_blend_t && !gen_job.running) {
            double blended[NUM_PARAMS];
            params_blend(state.params_l, state.params_r, state.blend_t, blended);
            int wt_dom = (state.blend_t <= 0.5) ? (int)state.params_l[0] : (int)state.params_r[0];
            blended[0] = (double)wt_dom;
            start_generation_blended(&gen_job, blended, (int)state.params_l[0], (int)state.params_r[0], state.blend_t, "BLEND");
            snprintf(state.status, sizeof(state.status), "Generating BLEND...");
        }

        // Handle button clicks
        if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            int cy;

            // Column 1 buttons
            cy = BTN_START;

            for (int i = 0; i < 6; i++) {
                if (mx >= col1_x && mx <= col1_x + UNIFIED_BTN_W && my >= cy && my <= cy + UNIFIED_BTN_H) {
                    switch(i) {
                        case 0:
                            if (!gen_job.running) {
                                start_generation(&gen_job, state.params_l, 0, "A");
                                snprintf(state.status, sizeof(state.status), "Generating A...");
                            }
                            break;
                        case 1: {
                            double blended[NUM_PARAMS];
                            params_blend(state.params_l, state.params_r, state.blend_t, blended);
                            int wt_dom = (state.blend_t <= 0.5) ? (int)state.params_l[0] : (int)state.params_r[0];
                            blended[0] = (double)wt_dom;
                            clone_params(blended, state.params_l);
                            if (state.play_on_gen && !gen_job.running) {
                                start_generation(&gen_job, state.params_l, 0, "A");
                                snprintf(state.status, sizeof(state.status), "Generating A...");
                            }
                            break;
                        }
                        case 2:
                            params_randomize(state.params_l);
                            if (state.play_on_gen && !gen_job.running) {
                                start_generation(&gen_job, state.params_l, 0, "A");
                                snprintf(state.status, sizeof(state.status), "Generating A...");
                            }
                            break;
                        case 3:
                            clone_params(state.params_r, state.params_l);
                            if (state.play_on_gen && !gen_job.running) {
                                start_generation(&gen_job, state.params_l, 0, "A");
                                snprintf(state.status, sizeof(state.status), "Generating A...");
                            }
                            break;
                        case 4:
                            params_randomize(state.params_l);
                            if (state.play_on_gen && !gen_job.running) {
                                start_generation(&gen_job, state.params_l, 0, "A");
                                snprintf(state.status, sizeof(state.status), "Generating A...");
                            }
                            break;
                        case 5: {
                            // Generate unique filename with hash
                            unsigned long long h = simple_hash(state.last_wave.samples, state.last_wave.num_samples * 2);
                            char export_name[256];
                                                        time_t now = time(NULL);
                            struct tm *t = localtime(&now);
                            char date_str[32];
                            strftime(date_str, sizeof(date_str), "%y_%m_%d", t);
                            snprintf(export_name, sizeof(export_name), "Export/Sample_A_%s_%llx.wav", date_str, h);
                            bfxr_wav_save(export_name, &state.last_wave);
                            snprintf(state.status, sizeof(state.status), "Exported %s", export_name);
                            break;
                        }
                    }
                }
                cy += UNIFIED_BTN_H + BTN_GAP;
            }

            // Column 3 buttons
            cy = BTN_START;

            for (int i = 0; i < 5; i++) {
                if (mx >= col3_x && mx <= col3_x + UNIFIED_BTN_W && my >= cy && my <= cy + UNIFIED_BTN_H) {
                    switch(i) {
                        case 0:
                            if (!gen_job.running) {
                                start_generation(&gen_job, state.params_r, 1, "B");
                                snprintf(state.status, sizeof(state.status), "Generating B...");
                            }
                            break;
                        case 1: {
                            double blended[NUM_PARAMS];
                            params_blend(state.params_l, state.params_r, state.blend_t, blended);
                            int wt_dom = (state.blend_t <= 0.5) ? (int)state.params_l[0] : (int)state.params_r[0];
                            blended[0] = (double)wt_dom;
                            clone_params(blended, state.params_r);
                            if (state.play_on_gen && !gen_job.running) {
                                start_generation(&gen_job, state.params_r, 1, "B");
                                snprintf(state.status, sizeof(state.status), "Generating B...");
                            }
                            break;
                        }
                        case 2:
                            params_randomize(state.params_r);
                            if (state.play_on_gen && !gen_job.running) {
                                start_generation(&gen_job, state.params_r, 1, "B");
                                snprintf(state.status, sizeof(state.status), "Generating B...");
                            }
                            break;
                        case 3:
                            clone_params(state.params_l, state.params_r);
                            if (state.play_on_gen && !gen_job.running) {
                                start_generation(&gen_job, state.params_r, 1, "B");
                                snprintf(state.status, sizeof(state.status), "Generating B...");
                            }
                            break;
                        case 4: {
                            unsigned long long h = simple_hash(state.last_wave.samples, state.last_wave.num_samples * 2);
                            char export_name[256];
                                                        time_t now = time(NULL);
                            struct tm *t = localtime(&now);
                            char date_str[32];
                            strftime(date_str, sizeof(date_str), "%y_%m_%d", t);
                            snprintf(export_name, sizeof(export_name), "Export/Sample_B_%s_%llx.wav", date_str, h);
                            bfxr_wav_save(export_name, &state.last_wave);
                            snprintf(state.status, sizeof(state.status), "Exported %s", export_name);
                            break;
                        }
                    }
                }
                cy += UNIFIED_BTN_H + BTN_GAP;
            }

            // Play Blend button
            if (mx >= col2_x && mx <= col2_x + UNIFIED_BTN_W && my >= BTN_START && my <= BTN_START + UNIFIED_BTN_H) {
                if (!gen_job.running) {
                    double blended[NUM_PARAMS];
                    params_blend(state.params_l, state.params_r, state.blend_t, blended);
                    start_generation_blended(&gen_job, blended, (int)state.params_l[0], (int)state.params_r[0], state.blend_t, "BLEND");
                    snprintf(state.status, sizeof(state.status), "Generating BLEND...");
                }
            }

            // Scene buttons
            if (mx >= gx && mx <= gx + gw && my >= gy && my <= gy + gh) {
                bfxr_save_scene("scene.bfxr", state.params_l, state.params_r, state.blend_t);
                strcpy(state.status, "Saved scene.bfxr");
            }
            if (mx >= gx + gw + gap && mx <= gx + gw + gap + gw && my >= gy && my <= gy + gh) {
                if (bfxr_load_scene("scene.bfxr", state.params_l, state.params_r, &state.blend_t) == 0) {
                    strcpy(state.status, "Loaded scene.bfxr");
                }
            }
            if (mx >= gx && mx <= gx + gw && my >= gy + gh + gap && my <= gy + gh + gap + gh) {
                // Export blend to WAV file with unique name
                double blended[NUM_PARAMS];
                params_blend(state.params_l, state.params_r, state.blend_t, blended);
                BfxrWave wave = bfxr_generate_wave_blended(blended, (int)state.params_l[0], (int)state.params_r[0], state.blend_t);
                unsigned long long h = simple_hash(wave.samples, wave.num_samples * 2);
                char export_name[256];
                                            time_t now = time(NULL);
                            struct tm *t = localtime(&now);
                            char date_str[32];
                            strftime(date_str, sizeof(date_str), "%y_%m_%d", t);
                            snprintf(export_name, sizeof(export_name), "Export/Sample_BLEND_%s_%llx.wav", date_str, h);
                bfxr_wav_save(export_name, &wave);
                bfxr_wave_free(&wave);
                snprintf(state.status, sizeof(state.status), "Exported %s", export_name);
            }
        }

        // Handle Play on Change checkbox
        if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            if (mx >= cx && mx <= cx + 26 && my >= ctrl_y && my <= ctrl_y + 26) {
                state.play_on_gen = !state.play_on_gen;
            }
        }

        // Handle volume slider
        if (IsMouseButtonDown(MOUSE_BUTTON_LEFT)) {
            int vol_sx = cx + 140;
            int vol_sw = cw - 160;
            if (abs(my - (vol_y + 5)) < 20 && mx >= vol_sx && mx <= vol_sx + vol_sw) {
                state.global_volume = (float)((double)(mx - vol_sx) / vol_sw);
                if (state.global_volume < 0.0f) state.global_volume = 0.0f;
                if (state.global_volume > 1.0f) state.global_volume = 1.0f;
                if (state.sound_loaded) {
                    SetSoundVolume(state.sound, state.global_volume);
                }
            }
        }

        BeginDrawing();
        ClearBackground((Color){240, 240, 240, 255});

        // Redraw panels
        draw_panel(LEFT_X, PANEL_Y, PANEL_W, PANEL_H, state.params_l, "PRESET A", &sx_l, &sw_l, &by_l, &row_h_l);
        draw_panel(RIGHT_X, PANEL_Y, PANEL_W, PANEL_H, state.params_r, "PRESET B", &sx_r, &sw_r, &by_r, &row_h_r);

        // Top controls
        DrawRectangleLines(cx, ctrl_y, 26, 26, DARKGRAY);
        if (state.play_on_gen) {
            DrawRectangle(cx + 4, ctrl_y + 4, 18, 18, (Color){200, 120, 30, 255});
        }
        DrawTextEx(_font, "Play on Change", (Vector2){cx + 34, ctrl_y + 4}, SLIDER_FONT_SIZE, 1, DARKGRAY);

        DrawTextEx(_font, "Vol", (Vector2){cx + 140 - 30, vol_y}, SLIDER_FONT_SIZE, 1, DARKGRAY);
        int vol_sx = cx + 140;
        int vol_sw = cw - 160;
        DrawRectangle(vol_sx, vol_y, vol_sw, 10, (Color){200, 200, 200, 255});
        int vol_filled = (int)(state.global_volume * vol_sw);
        if (vol_filled > 0) {
            DrawRectangle(vol_sx, vol_y, vol_filled, 10, (Color){200, 160, 40, 255});
        }
        DrawTextEx(_font, TextFormat("%.2f", state.global_volume), (Vector2){vol_sx + vol_sw + 6, vol_y - 4}, SLIDER_FONT_SIZE - 4, 1, DARKGRAY);

        // Status - show "Generating..." if generation is running
        if (gen_job.running) {
            DrawTextEx(_font, "Generating...", (Vector2){cx, status_y}, SLIDER_FONT_SIZE, 1, (Color){180, 140, 0, 255});
        } else {
            DrawTextEx(_font, state.status, (Vector2){cx, status_y}, SLIDER_FONT_SIZE, 1, (Color){0, 100, 200, 255});
        }

        // Column 1 buttons
        {
            Color COLOR_A = {40, 80, 160, 255};
            Color COLOR_XFER = {200, 100, 70, 255};
            Color COLOR_RAND = {120, 60, 160, 255};
            Color COLOR_COPY = {80, 80, 80, 255};

            int cy = BTN_START;
            const char* col1_labels[] = {"PLAY A", "A < BLEND", "A < RND", "A < B", "NOVEL A", "EXPORT A"};
            Color col1_colors[] = {COLOR_A, COLOR_XFER, COLOR_RAND, COLOR_COPY, COLOR_RAND, {100, 100, 160, 255}};

            for (int i = 0; i < 6; i++) {
                Color btn_color = (mx >= col1_x && mx <= col1_x + UNIFIED_BTN_W && my >= cy && my <= cy + UNIFIED_BTN_H) ?
                                   (Color){180, 180, 180, 255} : col1_colors[i];
                DrawRectangle(col1_x, cy, UNIFIED_BTN_W, UNIFIED_BTN_H, btn_color);
                DrawRectangleLinesEx((Rectangle){col1_x, cy, UNIFIED_BTN_W, UNIFIED_BTN_H}, 1, DARKGRAY);
                int tw = MeasureTextEx(_font, col1_labels[i], FONT_SIZE - 8, 1).x;
                DrawTextEx(_font, col1_labels[i], (Vector2){col1_x + (UNIFIED_BTN_W - tw) / 2, cy + 13}, FONT_SIZE - 8, 1, RAYWHITE);
                cy += UNIFIED_BTN_H + BTN_GAP;
            }
        }

        // Column 3 buttons
        {
            Color COLOR_B = {40, 130, 60, 255};
            Color COLOR_XFER = {200, 100, 70, 255};
            Color COLOR_RAND = {120, 60, 160, 255};
            Color COLOR_COPY = {80, 80, 80, 255};

            int cy = BTN_START;
            const char* col3_labels[] = {"PLAY B", "BLEND > B", "RND > B", "A > B", "EXPORT B"};
            Color col3_colors[] = {COLOR_B, COLOR_XFER, COLOR_RAND, COLOR_COPY, {100, 100, 160, 255}};

            for (int i = 0; i < 5; i++) {
                Color btn_color = (mx >= col3_x && mx <= col3_x + UNIFIED_BTN_W && my >= cy && my <= cy + UNIFIED_BTN_H) ?
                                   (Color){180, 180, 180, 255} : col3_colors[i];
                DrawRectangle(col3_x, cy, UNIFIED_BTN_W, UNIFIED_BTN_H, btn_color);
                DrawRectangleLinesEx((Rectangle){col3_x, cy, UNIFIED_BTN_W, UNIFIED_BTN_H}, 1, DARKGRAY);
                int tw = MeasureTextEx(_font, col3_labels[i], FONT_SIZE - 8, 1).x;
                DrawTextEx(_font, col3_labels[i], (Vector2){col3_x + (UNIFIED_BTN_W - tw) / 2, cy + 13}, FONT_SIZE - 8, 1, RAYWHITE);
                cy += UNIFIED_BTN_H + BTN_GAP;
            }
        }

        // Play Blend button
        {
            Color btn_color = (mx >= col2_x && mx <= col2_x + UNIFIED_BTN_W && my >= BTN_START && my <= BTN_START + UNIFIED_BTN_H) ?
                               (Color){200, 150, 50, 255} : (Color){180, 130, 20, 255};
            DrawRectangle(col2_x, BTN_START, UNIFIED_BTN_W, UNIFIED_BTN_H, btn_color);
            DrawRectangleLinesEx((Rectangle){col2_x, BTN_START, UNIFIED_BTN_W, UNIFIED_BTN_H}, 1, DARKGRAY);
            int tw = MeasureTextEx(_font, "PLAY BLEND", FONT_SIZE - 8, 1).x;
            DrawTextEx(_font, "PLAY BLEND", (Vector2){col2_x + (UNIFIED_BTN_W - tw) / 2, BTN_START + 13}, FONT_SIZE - 8, 1, RAYWHITE);
        }

        // Blend slider
        blend_released = 0;
        draw_blend_slider(col2_x, blend_slider_y1, UNIFIED_BTN_W, blend_h, state.blend_t, &blend_released);

        // Scene buttons
        {
            Color btn_color = (mx >= gx && mx <= gx + gw && my >= gy && my <= gy + gh) ?
                               (Color){120, 120, 180, 255} : (Color){100, 100, 160, 255};
            DrawRectangle(gx, gy, gw, gh, btn_color);
            DrawRectangleLinesEx((Rectangle){gx, gy, gw, gh}, 1, DARKGRAY);
            DrawTextEx(_font, "SAVE SCENE", (Vector2){gx + 10, gy + 13}, FONT_SIZE - 10, 1, RAYWHITE);

            btn_color = (mx >= gx + gw + gap && mx <= gx + gw + gap + gw && my >= gy && my <= gy + gh) ?
                          (Color){120, 120, 180, 255} : (Color){100, 100, 160, 255};
            DrawRectangle(gx + gw + gap, gy, gw, gh, btn_color);
            DrawRectangleLinesEx((Rectangle){gx + gw + gap, gy, gw, gh}, 1, DARKGRAY);
            DrawTextEx(_font, "LOAD SCENE", (Vector2){gx + gw + gap + 10, gy + 13}, FONT_SIZE - 10, 1, RAYWHITE);

            btn_color = (mx >= gx && mx <= gx + gw && my >= gy + gh + gap && my <= gy + gh + gap + gh) ?
                          (Color){120, 120, 180, 255} : (Color){100, 100, 160, 255};
            DrawRectangle(gx, gy + gh + gap, gw, gh, btn_color);
            DrawRectangleLinesEx((Rectangle){gx, gy + gh + gap, gw, gh}, 1, DARKGRAY);
            DrawTextEx(_font, "EXPORT BLEND", (Vector2){gx + 10, gy + gh + gap + 13}, FONT_SIZE - 10, 1, RAYWHITE);
        }

        // Visualization area
        if (state.wave_valid) {
            int viz_y = sh - 380;
            int viz_w = CENTER_W - 20;
            int viz_h = 120;
            int spec_h = viz_h * 2;
            int viz_x = CENTER_X + 10;

            vis_draw_waveform(&state.last_wave, viz_x, viz_y, viz_w, viz_h);
            DrawTextEx(_font, "Waveform", (Vector2){viz_x, viz_y - 20}, 16, 1, DARKGRAY);

            vis_draw_spectrogram_full(&state.last_wave, viz_x, viz_y + viz_h + 10, viz_w, spec_h);
            DrawTextEx(_font, "Spectrogram", (Vector2){viz_x, viz_y + viz_h + 10 - 20}, 16, 1, DARKGRAY);
        }

        EndDrawing();
    }

    // Save config and last scene
    state.config.volume = state.global_volume;
    state.config.autoplay = state.play_on_gen;
    config_save(&state.config);
    config_save_scene(state.params_l, state.params_r, state.blend_t);

    if (state.sound_loaded) UnloadSound(state.sound);
    if (state.wave_valid) bfxr_wave_free(&state.last_wave);
    if (gen_job.result.num_samples > 0) bfxr_wave_free(&gen_job.result);
    vis_clear_cache();
    if (_font.texture.id) UnloadFont(_font);
    CloseAudioDevice();
    CloseWindow();
    return 0;
}
