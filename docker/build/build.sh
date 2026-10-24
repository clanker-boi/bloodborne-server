#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
# Buildx invokes the same canonical Python/CMake/Conan workflow used locally.
platforms="${PLATFORMS:-linux/amd64,linux/arm64}"
docker buildx build --platform "$platforms" \
  --file docker/build/Dockerfile \
  --progress plain \
  --target build \
  "${@}" .
