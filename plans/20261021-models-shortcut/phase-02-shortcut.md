# Press-to-capture shortcut
- [x] A visible capture interaction records a chord by pressing keys; no manual chord typing is needed.
- [x] Escape cancellation, invalid/pure-modifier rejection and failed registration retain a usable previous shortcut.
- [x] Capturing an existing shortcut cannot start dictation or leave an active gesture stuck.
- [x] Saved shortcut survives reload and globally activates hold/release and toggle modes while another application is foreground.

Observed on Windows with real SendInput: Ctrl+Alt+F9 capture, full release, Use shortcut, Apply, settings reload, active-chord capture cancellation, and hold/toggle recording from another foreground editor with each new backend. Failing-before/passing-after regressions cover acceptance-time deactivation, both physical Ctrl keys, and Ctrl+Q recording versus the Quit action. Old-listener events and release events from button-started recordings are guarded.
