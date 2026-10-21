# Verification and delivery
- [x] Relevant behavioral tests and static checks pass.
- [x] Real downloaded model transcribes a real English speech fixture offline, with visible meaningful punctuation.
- [x] Actual desktop window, global keyboard gesture, Unicode clipboard and foreground insertion are exercised.
- [x] Model compatibility and failure paths receive review; actionable findings fixed.
- [x] Setup, model quality/privacy and Windows limitations documented; exercised evidence distinguished from unverified hardware/quality limits.

Evidence: 128 tests and Ruff pass. Fresh `setup.ps1` installation succeeds under Windows PowerShell. Official tiny.en now accepts the canonical tokenizer timestamp-tail omission and transcribes the JFK sample with all socket connections blocked. Native runtime dependency pins, microphone identity persistence, offline later launches and cleanup error handling repaired after review. Standalone bundle builds, shows a real window with Python absent from PATH and exits through Ctrl+Q. CTranslate2 emits its upstream pkg_resources deprecation warning. Vietnamese speech quality and a separate Python-free host remain unverified.

Final desktop smoke: actual recording cycle, global hold with repeat suppression, global toggle, clipboard and original-window Unicode delivery, changed-focus refusal, persisted preferences and tray hide/reopen all pass. The smoke harness yields the Python GIL while pumping Qt events so real audio callbacks can run; blocking Qt test waits had caused artificial input overflow.
