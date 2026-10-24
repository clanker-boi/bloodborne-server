cmake_minimum_required(VERSION 3.24)

# SPDX-License-Identifier: GPL-2.0-or-later
# Root CMake is the build authority; CI, containers and tools invoke its targets.
project(YharnamTogether LANGUAGES C CXX)

set(YT_COMPONENT "server" CACHE STRING "Build component: server, native, or all")
set_property(CACHE YT_COMPONENT PROPERTY STRINGS server native all)
option(YT_ENABLE_TESTS "Build and register tests" ON)
option(YT_USE_CONAN "Use the Conan dependency graph" ON)

if(NOT YT_COMPONENT MATCHES "^(server|native|all)$")
    message(FATAL_ERROR "YT_COMPONENT must be server, native, or all")
endif()

# Windows game executables and hooks are x86_64. ARM64 is supported by the
# standalone server, not by the native game runtime.
if(YT_COMPONENT MATCHES "^(native|all)$")
    string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _yt_cpu)
    if(NOT _yt_cpu MATCHES "^(x86_64|amd64|x64)$")
        message(FATAL_ERROR
            "Native Bloodborne client requires x86_64; server supports other architectures.")
    endif()
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
include(CTest)
if(NOT YT_ENABLE_TESTS)
    set(BUILD_TESTING OFF CACHE BOOL "Disable CTest targets" FORCE)
endif()

# Jobs are a memory budget: 4 compiles + 1 link on 4-vCPU / 16-GiB runners.
# A zero value leaves that pool unrestricted (local machine policy).
set(YT_COMPILE_JOBS "0" CACHE STRING "Maximum concurrent Ninja compile jobs, 0=unrestricted")
set(YT_LINK_JOBS "0" CACHE STRING "Maximum concurrent Ninja link jobs, 0=unrestricted")
foreach(_yt_var IN ITEMS YT_COMPILE_JOBS YT_LINK_JOBS)
    if(NOT ${_yt_var} MATCHES "^[0-9]+$")
        message(FATAL_ERROR "${_yt_var} must be a nonnegative integer")
    endif()
endforeach()
if(CMAKE_GENERATOR MATCHES "Ninja")
    set(_yt_pools "")
    if(YT_COMPILE_JOBS GREATER 0)
        list(APPEND _yt_pools "yt_compile=${YT_COMPILE_JOBS}")
        set(CMAKE_JOB_POOL_COMPILE yt_compile)
    endif()
    if(YT_LINK_JOBS GREATER 0)
        list(APPEND _yt_pools "yt_link=${YT_LINK_JOBS}")
        set(CMAKE_JOB_POOL_LINK yt_link)
    endif()
    if(_yt_pools)
        set_property(GLOBAL PROPERTY JOB_POOLS ${_yt_pools})
    endif()
endif()

# Configure-time feature switch; never change the linker mid-build silently.
set(YT_LINKER "default" CACHE STRING "Linker: default, mold or lld (Linux/ELF)")
set_property(CACHE YT_LINKER PROPERTY STRINGS default mold lld)
if(NOT YT_LINKER MATCHES "^(default|mold|lld)$")
    message(FATAL_ERROR "YT_LINKER must be default, mold or lld")
endif()
if(NOT YT_LINKER STREQUAL "default")
    if(WIN32 OR APPLE)
        message(FATAL_ERROR "Nondefault linker selection is currently verified only on Linux")
    endif()
    # Check compiler driver integration rather than relying on executable name
    # and hoping a mold/lld symlink is correctly installed.
    include(CheckLinkerFlag)
    check_linker_flag(CXX "-fuse-ld=${YT_LINKER}" YT_REQUESTED_LINKER_WORKS)
    if(NOT YT_REQUESTED_LINKER_WORKS)
        message(FATAL_ERROR "Compiler does not support -fuse-ld=${YT_LINKER}; install the linker or select default")
    endif()
    add_link_options("-fuse-ld=${YT_LINKER}")
endif()

if(YT_COMPONENT MATCHES "^(server|all)$")
    add_subdirectory(server)
endif()
if(YT_COMPONENT MATCHES "^(native|all)$")
    add_subdirectory(bbport/gpu)
endif()

message(STATUS "Yharnam Together: ${YT_COMPONENT}, linker=${YT_LINKER}, compile jobs=${YT_COMPILE_JOBS}, link jobs=${YT_LINK_JOBS}")
