"""Build an OS-native portable bundle and archive; never cross-compile."""

from __future__ import annotations

import importlib
import platform
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent


def main() -> int:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
        target = "windows-x64"
        bundle = ROOT / "dist" / "TalkNJ"
    elif sys.platform == "darwin" and machine in {"arm64", "x86_64"}:
        target = f"macos-{machine}"
        bundle = ROOT / "dist" / "TalkNJ.app"
    else:
        raise SystemExit("Build on Windows x64 or macOS arm64/x86_64 using native Python.")
    if not ((3, 11) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32):
        raise SystemExit("Building requires Python 3.11–3.13, 64-bit.")

    importlib.import_module("pywhispercpp.model")  # Initialize native library search paths.
    whispercpp = importlib.import_module("_pywhispercpp")

    print(f"Verified whisper.cpp native import: {machine} — {whispercpp.__file__}", flush=True)
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/file", whispercpp.__file__], check=True)

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "TalkNJ.spec"],
        cwd=ROOT, check=True,
    )
    archive = ROOT / "dist" / f"TalkNJ-{target}.zip"
    if sys.platform == "darwin":
        # ditto preserves the app's executable modes, symlinks and bundle metadata.
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)],
                       check=True)
        subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(bundle), str(archive)], check=True)
    else:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for file in sorted(bundle.rglob("*")):
                if file.is_file():
                    output.write(file, file.relative_to(bundle.parent))
    print(f"Portable bundle: {bundle}")
    print(f"Distribute: {archive}")
    print("Models and settings remain in external per-user storage; speech weights are not bundled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
