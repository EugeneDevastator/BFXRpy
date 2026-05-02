#!/bin/bash
# Build script for bfxrc using CMake
# Works on MSYS2/MinGW and Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

# Parse arguments
BUILD_TYPE=${1:-Release}
CLEAN=${2:-}

if [[ "$CLEAN" == "clean" ]]; then
    echo "Cleaning build directory..."
    rm -rf "${BUILD_DIR}"
fi

# Create build directory
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# Detect if we're on Windows/MSYS2 and configure accordingly
if [[ -n "$MSYSTEM" ]]; then
    echo "Detected MSYS2 environment: $MSYSTEM"
    GENERATOR="MinGW Makefiles"
    # MSYS2/MinGW already has correct CC/CXX in PATH
    unset CC CXX
else
    GENERATOR="Unix Makefiles"
fi

# Configure
echo "Configuring with CMake (Build Type: ${BUILD_TYPE})..."
cmake -G "${GENERATOR}" \
    -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
    "${SCRIPT_DIR}"

# Build
echo "Building..."
cmake --build . --config ${BUILD_TYPE} -- -j$(nproc 2>/dev/null || echo 4)

echo ""
echo "Build complete!"
echo "Executables in: ${SCRIPT_DIR}"
ls -la "${SCRIPT_DIR}"/*.exe "${SCRIPT_DIR}"/*bfxr* 2>/dev/null || true
