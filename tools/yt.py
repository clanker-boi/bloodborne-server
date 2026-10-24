#!/usr/bin/env python3
"""One build interface for Conan + CMake/Ninja/CTest.

Split dependency installation from application configuration so CI can
cache completed Conan binaries BEFORE app compilation/tests may fail.
Only CMake owns compiler flags, sources, generated code and link targets.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "yt"
COMPONENTS = ("server", "native", "all")
CONFIGS = ("Debug", "Release", "RelWithDebInfo")
LINKERS = ("default", "mold", "lld")


def run(*args: str) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def folder(component: str, config: str) -> Path:
    return OUT / component / config.lower()


def conan_dir(component: str, config: str) -> Path:
    return folder(component, config) / "conan"


def verify_tools(component: str, *, for_deps: bool) -> None:
    if component in ("native", "all") and platform.machine().lower() not in (
        "amd64", "x86_64", "x64"
    ):
        raise SystemExit("Native Bloodborne client requires x86_64")
    required = ("conan", "ninja") if for_deps else ("cmake", "ninja")
    for tool in required:
        if shutil.which(tool) is None:
            raise SystemExit(f"Missing '{tool}'; see docs/BUILD-MODERN.md")


def deps(component: str, config: str, *, build_policy: str, offline: bool) -> None:
    verify_tools(component, for_deps=True)
    dest = conan_dir(component, config)
    dest.mkdir(parents=True, exist_ok=True)
    # Use checked-in compiler/ABI profiles when available. This avoids
    # runner-image profile drift and makes cache identities reproducible.
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("aarch64", "arm64") else "amd64"
    profile = ROOT / "conan/profiles" / f"linux-{arch}"
    lockfile = ROOT / "conan/locks" / "server-linux.lock"
    pinned = platform.system() == "Linux" and component == "server" and profile.is_file()
    command = [
        "conan", "install", ".", "--output-folder", str(dest),
        "-s:h", f"build_type={config}", "-s:b", "build_type=Release",
        "-o", f"&:with_server={str(component in ('server', 'all'))}",
        "-o", f"&:with_native={str(component in ('native', 'all'))}",
        f"--build={build_policy}",
    ]
    if pinned:
        command.extend(("-pr:h", str(profile), "-pr:b", str(profile)))
        if lockfile.is_file():
            command.extend(("--lockfile", str(lockfile)))
    if offline:
        command.append("--offline")
    run(*command)


def generated_toolchain(component: str, config: str) -> Path:
    candidate = list(conan_dir(component, config).rglob("conan_toolchain.cmake"))
    if len(candidate) != 1:
        raise SystemExit(
            f"Expected exactly one Conan toolchain in {conan_dir(component, config)}; "
            f"found {len(candidate)}. Run 'yt.py deps {component}' first."
        )
    return candidate[0]


def configure(component: str, config: str, *,
              reuse_deps: bool, build_policy: str, offline: bool,
              linker: str, sccache: bool,
              compile_jobs: int, link_jobs: int) -> None:
    verify_tools(component, for_deps=False)
    if not reuse_deps:
        deps(component, config, build_policy=build_policy, offline=offline)
    toolchain = generated_toolchain(component, config)
    cmake = [
        "cmake", "-S", str(ROOT), "-B", str(folder(component, config) / "build"),
        "-G", "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
        f"-DCMAKE_BUILD_TYPE={config}",
        f"-DYT_COMPONENT={component}",
        "-DYT_ENABLE_TESTS=ON",
        f"-DYT_LINKER={linker}",
        f"-DYT_COMPILE_JOBS={compile_jobs}",
        f"-DYT_LINK_JOBS={link_jobs}",
    ]
    if sccache:
        if shutil.which("sccache") is None:
            raise SystemExit("Requested --sccache but executable not found")
        cmake.extend((
            "-DCMAKE_C_COMPILER_LAUNCHER=sccache",
            "-DCMAKE_CXX_COMPILER_LAUNCHER=sccache",
        ))
    run(*cmake)


def build(component: str, config: str, *, jobs: int, stats: bool,
          target: str | None = None) -> None:
    directory = folder(component, config) / "build"
    if not (directory / "CMakeCache.txt").exists():
        raise SystemExit(f"Not configured: run 'yt.py configure {component}' first")
    command = ["cmake", "--build", str(directory), "--config", config]
    if target:
        command += ["--target", target]
    if jobs:
        command += ["--parallel", str(jobs)]
    if stats:
        command += ["--", "-d", "stats"]
    run(*command)


def test(component: str, config: str, *, jobs: int, stats: bool) -> None:
    if component in ("server", "all"):
        build(component, config, jobs=jobs, stats=stats, target="yt-server-tests")
    command = [
        "ctest", "--test-dir", str(folder(component, config) / "build"),
        "--output-on-failure", "-C", config,
    ]
    if jobs:
        command += ["--parallel", str(jobs)]
    run(*command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("deps", "configure", "build", "test"):
        p = sub.add_parser(action)
        p.add_argument("component", choices=COMPONENTS)
        p.add_argument("--config", choices=CONFIGS, default="Release")
        if action in ("deps", "configure"):
            p.add_argument("--build-policy", choices=("never", "missing"),
                           default="missing", help="Conan policy for absent binaries")
            p.add_argument("--offline", action="store_true")
        if action == "configure":
            p.add_argument("--reuse-deps", action="store_true",
                           help="Use generators from the earlier deps invocation")
            p.add_argument("--linker", choices=LINKERS, default="default")
            p.add_argument("--sccache", action="store_true")
            p.add_argument("--compile-jobs", type=int, default=0)
            p.add_argument("--link-jobs", type=int, default=0)
        if action in ("build", "test"):
            p.add_argument("--jobs", type=int, default=0)
            p.add_argument("--ninja-stats", action="store_true",
                           help="Show Ninja scheduling stats during compilation")
    sub.add_parser("prune-conan", help="Remove Conan build sources after successful dependency install")

    args = parser.parse_args()
    start = time.perf_counter()
    if args.action == "prune-conan":
        run("conan", "cache", "clean", "*", "--source", "--build", "--download", "--temp")
    elif args.action == "deps":
        deps(args.component, args.config, build_policy=args.build_policy,
             offline=args.offline)
    elif args.action == "configure":
        if args.compile_jobs < 0 or args.link_jobs < 0:
            parser.error("job pools must be nonnegative")
        configure(args.component, args.config, reuse_deps=args.reuse_deps,
                  build_policy=args.build_policy, offline=args.offline,
                  linker=args.linker, sccache=args.sccache,
                  compile_jobs=args.compile_jobs, link_jobs=args.link_jobs)
    elif args.action == "build":
        if args.jobs < 0:
            parser.error("--jobs must be nonnegative")
        build(args.component, args.config, jobs=args.jobs, stats=args.ninja_stats)
    else:
        if args.jobs < 0:
            parser.error("--jobs must be nonnegative")
        test(args.component, args.config, jobs=args.jobs, stats=args.ninja_stats)
    print(f"YT_TIMING action={args.action} elapsed_s={time.perf_counter()-start:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
