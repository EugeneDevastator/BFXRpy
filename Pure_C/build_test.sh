#!/bin/bash
cd "$(dirname "$0")"
echo "==================================="
echo "bfxrc - Build Test"
echo "==================================="

# Build CLI (no raylib needed)
echo "Building CLI..."
gcc -O2 -Wall -Wextra -o bfxrc main.c bfxr_params.c bfxr_generator.c bfxr_wav.c bfxr_file.c -lm 2>&1

if [ -f bfxrc ]; then
    echo "CLI build: OK"
    echo "Testing..."
    ./bfxrc random test.wav 2>&1
    if [ -f test.wav ]; then
        echo "Test: OK (test.wav created, $(ls -la test.wav | awk '{print $5}') bytes)"
        rm -f test.wav
    fi
else
    echo "CLI build: FAILED"
    exit 1
fi

# Check for raylib and build GUI if available
if [ -f "raylib/include/raylib.h" ] && [ -f "raylib/src/libraylib.a" ]; then
    echo ""
    echo "Building GUI..."
    gcc -O2 -Wall -Wextra -o bfxrc_gui gui.c bfxr_params.c bfxr_generator.c bfxr_wav.c bfxr_file.c \
        -I"$(pwd)/raylib/include" -L"$(pwd)/raylib/src" -lraylib -lm -lpthread -ldl -lrt 2>&1
    if [ -f bfxrc_gui ]; then
        echo "GUI build: OK"
    else
        echo "GUI build: FAILED"
    fi
else
    echo ""
    echo "GUI build skipped (raylib not found or not built)"
    echo "To build GUI on Linux:"
    echo "  1. cd raylib/src"
    echo "  2. make PLATFORM=PLATFORM_DESKTOP"
    echo "  3. Re-run this script"
fi

echo ""
echo "Done."
