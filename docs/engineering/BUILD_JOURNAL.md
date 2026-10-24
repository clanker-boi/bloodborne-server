# Build and verification journal (append-only)

Record **every meaningful build attempt** here: UTC date, commit SHA,
runner OS/architecture, exact command, output/error, artifacts and follow-up.
Append the result; don't erase failed experiments.

## 2026-10-24 — initial build-system audit

**Source:** fork `clanker-boi/bloodborne-server`; branch
`build/modern-toolchain-conan-docker`, based on
`08e56cd82c5cfafa76200946f3e08d1616108deb`.

**Observed:** Server has CMake+Qt+vendored Protobuf; native Windows game
loader is built from GPU CMake; Linux loader and tooling are hand-compiled
from Bash; release is Windows PowerShell plus a separate MSYS2 packaging
step. This explains why root replacement is preferable to wrappers.

**Implemented:** root CMake, Conan recipe, `tools/yt.py`, server Conan
Protobuf linking, Dockerfile/Buildx entry, AMD64/ARM64 CI, docs.

**Validation:** `python -m compileall` and CMake configure are planned;
no successful Conan-driven server build has yet been observed.

**GitHub Actions triggered:**
- Push: https://github.com/clanker-boi/bloodborne-server/actions/runs/40134041041
- Pull request: https://github.com/clanker-boi/bloodborne-server/actions/runs/40134060300
- Job definitions: `.github/workflows/build-modern.yml` (Ubuntu 24.04 x64 and ARM64)

**Result at this checkpoint:** RUNNING; not passed. GitHub runner provides
a real compiler and dependency/network access. Local analysis container
does not have Conan, Qt, Docker or repository network access, so local
execution alone cannot establish full-build success. Capture CI logs and
remediate failures on branch.

**Known review concerns:** Qt Conan source build size, duplicated
`qt` tool dependencies, platform-specific native loader not yet under
root graph, provisional packaging, and lack of lockfile.

**Next:** inspect completed Actions jobs, fix reproducibly, rerun,
document exact failures and passing commit SHA.

## 2026-10-24 — first completed Linux AMD64 CI attempt: FAIL at CMake configure

**Actual run:** https://github.com/clanker-boi/bloodborne-server/actions/runs/40134041041
(job `120991651609`, Linux AMD64, initial experimental build at commit
`5e9f94d4eec13a40c4bc27161c36934ebfb3e5b8`).

**Command:** `python3 tools/yt.py configure server` (invokes Conan 2
`install --build=missing`, then root CMake).

**What succeeded:** GitHub runner checked out source and installed Conan;
Conan downloaded the Protobuf 5.29.6 package and compiled Qt 6.8.3
with HttpServer enabled. CMake found the Conan-provided Qt6 modules.

**Observed failure (verbatim diagnostic fragment):**
```text
CMake Error at server/CMakeLists.txt:25 (find_package):
  Could not find a package configuration file provided by "Protobuf"
  with any of the following names:
    ProtobufConfig.cmake
    protobuf-config.cmake
```

**Root cause:** Conan `CMakeConfigDeps` exposes this recipe as
`find_package(protobuf)` (lower-case, as the Conan install generator
explicitly prints). Root server CMake incorrectly requested
`find_package(Protobuf CONFIG REQUIRED)` and thus found no package.

**Corrective commit:** `6f1842dd26728d9c5d620370c127544a56f8637f`,
changing the Conan path to `find_package(protobuf CONFIG REQUIRED)`.
The recipe's `protobuf::libprotobuf` component target is correct per
Conan Center's package definition; `protobuf::protoc` is expected
from the build context and must be verified in the next run.

**Performance observation:** Qt Conan had no matching binary package for
the exact minimal/headless HttpServer build options, downloaded about
995 MB of Qt source and built ~687 Qt targets. A warm cache is essential.
Workflow now uses architecture-specific `actions/cache@v4` for Conan
(`e18e67a6b1d533ff0a3e9fad7d5c3897a7e3e893`), but the new cache
has not been proven to hit yet.

**Outcome:** FAILURE recorded, no executable produced by this run.
ARM64 companion run remained under Conan configuration at last check.
Next: inspect a CI run on commit with the lowercase find_package fix,
fix any further target/config errors, compile/link/test shadnet.
