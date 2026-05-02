cmake_minimum_required(VERSION 3.16)
project(bfxrc C)

set(CMAKE_C_STANDARD 11)

# Set default build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Platform detection
if(WIN32 OR MINGW OR MSYS)
    set(PLATFORM_WINDOWS TRUE)
    add_definitions(-DPLATFORM_DESKTOP -DGRAPHICS_API_OPENGL_33)
else()
    set(PLATFORM_LINUX TRUE)
endif()

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/raylib/src)

# Source files (common)
set(COMMON_SRCS
    bfxr_params.c
    bfxr_generator.c
    bfxr_wav.c
    bfxr_file.c
    bfxr_fft.c
)

# CLI executable
add_executable(bfxr main.c ${COMMON_SRCS})

# GUI executable sources
set(GUI_SRCS
    gui.c
    bfxr_ui.c
    bfxr_vis.c
    ${COMMON_SRCS}
)

add_executable(bfxr_gui ${GUI_SRCS})

# raylib - build from source
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/raylib/CMakeLists.txt)
    # Build raylib as subdirectory
    set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(BUILD_GAMES OFF CACHE BOOL "" FORCE)
    add_subdirectory(raylib)
    target_link_libraries(bfxr_gui raylib)
else()
    # Link against pre-built raylib
    find_library(RAYLIB_LIB raylib PATHS ${CMAKE_CURRENT_SOURCE_DIR}/raylib/src)
    if(RAYLIB_LIB)
        target_link_libraries(bfxr_gui ${RAYLIB_LIB})
    else()
        message(FATAL_ERROR "raylib not found. Please ensure raylib/ directory exists.")
    endif()
endif()

# Platform-specific libraries
if(PLATFORM_WINDOWS)
    target_link_libraries(bfxr_gui gdi32 winmm opengl32 pthread)
    # CLI doesn't need raylib
else()
    target_link_libraries(bfxr_gui m pthread dl rt X11)
    target_link_libraries(bfxr m)
endif()

# Set output directories
set_target_properties(bfxr bfxr_gui
    PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)

# Copy DLLs on Windows (if needed)
if(PLATFORM_WINDOWS)
    add_custom_command(TARGET bfxr_gui POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
        $<TARGET_FILE:raylib>
        $<TARGET_FILE_DIR:bfxr_gui>
        DEPENDS raylib
    )
endif()
