#!/usr/bin/env python3
"""Bundle the tested shadNet Linux executable with its Conan runtime libraries.

Docker NEVER recompiles: this stage is produced by root CMake + Conan CI.
The runtime uses Ubuntu 24.04 matching the runner's glibc and compiler ABI.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINARY = ROOT / "out/yt/server/release/build/server/shadnet"
DEFAULT_OUT = ROOT / "out/yt/server/release/stage"


def linked_libraries(binary: Path, *, extra_paths: list[Path] | None = None) -> set[Path]:
    env = dict(os.environ)
    if extra_paths:
        env["LD_LIBRARY_PATH"] = ":".join(map(str, extra_paths)) + ":" + env.get("LD_LIBRARY_PATH", "")
    output = subprocess.check_output(["ldd", str(binary)], text=True, env=env)
    if "not found" in output:
        raise RuntimeError(f"Missing runtime dependency for {binary}:\n{output}")
    paths = set()
    for line in output.splitlines():
        match = re.search(r"(?:=>\s+)?(/[^\s()]+)", line)
        if match:
            path = Path(match.group(1)).resolve()
            if path.exists():
                paths.add(path)
    return paths


def soname(path: Path) -> str | None:
    output = subprocess.check_output(["readelf", "-d", str(path)], text=True)
    match = re.search(r"\(SONAME\).*\[(.+?)\]", output)
    return match.group(1) if match else None


def package(binary: Path, dest: Path, *, conan_home: Path) -> None:
    if not binary.is_file():
        raise FileNotFoundError(f"Build the server before staging: {binary}")
    if not conan_home.is_dir():
        raise FileNotFoundError(f"Conan package cache does not exist: {conan_home}")
    root = dest / "opt" / "yharnam"
    if root.exists():
        shutil.rmtree(root)
    for directory in ("bin", "lib", "plugins/sqldrivers", "backend"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    shutil.copy2(binary, root / "bin/shadnet")
    for name in ("worlds.cfg", "scoreboards.cfg"):
        shutil.copy2(binary.parent / name, root / "bin" / name)
    (root / "bin/qt.conf").write_text("[Paths]\nPlugins=../plugins\n", encoding="utf-8")
    backend = ROOT / "backend"
    for name in ("notice.txt", "broadcast.txt", "login_message.txt"):
        path = backend / name
        if path.is_file():
            shutil.copy2(path, root / "backend" / name)
        else:
            (root / "backend" / name).write_text("", encoding="utf-8")

    # Qt's SQL plugin is loaded dynamically, so ldd on shadnet alone cannot find it.
    sqlite_candidates = [
        p for p in conan_home.rglob("libqsqlite.so")
        if "sqldrivers" in p.parts and p.is_file()
    ]
    if len(sqlite_candidates) != 1:
        raise RuntimeError(
            f"Expected one Conan Qt SQLite plugin, found {len(sqlite_candidates)}: {sqlite_candidates}"
        )
    plugin = sqlite_candidates[0].resolve()
    shutil.copy2(plugin, root / "plugins/sqldrivers/libqsqlite.so")

    # Copy only dynamic libraries from Conan packages. Distro libstdc++, glibc,
    # zlib, openssl etc. are satisfied by the same Ubuntu base in the runtime.
    paths = linked_libraries(binary)
    paths |= linked_libraries(plugin, extra_paths=[p.parent for p in paths] + [binary.parent])
    conan_prefix = str(conan_home.resolve()) + os.sep
    selected = {p for p in paths if str(p).startswith(conan_prefix)}
    # Qt and Conan dependencies can be transitive; recurse on their ELF objects.
    queue = list(selected)
    while queue:
        current = queue.pop()
        resolved = linked_libraries(
            current, extra_paths=[p.parent for p in selected] + [binary.parent]
        )
        for dependency in resolved:
            if str(dependency).startswith(conan_prefix) and dependency not in selected:
                selected.add(dependency)
                queue.append(dependency)
    names = {}
    for path in sorted(selected):
        name = path.name
        if name in names and names[name] != path:
            raise RuntimeError(f"Collision between Conan runtime libraries: {names[name]} and {path}")
        names[name] = path
        shutil.copy2(path, root / "lib" / name)
        # ldd resolves symlinks to the full-version ELF; the runtime linker
        # requests its DT_SONAME (for Qt this is e.g. libQt6Core.so.6).
        expected = soname(path)
        if expected and expected != name:
            alias = root / "lib" / expected
            if alias.exists():
                raise RuntimeError(f"Conflicting SONAME for {expected}")
            alias.symlink_to(name)
    if not selected:
        raise RuntimeError("No Conan shared libraries detected; refuse to package incomplete runtime")

    # Ship the applicable third-party license notices alongside redistributed
    # shared libraries and the root GPL license. Conan recipe sources are not
    # needed in the runtime image, but license files remain required.
    notices = root / "licenses"
    notices.mkdir(exist_ok=True)
    project_license = ROOT / "LICENSE"
    if project_license.is_file():
        shutil.copy2(project_license, notices / "PROJECT-LICENSE")
    packages = set()
    for lib in selected:
        for ancestor in lib.parents:
            if not str(ancestor).startswith(conan_prefix):
                break
            if (ancestor / "licenses").is_dir():
                packages.add(ancestor)
                break
    for package_root in sorted(packages):
        destination = notices / package_root.parent.name
        shutil.copytree(package_root / "licenses", destination, dirs_exist_ok=True)

    # A straightforward manifest makes distributed artifacts auditable. OCI
    # digests protect the container itself; this records its bundled files.
    entries = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        if item.is_symlink():
            entries[relative] = {"symlink": os.readlink(item)}
        elif item.is_file():
            entries[relative] = {"sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
    (root / "manifest.json").write_text(
        json.dumps({"format": 1, "files": entries}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Staged {binary.name}, Qt SQLite plugin and {len(selected)} Conan shared libraries at {dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--conan-home", type=Path, default=Path.home() / ".conan2")
    args = parser.parse_args()
    package(args.binary.resolve(), args.output.resolve(), conan_home=args.conan_home.resolve())


if __name__ == "__main__":
    main()
