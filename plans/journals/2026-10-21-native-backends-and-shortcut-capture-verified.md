---
title: Native backends and shortcut capture verified
date: 2026-10-21
summary: "Parakeet and whisper.cpp local inference, press-to-capture shortcuts, and shipped Windows runtime verification."
---

# Native backends and shortcut capture verified

## What happened
Added NVIDIA Parakeet TDT 0.6B v2 int8 through sherpa-onnx and Whisper Base through actual whisper.cpp/pywhispercpp. Existing faster-whisper behavior remains available. Catalog downloads, local import validation, model selection, CPU inference and dependency packaging cover both new formats. Parakeet is English-only; multilingual Whisper Base retains English/Vietnamese selection.

Replaced typed hotkey configuration with press-to-capture selection and verified confirm, Apply/persistence, Escape cancellation, and global hold/toggle activation on the actual Windows desktop.

## Failures and repairs
A real five-minute input with speech after long silence exposed lost Parakeet tail speech. Bounded local VAD spans preserve that speech; the real regression now passes. whisper.cpp uses a persistent spawned worker for repeated in-memory requests and native-failure isolation. Failed engines are released without automatically retrying a recording. Integrity discovery/import work runs off the GUI thread.

Three Qt regressions failed before their fixes and passed afterward: accepted-dialog deactivation, both physical Ctrl keys held, and capture of Ctrl+Q colliding with Quit. Standalone runtime smoke then caught missing vendored jaraco despite a successful build; exposing setuptools' vendor path to PyInstaller fixed actual startup. One automation focus handoff was denied by Windows; the throwaway driver grants activation with an Alt press/release rather than changing application focus behavior.

## Verification
- Full native-enabled suite: 198 passed, one Windows symlink-permission skip. Ruff passes; pip check reports no broken requirements. The documented external CTranslate2/setuptools deprecation warning remains visible.
- Permanent opt-in native checks cover real five-minute tail speech and persistent whisper.cpp PCM requests using explicit local model/fixture paths, without automatic downloads.
- Both official new model exports transcribed real English speech locally with Python socket connections blocked.
- Rebuilt dist/TalkNJ/TalkNJ.exe opened, completed microphone capture and exited cleanly via Ctrl+Q with each new model selected. Desktop screenshots were inspected.
- The shipped executable's real multiprocessing bootstrap also transcribed the local JFK fixture through each bundled native backend. Child imports were restricted to shipped files and Python was removed from PATH. Both engines closed cleanly; repeated bundled whisper.cpp requests reused one live worker.

## Decisions and boundaries
The five-minute application safety/latency guard stays unchanged; it is not a model duration limit. Real-time partial preview is feasible with bounded rolling chunks and a final pass, but streaming and changed text-delivery semantics are not part of this update. No cloud fallback, automatic recording retry, GPU requirement, commits or publication were added.

README and all three implementation phases record the exercised evidence and reproduction prerequisites. Temporary smoke harnesses and audio/screenshots are removed after verification; production model downloads remain available to the app.

## Remaining measurement limits
Vietnamese speech-recognition quality, five minutes of continuous-speech accuracy, sustained throughput, arbitrary target-app compatibility and installation on a separate Python-free machine have not been measured. These are measurement limits, not claims of completed benchmarks.

## Advisory review follow-up
The packaged-runtime concern predates the deterministic JFK proof through the actual shipped executable. Startup hashing is already in background jobs. Explicit backend metadata, format-specific validation, allowlisted raw model files and atomic installation already address the format/download concern without introducing archive extraction.

An actual Windows SendInput probe pressed Win first, then Ctrl+F9, and released the entire chord. The picker stayed visible, enabled Use shortcut after release, and returned `ctrl+win+f9`; its screenshot was inspected. The proposed WindowDeactivate removal was not justified by this observed behavior, so focus-loss cancellation remains to avoid retaining incomplete key state after genuinely losing focus.

Added two permanent fast Parakeet cases for ordered three-span output and omission of blank decoded text. These exercise aggregation behavior rather than a forwarding-only mock contract; the real whisper.cpp integration regression remains. The updated default suite passes 198 cases with three skips, and Ruff passes. No application behavior changed, so the existing shipped-bundle inference proof remains applicable. Temporary follow-up probe and screenshot are removed.


> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
