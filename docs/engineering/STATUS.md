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
- [ ] Clean Conan resolution without local packages or unpinned side effects
- [x] Linux AMD64 server compiles and links from root build — CI #40135063503
- [x] Linux ARM64 server compiles and links from root build — CI #40135063503
- [x] Server CTest suite passes in both architectures — 16/16 each in CI #40135063503
- [ ] Headless process boots, binds expected ports and serves `/status`
- [ ] Server loads/saves a team world, and can restart with persistent data
- [ ] Dedicated Docker runtime image works with non-root UID + mounted state
- [ ] Deployment docs, health checks and image labels validated

### Gate N: native client
- [ ] Windows x86_64 Conan graph including MSYS2/Clang ABI settled
- [ ] Windows `bb-probe`, launcher and runtime build under canonical targets
- [ ] Linux x86_64 client builds using same public CLI
- [ ] GPU shader generation and native port test targets pass
- [ ] Co-op integration and game startup regression tested on actual hardware

### Gate R: packaging and cutover
- [ ] Reproducible lockfile/versioned dependency profiles
- [x] GitHub Actions early Conan cache save and unified local build commands validated on both Linux targets (CI #40137604748); warm cache reuse still to be tested
- [ ] Windows player installer/release artifacts match old feature set
- [ ] SHA-256, SBOM/license notices and artifact provenance available
- [ ] Remove legacy build/release entrypoints after parity tests
- [ ] Update README to point only at final supported commands

## Performance branch test

Implementation commit: `6440248` (CLI test correction `497cd56`).
The first optimized [CI #40137604748](https://github.com/clanker-boi/bloodborne-server/actions/runs/40137604748) **passed on AMD64 and ARM64** with 16/16 tests each, mold, sccache and bounded Ninja job pools. Conan caches were saved in each job before application compilation. Cold builds: AMD64 7m41s; ARM64 19m45s. See the journal for exact measurements. A separate cache-hit test is still required before claiming faster recurring builds.

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

## Immediate next actions

1. Implement caching strategy and benchmark plan in [BUILD-PERFORMANCE.md](BUILD-PERFORMANCE.md); preserve clean full-source builds as audit jobs. Measure dependency source builds, compiler critical path and object-cache hit rate.
2. Start shadnet in CI, poll WebAPI `/status`, and run an integration smoke
   test; ensure server doesn't depend on a game install.
3. Finalize container build/runtime stages, non-root volume, health check.
4. Inventory every `bbport/build.sh` hand-compiled source/flag and move it
   into root CMake, proving native Linux x86_64 parity.
5. Migrate packaging and release; retire original scripts after CI parity.

## Resume protocol

Read `AGENTS.md` -> `BUILD_ARCHITECTURE.md` -> latest entries in
`BUILD_JOURNAL.md` -> current branch diff -> CI. Work on the branch;
update these documents and leave a precise next action after each change.
