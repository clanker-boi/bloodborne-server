# Engineering handoff for ChatGPT, Codex and Claude Code

**Read first**: [docs/engineering/README.md](docs/engineering/README.md), then
[STATUS.md](docs/engineering/STATUS.md),
[BUILD_ARCHITECTURE.md](docs/engineering/BUILD_ARCHITECTURE.md),
[BUILD_JOURNAL.md](docs/engineering/BUILD_JOURNAL.md),
[BUILD-PERFORMANCE.md](docs/engineering/BUILD-PERFORMANCE.md),
[HEADLESS-SERVER.md](docs/engineering/HEADLESS-SERVER.md), and
[DECISIONS.md](docs/engineering/DECISIONS.md).

This file is intentionally short. All substantive context and test evidence
must live in tracked documentation, not only in an AI conversation.

## Mission
Replace the fragmented Yharnam Together build/release machinery with **one
authoritative root CMake build graph** and **Conan 2 dependency graph**.
Make Linux and Windows first-class development hosts, and native server
Linux AMD64 and ARM64 builds real, tested targets. Support the native
Bloodborne Windows x64 client without regressing playability. Goldberg
additional-support is a read-only *reference* for ideas, not code to copy
or a second build system to preserve.

## Rules for contributors and agents
1. Do not claim a target works until an actual clean build/test run passes.
2. Keep changes isolated to `build/modern-toolchain-conan-docker` and draft
   PR #1 until its acceptance gates pass. Do not modify `main` directly.
3. Edit the single source of truth. No long-lived PowerShell/Bash/Docker
   variants that embed their own separate compile or dependency logic.
4. Conan's *build context* runs tools such as protoc; *host context*
   provides target libraries, especially for cross-architecture builds.
5. Preserve game/runtime patching, ABI, and existing functionality.
   Do not add proprietary game data, assets, or copyrighted SDK binaries.
6. The legacy `tools/build-*.ps1`, `tools/make-release.ps1`,
   `bbport/build.sh` and related packaging scripts are migration sources,
   **not the desired permanent public build interface**. Delete only
   after behavior parity and real build coverage.
7. Update `STATUS.md` and append to `BUILD_JOURNAL.md` each time you
   attempt a build or make a meaningful change; record run URL, command,
   architecture, result and remaining blockers.
8. Put architectural choices and reversals in `DECISIONS.md`; unresolved
   work belongs in the status checklist. Keep all three current.
9. Don't alter protobuf wire format, co-op event generation, save formats
   or application networking as part of build migration without separate
   scope and tests.
10. Do not automatically merge a draft PR on the basis of green smoke
    checks: test all affected production targets.

## Project pointers
- Repository: https://github.com/clanker-boi/bloodborne-server
- Build branch: `build/modern-toolchain-conan-docker`
- Draft PR: https://github.com/clanker-boi/bloodborne-server/pull/1
- Target CLI: `python3 tools/yt.py configure|build|test server`
- Root project: `CMakeLists.txt`
- Conan graph: `conanfile.py`
- CI: `.github/workflows/build-modern.yml`

Read status/journal for what is **actually validated** rather than assuming
documentation of an intended platform means it is supported.
