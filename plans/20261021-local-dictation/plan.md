---
title: TalkNJ local Windows dictation
status: completed
---

# Outcome
A runnable Windows desktop dictation app using local CPU models, with no cloud inference. English and optional Vietnamese, natural punctuation, explicit clipboard-only or active-app typing, global hold/toggle hotkey, user-chosen model storage and selection.

# Decisions and boundaries
- Python 3.11–3.13, Qt/PySide6, faster-whisper with CPU int8; Windows 10/11 x64.
- Local Systran CTranslate2 Whisper model downloads; import compatible existing model folders without copying.
- Clipboard-only is the safe initial mode. Typing requires unchanged original foreground application and released modifiers; clipboard and transcript preserve recovery.
- No accounts, telemetry, cloud fallback, live word-by-word streaming, LLM rewriting, GPU configuration, publication or repository operations.
- Whisper provides punctuation probabilistically; neither perfect punctuation nor Vietnamese accuracy is guaranteed. Five-minute recording limit bounds memory.

# Phases
1. [phase-01-core.md](phase-01-core.md): local model, capture, inference and Windows integration.
2. [phase-02-desktop.md](phase-02-desktop.md): desktop UI, persistence, tray and packaging.
3. [phase-03-verification.md](phase-03-verification.md): runtime proof, review and onboarding.
