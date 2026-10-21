# Desktop integration
- [x] Native desktop UI exposes recording, transcript, model downloads, import, storage and selection.
- [x] Preferences expose language, microphone, output, configurable hotkey and hold/toggle behavior; atomic settings survive restart.
- [x] Tray allows background use and explicit quit; no focus stealing during hotkey activation.
- [x] Windows folder bundle builds and launches without Python installation.

Evidence: real 1050×810 desktop pages and primary recording button inspected visually; live recording, global hold/toggle shortcuts and Unicode controller delivery pass; preference persistence and tray hide/reopen pass. `dist/TalkNJ/TalkNJ.exe` builds, opens its native desktop with Python removed from PATH and exits cleanly through Ctrl+Q. Runtime is bundled; a separate clean host without Python has not been tested.
