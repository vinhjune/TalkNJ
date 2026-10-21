# Native engine integration
- [x] Parakeet TDT 0.6B v2 int8 is downloadable, selectable/importable and runs locally on CPU; English-only compatibility enforced.
- [x] whisper.cpp Whisper Base is downloadable, selectable/importable and runs through actual whisper.cpp; English/Vietnamese compatibility retained.
- [x] Existing faster-whisper model behavior, atomic downloads, cancellation, progress and integrity validation remain coherent.
- [x] Dependencies and standalone bundle include both runtimes; switching releases the previous model and inference never auto-downloads.

Observed: official native exports downloaded and validated; both transcribed a real English fixture with socket connections blocked. Parakeet processes local VAD-bounded spans after a whole-context five-minute silence/tail check exposed lost speech; the repaired full-input check succeeds. whisper.cpp reused one actual spawned worker for repeated in-memory PCM requests. Integrity scans/imports now run in background jobs, preserving checksums without blocking shortcut setup.

Standalone proof: both backends transcribed the local JFK fixture through the shipped `TalkNJ.exe` multiprocessing bootstrap with Python removed from `PATH` and child imports restricted to bundled modules. Both closed cleanly; bundled whisper.cpp repeated requests reused a live native worker. The actual desktop also started, completed microphone capture and exited via Ctrl+Q with each model selected.
