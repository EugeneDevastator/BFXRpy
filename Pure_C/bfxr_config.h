#ifndef BFXR_CONFIG_H
#define BFXR_CONFIG_H

#include "bfxr_params.h"

typedef struct {
    float volume;
    int autoplay;
    // Spectrogram colors (3 gradient stops with r,g,b)
    float grad_r[3];
    float grad_g[3];
    float grad_b[3];
    float grad_t[3];
} BfxrConfig;

void config_load(BfxrConfig* cfg);
void config_save(const BfxrConfig* cfg);

void config_load_scene(double params[NUM_PARAMS]);
void config_save_scene(const double params[NUM_PARAMS]);

#endif
