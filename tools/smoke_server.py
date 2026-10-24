#!/usr/bin/env python3
"""Start a staged headless server twice, check HTTP, SQLite and persistent files.

No Bloodborne game/client is necessary. This is infrastructure smoke,
not a simulation or gameplay persistence test.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen

def free_ports(n: int) -> list[int]:
    bound = []
    try:
        for _ in range(n):
            sk = socket.socket()
            sk.bind(("127.0.0.1", 0))
            bound.append(sk)
        return [sk.getsockname()[1] for sk in bound]
    finally:
        for sk in bound:
            sk.close()

def health(port: int, *, timeout: float = 15) -> None:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        try:
            with urlopen(f"http://127.0.0.1:{port}/status", timeout=1) as response:
                body = json.load(response)
                if response.status == 200 and body.get("ok") is True and body.get("service") == "shadnet-webapi":
                    return
        except (OSError, ValueError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError(f"WebAPI /status was not ready on port {port}")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", type=Path, required=True)
    args = p.parse_args()
    root = args.stage.resolve() / "opt/yharnam"
    binary = root / "bin/shadnet"
    plugin = root / "plugins/sqldrivers/libqsqlite.so"
    assert binary.is_file() and plugin.is_file()
    with tempfile.TemporaryDirectory(prefix="yt-smoke-") as scratch:
        state = Path(scratch)
        web, backend, tcp, udp = free_ports(4)
        cfg = (f"[General]\nHost=127.0.0.1\n"
               f"UnsecuredPort={tcp}\nMatchingUdpPort={udp}\nWebApiPort={web}\n"
               f"BackendPort={backend}\nMatching2Enabled=true\nBloodborneSeamlessCoop=true\n"
               f"BloodborneBackend=true\nStatsEnabled=false\nTcpLocalOnly=true\n"
               f"BackendFolder={root / 'backend'}\n"
               f"BackendStore={state / 'db' / 'bloodborne_content.db'}\n"
               f"BloodborneWorldPath={state / 'bloodborne_worlds'}\n")
        (state / "shadnet.cfg").write_text(cfg, encoding="utf-8")
        (state / "db").mkdir()
        env = dict(os.environ, SHADNET_HOME=str(state), QT_PLUGIN_PATH=str(root / "plugins"),
                   LD_LIBRARY_PATH=str(root / "lib"))
        for attempt in range(2):
            with (state / f"run-{attempt}.log").open("w") as log:
                proc = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    health(web)
                    assert (state / "db/shadnet.db").exists(), "shadNet SQLite database was not created"
                    assert (state / "db/bloodborne_content.db").exists(), "Backend store was not created"
                    marker = state / "bloodborne_worlds" / "smoke-restart-sentinel"
                    marker.parent.mkdir(exist_ok=True)
                    if attempt == 0:
                        marker.write_text("preserve me", encoding="utf-8")
                    else:
                        assert marker.read_text(encoding="utf-8") == "preserve me"
                except Exception:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    print((state / f"run-{attempt}.log").read_text(errors="replace"))
                    raise
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
        print("PASS: headless startup, HTTP /status, SQLite creation, state directory retained after restart")
        print("NOTE: this does not validate multiplayer team-world data or network gameplay")
if __name__ == "__main__":
    main()
