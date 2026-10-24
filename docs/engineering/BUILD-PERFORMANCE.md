# Build-performance engineering plan

Date: 2026-10-24. **Status: first optimization implementation committed, validation underway.**
This document is a persistent companion to [BUILD_ARCHITECTURE.md](BUILD_ARCHITECTURE.md),
[STATUS.md](STATUS.md), [BUILD_JOURNAL.md](BUILD_JOURNAL.md), and
[draft PR #1](https://github.com/clanker-boi/bloodborne-server/pull/1).

## Initial implementation (2026-10-24)

Commit `6440248`, then test fix `497cd56`: Conan `deps` + early cache-save, fast sccache compiler launchers, mold/LLD selector (Linux only), CMake Ninja job pools, command timings and CLI unit tests. Default values outside CI are unchanged. This is not yet a completed benchmark: optimized [CI run #40137604748](https://github.com/clanker-boi/bloodborne-server/actions/runs/40137604748) passed with mold/sccache on both targets. PCH, unity, ThinLTO, distributed compile and GHCR binary promotion remain experiments, not enabled defaults.

## Objective

Minimize **developer feedback latency**, **CI elapsed time** and unnecessary
recompilation, while retaining reproducibility and the single authoritative
CMake+Conan build graph. Avoid a pile of independently maintained shell
flags. Goldberg is reference material only.

Measure cold build, incremental build (one touched .cpp), public-header change,
link-only change, complete test build, and release/PGO build **separately**.
A fast link will not hide a ten-minute Conan source compilation. A big unity
build may improve clean throughput and worsen incremental edits.

## Verified Linux server baseline

[GitHub Actions #40135063503](https://github.com/clanker-boi/bloodborne-server/actions/runs/40135063503)
at commit `7b834c9` (the build was triggered before further documentation
commits). The action has separate native AMD64 and ARM64 jobs, each on
Ubuntu 24.04 public-repository standard runners (4 vCPU, 16 GiB RAM).

| Step | AMD64 | ARM64 |
| --- | ---: | ---: |
| Conan dependencies + root CMake configure | 6m25s | 16m44s |
| Root CMake application build | 54s | 51s |
| CMake test-target compilation + CTest execution | 53s | 51s |
| **Actual CTest execution** (within test step) | **2.61s** | **2.68s** |
| Tests | 16/16 passed | 16/16 passed |
| Complete job (including setup/cache upload) | 9m21s | 19m19s |

Both full jobs completed successfully. The initial Conan cache was cold.
Qt 6.8.3 HttpServer option set required a full Qt source build (~995 MB
download, approximately 687 Ninja steps). Link-time optimizations cannot
fix that dependency bottleneck; see caching plan in PR #1.

## Classification and sequence

| Candidate | Target | What it changes | Priority | Risk |
| --- | --- | --- | --- | --- |
| Prebuilt Conan Qt/Protobuf (GHCR or Conan remote) | cold CI | eliminate *dependency* source compilation | P0 | low after lock/ABI verification |
| Trace critical path and cache hits | every build | know where time actually goes | P0 | low |
| Ninja + bounded parallelism | compiler execution | schedule jobs concurrently without OOM | P0 | low |
| Mold versus LLD benchmark | Linux link | less time linking ELF | P1 | low-medium (toolchain behavior) |
| sccache | repeated .cpp compiles | avoid compiling matching source+options again | P1 | low-medium (PCH paths/keys) |
| Per-target PCH | template-heavy source | parse common, stable headers once per target | P1 | medium |
| Selective unity | enormous cold client builds | cut repeated header parsing / compiler startups | P2 | medium-high (ODR, churn) |
| No LTO for dev; ThinLTO for release | linking, developer builds | avoid repeated expensive whole-program optimization | P1 | medium (release perf) |
| Isolate hot vs cold source targets | incremental builds | stop unrelated heavyweight targets relinking | P2 | medium |
| Improve shader/codegen dependencies | GPU compile | prevent broad unnecessary shader/protobuf rebuilds | P1 | medium |
| Larger runner / distributed compile | giant cold builds | increase available CPU/parallel workers | P3 after measurement | cost/maintenance |

### 1. Parallelism is a CPU+memory budget, not just `-j`

Yharnam already uses CMake with Ninja for server and renderer. Replacing Ninja
with another frontend by itself is unlikely to improve much. The CLI already
accepts `--jobs`; CI currently runs `--jobs 4` on **4-vCPU / 16GB** public
runners. Benchmark `-j2`, `-j4`, `-j6` for server **and** renderer:
more runnable tasks may reduce CPU stalls or trigger RAM exhaustion.
Use explicit bounded jobs, not Ninja's default `cores + 2` blindly.

**Separate constraints:**
- C++ compiles: initially 4 concurrent on a 4-core runner; lower if
  compiler peak RSS exceeds memory budget.
- Heavy final links / ThinLTO: often 1 concurrent link on 16 GB runner.
- Protobuf/shader generation: separate Ninja outputs, `DEPENDS` and
  `BYPRODUCTS` so independent tasks can schedule in parallel.
- Keep Conan `tools.build:jobs` separate from application build jobs:
  a Conan recipe compiling Qt uses its own job scheduler. Pin it in
  Conan profile/global.conf, not in CI-specific source-code patches.

CMake allows Ninja-specific job pools at the root (CMake 3.16+):

```cmake
# Illustrative; measure workloads before choosing limits.
set_property(GLOBAL PROPERTY JOB_POOLS yt_heavy_link=1 yt_compile=4)
set(CMAKE_JOB_POOL_COMPILE yt_compile)
set(CMAKE_JOB_POOL_LINK yt_heavy_link)
```

Set before targets are declared; tune by architecture/runner class.
Avoid giving a job-pool limit *and* many background independent jobs that
silently compete for the same RAM. A per-target pool is preferable for
one exceptional renderer target.

### 2. Faster linkers: Linux mold vs LLD; Windows LLD

CMake **3.29+** exposes native linker selection (root currently requires
3.24, so update minimum only when supported toolchains are ready):

```sh
cmake -S . -B out/yt/server/mold -G Ninja \
    -DCMAKE_LINKER_TYPE=MOLD -DYT_COMPONENT=server \
    -DCMAKE_TOOLCHAIN_FILE=<Conan-generated-toolchain>
# and repeat in a separate build tree with -DCMAKE_LINKER_TYPE=LLD
```

* Linux AMD64/ARM64: benchmark **mold**, **LLD**, and current/default.
  Linker speedups can be large for enormous binaries but are a small
  fraction of today's 54-second server build. Test dynamic linking,
  symbols, output size, sanitizer builds, Qt plugin loading and
  runtime on both architectures.
* Windows MSYS2 CLANG64: use `ld.lld` via Clang's `-fuse-ld=lld`
  (CMake linker type `LLD`) for PE/COFF through GNU-style front-end.
  Windows MSVC/clang-cl: use `lld-link` or compare with `link.exe`;
  do **not** use Unix ELF mold. Preserve native loader's custom ASLR,
  image-base, stack and subsystem flags.
* No linker benchmarking conclusions from mold's published marketing
  numbers: measure *this repository* and outputs. Keep fallback.

### 3. Build profiles: optimize feedback vs ship performance

**Dev/PR**: prefer `RelWithDebInfo` with **LTO off**, moderate optimization
(level appropriate to target), compiler cache and fast linker. For very
quick iteration, `Debug` / `-O0` can reduce compile time but may not be
representative for gameplay behavior/performance. Preserve assertions
and checks as required. **Do not use `-Ofast` indiscriminately.**

**Release**: consider `-flto=thin` + `lld` with a bounded ThinLTO job
count/cache; compare with non-LTO and full LTO on cold+incremental builds
and runtime benchmarks. Under current `bbport/gpu/CMakeLists.txt`,
`BB_LTO` defaults **ON** and uses CMake IPO support, so current
Windows PowerShell `bbport/build.sh` explicitly overrides it to OFF.
Define explicit `YT_DEV_FAST` and `YT_RELEASE_OPTIMIZED` presets so this
does not happen accidentally. Treat PGO separately (it requires training).

CMake target-level IPO is an implementation detail, not a license to
silently switch compilers or change the runtime's architecture-specific
flags.

### 4. Compiler launcher, PCH and unity builds

**sccache**: `CMAKE_C_COMPILER_LAUNCHER=sccache` and
`CMAKE_CXX_COMPILER_LAUNCHER=sccache` configured via Conan/CMake toolchain
before target creation. Enable compiler timings/stats, verify actual hits,
and account for cache transfer overhead on tiny jobs. Don't assume PCH
outputs can be shared across unrelated compiler/version/flag combinations.

**PCH**: test on template-heavy `bbgpu`/emulator targets first.
`target_precompile_headers(bbgpu PRIVATE ...)` with **stable** ubiquitous
headers (C++ STL, fmt, Vulkan etc. only where legal). CMake's `REUSE_FROM`
requires identical compile options/defines between targets; don't blindly
share across co-op/shader/per-platform builds. Changes to a PCH header
invalidate many TUs. PCH can interfere with distributed compilation and
object cache hit rate; benchmark them combined, not independently.

**Unity/jumbo**: `CMAKE_UNITY_BUILD=ON` or per-target
`UNITY_BUILD ON` / `UNITY_BUILD_BATCH_SIZE=N` for selected heavy targets,
with exclusions for ODR collisions, inline globals and differing
compile flags. Start with small batch 4–8 and **do not globally turn it
on** for emulator or generated code. Unity may help clean C++ builds but
will combine multiple source files into one object, making incremental
single-file edits and sccache less effective. CMake currently cautions
about `CMAKE_EXPORT_COMPILE_COMMANDS` interaction.

**Modules/header units**: experimental future option after PCH profiling;
nontrivial with Vulkan/shadPS4 headers and multiple compiler versions.
Don't change architecture around them prematurely.

### 5. Avoid unnecessary work in the native build graph

The native client's `bbport/gpu/CMakeLists.txt` includes:
- Multiple independent shader header generation custom commands and
  `host_shaders` target, followed by `bbgpu`.
- `bbcoop_revision` generated through a custom target that runs each
  build and checks content before writing. **Inspect whether the header
  causes recompilation on unchanged revisions; keep content-stable writes.**
- Protobuf from the same shared `server` schemas; prefer canonical
  code-generation targets and outputs, do not duplicate across components
  when one build tree could share the generator.
- `file(GLOB_RECURSE ... CONFIGURE_DEPENDS)`, harmless at small scale but
  rechecks filesystem during `ninja` regeneration. Measure first.
- Large `bbgpu` and `bbnet` targets; separate relatively stable graphics
  translation libraries from frequently edited co-op/launcher code when
  dependencies allow. Avoid rebuilding the graphics core for a lobby change.
- Server `CMAKE_AUTOMOC ON` globally; prefer appropriately scoped Qt
  autogen on Qt-using targets only if autogen overhead appears in trace.

For shader outputs, avoid a blanket run of all shader compilers after a
single source edit. Ensure output file is only written on byte change,
so Ninja restat semantics avoid recompiling dependent C++ TUs.

### 6. Instrument and benchmark, rather than trusting plausible flags

Artifact-producing diagnostic commands:

```sh
# What forces an incremental rebuild?
ninja -C out/yt/server/release/build -n -d explain

# Ninja internal scheduler overhead and commands:
ninja -C out/yt/server/release/build -d stats
ninja -C out/yt/server/release/build -t targets all

# Converts .ninja_log into a Chrome/Perfetto timeline:
ninjatracing out/yt/server/release/build/.ninja_log > trace.json
```

On Clang diagnostic builds enable `-ftime-trace` for hotspot sources
(use `ClangBuildAnalyzer` to aggregate) rather than emit large traces
on every default build. `/usr/bin/time -v` on Linux records wall time,
peak RSS and CPU utilization, helpful for `-j` and link pool choices.
CTests currently take ~2.6 seconds to **execute**; the 53-second workflow
Test step mostly builds EXCLUDE_FROM_ALL test targets. Use that fact
to prioritize source compilation, not parallel test tuning.

Record compiler+linker versions and command options, elapsed time,
peak memory, total object count, linker time, changed units and
sccache hits/misses. If a configuration is unstable, revert the
optimization instead of accepting the benchmark win.

### 7. Multi-runner strategies

**Per-architecture GitHub Actions jobs** already parallelize x64 and ARM64.
Keep a shared dependency promotion pipeline, but ensure ordinary PRs
do not rebuild the entire Qt graph. Build independent components in
parallel only if their compile artifacts can safely be combined.
Sharding arbitrary C++ object compilation across ephemeral runners
requires durable transfer of all .o files, plus identical compiler,
flags and paths; network and archive overhead may dominate at this scale.

**Bigger runners**: standard public 4 vCPU / 16 GB are free, while
larger GitHub-hosted runners generally incur extra costs. Benchmark
whether 8/16 vCPU reduce long **native-client** cold builds enough to
justify the expense. Do not upgrade hardware for a 50-second server build
without an actual speedup calculation.

**Distributed compilation**: sccache distributed workers, icecc,
reclient or commercial systems require real CPU capacity, authenticating
untrusted PR code safely, pinned toolchains, path mapping and fast
object transport. Consider only when native client has hundreds/thousands
of uncached translation units and large enough builds to amortize overhead.

## Experiments (do not change production default until measured)

Run on both architectures with the *same* Conan lock/package store.

1. **E0 baseline:** Ninja `-j4`, current linker, sccache off, LTO off;
   repeat 3 times clean and 3 times one-file edit, record median.
2. **E1 scheduler:** `-j2/4/6` with peak RSS / fail rate. Profile Conan
   Qt recipe separately, since it runs in the dependency phase.
3. **E2 linkers:** default vs LLD vs mold; record standalone final
   link duration and byte-level runtime smoke + test parity.
4. **E3 compiler cache:** sccache cold, warm, one-file edit and public
   header edit, including restore/download seconds.
5. **E4 PCH:** selected targets only with compiler cache on/off.
6. **E5 unity:** selected large targets, batch 4 and 8, separately
   measure cold speed and incremental one-file edit + source breakages.
7. **E6 release LTO:** no LTO, ThinLTO+LLD cache, and full LTO; measure
   compile+link+runtime smoke, then adopt fastest acceptable profile.
8. **E7 build-graph invalidations:** touch one co-op source, server
   schema, graphic shader, and unchanged revision; inspect Ninja
   `-d explain` + Perfetto traces for unintended rebuild fanout.

Do not run these as an always-on Cartesian-product CI matrix. Use one
manually dispatched benchmarking workflow with artifact reports; only
promote **measured winners** to ordinary PR CI.

## Suggested order

1. Fix immutable binary dependency reuse (GHCR/Conan remote) to remove
   6–17 minute configure steps.
2. Add low-overhead timers, Ninja trace and reporting.
3. Test sccache and linker (mold on Linux, LLD on Windows).
4. Add memory-aware job pools and tune Ninja/Conan concurrency.
5. Benchmark selective PCH and unity on the large client targets.
6. Rework coarse-grained targets/codegen graph to reduce incremental
   invalidation.
7. Optimize release-only LTO/PGO independently.

**Success criteria:** normal PR CI performs **zero third-party dependency
source compilation**, no unnecessary full graphic recompilation for a
co-op source change, and headless server build + tests finish within a
measured, documented budget on GitHub standard runners.

## References

- Runner specs: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- Ninja: https://ninja-build.org/manual.html
- CMake linker selection: https://cmake.org/cmake/help/v3.29/prop_tgt/LINKER_TYPE.html
- CMake Ninja job pools: https://cmake.org/cmake/help/latest/prop_gbl/JOB_POOLS.html
- CMake PCH: https://cmake.org/cmake/help/latest/command/target_precompile_headers.html
- CMake unity: https://cmake.org/cmake/help/latest/variable/CMAKE_UNITY_BUILD.html
- LLVM ThinLTO: https://clang.llvm.org/docs/ThinLTO.html
- Clang time trace: https://clang.llvm.org/docs/UsersManual.html
- Ninja trace: https://github.com/nico/ninjatracing
- Mold: https://github.com/rui314/mold
- Conan job count: https://docs.conan.io/2/reference/tools/build.html

## Implemented optimization evidence (2026-10-24)

[Optimized cold CI #40137604748](https://github.com/clanker-boi/bloodborne-server/actions/runs/40137604748) passed all server tests on both architectures. It used `YT_LINKER=mold`, sccache GHA backend, 4-way compile / 1-way link Ninja pools and saved Conan binary caches before CMake compilation.

| Cold metric | AMD64 | ARM64 |
| --- | ---: | ---: |
| Conan install including large Qt source build | 301.88s | 1016.32s |
| Conan source/build cache prune | 43.77s | 21.27s |
| CMake configure using mold | 1.65s | 0.64s |
| Application compile/link | 45.28s | 55.56s |
| Test-target build and test | 41.05s | 49.92s |
| sccache hit rate | 15.05% | 12.90% |
| Full GitHub job duration | 7m41s | 19m45s |
| CTest | 16/16 pass | 16/16 pass |

AMD64's compressed Conan archive was **145,659,012 bytes (~146 MB)** after pruning, uploaded in about 3 seconds. Both architectures reported successful early cache saves. These numbers are not controlled attribution to individual compiler/linker optimizations. A **warm-cache run** must validate `--build=never` and quantify recurring PR time. PCH, unity, ThinLTO and GHCR images remain future, benchmark-gated work.

## Verified warm-cache outcome

[Run #40139233770](https://github.com/clanker-boi/bloodborne-server/actions/runs/40139233770)
confirmed exact Conan cache restoration, `--build=never` and sccache
reuse in an entirely new runner. AMD64 cached Conan archive **146 MB**,
ARM64 **211 MB**; Conan graph resolution **1.12s / 0.84s**, application
build **7.32s / 8.70s**, test build+CTest **7.17s / 7.58s**. The complete
jobs finished in **51s / 60s**, each **16/16 CTest passed** with
**92 of 93 sccache hits (98.92%)**.

This validates the P0 GitHub Actions cache mechanism and first compiler
cache integration. It does **not** isolate mold vs LLD, prove PCH/unity
benefits, or validate gameplay or Windows. GHCR/Conan remotes are still
valuable for long-lived availability and cache eviction recovery, but
need a trusted publishing workflow and pinned lockfiles before adoption.
