#ifndef BFXR_FILE_H
#define BFXR_FILE_H

#include "bfxr_params.h"
#include <stdio.h>

int bfxr_save_preset(const char* filename, const double params[NUM_PARAMS]);
int bfxr_load_preset(const char* filename, double params[NUM_PARAMS]);

#endif
