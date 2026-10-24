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
