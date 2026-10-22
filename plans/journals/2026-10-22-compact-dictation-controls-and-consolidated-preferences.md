---
title: Compact Dictation controls and consolidated Preferences
date: 2026-10-22
summary: "Relocated everyday controls, fixed active-app delivery, merged model settings, and removed App menu."
---

# Compact Dictation controls and consolidated Preferences

## What changed
- Moved language, a checkable Push to talk On/Off control, and pencil Edit hotkey action into a compact Dictation settings card.
- Confirming a captured hotkey now registers and saves immediately. Cancellation and registration failures preserve the working chord; obsolete pending/Apply UI and controller paths were removed.
- Removed the text-delivery setting and session mode plumbing. Delivery always copies first and types into the captured target when present; in-app recording stays a safe clipboard preview. Legacy JSON delivery keys are ignored without losing other preferences.
- Combined microphone, model selector/imports, compact catalog, and storage/download controls into one Preferences page. Removed the App menu, retaining tray Quit and the collision-aware quit keyboard action.
- Updated README instructions and privacy/permission notes.

## Verification
- Full pytest suite: 312 passed, 3 skipped, one existing CTranslate2/pkg_resources warning. Final affected settings/shortcut/microphone checks: 92 passed after shortcut-feedback polish.
- Ruff passed for talknj, tests, launch.py, build_portable.py, and smoke_portable.py.
- Real Windows Qt UI smoke at 1050x810 and 880x700: navigation, language/toggle persistence, actual shortcut capture and Escape cancellation, native listener replacement, disabled busy controls, no App menu, and no horizontal overflow. Screenshots include normal, empty-model, shortcut error and dialog states under .smoke/.
- Real Windows delivery smoke into a disposable external Qt process: Vietnamese Unicode inserted, clipboard copy retained, changed-focus typing refused, and preview remained clipboard-only. Original clipboard MIME content was restored.
- The initial UI smoke wait strategy timed out before model completion; explicitly joining the worker before processing queued signals made the smoke deterministic. Visual checks then exposed horizontal overflow from combo-box content size hints; bounded minimum-content sizing fixed it.

## Constraints and limits
- Requested Haiku delegation was unavailable: the native task tool rejected model overrides for ordinary agents and no Claude CLI was installed. No alternate-model delegates were used; implementation/review remained in the GPT-6.1 Sol main agent.
- No native macOS run or portable rebuild was performed. Existing plan resolution returned no active plan. No commit or publication requested.
- Automatic journal preference resolved to the default enabled state. AgentWiki publish skipped.

## Review follow-up
- Accepted the wording findings: mode guidance now explains both On (hold/release) and Off (press start/stop), and the capture card explicitly distinguishes global-hotkey typing from recording-button clipboard preview. Both toggle states were rendered and reviewed at desktop sizes without horizontal overflow.
- Confirmed a real macOS regression: the Accessibility check was outside foreground capture's failure-target handler, so permission denial raised before recording could start. A permanent native-boundary regression failed before the repair; moving the permission check inside that handler retains a refusal target rather than swallowing the error or treating it as a preview.
- The controller smoke, using the repository's simulated Mac OS/audio boundaries on Windows, exercised press/release through recording, transcription delivery and clipboard recovery: the transcript was copied, no key events were posted, and an Accessibility refusal was displayed. This is not a native macOS run.
- Final full suite: 312 passed, 3 skipped; affected Mac/shortcut tests: 133 passed; Ruff clean. The icon finding was stale: edit.svg exists, the package-data glob includes SVGs, and prior live render checks verified a non-null icon. Historical seance routing was not used as an implementation-delegation workaround.


> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
