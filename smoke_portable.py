"""Exercise the native frozen bundle without models, microphone capture or permissions.

Run after build_portable.py. Each run uses a fresh evidence directory, so a
successful bootstrap cannot reuse an old receipt. No app-only test CLI is added.
"""

from __future__ import annotations

import importlib
import json
import multiprocessing
from pathlib import Path
import platform
import runpy
import sys
import tempfile
import traceback


ROOT = Path(__file__).resolve().parent


def _exercise(report_path: Path) -> int:
    window = None
    try:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Smoke target must execute in the frozen bundle.")
        bundle = Path(sys._MEIPASS).resolve()
        # macOS may symlink package data between Frameworks and Resources.
        container = Path(sys.executable).resolve().parent.parent if sys.platform == "darwin" else bundle
        # Spawn inherits the source parent's paths; restore only frozen import roots.
        sys.path[:] = [str(bundle), str(bundle / "base_library.zip"), str(bundle / "lib-dynload")]
        modules = {}
        for name in (
            "pywhispercpp.model", "_pywhispercpp", "av", "ctranslate2",
            "faster_whisper", "sherpa_onnx", "sounddevice", "talknj.audio",
            "talknj.transcription", "talknj._whispercpp", "talknj.native", "talknj.ui",
            "talknj.app",
        ):
            module = importlib.import_module(name)
            location = Path(module.__file__).resolve()
            if not location.is_relative_to(container):
                raise RuntimeError(f"{name} escaped the bundle: {location}")
            modules[name] = str(location)
        if sys.platform == "darwin":
            importlib.import_module("talknj._native_macos")._MacAPI()

        from PySide6.QtWidgets import QApplication
        from talknj.ui import MainWindow

        application = QApplication([])
        window = MainWindow()
        window.show()
        application.processEvents()
        image = report_path.with_suffix(".png")
        if not window.grab().save(str(image)):
            raise RuntimeError("The frozen Qt window could not be rendered.")
        icon_image = report_path.with_suffix(".icon.png")
        icon = window.windowIcon().pixmap(64, 64)
        if icon.isNull() or not icon.save(str(icon_image)):
            raise RuntimeError("The frozen application icon could not be rendered.")
        result = {"ok": True, "platform": sys.platform, "architecture": platform.machine(),
                  "executable": sys.executable, "modules": modules, "screenshot": str(image),
                  "icon": str(icon_image)}
    except BaseException:
        result = {"ok": False, "error": traceback.format_exc()}
    finally:
        if window is not None:
            window.allow_close = True
            window.close()
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


def main() -> int:
    if sys.platform == "win32":
        executable = ROOT / "dist" / "TalkNJ" / "TalkNJ.exe"
    elif sys.platform == "darwin":
        executable = ROOT / "dist" / "TalkNJ.app" / "Contents" / "MacOS" / "TalkNJ"
    else:
        raise SystemExit("Run on the native Windows or macOS build host.")
    if not executable.is_file():
        raise SystemExit("Native bundle not found; run build_portable.py first.")
    evidence_root = ROOT / "dist" / "smoke"
    evidence_root.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="bundle-", dir=evidence_root))
    report = evidence / "runtime.json"
    # Match freeze_support's bootloader command shape. Setting the base identity
    # also prevents Windows venv spawning from redirecting back to base Python.
    sys.executable = str(executable)
    sys._base_executable = sys.executable
    sys.frozen = True
    multiprocessing.set_executable(sys.executable)
    process = multiprocessing.get_context("spawn").Process(
        target=runpy.run_path, args=(str(Path(__file__).resolve()),),
        kwargs={"run_name": "__frozen_smoke__", "init_globals": {"_REPORT_PATH": str(report)}},
    )
    process.start()
    try:
        process.join(90)
        if process.is_alive():
            process.terminate()
            process.join()
            print("Frozen runtime smoke timed out.", file=sys.stderr)
            return 1
        result = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else None
        print(json.dumps({"exit_code": process.exitcode, "receipt": str(report), "result": result}, indent=2))
        return 0 if process.exitcode == 0 and result and result.get("ok") is True else 1
    finally:
        process.close()


if __name__ == "__frozen_smoke__":
    raise SystemExit(_exercise(Path(globals()["_REPORT_PATH"])))
elif __name__ == "__main__":
    raise SystemExit(main())
