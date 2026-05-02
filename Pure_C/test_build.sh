#!/bin/bash
cd "$(dirname "$0")"
echo "==================================="
echo "bfxrc - Build Test"
echo "==================================="

# Build CLI
echo "Building CLI..."
gcc -O2 -Wall -Wextra -o bfxrc main.c bfxr_params.c bfxr_generator.c bfxr_wav.c bfxr_file.c -lm 2>&1
if [ -f bfxrc ]; then
    echo "CLI: OK"
    ./bfxrc random test.wav 2>&1
    ls -la test.wav 2>/dev/null && rm test.wav
else
    echo "CLI build failed"
    exit 1
fi

# Build raylib if needed
if [ ! -f "raylib/include/raylib.h" ]; then
    echo "Cloning raylib 6.0..."
    git clone --depth 1 --branch 6.0 https://github.com/raysan5/raylib.git 2>&1 | tail -3
fi

# Build raylib
if [ -d "raylib/src" ] && [ ! -f "raylib/src/libraylib.a" ]; then
    echo "Building raylib..."
    cd raylib/src
    make PLATFORM=PLATFORM_DESKTOP 2>&1 | tail -5
    cd ../..
fi

# Build GUI
if [ -f "raylib/src/libraylib.a" ]; then
    echo "Building GUI..."
    gcc -O2 -Wall -Wextra -o bfxrc_gui gui.c bfxr_params.c bfxr_generator.c bfxr_wav.c bfxr_file.c \
        -I"$(pwd)/raylib/include" -L"$(pwd)/raylib/src" -lraylib -lm -lpthread -ldl -lrt 2>&1
    if [ -f bfxrc_gui ]; then
        echo "GUI: OK"
    else
        echo "GUI build failed"
    fi
else
    echo "Skipping GUI (raylib not available)"
fi

echo
echo "Done."
