---
title: Single-row Dictation settings
date: 2026-10-22
summary: Consolidate Dictation controls into one compact responsive row.
---

# Single-row Dictation settings

## Outcome and cause
The Dictation settings used two QHBoxLayouts and an expanding language combo box. A separate Push to talk label and On/Off button text consumed extra space; Controller.populate_preferences also restored the old text on startup.

## Changes
- talknj/ui.py now places Language, its dropdown, a self-labeled checkable Push to talk button, Hotkey, the chord and pencil Edit button in one row. Existing colors and checked-state styling are retained.
- The language field caps its width at approximately 50 average characters and shrinks to fit smaller windows. Long chord text is elided only when necessary, with the full value retained in the label text and tooltip.
- talknj/app.py no longer overwrites the toggle label during settings population. README.md describes the revised row and toggle state.

## Verification
- Ran the actual Windows Qt controller smoke, not merely its source: navigation, mouse and keyboard language/toggle persistence, shortcut capture/save/cancel, busy-state disabling, real hotkey listener replacement and no horizontal overflow.
- Inspected fresh 1050x810 and 880x700 screenshots under .smoke/, including a long Ctrl+Alt+Shift+Win+F12 chord. Every settings control shares one horizontal center line without overlap; dropdown widths were 237 and 147 pixels respectively. Long chords elide at the smaller width and retain their tooltip.
- Full pytest suite: 312 passed, 3 skipped, one existing CTranslate2/pkg_resources deprecation warning. Ruff passed for talknj, tests, launch.py, build_portable.py and smoke_portable.py.
- No permanent wording/layout-copy test was added; live interaction and geometry smoke covered the UI-only refinement. No native macOS run or portable rebuild was performed. No commit or publication requested.

## Design review
Preserved the existing restrained light product UI, Segoe UI typography, indigo selected states and compact cards. Checked row alignment, group order, toggle state visibility, keyboard interaction and responsive fit against the actual renders; no unresolved defects were observed in the changed surface.

## Width refinement
The average-character cap still allowed the language dropdown to reach 237 px at the default window width. Replaced that cap with 160 px; remaining space goes to the hotkey display. Reran the real keyboard/mouse Qt controller smoke and inspected refreshed screenshots: the dropdown measures 160 px at 1050x810 and 147 px at 880x700, with one-row alignment, no horizontal overflow, and working settings persistence and shortcut editing. The full-suite result above predates this width-only adjustment; the live UI smoke covers the final sizing change.

## Left/right grouping refinement
Moved Push to talk before Language. Removed stretch factors from the dropdown and chord, added one expanding spacer between the groups, and right-aligned the chord's text next to Edit. The Edit button retains its right-edge position. The real Windows controller smoke passed at both 1050x810 and 880x700: the dropdown is 160 px at each size, the normal shortcut sits 6 px from Edit, and both groups stay on one row with no overlap or horizontal overflow. Refreshed screenshots were inspected, including long-hotkey elision at 880 px. Mouse/keyboard settings persistence, shortcut editing/cancellation and busy-state disabling passed. Affected shortcut/settings tests: 90 passed; Ruff clean. The earlier full-suite result was not rerun for this layout-only refinement. AgentWiki publish skipped.



> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
