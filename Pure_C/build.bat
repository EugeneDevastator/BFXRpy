@echo off
echo Building bfxrc with raylib 6.0...
set RAYLIB_DIR=%cd%\raylib

if not exist "%RAYLIB_DIR%\include\raylib.h" (
    git clone --depth 1 --branch 6.0 https://github.com/raysan5/raylib.git "%RAYLIB_DIR%"
)

if not exist "%RAYLIB_DIR%\src\libraylib.a" (
    cd "%RAYLIB_DIR%\src"
    make PLATFORM=PLATFORM_DESKTOP
    cd /d "%~dp0"
)

gcc -O2 -Wall -Wextra -o bfxrc.exe main.c bfxr_params.c bfxr_generator.c bfxr_wav.c bfxr_file.c -I"%RAYLIB_DIR%\include" -L"%RAYLIB_DIR%\src" -lraylib -lgdi32 -lwinmm -lole32

gcc -O2 -Wall -Wextra -o bfxrc_gui.exe gui.c bfxr_params.c bfxr_generator.c bfxr_wav.c bfxr_file.c -I"%RAYLIB_DIR%\include" -L"%RAYLIB_DIR%\src" -lraylib -lgdi32 -lwinmm -lole32

if exist bfxrc.exe echo SUCCESS: bfxrc.exe
if exist bfxrc_gui.exe echo SUCCESS: bfxrc_gui.exe
pause
