# Build system v2 (experimental migration branch)

This branch introduces one developer-facing build interface, `tools/yt.py`.
The root CMake project owns the build graph, while Conan 2 owns dependencies.
Docker and CI execute the same commands; they do not carry alternate build
logic. Compilation is incremental; clean operations must be explicit.

## Start here

Prerequisites: Python 3.10+, CMake 3.24+, Ninja, Conan 2.33+, C/C++ toolchain,
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

## Fast CI / local workflows

Dependency compilation and application compilation are separate steps now:

```sh
# Once per dependency graph change or new Conan cache:
python3 tools/yt.py deps server --build-policy missing
# Save binary packages before changing application code or launching CTests.
python3 tools/yt.py prune-conan

# On a fresh runner with prebuilt Conan cache (no dependency source builds):
python3 tools/yt.py deps server --build-policy never

# A single root CMake graph with fast Linux mold linking, sccache and bounded Ninja:
python3 tools/yt.py configure server --reuse-deps --linker mold --sccache \
    --compile-jobs 4 --link-jobs 1
python3 tools/yt.py build server --jobs 4 --ninja-stats
python3 tools/yt.py test server --jobs 4 --ninja-stats
```

Install mold and sccache before requesting them. Other linker values are
`default` and `lld`; nondefault linker selection is currently Linux-only.
Without `--reuse-deps`, `configure` performs dependency installation for
convenient local development. On CI the `deps` and `prune-conan` steps
must be completed before the independent cache/save action.

`prune-conan` deletes downloaded recipe archives and temporary
dependency source/build trees **but preserves installed binaries**. Never
run it concurrently with an active Conan installation. Cache keys need
to include OS, architecture, Conan version, ABI and dependency graph.
CI currently uses Conan 2.33.0 and builds the application via Ninja.
See [engineering/BUILD-PERFORMANCE.md](engineering/BUILD-PERFORMANCE.md).

## Platform matrix (intended, not yet fully validated)

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
