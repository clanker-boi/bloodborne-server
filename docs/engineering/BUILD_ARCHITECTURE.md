# Build architecture and migration strategy

## One authority, multiple execution environments

```text
                   developer CLI (thin)
                             |
      GitHub Actions / Buildx / local terminals (same commands)
                             |
                    Root CMake targets
                   /       |        \
          shadnet server  native bbport  emulator (future/optional)
                    \       |        /
            Conan 2 build/host dependency graph
                  + reproducible lockfiles
```

**CMake** owns target sources/defines/link dependencies/generation,
**Conan** owns third-party versions and transitive dependency resolution.
Python CLI validates inputs, invokes Conan/CMake/CTest and reports results;
it must not independently compile files or maintain an alternate copy
of build flags. Docker and CI are executors, not alternative build systems.

## What the original project actually does

- `server/CMakeLists.txt`: Qt6 (Core/Network/Sql/Concurrent/HttpServer),
  C++20, Protobuf generation from `server/src/shadnet.proto` and
  `server/coop/coop.proto`, tests excluded from the ordinary build.
- `bbport/gpu/CMakeLists.txt`: renderer and co-op dependencies (including
  source files from `emulator/src` and `server/coop`), shader generation;
  on Windows also builds `bb-probe`, `bb-play` and GPU probe tools.
- `bbport/build.sh`: invokes GPU CMake on both platforms, but on Linux
  additionally compiles the native loader and tools with direct C compiler
  commands. This must be modeled as proper build targets.
- `emulator/CMakeLists.txt`: separate large CMake project, currently
  substantial set of Git submodules.
- `tools/build-server.ps1`, `tools/build-bbport.ps1` and
  `tools/make-release.ps1`: Windows-specific orchestration, environment
  bootstrapping, packaging, game-data handling and installer creation.
- `server/src/main.cpp`: a headless `QCoreApplication`; server can run
  independently, with an optional watchdog and integrated backend.

## Dependency policy

1. Conan 2 throughout the supported build. Host profiles specify
   OS/CPU/compiler/ABI; build profiles specify where tools actually run.
2. Generated code (including Protobuf) is produced **at build time**
   in the binary tree, never checked in and never generated in-source.
3. Protobuf version and wire compatibility are shared between client and
   server. The `protoc` executable is a build-machine tool;
   `libprotobuf` is a host/target library.
4. Qt must provide required modules, especially HttpServer and SQLite
   driver. Verify available Conan configurations, linking and runtime
   plugin deployment. Do not assume a Qt package works merely because
   Conan resolved its graph.
5. Source patches for FSR, graphics extensions, submodules and proprietary
   SDK interfaces need explicit pinned, auditable stages.
6. No implicit network access during compilation or test execution.
   Dependencies may be downloaded only during a declared fetch/install
   step; lockfile, SHA and licenses must be preserved.

## Architecture/platform truth table

| Artifact | Windows AMD64 | Linux AMD64 | Linux ARM64 |
| --- | --- | --- | --- |
| Headless server | intended | CI target, **unverified** | CI target, **unverified** |
| Native game runtime | current upstream | current upstream | unsupported (x86-64 game code) |
| Full fork build with new root system | incomplete | incomplete | server only |
| Docker builder | intended | prototype | prototype |
| Windows player installer | legacy scripts | N/A | N/A |

This table describes **actual migration progress**, not what upstream
can do or what the underlying dependencies could theoretically support.

## Build-performance requirements

- Out-of-tree, incremental CMake/Ninja; don't delete the build directory
  on every command.
- BuildKit cache mounts for Conan package downloads, compiler cache where
  stable, no hard-coded `--parallel 24`.
- Use generated dependency files and incremental host shader generation.
- Build graph should permit `server` without downloading the renderer's
  huge Git submodules or proprietary assets.
- Use separate cache keys across host architecture, compiler version,
  dependency lockfile, build profile and config.
- Build-time dependency tools such as `protoc` must not execute a target
  ARM64 binary on an x86_64 machine.

## Source/release boundaries

Game dumps, game executable, textures and decrypted game files are never
committed or fetched by the build. Server unit/integration tests must run
without game files. End-to-end gameplay checks are an opt-in separate job.
GPU SDK DLLs and other licensed redistributables must be acquired and
packaged only in license-compliant workflows.

## Definition of done

A PR labeled 'migration complete' must prove Gate S, Gate N and Gate R
from STATUS.md, using links to successful jobs and reproducible commands.
The original scripts can disappear only after all feature-relevant targets
have equivalent supported build/test/package paths. No unverified promises.
