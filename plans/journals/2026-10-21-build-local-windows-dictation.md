---
title: Build local Windows dictation
date: 2026-10-21
summary: "Implemented local Windows dictation and repaired model, setup and native runtime integration failures."
---

# Build local Windows dictation

## Outcome
Implemented TalkNJ as a Windows Qt desktop dictation app using local CPU/int8 Whisper inference, configurable model storage and imports, English/Vietnamese selection, clipboard or original-window typing, and global hold/toggle shortcuts.

Final live desktop smoke passes recording, both shortcut modes, Unicode delivery, preference persistence and tray hide/reopen. The harness explicitly yields to audio callbacks while pumping Qt events; blocking Qt test waits had caused artificial input overflow.

## Failures and repairs
- Windows PyAV/CTranslate2 imports required compatible runtime pins: av 16.0.1, ctranslate2 4.6.0 and setuptools 80.9.0.
- Official Systran tokenizers omit the canonical 1,501 timestamp-token suffix; model validation now accepts that exact layout without relaxing model/vocabulary or special-token consistency.
- Windows PowerShell stripped embedded Python string quotes in setup probes. Quote-free interpreter checks and fallback handling now pass a clean temporary setup installation.
- Microphone selections persist stable device identity instead of volatile PortAudio indices; later launches avoid pip/network access.
- An over-specific Qt card stylesheet made the primary recording control transparent. Scoped label styling restores its visible background.

## Exercised evidence
128 behavioral tests and Ruff pass. A real Tiny English download transcribed a real speech fixture with all socket connections blocked. Actual microphone capture, Unicode clipboard/foreground insertion and changed-focus rejection were observed. The standalone bundle builds, displays its desktop with Python removed from PATH and exits cleanly through Ctrl+Q.

## Limits
Whisper punctuation remains probabilistic. Vietnamese speech quality, long-session performance, every target application's simulated-input compatibility and a separate Python-free host have not been measured. No commit or publication was requested.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
