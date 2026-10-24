# Architecture decision record

Append new decisions with date, context, choice, tradeoffs and reversal
conditions. Update a previous entry with a superseded link rather than
silently rewriting history.

## ADR-001 — One authoritative CMake build graph
**Date:** 2026-10-24. **Status:** Accepted as design direction.

**Context:** Server and emulator were CMake projects; the native loader,
packaging and release steps were fragmented across Bash, PowerShell,
MSYS2, PyInstaller and Inno Setup. Mirroring Goldberg's scaffolding
would preserve duplicate build rules.

**Decision:** Root CMake must own all compile/link/generate/install targets.
A small `tools/yt.py` may orchestrate configure/build/test but must
not be another place that implements compilation. Long-term legacy
scripts are to be deleted once behavior-parity gates pass.

**Tradeoff:** Significant up-front migration and CI effort. Payoff is fewer
independent build recipes and more robust incremental builds.

## ADR-002 — Conan 2 for dependency graphs
**Date:** 2026-10-24. **Status:** Accepted as design direction,
implementation unverified.

**Decision:** Prefer Conan 2 with explicit build and host profiles and
lockfiles. Protobuf generation must separate build-machine protoc from
target-library libprotobuf. Qt must be assembled with the specific
modules required by shadnet. GPU/native dependencies join this graph
when tested; avoid disguising distro/MSYS2 packages as Conan-managed.

**Tradeoff:** Initial Qt/protobuf graph may require significant source
build time, and ABI/toolchain incompatibilities must be resolved.

## ADR-003 — Goldberg is reference, not source dependency
**Date:** 2026-10-24. **Status:** Accepted.

**Decision:** Analyze the uploaded Goldberg additional-support ZIP for
builder, Docker, multi-platform and dependency-management ideas. Do not
copy its historical scripts, source or dependency configurations en masse.
This repository's own target dependencies and licenses govern decisions.

## ADR-004 — Architecture matrix is per-component
**Date:** 2026-10-24. **Status:** Accepted.

**Decision:** Aim for Linux AMD64/ARM64 headless server builds. Native
Bloodborne client uses original x86-64 executable code and cannot be
advertised as native ARM64 support; a build passing does not mean the game
works on that CPU. CI must accurately identify each tested target.

## ADR-005 — Build/run evidence governs release gates
**Date:** 2026-10-24. **Status:** Accepted.

**Decision:** Every milestone includes real build/run/test evidence
with command and CI URL. Existing playable release is not replaced
until demonstrated parity. Experimental migration lives in a draft PR.
No hidden 'green' check based solely on lint or documentation.

## ADR-006 — Portable, hermetic Docker builders
**Date:** 2026-10-24. **Status:** Direction accepted, implementation incomplete.

**Decision:** Docker stages use the same root build commands. Avoid
hard-coded host paths, silent architecture substitutions, mutable
unversioned dependencies, and source directories used as output.
Use separate Buildx architecture runners/QEMU where needed, plus
cache mounts keyed to actual toolchain/dependency inputs.

**Tradeoff:** Actual arm64 build latency can be higher under emulation;
prefer native runners for routine ARM64 CI.

## ADR-007 — Package the tested binary instead of compiling in Docker
**Date:** 2026-10-24. **Status:** Accepted and validated on Linux AMD64/ARM64.

**Decision:** Native GitHub Actions runners build, link and test shadnet
from root CMake/Conan. A packaging script stages its Conan dynamic
libraries and required Qt SQLite plugin. Docker only packages that
tested binary. The non-root runtime uses UID 10001, a dedicated state
volume and an HTTP healthcheck. The image contains no game data.
Standalone archives preserve UNIX file modes and symlinks.

**Tradeoff:** The distro/glibc ABI of the packaging runner must remain
compatible with the Ubuntu 24.04 runtime base. The Qt plugin/SONAME
discovery script requires smoke testing on both architectures.

## ADR-008 — GHCR binary-snapshot fallback and trusted image publication
**Date:** 2026-10-24. **Status:** Implemented, real clean-home AMD64/ARM64 GHCR restore verified.

**Decision:** GHCR stores architecture-specific Conan *binary package*
snapshots in OCI data images keyed by Conan recipe/profile/lock hash.
PR CI uses temporary Actions caches first, read-only GHCR snapshots
second, then an explicit Conan source build as cold recovery. Only a
trusted direct branch push may publish images, and both architectures
must pass before assembling the multiarch manifest.

**Tradeoff:** The snapshot is tied to a compiler ABI and runner OS,
so the profiles must be pinned. Conan recipe revisions are locked,
but byte-for-byte compiler-image provenance is not yet guaranteed.
Package visibility and authentication must be managed through GHCR.
