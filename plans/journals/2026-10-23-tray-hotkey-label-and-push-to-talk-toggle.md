---
title: Tray hotkey label and push-to-talk toggle
date: 2026-10-23
summary: Added hotkey label and push-to-talk toggle to tray menu
---

# Tray hotkey label and push-to-talk toggle

## Changes
- Tray menu gains a disabled hotkey label (`Hotkey: <shortcut> (hold|press)`) and a checkable **Push to talk** action.
- The tray action drives the existing Preferences checkbox, so it persists through the same path, and it is disabled while not idle.
- Label and check state refresh in `update_hints()`, which already runs on every hotkey and preference change.

## Verification
- `tests/test_shortcuts.py`: label text follows shortcut and mode; tray toggle persists both modes; action disabled while recording.
- Full suite: 330 passed, 3 skipped. Ruff passes.
- Not exercised on a real Windows or macOS tray surface.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
