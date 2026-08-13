cmake_minimum_required(VERSION 3.20)
project(opcdiaggen_native LANGUAGES CXX)

include(FetchContent)

option(OPCDIAGGEN_FETCH_DEPENDENCIES
       "Fetch Adaptagrams and pybind11 when they are not available locally"
       ON)
set(OPCDIAGGEN_ADAPTAGRAMS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/adaptagrams"
    CACHE PATH "Adaptagrams checkout containing the cola directory")
set(OPCDIAGGEN_ADAPTAGRAMS_TAG "master"
    CACHE STRING "Adaptagrams Git tag, branch, or commit used by FetchContent")
set(OPCDIAGGEN_PYBIND11_TAG "v2.13.6"
    CACHE STRING "pybind11 Git tag used by FetchContent")

find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)

if(EXISTS "${OPCDIAGGEN_ADAPTAGRAMS_DIR}/cola/libavoid/libavoid.h")
    set(OPCDIAGGEN_COLA_DIR "${OPCDIAGGEN_ADAPTAGRAMS_DIR}/cola")
elseif(OPCDIAGGEN_FETCH_DEPENDENCIES)
    FetchContent_Declare(
        adaptagrams
        GIT_REPOSITORY https://github.com/mjwybrow/adaptagrams.git
        GIT_TAG ${OPCDIAGGEN_ADAPTAGRAMS_TAG}
        GIT_SHALLOW TRUE
    )
    FetchContent_GetProperties(adaptagrams)
    if(NOT adaptagrams_POPULATED)
        FetchContent_Populate(adaptagrams)
    endif()
    set(OPCDIAGGEN_COLA_DIR "${adaptagrams_SOURCE_DIR}/cola")
else()
    message(FATAL_ERROR
        "Adaptagrams not found. Set OPCDIAGGEN_ADAPTAGRAMS_DIR or enable "
        "OPCDIAGGEN_FETCH_DEPENDENCIES.")
endif()

if(NOT EXISTS "${OPCDIAGGEN_COLA_DIR}/libavoid/libavoid.h")
    message(FATAL_ERROR "libavoid headers not found in ${OPCDIAGGEN_COLA_DIR}")
endif()

if(NOT TARGET pybind11::headers)
    find_package(pybind11 CONFIG QUIET)
endif()
if(NOT TARGET pybind11::headers AND OPCDIAGGEN_FETCH_DEPENDENCIES)
    FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11.git
        GIT_TAG ${OPCDIAGGEN_PYBIND11_TAG}
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(pybind11)
endif()
if(NOT TARGET pybind11::headers)
    message(FATAL_ERROR
        "pybind11 not found. Install it or enable OPCDIAGGEN_FETCH_DEPENDENCIES.")
endif()

set(OPCDIAGGEN_LIBAVOID_SOURCES
    connectionpin.cpp
    connector.cpp
    connend.cpp
    geometry.cpp
    geomtypes.cpp
    graph.cpp
    junction.cpp
    makepath.cpp
    obstacle.cpp
    orthogonal.cpp
    router.cpp
    shape.cpp
    timer.cpp
    vertices.cpp
    viscluster.cpp
    visibility.cpp
    vpsc.cpp
    hyperedge.cpp
    hyperedgeimprover.cpp
    mtst.cpp
    hyperedgetree.cpp
    scanline.cpp
    actioninfo.cpp
)
list(TRANSFORM OPCDIAGGEN_LIBAVOID_SOURCES
     PREPEND "${OPCDIAGGEN_COLA_DIR}/libavoid/")

add_library(libavoid STATIC ${OPCDIAGGEN_LIBAVOID_SOURCES})
target_include_directories(libavoid PUBLIC "${OPCDIAGGEN_COLA_DIR}")
target_compile_features(libavoid PUBLIC cxx_std_11)
set_target_properties(libavoid PROPERTIES POSITION_INDEPENDENT_CODE ON)
if(MSVC)
    target_compile_definitions(libavoid PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

pybind11_add_module(_libavoid_py11 MODULE libavoid_py11.cpp)
target_link_libraries(_libavoid_py11 PRIVATE libavoid)
target_include_directories(_libavoid_py11 PRIVATE "${OPCDIAGGEN_COLA_DIR}")
target_compile_features(_libavoid_py11 PRIVATE cxx_std_11)
set_target_properties(_libavoid_py11 PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
)

install(TARGETS _libavoid_py11
        LIBRARY DESTINATION .
        RUNTIME DESTINATION .)
