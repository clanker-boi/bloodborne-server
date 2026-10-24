# syntax=docker/dockerfile:1.7
# Architecture-native server builder. BuildKit cache survives rebuilds.
FROM --platform=$BUILDPLATFORM ubuntu:24.04 AS build
ARG TARGETARCH
ARG BUILDPLATFORM
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv pipx cmake ninja-build clang \
    git ca-certificates pkg-config build-essential && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"
RUN pipx install 'conan>=2.31,<3' && conan profile detect --force
WORKDIR /src
COPY . .
# Native cross-architecture builds are achieved using buildx emulation or native runners.
# Cross-compiler setups should use explicit Conan build/host profiles instead.
RUN --mount=type=cache,target=/root/.conan2/p \
    python3 tools/yt.py configure server && \
    python3 tools/yt.py build server
RUN --mount=type=cache,target=/root/.conan2/p \
    python3 tools/yt.py test server
