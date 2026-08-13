#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail

usage() {
    cat <<'EOF'
Configure and build libavoid and its pybind11 extension with CMake.

Usage:
  ./build_libavoid_py11.sh [adaptagrams-directory]

Environment overrides:
  PYTHON          Python executable passed to CMake (default: python3)
  CXX             C++ compiler passed to CMake (optional)
  CMAKE_BUILD_DIR Build directory (default: <project>/build)
  CMAKE_GENERATOR CMake generator (optional)
  CMAKE_BUILD_TYPE Build type for single-config generators (default: Release)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ADAPTAGRAMS_DIR=${1:-"$ROOT_DIR/adaptagrams"}
BUILD_DIR=${CMAKE_BUILD_DIR:-"$ROOT_DIR/build"}
PYTHON=${PYTHON:-python3}
BUILD_TYPE=${CMAKE_BUILD_TYPE:-Release}

die() {
    printf 'error: %s\n' "$1" >&2
    exit 2
}

command -v cmake >/dev/null || die "CMake was not found"
command -v "$PYTHON" >/dev/null || die "Python executable not found: $PYTHON"

cmake_args=(
    -S "$ROOT_DIR"
    -B "$BUILD_DIR"
    "-DPython3_EXECUTABLE=$PYTHON"
    "-DOPCDIAGGEN_ADAPTAGRAMS_DIR=$ADAPTAGRAMS_DIR"
)
if [[ -n "${CXX:-}" ]]; then
    cmake_args+=("-DCMAKE_CXX_COMPILER=$CXX")
fi
if [[ -n "${CMAKE_GENERATOR:-}" ]]; then
    cmake_args+=("-G" "$CMAKE_GENERATOR")
fi

cmake "${cmake_args[@]}"
cmake --build "$BUILD_DIR" --config "$BUILD_TYPE" --parallel

printf 'built libavoid and pybind11 extension in %s\n' "$BUILD_DIR"
