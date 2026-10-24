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

## 2026-10-24 — corrected real Linux AMD64 and ARM64 builds PASSED

**Run:** https://github.com/clanker-boi/bloodborne-server/actions/runs/40135063503
(checked-out commit `7b834c9`, Ubuntu 24.04 standard public runners,
4 vCPU and 16 GiB RAM per architecture). Both jobs completed **success**.
Commands from the single `tools/yt.py` interface:
```sh
python3 tools/yt.py configure server
python3 tools/yt.py build server --jobs 4
python3 tools/yt.py test server --jobs 4
```
**Results:** AMD64 and ARM64 compiled and linked `shadnet`, compiled
excluded unit-test executables, and passed **16/16 CTest** each.
Tests ran in **2.61s** and **2.68s** respectively; the workflow `Test`
step (~53s and ~51s) was mainly test executable compilation.

| CI step | AMD64 | ARM64 |
| --- | ---: | ---: |
| Conan + CMake configure | 6m25s | 16m44s |
| Build server | 54s | 51s |
| Test build + CTest | 53s | 51s |
| Full job | **9m21s** | **19m19s** |

**Findings:** cold Conan Qt HttpServer dependencies dominate elapsed time.
There is now proof of a successful server build/test on both architectures,
but **no runtime headless-server smoke-test proof**, persistent-world restart,
Docker runtime image, native Windows/client build, or release-package parity.
No reason yet to spend extensive time optimizing CTest scheduling.

**Follow-up:** see [BUILD-PERFORMANCE.md](BUILD-PERFORMANCE.md) for
Ninja job pools, mold/LLD, sccache, PCH, unity and ThinLTO experiments.
Prioritize pinned precompiled Conan binary packages; don't repeatedly
compile Qt on normal PRs. Do not declare the build-system migration done.

## 2026-10-24 — initial performance implementation on branch

**Commit:** `6440248e86cbabe05dbc0b41154a54b7cbf5edbe`.
Introduced canonical Conan `deps` phase, `--reuse-deps`, `--build-policy`
(`missing` or `never`), Conan cache pruning, early `actions/cache/save`,
versioned Conan 2.33.0 in CI, sccache compiler launchers, Linux mold/LLD
linker selection, Ninja bounded compile/link job pools, timing/Ninja stats
and Python CLI unit tests. Corrected one test's sccache discovery mock
in commit `497cd562f5a0d7fcad1c650cca18538cc6d0a53d`.

**Real CI test:** https://github.com/clanker-boi/bloodborne-server/actions/runs/40137298135
on Linux AMD64 and ARM64.
Initial superseded run #40137259555 failed the CLI unit test because
its mocked configure path still checked for an actual sccache executable;
the unit test is fixed. The superseded run did not reach a compiler/linker
test and was cancelled on the corrective commit.

**State:** optimized CI still running when this entry was written;
do not claim mold/sccache, early Conan cache reuse or improved elapsed
time until the jobs finish. The unoptimized baseline remains
[run #40135063503](https://github.com/clanker-boi/bloodborne-server/actions/runs/40135063503)
(AMD64 9m21s, ARM64 19m19s, both 16/16 CTest passed).

**Next:** inspect run #40137298135 for exact stage timings, cache hit/miss,
sccache stats and 16-test result on both arches. Fix failures and compare
warm-cache run with baseline cold source compilation. Test warm cache
explicitly; one cold run cannot prove the benefit.

## 2026-10-24 — first optimized CI: AMD64 + ARM64 succeeded

**Run:** https://github.com/clanker-boi/bloodborne-server/actions/runs/40137604748
(checkout `9e89c86`, which includes the optimization implementation `6440248`
and CLI test fix `497cd56`; previous run #40137298135 was canceled when
documentation synchronized the PR).

**Both jobs completed successfully.** On Linux AMD64 and native ARM64:
- `python3 -m unittest discover -s tools/tests -v` passed.
- `python3 tools/yt.py deps server --build-policy missing` built Conan requirements.
- `python3 tools/yt.py prune-conan` removed temporary recipe sources/build trees.
- `actions/cache/save@v4` **saved Conan binaries before CMake build**.
- `python3 tools/yt.py configure server --reuse-deps --sccache --linker mold --compile-jobs 4 --link-jobs 1` passed.
- `python3 tools/yt.py build server --jobs 4 --ninja-stats` compiled and linked.
- `python3 tools/yt.py test server --jobs 4 --ninja-stats` passed 16/16 CTest.

| Measured stage | AMD64 | ARM64 |
| --- | ---: | ---: |
| Conan dependency install | 301.88s | 1016.32s |
| Conan pruning | 43.77s | 21.27s |
| CMake configure | 1.65s | 0.64s |
| Server build | 45.28s | 55.56s |
| Test build + CTest | 41.05s | 49.92s |
| Total job | 7m41s | 19m45s |
| sccache hit rate | 15.05% | 12.90% |
| Tests | 16/16 | 16/16 |

**Cache evidence:** AMD64 Conan cache had compressed size 145,659,012
bytes (about 146 MB), upload ~3 seconds. Both cache saves completed.
This is a **cold-run** result. No cache-hit improvement claimed yet.

**Follow-up:** next PR run on the identical Conan hash should restore the
cache and use `conan install --build=never`, proving that Qt source is
not compiled in regular PRs. Do not update unrelated branch files while
that run is in progress: PR synchronization cancels in-flight jobs.

## 2026-10-24 — warm cache validation: both architectures PASSED

**Run:** https://github.com/clanker-boi/bloodborne-server/actions/runs/40139233770
(commit `5f777f0`, documentation synchronization after the successful
optimized cold build). All **16/16 CTests on AMD64 and ARM64 passed**.

**Cache behavior verified from logs:**
- GitHub `actions/cache/restore@v4` restored Conan binaries from the exact previous key;
  AMD64 archive **145,659,012 bytes (~146 MB)**, ARM64 archive
  **210,645,227 bytes (~211 MB)**.
- `python3 tools/yt.py deps server --build-policy never` completed
  successfully in **1.12s AMD64 / 0.84s ARM64**.
- The cache-miss `--build=missing` phase was skipped; no Qt source
  compilation occurred.
- `sccache` reported **92 hits / 93 requests (98.92%)** on both
  architectures, with no cache errors reported.

| Warm stage | AMD64 | ARM64 |
| --- | ---: | ---: |
| Conan deps (`--build=never`) | 1.12s | 0.84s |
| CMake configure with mold | 0.94s | 3.08s |
| Full project build | 7.32s | 8.70s |
| Test binaries + CTest | 7.17s | 7.58s |
| Full GitHub Actions job | **51s** | **60s** |
| CTest | 16/16 passed | 16/16 passed |

**Comparison to optimized cold job #40137604748:** AMD64
7m41s -> **51s** (~9.0x); ARM64 19m45s -> **60s**
(~19.8x). These are actual wall-clock jobs, not projections.
Application code was unchanged between runs, which maximized sccache
hits; normal source changes will recompile affected translation units.
Most speedup comes from avoiding Conan Qt dependency source builds and
reusing cached compiler objects, **not proven mold-only improvement**.

**Future work:** pin Conan dependency lockfile and compiler profiles,
promote immutable dependency package images/remote for long-lived cache
survival, benchmark controlled linker/PCH/unity variants, add runtime
headless smoke tests, and migrate Windows/native client build.
