#!/usr/bin/env python3
"""Single build entrypoint: Conan resolves, CMake configures/builds/tests.

No platform-specific compiler commands or dependency versions live here.
Reconfiguration is incremental; nothing deletes build trees implicitly.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "yt"
COMPONENTS = ("server", "native", "all")
CONFIGS = ("Debug", "Release", "RelWithDebInfo")


def run(*args: str, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=ROOT, env=env, check=True)


def folder(component: str, config: str) -> Path:
    return OUT / component / config.lower()


def configure(component: str, config: str, *, offline: bool = False) -> None:
    if component not in COMPONENTS or config not in CONFIGS:
        raise ValueError("Invalid component/config")
    path = folder(component, config)
    deps_dir = path / "conan"
    deps_dir.mkdir(parents=True, exist_ok=True)
    with_server = component in ("server", "all")
    with_native = component in ("native", "all")
    if with_native and platform.machine().lower() not in ("amd64", "x86_64", "x64"):
        raise SystemExit("Native client requires x86_64; server can be built for ARM64")
    if shutil.which("conan") is None:
        raise SystemExit("Conan 2.31+ is required (pipx install 'conan>=2.31,<3')")
    if shutil.which("ninja") is None:
        raise SystemExit("Ninja is required")
    command = [
        "conan", "install", ".", "--output-folder", str(deps_dir),
        "-s:h", f"build_type={config}", "-s:b", "build_type=Release",
        "-o", f"&:with_server={str(with_server)}",
        "-o", f"&:with_native={str(with_native)}",
        "--build=missing",
    ]
    if offline:
        command.append("--offline")
    run(*command)
    toolchains = list(deps_dir.rglob("conan_toolchain.cmake"))
    if len(toolchains) != 1:
        raise SystemExit(f"Expected one Conan toolchain under {deps_dir}, got {len(toolchains)}")
    run(
        "cmake", "-S", str(ROOT), "-B", str(path / "build"), "-G", "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={toolchains[0]}",
        f"-DCMAKE_BUILD_TYPE={config}", f"-DYT_COMPONENT={component}",
        "-DYT_ENABLE_TESTS=ON",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for command in ("configure", "build", "test"):
        p = sub.add_parser(command)
        p.add_argument("component", choices=COMPONENTS)
        p.add_argument("--config", choices=CONFIGS, default="Release")
        if command == "configure":
            p.add_argument("--offline", action="store_true")
        else:
            p.add_argument("--jobs", type=int, default=0)
    args = parser.parse_args()
    path = folder(args.component, args.config) / "build"
    if args.action == "configure":
        configure(args.component, args.config, offline=args.offline)
    elif not (path / "CMakeCache.txt").exists():
        raise SystemExit("Not configured: run 'python tools/yt.py configure "
                         + args.component + "' first")
    elif args.action == "build":
        command = ["cmake", "--build", str(path), "--config", args.config]
        if args.jobs:
            command += ["--parallel", str(args.jobs)]
        run(*command)
    else:
        command = ["ctest", "--test-dir", str(path), "--output-on-failure", "-C", args.config]
        if args.jobs:
            command += ["--parallel", str(args.jobs)]
        run(*command)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
