---
title: Modifier-only and punctuation dictation shortcuts
date: 2026-10-22
summary: Support Ctrl+Win and Alt+. with verified hold/toggle behavior and unchanged release recovery.
---

# Modifier-only and punctuation dictation shortcuts

## Request and cause
Allow a wider range of global dictation shortcuts, specifically Ctrl+Win and Alt+., without changing push-to-talk or press-to-start/stop behavior. Validation previously required one non-modifier trigger, the capture dialog ignored modifier-only combinations and punctuation, and native matching assumed every chord had a trigger key.

## Changes
- Expanded shared validation/key identities for two or more distinct modifiers and modifier-plus-common-punctuation chords. Single modifiers, unmodified keys, duplicate members and multiple triggers remain unsupported.
- Updated the Qt chooser to capture these combinations, show clear instructions and require complete release before confirmation. Windows capture uses native virtual-key identities; macOS retains its logical character/Control/Command mapping.
- Updated shared chord matching and the Windows/macOS listeners for optional trigger keys. Windows modifier-only shortcuts use the passive hook without the incompatible RegisterHotKey availability probe. Ordinary shortcut probing and event forwarding remain intact.
- Added behavior regressions for modifier-only transitions, opposite physical modifier sides, punctuation identity, event forwarding, repeat handling and macOS modifier flags. Updated README usage, conflict limitations and current Windows verification evidence.

## Verification
- Captured the original unsupported behavior: nine targeted cases failed before implementation.
- Affected native, macOS-boundary, shortcut and settings regressions: 211 passed.
- Final full suite: 327 passed, 3 skipped; one existing CTranslate2/pkg_resources deprecation warning. Ruff passed for talknj, tests, launch.py, build_portable.py and smoke_portable.py.
- Real Windows Qt controller: captured and saved Ctrl+Win and Alt+. through the actual dialog, checked reloaded settings, and injected real Windows SendInput events through the production keyboard hook. Both shortcuts started/stopped correctly in hold and toggle modes. Microphone and inference were simulated with an empty transcript; this did not record speech, type text or change the clipboard.
- Inspected the new Ctrl+Win dialog and 880px Alt+. Dictation screenshot. The smoke checked both 1050x810 and 880x700 surfaces without horizontal overflow; artifacts remain under .smoke/.

## Evidence correction and limits
An initial smoke assertion did not establish a stale GetAsyncKeyState defect. The trace could show expected release after injected key-up, so it did not justify polling hysteresis. Removed the speculative regression scaffold and simplified the live smoke to completed press/release cycles. Existing immediate lost-keyup recovery and its 50ms polling interval are unchanged; autorepeat is covered by deterministic hook regressions.

No native macOS run or portable rebuild was performed. OS and focused-application shortcut actions remain unsuppressed. No commit or publication was requested.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
