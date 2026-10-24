# syntax=docker/dockerfile:1.7
# Only COPY the tested, staged application; never build Qt or C++ inside image.
FROM ubuntu:24.04
LABEL org.opencontainers.image.source="https://github.com/clanker-boi/bloodborne-server" \
      org.opencontainers.image.description="Yharnam Together headless shadNet server"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl libsqlite3-0 libssl3t64 zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 yharnam && useradd -r -u 10001 -g yharnam -d /data yharnam \
    && mkdir -p /data /opt/yharnam && chown yharnam:yharnam /data
COPY opt/yharnam/ /opt/yharnam/
COPY --chown=10001:10001 docker-entrypoint.sh /opt/yharnam/bin/entrypoint.sh
COPY shadnet.cfg /opt/yharnam/config/shadnet.cfg
ENV SHADNET_HOME=/data \
    LD_LIBRARY_PATH=/opt/yharnam/lib \
    QT_PLUGIN_PATH=/opt/yharnam/plugins
USER 10001:10001
VOLUME ["/data"]
EXPOSE 31314/udp 31315/tcp 20443/tcp
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=15s --timeout=4s --start-period=15s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:31315/status || exit 1
ENTRYPOINT ["/bin/sh", "/opt/yharnam/bin/entrypoint.sh"]
