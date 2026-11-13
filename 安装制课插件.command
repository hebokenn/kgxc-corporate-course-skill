#!/bin/sh
cd -- "$(dirname -- "$0")"
exec python3 scripts/install_plugin.py --host dsh
