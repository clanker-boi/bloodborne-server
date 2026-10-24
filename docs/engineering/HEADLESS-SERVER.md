# Headless server: reproducible build, registry caches and deployment

> **Migration-branch implementation.** Tested commits and registry publication
> status are tracked in [STATUS.md](STATUS.md) and [BUILD_JOURNAL.md](BUILD_JOURNAL.md).
> Do not infer a GHCR image exists simply because a tag is shown below.
>
> No Bloodborne game files are included in the headless server artifact.

## Canonical build architecture

The root `CMakeLists.txt` owns compilation. `conanfile.py` provides the
dependency graph, and `tools/yt.py` is the only user-facing compiler/build
orchestrator. Docker is packaging, **not a competing C++ builder**.

```text
Pinned GCC 13 + Conan 2.33 profile
           + Conan recipe revision lock
                       |
       Actions cache / GHCR snapshot
                       |
              root CMake + Ninja
                       |
              server shadnet binary
                /              \
       direct smoke         Docker staging
                                  |
                    OCI nonroot runtime image
                    ghcr.io/clanker-boi/yharnam-server
```

The Linux profiles are `conan/profiles/linux-amd64` and
`conan/profiles/linux-arm64`. They specify GCC 13, libstdc++11 ABI and
architecture. `conan/locks/server-linux.lock` pins transitive *recipe
revisions* (same graph resolved on both architectures). This is **not a
package-revision lock**: the binary package IDs and their compiled content
still vary with target architecture and compiler environment.

`tools/yt.py deps server` uses the checked-in profile/lock on native
Linux. Conan binary package availability is validated by the lockfile plus
Conan's package IDs. The lockfile should be changed only with an intentional
dependency update reviewed on both architectures.

For a developer with prerequisites installed:

```sh
python3 tools/yt.py deps server --build-policy missing
python3 tools/yt.py configure server --reuse-deps --linker mold \
  --compile-jobs 4 --link-jobs 1
python3 tools/yt.py build server --jobs 4
python3 tools/yt.py test server --jobs 4
python3 tools/package_server.py
python3 tools/smoke_server.py --stage out/yt/server/release/stage
python3 tools/smoke_container.py --stage out/yt/server/release/stage
```

For a fully warmed Conan/GHCR cache, use `deps server --build-policy never`.
Missing dependencies then fail explicitly rather than recompiling Qt.

## Two levels of remote cache

1. **GitHub Actions cache** (primary speed path): Conan binaries
   (`~/.conan2`) are saved immediately after dependency compilation and
   before application configure/tests. The cache key includes Conan recipe,
   profiles, the lockfile, OS and target architecture. Builds also use the
   sccache GitHub Actions storage backend for compiler-object reuse.
2. **GHCR package snapshot** (durability/fallback): a *trusted push* workflow
   copies the binary-only Conan cache into an OCI **data layer**, publishes
   separate native AMD64/ARM64 architecture images and combines them into a
   multiarch manifest. No credentials or proprietary game data should be
   included. A PR run pulls it **read-only** on a primary cache miss and
   runs Conan with `--build=never`. Only if the snapshot is unavailable does
   it perform the expensive explicit `--build=missing` recovery.

The snapshot reference has the form:
```text
ghcr.io/clanker-boi/yharnam-conan-cache:lock-<recipe+profile+lock hash>
```
Normal CI uses architecture-specific tags with `-amd64` / `-arm64`.
Publish only through `.github/workflows/publish-images.yml`, which never
runs on an untrusted PR and uses `packages: write` only in trusted runs.
Conan binary snapshots are not a substitute for retaining original recipes
and sources under their upstream licenses.

## Deployment

A successful trusted publishing workflow creates:
```text
ghcr.io/clanker-boi/yharnam-server:git-<full-commit-sha>
```
This is a multiarch image containing Linux AMD64 and ARM64 variants that
were independently compiled and tested on native runners. Pin the chosen
image by **digest** in production after inspecting the published manifest:

```sh
docker buildx imagetools inspect ghcr.io/clanker-boi/yharnam-server:git-<full-commit-sha>
```

Use a **private LAN or VPN**, never openly expose the entire service without
further access controls. Example (substitute a verified available tag/digest):

```sh
docker volume create yharnam-state
docker run -d --name yharnam-server --restart unless-stopped \
  --mount type=volume,src=yharnam-state,dst=/data \
  -p 127.0.0.1:31315:31315/tcp \
  -p 127.0.0.1:20443:20443/tcp \
  -p 127.0.0.1:31314:31314/udp \
  ghcr.io/clanker-boi/yharnam-server:git-<full-commit-sha>
```

The loopback publishing above permits only local access. To serve trusted
remote players, bind the mapped ports to the server's real private/Tailscale
address or manage them with an appropriate VPN/host firewall. The internal
unsecured TCP port 31313 is deliberately configured `TcpLocalOnly=true`;
it is **not** published. Open only the specific game ports actually required
by your client's network mode.

The container runs as **UID/GID 10001**, uses an exec-based entrypoint,
and has an HTTP health check at `/status`. A named volume is recommended
because Docker can populate it with the image's initial ownership. For
bind mounts, the host directory must be writable by UID 10001.

Config resides at `/data/shadnet.cfg` and is created from a template only
on first start. Edit this persistent file for your actual host address,
registration secret and world settings. The default registration key is
empty: do **not** expose registration services publicly without configuring
authentication and ingress restrictions.

World data, SQL stores, reports and configuration reside under `/data`.
Stop the server before filesystem backups to avoid partially copied
SQLite WAL files and journal records:

```sh
docker stop yharnam-server
# Back up the named volume's complete /data tree by your preferred tool.
docker start yharnam-server
```

Keep the full volume, not only `db/shadnet.db`: it also contains
`db/bloodborne_content.db`, `bloodborne_worlds/`, settings, reports and
any other persistent state created by new versions.

## Validation and limits

CI direct smoke validates a **headless binary** can initialize SQLite,
answer WebAPI `/status`, shut down and restart using the same directory.
Docker smoke validates the image starts as a non-root user, responds to
WebAPI and preserves a test marker in the mounted world directory after
recreation. It is **not** a live Bloodborne game-client compatibility test
nor proof of end-to-end multiplayer world-journal progression.

The runtime image is based on Ubuntu 24.04 and bundles Conan-linked
libraries and the Qt SQLite plugin. It must be tested under both target
architectures before release. We have pinned the GCC **major** version and
Conan recipe revisions, but GitHub runner images and Ubuntu package
revisions may still change; a fully bit-reproducible supply chain would
also pin the OS image digest, system packages, and compiler binary
digests. Keep PR #1 in draft until Windows/native-client and release
parity gates are completed.

## Files

- `conan/profiles/*`, `conan/locks/server-linux.lock`: versioned build inputs
- `tools/yt.py`: Conan/CMake/Ninja/CTest interface
- `tools/package_server.py`: stage dynamic dependencies and Qt plugin
- `tools/smoke_server.py`: direct binary smoke/restart
- `tools/smoke_container.py`: Docker smoke/restart
- `docker/server/{Dockerfile,docker-entrypoint.sh,shadnet.cfg}`: runtime image
- `docker/deps/Dockerfile`: Conan cache data image
- `.github/workflows/build-modern.yml`: PR validations (read-only)
- `.github/workflows/publish-images.yml`: trusted GHCR package release

Workflow and cache design details also live in
[BUILD-PERFORMANCE.md](BUILD-PERFORMANCE.md).
