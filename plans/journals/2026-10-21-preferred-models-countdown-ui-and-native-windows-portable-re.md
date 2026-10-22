---
title: "Preferred models, countdown UI and native Windows portable release"
date: 2026-10-21
summary: Verified updated Windows UI and all frozen local engines; macOS source/build paths complete but native artifacts remain blocked.
---

# Preferred models, countdown UI and native Windows portable release

## What happened

Preserved the current Qt layout and palette while putting whisper.cpp first/default, Parakeet second, and retaining the remaining catalog order. Existing explicit model choices survive refresh/reload. Both recording displays now show a five-minute remaining countdown. Dropdowns and scrollbars use the existing visual language and packaged SVG chevrons.

Added native macOS keyboard/foreground/Unicode/clipboard integration and native build paths for Intel and Apple Silicon; Python launch support remains. Linux is excluded. Windows portable artifacts are `dist/TalkNJ/TalkNJ.exe` and `dist/TalkNJ-windows-x64.zip`; model weights and settings remain external.

## Bugs and verification

Independent source review found that Cocoa's native Quit accelerator can bypass cleared QAction shortcuts and that aggregate Cocoa modifier identity can differ from physical key release identity. Added own-application-only Cmd+Q reservation with explicit lifecycle cleanup, and logical Darwin modifier capture. Regressions failed before the fixes and pass after them; follow-up source review found no additional blocking finding in the repairs.

The final suite passed 297 cases with 3 skips; Ruff passed. Exercised the actual Windows source desktop and portable executable, including model order/default, saved selection preservation, dropdowns, scrollbar, countdown and discarding an active recording before clean exit. The executable ran with Python removed from PATH. ZIP CRC, executable/asset inclusion and absence of selected model weights passed; archive size is 155,338,596 bytes.

Actual frozen offline inference produced expected speech transcripts with whisper.cpp-base, Parakeet int8 and faster-whisper tiny.en. whisper.cpp also reused its persistent native worker across a second transcription. The smoke restricted imports to the bundle and rejected Python socket connections. A zero exit alone was not accepted: the non-frozen harness initially used Python-style arguments, and virtualenv spawn rewriting then selected base Python; correcting frozen bootstrap identities produced the explicit inference receipt. Throwaway scripts were removed after verification; local screenshots and result receipts remain ignored evidence.

## Decisions and remaining blocker

Cross-platform boundary tests and successful wheel-only resolution for macOS x86_64/arm64 do not verify native execution. No actual Mac or runnable native Mac runner was available. No macOS executable has been built or claimed verified. Native privacy prompts, Cocoa global-tap/local-monitor ordering, focus-safe application delivery and both .app architectures still require a Mac. The implementation plan remains blocked on that release evidence. No commits, pushes or publication were performed.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
