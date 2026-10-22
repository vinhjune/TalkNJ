---
title: Preferred models, countdown controls, and Windows/macOS portable releases
status: blocked
---

# Outcome
Preserve existing local dictation behavior while prioritizing whisper.cpp, showing remaining recording time, refreshing dropdowns/scrollbars, and providing Windows/macOS native portable build paths alongside Python execution. The user explicitly removed Linux from scope.

# Phases
1. [Experience](phase-01-experience.md): model priority, countdown and control styling.
2. [macOS integration](phase-02-macos.md): real platform hotkeys, clipboard/text delivery and settings location.
3. [Packaging and proof](phase-03-packaging.md): native artifacts, repeatable builds, verification and documentation.

# Shared contracts
- Preserve explicitly saved model selections; whisper.cpp is the default/first available preference, Parakeet second, with existing catalog models afterward. Never download weights implicitly.
- Five-minute audio safety cap remains unchanged. Both recording displays start at 05:00 remaining and count down without negative values.
- Preserve the existing public native integration callables and Windows behavior. macOS implements real OS APIs with actionable Input Monitoring/Accessibility permission handling and focus-safe delivery.
- UI owner: models.py, ui.py, app.py and related UI/model regressions. Allow Windows and macOS startup; use logical Qt keys rather than Windows virtual-key interpretation on macOS.
- macOS owner: native.py, new _native_macos.py, settings.py and platform-specific regressions. Parent integrates dependencies, build configuration, assets packaging and documentation.
- Keep existing palette/layout. Any new SVG UI assets live under talknj/assets and are included by package/build metadata.
- Native bundles contain runtimes, not speech weights; explicit downloads and external per-user storage remain. Build on each target OS; do not claim cross-built or unexercised macOS binaries.
- No commits, pushing or publishing without authorization. Skip mid-flight tests/lint/builds in implementation slices; run integration checks afterward.

## Delivery state
- Experience changes and native Windows packaging are complete; final Windows artifact smoke evidence is recorded in phase 03.
- The remaining release blocker is producing and exercising native macOS bundles on an actual Mac/runner. No macOS executable has been built or claimed verified on this Windows machine.
