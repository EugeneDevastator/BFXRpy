@echo off
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
if exist bfxrc.exe echo SUCCESS: bfxrc.exe
if exist bfxrc_gui.exe echo SUCCESS: bfxrc_gui.exe
