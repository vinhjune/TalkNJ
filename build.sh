#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
sh setup.sh --dev
exec .venv/bin/python build_portable.py
