"""Conan 2 dependency graph for the authoritative CMake build.

Dependencies are architecture-aware. protoc runs in the BUILD context;
its linked protobuf library is in the HOST context, including cross builds.
"""
from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMakeConfigDeps, cmake_layout


class YharnamTogetherConan(ConanFile):
    name = "yharntogether-build"
    version = "0.1"
    settings = "os", "arch", "compiler", "build_type"
    options = {"with_server": [True, False], "with_native": [True, False]}
    default_options = {
        "with_server": True,
        "with_native": False,
        "qt/*:shared": True,
        "qt/*:gui": False,
        "qt/*:widgets": False,
        "qt/*:qthttpserver": True,
    }

    def requirements(self):
        # Same protobuf version for the server and native game's wire protocol.
        self.requires("protobuf/5.29.6")
        if self.options.with_server:
            self.requires("qt/6.8.3")
        # Native renderer requirements are not yet fully Conan-managed.
        # The root CMake build currently resolves its other packages from the
        # selected host toolchain (MSYS2 CLANG64 / Linux distribution).

    def build_requirements(self):
        # Never attempt to execute a target-architecture protoc during a cross build.
        self.tool_requires("protobuf/5.29.6")

    def layout(self):
        cmake_layout(self)

    def generate(self):
        toolchain = CMakeToolchain(self, generator="Ninja")
        toolchain.variables["YT_USE_CONAN"] = True
        toolchain.generate()
        CMakeConfigDeps(self).generate()
