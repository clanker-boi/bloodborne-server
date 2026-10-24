#!/bin/sh
set -eu
mkdir -p /data/db /data/bloodborne_worlds /data/reports
if [ ! -f /data/shadnet.cfg ]; then
  cp /opt/yharnam/config/shadnet.cfg /data/shadnet.cfg
fi
exec /opt/yharnam/bin/shadnet "$@"
