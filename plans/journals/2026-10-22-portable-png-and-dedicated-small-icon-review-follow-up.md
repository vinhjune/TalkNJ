---
title: Portable PNG and dedicated small icon review follow-up
date: 2026-10-22
summary: Addressed supported icon feedback and verified authored PNG runtime frames and native Windows packaging.
---

# Portable PNG and dedicated small icon review follow-up

## Supported feedback

Trimmed the README icon paragraph to durable artwork and platform-asset roles. Changed Qt runtime icon loading from Windows ICO to portable PNG assets. Inspected the dedicated 16/24/32/48/64 tiles against downscaled artwork; retained their authored proportions in separate PNGs and corresponding Windows ICO frames. The larger PNG and ICNS artwork remain unchanged.

## Proof

The live Windows Qt window and tray selected each dedicated PNG exactly, with transparent corners. Inspected the native title bar and light/dark previews. All seven ICO frames decode; native EXE icon payloads match source. The rebuilt wheel and frozen bundle include all eight icon assets. The production frozen smoke passed with bundle-only imports at dist/smoke/png-icons-jylk_heo/runtime.json; its 64px icon matches the dedicated PNG exactly.

308 tests passed, 3 skipped; Ruff passed. Refreshed dist/TalkNJ-windows-x64.zip is 156044423 bytes and passes CRC/artwork checks. The separately built executable remains dist/branded/TalkNJ/TalkNJ.exe, preserving the running old instance. Temporary probes were removed.

## Limits

Native Mac runtime verification is still outstanding; portable PNG loading removes an unnecessary ICO dependency but is not native Mac evidence. No commits, pushes or publication performed.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
