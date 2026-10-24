# Claude Code project context

This fork is actively replacing its build system. **Before changing code**, read
[AGENTS.md](AGENTS.md) and these committed engineering documents:

1. [Migration status and acceptance gates](docs/engineering/STATUS.md)
2. [Build-system architecture](docs/engineering/BUILD_ARCHITECTURE.md)
3. [Architecture decisions](docs/engineering/DECISIONS.md)
4. [Build attempts, CI evidence and failures](docs/engineering/BUILD_JOURNAL.md)
5. [Build performance design and benchmarks](docs/engineering/BUILD-PERFORMANCE.md)
6. [Headless packaging, GHCR cache and deployment](docs/engineering/HEADLESS-SERVER.md)

The work belongs on branch `build/modern-toolchain-conan-docker`, draft
PR https://github.com/clanker-boi/bloodborne-server/pull/1, never straight
onto `main`. Goldberg additional-support is a read-only reference archive;
do not import its legacy infrastructure wholesale.

## Non-negotiable workflow

- Inspect CI/build journal before editing.
- One authoritative root CMake graph + Conan 2 dependencies.
- Build context and host context are distinct for code generators.
- Make the same build commands work locally, in Docker and in CI.
- Do not declare a platform supported based only on configure or lint.
- Append precise commands, log evidence and outcomes to BUILD_JOURNAL.md.
- Update STATUS.md and DECISIONS.md for meaningful changes.
- Preserve gameplay/network protocol and exclude copyrighted game assets.
- Keep the PR a draft until clean build, test, smoke and packaging gates pass.

Read AGENTS.md for further specific constraints and component pointers.
