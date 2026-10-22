#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ "$(uname -s)" != Darwin ]; then
    echo 'This launcher supports macOS only. On Windows use setup.ps1.' >&2
    exit 1
fi
if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != --dev ]; }; then
    echo 'Usage: sh setup.sh [--dev]' >&2
    exit 1
fi
if [ ! -x .venv/bin/python ]; then
    interpreter=''
    for candidate in python3.13 python3.12 python3.11; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14) and sys.maxsize > 2**32'; then
            interpreter="$candidate"
            break
        fi
    done
    if [ -z "$interpreter" ]; then
        echo 'Install native macOS Python 3.11–3.13 (64-bit) before setup.' >&2
        exit 1
    fi
    "$interpreter" -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.platform == "darwin" and (3,11) <= sys.version_info[:2] < (3,14) and sys.maxsize > 2**32'
.venv/bin/python -c 'import platform; assert int(platform.mac_ver()[0].split(".")[0]) >= 14, "TalkNJ requires macOS 14 or newer."'
python_architecture=$(.venv/bin/python -c 'import platform; print(platform.machine())')
if [ "$python_architecture" != "$(uname -m)" ]; then
    echo 'Use Python matching the native shell architecture; do not mix Rosetta and native builds.' >&2
    exit 1
fi
if [ "$python_architecture" = x86_64 ]; then
    if ! xcode-select -p >/dev/null 2>&1; then
        echo 'Intel whisper.cpp builds need Xcode Command Line Tools. Run xcode-select --install, then retry.' >&2
        exit 1
    fi
    # The pinned upstream release has Apple Silicon wheels, but no Intel wheel.
    # Static CPU libraries avoid leaking build-machine dylib paths into the app.
    CMAKE_ARGS="${CMAKE_ARGS-} -DGGML_NATIVE=OFF -DGGML_METAL=OFF -DWHISPER_COREML=OFF -DBUILD_SHARED_LIBS=OFF"
    export CMAKE_ARGS
fi
package='.'
if [ "${1-}" = --dev ]; then package='.[dev]'; fi
.venv/bin/python -m pip install -e "$package"
.venv/bin/python -c 'import pywhispercpp.model; import _pywhispercpp, platform, subprocess; print("Verified whisper.cpp native import:", platform.machine(), flush=True); subprocess.run(["/usr/bin/file", _pywhispercpp.__file__], check=True)'
