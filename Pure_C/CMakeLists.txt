cmake_minimum_required(VERSION 3.16)
project(bfxrc C)

set(CMAKE_C_STANDARD 11)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

include_directories(${CMAKE_CURRENT_SOURCE_DIR})

set(COMMON_SRCS
	os_util.c
    bfxr_params.c
    bfxr_generator.c
    bfxr_wav.c
    bfxr_file.c
    bfxr_fft.c
    bfxr_config.c
    ini.c
)

add_executable(bfxr main.c ${COMMON_SRCS})

set(GUI_SRCS
    gui.c
    bfxr_ui.c
    bfxr_vis.c
    ${COMMON_SRCS}
)

add_executable(bfxr_gui ${GUI_SRCS})

# --- Pre-built raylib 6.0 ---
include(FetchContent)

FetchContent_Declare(
    raylib_prebuilt
    URL https://github.com/raysan5/raylib/releases/download/6.0/raylib-6.0_win64_mingw-w64.zip
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(raylib_prebuilt)

set(RAYLIB_DIR ${raylib_prebuilt_SOURCE_DIR})

target_include_directories(bfxr_gui PRIVATE ${RAYLIB_DIR}/include)

target_link_libraries(bfxr_gui PRIVATE
    ${RAYLIB_DIR}/lib/libraylib.a
    gdi32 winmm opengl32 pthread
)

set_target_properties(bfxr bfxr_gui
    PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)
