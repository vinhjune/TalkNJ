#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ "$(uname -s)" != Darwin ]; then
    echo 'This launcher supports macOS only. On Windows use start.ps1.' >&2
    exit 1
fi
if [ ! -x .venv/bin/talknj ]; then sh setup.sh; fi
exec .venv/bin/python -m talknj
