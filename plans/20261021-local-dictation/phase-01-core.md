# Core engine
- [x] Download/select small models into a user-chosen folder and import compatible existing folders.
- [x] Capture bounded 16 kHz audio and run local-only CPU Whisper with English/Vietnamese compatibility checks and natural punctuation.
- [x] Observe global hold/toggle chord gestures without key repeat activation.
- [x] Copy Unicode text or type safely into the unchanged original foreground window.

Evidence: 128 deterministic behavior tests; official tiny.en download, model discovery, network-blocked English speech transcription with punctuation, English-model/Vietnamese rejection, real microphone capture, real Win32 Unicode clipboard/typing (Vietnamese and supplementary-plane text), focus-change refusal and global keyboard-hook transitions. Vietnamese recognition quality remains unmeasured.
