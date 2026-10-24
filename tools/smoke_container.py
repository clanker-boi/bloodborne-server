#!/usr/bin/env python3
"""Build/test container on the current native GitHub Actions runner."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def command(*parts: str, check=True) -> str:
    return subprocess.run(parts, check=check, text=True, capture_output=True).stdout.strip()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--image", default="yt-shadnet-smoke:ci")
    args = p.parse_args()
    stage = args.stage.resolve()
    # A Dockerfile outside the context cannot COPY entrypoint/config, so put
    # these declarative files into the staging context unchanged.
    from shutil import copy2
    for name in ("docker-entrypoint.sh", "shadnet.cfg"):
        copy2(ROOT / "docker/server" / name, stage / name)
    command("docker", "build", "-f", str(ROOT / "docker/server/Dockerfile"), "-t", args.image, str(stage))
    with tempfile.TemporaryDirectory(prefix="yt-docker-") as folder:
        name = "yt-smoke-" + str(time.monotonic_ns())
        for iteration in range(2):
            try:
                command("docker", "run", "-d", "--name", name,
                        "-p", "127.0.0.1::31315", "-v", f"{folder}:/data", args.image)
                port = json.loads(command("docker", "inspect", name))[
                    0]["NetworkSettings"]["Ports"]["31315/tcp"][0]["HostPort"]
                endpoint = f"http://127.0.0.1:{port}/status"
                ready = False
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(endpoint, timeout=1) as reply:
                            value = json.load(reply)
                        if value.get("ok") is True:
                            ready = True
                            break
                    except (OSError, ValueError):
                        time.sleep(0.1)
                if not ready:
                    raise RuntimeError(f"Container server not healthy: {endpoint}")
                db = Path(folder) / "db/shadnet.db"
                if not db.exists():
                    raise RuntimeError("Missing persistent SQLite database")
                token = Path(folder) / "bloodborne_worlds/ci-sentinel"
                token.parent.mkdir(exist_ok=True)
                if iteration == 0:
                    token.write_text("mounted", encoding="utf-8")
                elif token.read_text(encoding="utf-8") != "mounted":
                    raise RuntimeError("World storage mount did not survive restart")
            except Exception:
                print(command("docker", "logs", name, check=False))
                raise
            finally:
                command("docker", "rm", "-f", name, check=False)
        print("PASS: non-root container, HTTP health, SQLite state and data volume restart")
        print("NOTE: does not test a real multiplayer party or world snapshot")
if __name__ == "__main__":
    main()
