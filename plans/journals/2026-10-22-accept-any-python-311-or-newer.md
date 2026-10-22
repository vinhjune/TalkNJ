---
title: Accept any Python 3.11 or newer
date: 2026-10-22
summary: Widen Python support to 3.11+ and bump PySide6/CTranslate2 pins with 3.14 wheels; verified on 3.11, 3.13 and 3.14.
---

# Accept any Python 3.11 or newer

## Request and outcome
Allow any Python 3 at or above 3.11 to run TalkNJ, instead of a specific 3.11–3.13 range.

## Cause
The range was enforced in `pyproject.toml` (`>=3.11,<3.14`), `setup.ps1`, `setup.sh`, `build_portable.py` and the README. The blocking pins were PySide6 6.10.2 and CTranslate2 4.6.0, which had no Python 3.14 wheels. Other pins already had 3.14 wheels; `pywhispercpp` has no Intel macOS wheel at any tag and keeps its documented source build.

## Changes
- `pyproject.toml`: `requires-python = ">=3.11"`; `PySide6==6.12.0`; `ctranslate2==4.8.0`.
- `setup.ps1`: probes the default `py -3` launcher first, then 3.20 down to 3.11; checks 64-bit and 3.11+.
- `setup.sh`: probes `python3` then python3.20 down to python3.11; checks 3.11+ 64-bit.
- `build_portable.py`: accepts 3.11+ 64-bit.
- `README.md`: requirements, launcher examples and pinned versions updated.
- Not changed: `.github/workflows/portable.yml` still builds with Python 3.13.

## Verification
- Wheel probes with macOS 14 tags: PySide6 6.12.0 (abi3 universal2), CTranslate2 4.8.0 arm64/x86_64, PyAV 16.0.1 arm64/x86_64 have cp314 wheels. The earlier macOS 11/10.15 probe was invalid.
- Real CPython 3.14.3 venv (uv): editable install with dev extras; `pytest`: 327 passed, 3 skipped; Ruff clean.
- Fresh CPython 3.13.1 venv (uv, `.venv313-verify`): same install, same result. Both verification venvs were then removed.
- Fresh-directory `setup.ps1` (no -Dev) through the real `py -3` launcher selected 3.13.1 and installed PySide6 6.12.0, CTranslate2 4.8.0, PyAV 16.0.1. Adding dev extras there: 327 passed, 3 skipped; Ruff clean.
- Fresh CPython 3.11.14 venv (uv): editable install with dev extras; 327 passed, 3 skipped; Ruff clean. Removed afterward.
- macOS 14 wheel probes cover every pinned macOS dependency for cp314, including the five `pyobjc-*==11.1` pins and `pyinstaller==6.16.0`. Intel `pywhispercpp` has no wheel and keeps its documented source build.
- `sh -n setup.sh` and `start.sh` pass; `setup.ps1` parses with zero errors through the PowerShell AST parser; `build_portable.py` compiles.
- CI: `.github/workflows/portable.yml` gains a `test` job on Windows 3.13, Windows 3.14 and macOS 3.14. This workflow is not executed locally.

## Limitations
- The existing project `.venv` is still on the old 3.13 pins: a file lock on `Qt6Core.dll` blocked reinstalling it. Run `setup.ps1` or reinstall to pick up the new pins.
- `setup.sh`, the macOS build and the Windows portable build were not executed. Native macOS execution and an end-to-end speech run on the new pins were not performed.
- Python 3.15+ is not verified; installing it depends on upstream wheels. The verified range is 3.11 through 3.14.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
