---
title: Review follow-up modifier release macOS permissions and frozen smoke
date: 2026-10-21
summary: Repaired review findings; verified rebuilt Windows bundle and all engines; native Mac release evidence remains blocked.
---

# Review follow-up modifier release macOS permissions and frozen smoke

## What happened

Closed the late-review source and packaging gaps: Darwin shortcut capture now uses raw QInputEvent modifier state so either physical release order of both-side modifiers remains coherent. Clipboard-only shortcuts require Input Monitoring, not Accessibility; foreground capture and automatic typing retain their Accessibility requirement. The controller regression reaches actual recording state rather than checking mock forwarding.

The native build workflow now gates uploads on a model-free frozen-runtime import and Qt render smoke with fresh per-run receipts. Setup/build imports the actual whisper.cpp extension and checks native interpreter identity; macOS additionally reports Mach-O architecture with file. README now documents the Windows build command, Intel compiler prerequisites, least-privilege permissions and verification limits.

## Failure and verification

The rebuilt Windows artifact initially failed the new smoke with ModuleNotFoundError for pywhispercpp. Analysis confirmed the package was bundled: multiprocessing preparation had overwritten the frozen import roots with source-interpreter paths, leaving an empty path after filtering. Restoring only frozen import roots fixed the harness without source/venv fallbacks.

The final suite passed 308 cases with 3 skips; Ruff and shell syntax checks passed. The rebuilt frozen executable loaded all speech runtimes and production controller modules from its own bundle and rendered the actual Qt window. A real zero-exit bootstrap without a target receipt was rejected. Offline fixture inference succeeded with whisper.cpp-base, Parakeet int8 and faster-whisper tiny.en; a repeated whisper.cpp transcription reused its native worker. Fresh evidence is recorded in the packaging phase. ZIP CRC validation passed for the 155,336,757-byte Windows archive, including executable/assets and excluding selected speech-model weights.

## Remaining blocker

No native Mac or runnable Mac runner is available. Intel and Apple Silicon apps have not been built or exercised, and actual Cocoa event ordering, privacy prompts and foreground delivery remain unverified. The release plan stays blocked on that native evidence. No commits, pushes or publication were performed.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
