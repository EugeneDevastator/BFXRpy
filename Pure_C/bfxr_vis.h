#ifndef BFXR_VIS_H
#define BFXR_VIS_H

#include "bfxr_generator.h"
#include "raylib.h"

void vis_draw_waveform(const BfxrWave* wave, int x, int y, int w, int h);
void vis_draw_spectrogram_full(const BfxrWave* wave, int x, int y, int w, int h);
void vis_clear_cache(void);

#endif
