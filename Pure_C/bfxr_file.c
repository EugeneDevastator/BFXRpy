#include "bfxr_file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int bfxr_save_preset(const char* filename, const double params[NUM_PARAMS]) {
    FILE* fp = fopen(filename, "w");
    if (!fp) return -1;
    for (int i = 0; i < NUM_PARAMS; i++) {
        fprintf(fp, "%.6f\n", params[i]);
    }
    fclose(fp);
    return 0;
}

int bfxr_load_preset(const char* filename, double params[NUM_PARAMS]) {
    FILE* fp = fopen(filename, "r");
    if (!fp) return -1;
    for (int i = 0; i < NUM_PARAMS; i++) {
        if (fscanf(fp, "%lf", &params[i]) != 1) {
            fclose(fp);
            return -1;
        }
    }
    fclose(fp);
    return 0;
}
