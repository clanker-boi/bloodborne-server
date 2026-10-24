# Current migration status

Last updated: **2026-10-24**. See the append-only
[build journal](BUILD_JOURNAL.md) for observed evidence.

## At-a-glance

**State: Linux AMD64 and ARM64 optimized server builds (mold, sccache, Ninja job pools) passed all 16 tests each in CI #40137604748; other acceptance gates remain open.** Work is isolated in
[draft PR #1](https://github.com/clanker-boi/bloodborne-server/pull/1).
Neither server nor native client is yet certified against the new build.

## Implemented on branch (source change, not necessarily passing build)

- [x] Root CMake entrypoint with server/native/all selectors
- [x] Conan 2 recipe for initial Qt6 / Protobuf dependency graph
- [x] Shared Python CLI for configure, build, and test
- [x] Experimental Buildx Docker builder
- [x] GitHub Actions Linux AMD64 and ARM64 server job definitions
- [x] Protobuf target plumbing in `server/CMakeLists.txt`
- [x] Persistent design, status and build-journal documentation
- [x] Conan deps separated from app configure and early cache saving in CI (validation in progress)
- [x] sccache, Linux mold/LLD selection and Ninja job-pool limits (validation in progress)
- [x] CLI smoke/unit tests and per-stage build timing (validation in progress)

## Required acceptance gates

### Gate S: Linux standalone server
- [x] Pinned Linux GCC13 host/build profiles and Conan recipe revisions; both native arch builds passed [CI #40142312225](https://github.com/clanker-boi/bloodborne-server/actions/runs/40142312225)
- [x] Linux AMD64 server compiles and links from root build — CI #40135063503
- [x] Linux ARM64 server compiles and links from root build — CI #40135063503
- [x] Server CTest suite passes in both architectures — 16/16 each in CI #40135063503
- [x] Direct headless startup, /status, SQLite and restart smoke passed on AMD64/ARM64 in [CI #40142312225](https://github.com/clanker-boi/bloodborne-server/actions/runs/40142312225)
- [ ] Server loads/saves a team world, and can restart with persistent data
- [x] Non-root Docker runtime and mounted-state restart smoke passed on both architectures in CI #40142312225
- [x] Deployment template, health checks and OCI source labels exercised; [HEADLESS-SERVER.md](HEADLESS-SERVER.md) describes caveats

### Gate N: native client
- [ ] Windows x86_64 Conan graph including MSYS2/Clang ABI settled
- [ ] Windows `bb-probe`, launcher and runtime build under canonical targets
- [ ] Linux x86_64 client builds using same public CLI
- [ ] GPU shader generation and native port test targets pass
- [ ] Co-op integration and game startup regression tested on actual hardware

### Gate R: packaging and cutover
- [x] Conan recipe lockfile and Linux x86_64/armv8 GCC13 profiles committed; binary package revisions may vary by build and full OS bit-reproducibility remains out of scope
- [x] GitHub Actions early Conan cache save and **warm binary restore** verified on AMD64 + ARM64 (cold #40137604748, warm #40139233770)
- [ ] Windows player installer/release artifacts match old feature set
- [ ] SHA-256, SBOM/license notices and artifact provenance available
- [ ] Remove legacy build/release entrypoints after parity tests
- [ ] Update README to point only at final supported commands

## Performance branch test

Implementation commit: `6440248` (CLI test correction `497cd56`).
The first optimized [CI #40137604748](https://github.com/clanker-boi/bloodborne-server/actions/runs/40137604748) **passed on AMD64 and ARM64** with 16/16 tests each, mold, sccache and bounded Ninja job pools. Conan caches were saved in each job before application compilation. Cold builds: AMD64 7m41s; ARM64 19m45s. See the journal for exact measurements. **Warm cache verified:** [CI #40139233770](https://github.com/clanker-boi/bloodborne-server/actions/runs/40139233770) restored cached Qt/Protobuf on both architectures and passed all 16 CTests each with `--build=never`; AMD64 full job 51s, ARM64 60s. Both had 92/93 sccache hits (98.92%).

## Verified warm-cache outcome

Cold [run #40137604748](https://github.com/clanker-boi/bloodborne-server/actions/runs/40137604748) passed 16 tests per architecture in **7m41s AMD64 / 19m45s ARM64**. Warm [run #40139233770](https://github.com/clanker-boi/bloodborne-server/actions/runs/40139233770) passed all tests in **51s AMD64 / 60s ARM64**, with 92/93 sccache hits and no Qt/Protobuf recompilation. See [BUILD_JOURNAL.md](BUILD_JOURNAL.md) for command timings and cache sizes. No runtime/gameplay smoke test, Windows build or GHCR provenance claim is made.

## Intermittent test case and mitigation

A documentation-triggered warm [CI #40139403227](https://github.com/clanker-boi/bloodborne-server/actions/runs/40139403227) had an intermittent AMD64 `bloodborne_backend_parity` failure (the wrong service responded HTTP 404), even though earlier runs passed. Investigation found the test allocated four independent `free_port()` ephemeral listener ports without holding sockets; duplicate allocations could target another service. The test also accepted any HTTP response during readiness, including 404.

Commit `4b100db` changes the test to allocate four distinct simultaneously reserved ports and require HTTP 200 readiness. [CI #40139603742](https://github.com/clanker-boi/bloodborne-server/actions/runs/40139603742) subsequently passed 16/16 on both AMD64 and ARM64. This supports the fix but does not establish that all timing races are impossible.

## Known blockers and risks

1. **Initial AMD64 CI failure fixed** (`find_package(protobuf)`); both architectures now pass compilation and the full 16-test suite at commit `7b834c9` in CI #40135063503. This does not verify a server runtime smoke test, Docker image, client, or release. Do not merge yet.
2. Conan Qt6 HttpServer builds may be costly and may lack a matching binary
   package for the chosen option set. Dependencies need caching and lockfiles.
3. The server currently uses a vendored Protobuf CMake subtree; the new
   Conan path must correctly resolve target-architecture libprotobuf and
   host-architecture protoc.
4. Native Linux `bbport/build.sh` hand-links C sources; it is not yet fully
   expressed in root CMake, so `YT_COMPONENT=native` is incomplete there.
5. Native Windows release combines MSYS2 CLANG64, MSVC-built DLSS bridge,
   Python/PyInstaller, Qt server, game data preparation and Inno Setup.
   The replacement needs explicit compatibility checks.
6. `docker/build/Dockerfile` is a builder prototype, not a polished
   minimal headless runtime image; multi-arch needs actual separate-arch
   compilation tests.

## Headless release proof (2026-10-24)

- [x] Exact Conan lockfile generated from real native AMD64 and ARM64 jobs ([run #40142122685](https://github.com/clanker-boi/bloodborne-server/actions/runs/40142122685)); both produced identical recipe-revision graphs.
- [x] Packed and tested headless server on both AMD64 and ARM64 with license notices, file checksums and standalone archives ([final CI #40143857302](https://github.com/clanker-boi/bloodborne-server/actions/runs/40143857302), jobs 92s/69s).
- [x] Trusted publishing jobs for both architectures **and both manifests** passed ([final run #40143853161](https://github.com/clanker-boi/bloodborne-server/actions/runs/40143853161)); per-arch tarballs with SHA256 artifacts uploaded.
- [x] Final audited multiarch **server** manifest published at `ghcr.io/clanker-boi/yharnam-server:git-77e3106453f77251b4a20b7f8d5035548c7b8e2c` with digest `sha256:3df8277ef2c8b71091695f6ca11670e1a437f7f0f2f727e355f6e46d72a7fde4`. Includes checksum manifest and third-party notices. Earlier build's digest remains in journal.
- [x] Multiarch **Conan cache** manifest published in [final run #40143853161](https://github.com/clanker-boi/bloodborne-server/actions/runs/40143853161), digest `sha256:66331832025c15f92d244747dfd599ded82f6a2d70c190e9896c816a9a5f13f7`. Initial checkout failure is recorded and fixed.
- [x] Independent **clean Conan home** GHCR restore with `--build=never` passed on AMD64 and ARM64 in [CI #40143853112](https://github.com/clanker-boi/bloodborne-server/actions/runs/40143853112).
- [ ] Team-world persistence from real gameplay and native Windows client compatibility remain untested. Docker smoke verifies filesystem state retention, not gameplay.

## Immediate next actions

1. Headless server and Conan-cache image publication is now verified. Next: test server persistence with *real co-op world state* and an actual client, then consider runtime security hardening/backup automation; see [HEADLESS-SERVER.md](HEADLESS-SERVER.md).
2. The direct and container headless smoke tests now pass without game assets; expand them to exercise real game networking rather than a sentinel-only persistence check.
3. Finalize container build/runtime stages, non-root volume, health check.
4. Inventory every `bbport/build.sh` hand-compiled source/flag and move it
   into root CMake, proving native Linux x86_64 parity.
5. Migrate packaging and release; retire original scripts after CI parity.

## Resume protocol

Read `AGENTS.md` -> `BUILD_ARCHITECTURE.md` -> latest entries in
`BUILD_JOURNAL.md` -> current branch diff -> CI. Work on the branch;
update these documents and leave a precise next action after each change.
