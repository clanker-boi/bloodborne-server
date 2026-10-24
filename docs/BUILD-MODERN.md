# Build system v2 (experimental migration branch)

This branch introduces one developer-facing build interface, `tools/yt.py`.
The root CMake project owns the build graph, while Conan 2 owns dependencies.
Docker and CI execute the same commands; they do not carry alternate build
logic. Compilation is incremental; clean operations must be explicit.

## Start here

Prerequisites: Python 3.10+, CMake 3.24+, Ninja, Conan 2.31+, C/C++ toolchain,
and Git submodules initialized.

```sh
git submodule update --init --recursive
conan profile detect --force
python3 tools/yt.py configure server
python3 tools/yt.py build server
python3 tools/yt.py test server
```

Build containers (requires Docker Buildx):

```sh
bash docker/build/build.sh
```

## Platform matrix (intended, not yet validated)

| Component | Windows x86_64 | Linux x86_64 | Linux arm64 |
| --- | --- | --- | --- |
| shadnet server | Target | Target | Target |
| Native Bloodborne client | Target | Target | Unsupported: original executable is x86_64 |
| shadPS4 emulator | Separate upstream CMake target | Separate upstream CMake target | Not included in this first migration |

## Migration debt

1. Run and fix Conan server package-resolution/build tests on all targets.
2. Unify the native port loader and renderer targets under root CMake on Linux,
   replacing the hand-rolled compile/link commands in bbport/build.sh.
3. Replace MSYS2 system dependencies with Conan recipe-based requirements,
   while retaining the required compiler ABI compatibility.
4. Move game packaging and releases out of PowerShell into declarative CPack /
   Python packaging steps that consume installed target outputs.
5. Add cross-profile/host-build tests and reproducible Conan lockfiles, then
   pin toolchain versions, CI action SHAs and builder image digests.
6. Only after parity verification, delete legacy build scripts and document
   the removed entrypoints. This branch does not pretend to complete that cutover.

The server Protobuf is moved to Conan without changing shared .proto sources.
The native port's remaining dependencies are intentionally not declared as
Conan-managed until their CMake targets have been tested on each platform.

Do not run packaged builds using one server revision and different clients.
Do not redistribute any Bloodborne game data.
