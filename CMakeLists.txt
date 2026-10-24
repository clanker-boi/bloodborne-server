cmake_minimum_required(VERSION 3.24)

# SPDX-License-Identifier: GPL-2.0-or-later
# The root project is the build graph; Python/CI/Docker only invoke it.
project(YharnamTogether LANGUAGES C CXX)

set(YT_COMPONENT "server" CACHE STRING "Build component: server, native, or all")
set_property(CACHE YT_COMPONENT PROPERTY STRINGS server native all)
option(YT_ENABLE_TESTS "Build and register tests" ON)
option(YT_USE_CONAN "Use the Conan dependency graph" ON)

if(NOT YT_COMPONENT MATCHES "^(server|native|all)$")
    message(FATAL_ERROR "YT_COMPONENT must be server, native, or all")
endif()

# Bloodborne's executable is x86_64 code; this guard only applies to the native client.
if(YT_COMPONENT MATCHES "^(native|all)$")
    string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _yt_cpu)
    if(NOT _yt_cpu MATCHES "^(x86_64|amd64|x64)$")
        message(FATAL_ERROR
            "Native Bloodborne client requires x86_64; server builds support additional architectures.")
    endif()
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
include(CTest)
if(NOT YT_ENABLE_TESTS)
    set(BUILD_TESTING OFF CACHE BOOL "Disable CTest targets" FORCE)
endif()

if(YT_COMPONENT MATCHES "^(server|all)$")
    add_subdirectory(server)
endif()

if(YT_COMPONENT MATCHES "^(native|all)$")
    # The game's graphics and native runtime are already a CMake project.
    # Keep target definitions there rather than reimplementing its flags in a wrapper.
    add_subdirectory(bbport/gpu)
endif()

message(STATUS "Yharnam Together component: ${YT_COMPONENT}")
