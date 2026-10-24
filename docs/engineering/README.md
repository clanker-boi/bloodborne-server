# Yharnam Together build-system engineering

**Canonical handoff and project context.** The aim is that a fresh human
contributor or new Codex/Claude/ChatGPT conversation can continue work
without relying on previous chat history.

| Document | Contents |
| --- | --- |
| [STATUS.md](STATUS.md) | Current status, milestones, blockers, next concrete tasks |
| [BUILD_ARCHITECTURE.md](BUILD_ARCHITECTURE.md) | Scope, architecture, dependency boundaries, acceptance tests |
| [DECISIONS.md](DECISIONS.md) | Decisions and their tradeoffs, including rejected approaches |
| [BUILD_JOURNAL.md](BUILD_JOURNAL.md) | Dated, append-only build attempts, CI links and observed errors |
| [../../AGENTS.md](../../AGENTS.md) | Compact operating instructions for coding agents |
| [../BUILD-MODERN.md](../BUILD-MODERN.md) | Current experimental CLI, Docker and CI commands |

## Project objective

The fork owner wants Yharnam Together's build infrastructure modernized,
including Dockerized builders, useful developer commands, cross-platform and
cross-architecture support, Conan dependencies, faster incremental builds,
and a clean top-level system. A Goldberg additional-support source archive
was provided as **read-only reference material**. Its ideas are relevant;
its historical complexity is expressly **not** a template to copy.

The owner explicitly prefers an aggressive up-front architecture rework
rather than incremental wrappers around legacy build scripts. It is
acceptable to rewrite the build system, but not acceptable to lose a
working game/release because the new path has never built.

## Repository and coordination

- Fork: https://github.com/clanker-boi/bloodborne-server
- Upstream: https://github.com/lKaniel/bloodborne-server
- Work branch: `build/modern-toolchain-conan-docker`
- Draft PR: https://github.com/clanker-boi/bloodborne-server/pull/1
- Shared source of truth: committed documents and CI logs; never a chat transcript
- Date of initial work: 2026-10-24

When a task is completed, update `STATUS.md`, record evidence in
`BUILD_JOURNAL.md`, and capture design changes in `DECISIONS.md`.
If an experiment fails, say so explicitly rather than silently retaining
unverified platform checkmarks.

## Contributing policy

Keep build outputs out of the source tree where feasible, create pinned
build profiles/lockfiles, avoid downloading unaudited runtime assets at
configure time, preserve separate debug symbols, and never vendor game
files. Favor reproducible commands and CI artifacts over screenshots or
unrecorded local state.

A private game copy is not required for server build/test. The game
and proprietary graphical redistributables are **not** CI inputs.
