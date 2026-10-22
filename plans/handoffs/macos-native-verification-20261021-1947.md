---
handoff-version: 1
generated: 2026-10-21T19:47:23Z
generator: ak:handoff@2.1.0
focus: Mac native build and runtime verification
branch: master
head: 72631a586ddbaea0174c4d13470987c6ac73b00c
---

# HANDOFF: Mac native build and runtime verification

## Mission and current status

Continue TalkNJ on a real Mac: build, exercise and repair the macOS application, then record honest native release evidence. TalkNJ is local speech-to-text dictation, not TTS or streaming transcription.

**Done:** Windows desktop, portable packaging, three local inference engines, model priority, countdown/control polish, macOS OS integration and native build paths are implemented. Windows runtime evidence is complete. The latest suite passed **308 tests, 3 skipped**; Ruff passed.

**Remaining:** Actual native Intel and Apple Silicon `.app` builds and runtime verification. The owning plan remains **blocked**, not complete: `plans/20261021-portable-polish/plan.md`. Source inspection, fake-OS tests and wheel resolution are not native Mac evidence.

## Scope and guardrails

- **Workspace:** this project root on the destination Mac; paths below are repo-relative.
- **In scope:** native Mac setup/build failures, real PyObjC/Qt event ordering, permissions, dictation/output, packaging and regressions caused by repairs.
- **Out of scope:** Linux, new features, cloud inference, model rewrites, streaming, installers, public signing/notarization or publication.
- **Constraints:** preserve Windows behavior; keep Python launch support; support macOS 14+ and native 64-bit Python 3.11–3.13. Build separately on each target architecture; do not call a Rosetta build native Intel verification.
- Preserve valid saved model choices. With no valid choice, prefer whisper.cpp, then Parakeet, then the existing faster-whisper order. Never download weights implicitly.
- Preserve clipboard-only and automatic typing modes, hold/toggle shortcuts, and the five-minute capture cap. Both recording displays count down from `05:00 remaining`.
- Audio stays in memory; both output modes copy to the clipboard. Models/settings remain external to the app bundle. Do not introduce cloud fallbacks, telemetry or transcript history.
- **Safety boundaries:** do not discard existing changes, copy personal settings into evidence, bypass OS security, reset privacy databases, disable Gatekeeper globally, or test insertion in sensitive/user documents. No commits, pushes, workflow dispatch or publication without authorization.

## Current state

Snapshot captured before writing this handover; re-check it on the Mac.

- **Branch:** `master`
- **HEAD:** `72631a586ddbaea0174c4d13470987c6ac73b00c`
- **Working tree:** dirty; 14 modified tracked files and 17 untracked files below.
- **Intentional local modifications:** yes; existing implementation changes are to be preserved. Their authorship is not inferred from Git status.
- **Changed files:**

```text
README.md
TalkNJ.spec
build.ps1
pyproject.toml
talknj/app.py
talknj/audio.py
talknj/models.py
talknj/native.py
talknj/settings.py
talknj/ui.py
tests/test_models.py
tests/test_native.py
tests/test_settings.py
tests/test_shortcuts.py
```

- **Untracked files:**

```text
.github/workflows/portable.yml
build.sh
build_portable.py
packaging/macos-entitlements.plist
plans/20261021-portable-polish/phase-01-experience.md
plans/20261021-portable-polish/phase-02-macos.md
plans/20261021-portable-polish/phase-03-packaging.md
plans/20261021-portable-polish/plan.md
plans/journals/2026-10-21-preferred-models-countdown-ui-and-native-windows-portable-re.md
plans/journals/2026-10-21-review-follow-up-modifier-release-macos-permissions-and-froz.md
setup.sh
smoke_portable.py
start.sh
talknj/_native_macos.py
talknj/assets/chevron-down-disabled.svg
talknj/assets/chevron-down.svg
tests/test_native_macos.py
```

This handover is one additional new file after that snapshot. **A clone of HEAD alone will omit the current Mac implementation and build tooling.** Transfer the modified AND untracked project files, including this document. Do not transfer/reuse the Windows `.venv`, `build/` or `dist/` as Mac dependencies/artifacts. Ignored `.smoke/` and `dist/smoke/` evidence may not be transferred; it is historical Windows evidence, not a Mac prerequisite. Model weights live outside the repository by default. Previous Eval variables and in-memory inference scripts are not available to the next session.

## Decisions and rationale

- **Python + Qt/PySide6 with CPU inference:** retain the existing working stack rather than replace it during native validation. Current pins are in `pyproject.toml`.
- **Three real local backends:** whisper.cpp Base via `pywhispercpp`, Parakeet int8 via sherpa-onnx, and faster-whisper. whisper.cpp uses a persistent child process to isolate native failures; it must work in a frozen app as well as source execution.
- **Real OS integration:** `talknj/native.py` routes to `talknj/_native_macos.py` on Darwin. Quartz observes global keys; AppKit/Accessibility provide clipboard, foreground targets and Unicode delivery. No simulated success fallback.
- **Least privilege:** clipboard-only global dictation needs Microphone and Input Monitoring, not Accessibility. Foreground-target capture/automatic typing additionally needs Accessibility. Permission denial must give actionable UI feedback without crashing.
- **Focus safety is best effort:** typing revalidates the original process, window and focused element, and waits for modifiers. PID-targeted events cannot eliminate asynchronous focus races. Refuse changed/inaccessible targets and preserve the complete clipboard transcript; do not weaken these checks.
- **Mac modifier semantics:** keep Command and Control distinct. The chooser reads `QInputEvent.modifiers`, not `QKeyEvent`'s own-modifier toggle. Logical modifiers remain held until the aggregate mask clears, including both-side press/release sequences.
- **Cmd+Q:** reserve it only inside TalkNJ when configured as the recording shortcut. The local monitor must coexist with the passive global tap. Explicit menu/tray Quit remains available; other apps retain their normal Cmd+Q behavior.
- **Native packaging only:** PyInstaller makes separate architecture-specific bundles. macOS uses ad-hoc signing and `ditto` ZIP creation to preserve symlinks/modes; it is not Developer ID-signed or notarized. See `TalkNJ.spec`, `build_portable.py` and `packaging/macos-entitlements.plist`.

## Work performed

- Model ordering/default and saved-selection handling, countdown displays, dropdowns/scrollbars and bundled SVG assets were implemented and exercised on Windows.
- macOS integration and platform-specific settings location were implemented. Default Mac data root is `~/Library/Application Support/TalkNJ/`; never assume Windows absolute model paths are usable on the Mac.
- Review repairs addressed Cocoa Cmd+Q dispatch, both-side modifier release and unnecessary Accessibility checks in clipboard-only recording. Behavior regressions cover these boundaries; they have not yet proved actual Cocoa/PyObjC execution.
- `setup.sh` checks OS/Python versions and Python/shell architecture consistency. Intel requires Xcode Command Line Tools because pinned `pywhispercpp==1.5.1` has no Intel Mac wheel. Its source build uses portable static CPU flags, with Metal/CoreML disabled. Setup/build imports the real extension and prints its Mach-O architecture with `file`.
- `.github/workflows/portable.yml` defines Windows, `macos-15` arm64 and `macos-15-intel` jobs. Each checks tests/lint, builds, runs the frozen smoke and only then uploads an archive. This is configured source, not evidence that any Mac job ran.
- `smoke_portable.py` launches the frozen executable through multiprocessing, imports all three runtimes and production modules from the bundle, and renders the Qt window. Each run creates a new receipt directory; zero exit without a fresh successful receipt fails.
- The first rebuilt Windows smoke failed with `ModuleNotFoundError: pywhispercpp` even though Analysis included it. Spawn preparation had replaced frozen import roots with source-parent paths, and filtering left no paths. Restoring only bundle roots fixed this. On Mac, package-data symlinks can resolve between `Contents/Frameworks` and `Contents/Resources`; preserve the container-aware checks.
- No implementation commits, pushes or publication were performed in this session. Git identity/status were read for this handover only.

0 redactions applied; no credentials or personal absolute filesystem paths are included.

## Verification

All outcomes below are **Windows-session evidence**, not Mac results.

| Check | Command or scenario | Outcome | When |
|---|---|---|---|
| Behavioral suite | `.venv/Scripts/python.exe -m pytest -q` | 308 passed, 3 skipped; upstream pkg_resources deprecation warning | Final source state before handover |
| Lint | `.venv/Scripts/python.exe -m ruff check talknj tests launch.py build_portable.py smoke_portable.py` | Passed | Same final state |
| Shell syntax | `sh -n setup.sh build.sh start.sh` | Passed; not native execution | Same final state |
| Windows build | `.venv/Scripts/python.exe build_portable.py` | Produced executable and ZIP | Final Windows rebuild |
| Frozen runtime/UI | `.venv/Scripts/python.exe smoke_portable.py` | Bundle-only imports and rendered Qt window passed; screenshot inspected | After import-root repair |
| Fresh receipt requirement | Actual frozen zero-exit bootstrap that never ran the target | Rejected as intended | Same rebuilt artifact |
| Offline inference | Actual frozen process with local JFK speech and all three models | Expected speech from whisper.cpp Base, Parakeet int8 and tiny.en; repeated whisper.cpp call reused worker | Same rebuilt artifact |
| Windows ZIP | CRC plus executable/assets/selected-weight checks | Passed; 155,336,757 bytes; speech weights excluded, bundled VAD retained | Same rebuilt artifact |

Windows receipts, if transferred: `dist/smoke/bundle-0hjxydqa/runtime.json` with its PNG, and `.smoke/final-models-9vg8ps4w/inference.json`. Do not reuse these to validate a Mac build. The three-engine frozen inference probe was in-memory, not a checked-in reusable script.

**Not run:**
- Native Mac setup, PyObjC calls, microphone/privacy prompts, actual global/local event ordering, secure-input behavior, Unicode delivery and Qt desktop interaction: no Mac was available.
- Intel/Apple Silicon `.app` builds, extracted-archive launch, native signing verification and real-model frozen Mac inference: no native runner was available. Prior wheel-only resolution for both architectures is not a substitute.
- Opt-in native tests are not proof merely because the default suite passes: explicitly provide their local assets and inspect skips on the Mac.

## Open risks and blockers

- **Type: blocker. Owner: next Mac session. Impact:** native runtime/build evidence is the remaining release gate. A single Mac verifies only its architecture; keep the other architecture open until a native runner/machine is exercised.
- **Type: risk. Owner: next Mac session. Impact:** PyObjC API signatures, Quartz run-loop teardown, aggregate modifier flags, Qt/AppKit Cmd+Q ordering, Unicode scalars and permission changes may differ from boundary fakes. Reproduce before changing behavior; repair root causes, not tests to match failures.
- **Type: risk. Owner: next Mac session. Impact:** native libraries, frozen subprocess spawning, Qt plugins, bundle symlinks or signing may fail only after packaging/extraction. Source execution alone is insufficient.
- **Type: risk. Owner: user and next Mac session. Impact:** source and bundled apps may have different privacy identities; grant permissions to the actual Terminal/Python host or TalkNJ as appropriate, then relaunch. Do not assume one grant covers both.
- **Type: risk. Owner: next Mac session. Impact:** a clean clone misses the uncommitted/untracked work listed above. Verify the transferred tree before diagnosing missing files.

## Exact next actions

1. **First safe step** — from the transferred project root on the Mac, read this handover and the owning plan, then compare the actual workspace and native host before editing:

   ```sh
   pwd
   git rev-parse --abbrev-ref HEAD
   git rev-parse HEAD
   git status --short --untracked-files=all
   sw_vers
   uname -m
   ```

   Confirm the modified/untracked Mac files are present. Use a native Terminal/Python, not a mixed Rosetta environment. Do not recreate the missing implementation from a clean HEAD or discard differences to match this snapshot.

2. Confirm macOS 14+ and native Python 3.11–3.13. On Intel, check `xcode-select -p`; if missing, run `xcode-select --install` and complete the OS installer. Create a Mac-local environment with `sh setup.sh --dev`. Do not reuse a Windows or other-architecture virtual environment. Inspect the setup output for actual whisper.cpp import and Mach-O architecture; do not work around failures with disabled engines or fake libraries.

3. Run the isolated checks and record exact Mac results/skip reasons:

   ```sh
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
   .venv/bin/python -m ruff check talknj tests launch.py build_portable.py smoke_portable.py
   sh -n setup.sh build.sh start.sh
   ```

   Keep `QT_QPA_PLATFORM=offscreen` confined to the test command; desktop verification must use the real UI. Diagnose Mac failures before editing and rerun affected checks after repairs.

4. Launch the real source UI with `sh start.sh` or `.venv/bin/python -m talknj`. Use explicit model downloads/imports via Model library; obtain whisper.cpp Base, Parakeet int8 and tiny.en for parity with Windows. Use a multilingual model for Vietnamese. Record setup/permission observations and screenshots. Exercise the following in disposable TextEdit documents, not personal content:

   - Microphone capture, English transcription and natural punctuation with each backend; clipboard-only output; repeated whisper.cpp recordings.
   - Clipboard-only global dictation with Microphone/Input Monitoring granted and Accessibility denied. No Accessibility prompt or AX target-capture requirement should be introduced for this mode.
   - Automatic insertion with Accessibility granted: original app/window/element stays selected, clipboard retains the full transcript; changed/closed targets refuse typing instead of redirecting it. Check Unicode/Vietnamese output with a suitable multilingual model, without promising recognition quality.
   - Hold and toggle gestures, auto-repeat, rebind/cancel, left/right modifiers held together and released in both orders, trigger release and lost-release recovery. Display Command/Option/Control/Shift correctly.
   - Configure Cmd+Q and test inside TalkNJ: recording must not unexpectedly quit it; explicit Quit must remain available. Other apps must not have Cmd+Q suppressed. Use only disposable apps/documents for this check.
   - Denied/revoked Input Monitoring or Accessibility, listener restart/teardown, button recording when global listening is denied, and actionable errors without hangs or false success.
   - Model priority, saved selection after refresh/relaunch, dropdown/scrollbar rendering, countdown in both displays, tray/menu-bar behavior and discard-and-quit. Closing the window hides the app; it is not Quit.

5. Run the existing opt-in real-model regressions after obtaining the public JFK WAV from the upstream link in README. Substitute its actual local path below. The model root must contain the catalog-named `whisper.cpp-base` and `parakeet-tdt-0.6b-v2-int8` directories; adapt it if using another download location:

   ```sh
   TALKNJ_NATIVE_MODELS="$HOME/Library/Application Support/TalkNJ/models" \
   TALKNJ_NATIVE_SPEECH="/absolute/path/to/jfk.wav" \
   .venv/bin/python -m pytest tests/test_native_engines_integration.py -q
   ```

   These tests exercise speech after long silence and persistent-worker reuse. They do not download assets or prove packaged execution.

6. Quit every source/bundled TalkNJ instance via its explicit Quit menu before switching launch modes; the app is single-instance. Build and smoke the actual native bundle:

   ```sh
   sh build.sh
   .venv/bin/python smoke_portable.py
   codesign --verify --deep --strict dist/TalkNJ.app
   open dist/TalkNJ.app
   ```

   Expected outputs are `dist/TalkNJ.app` and `dist/TalkNJ-macos-arm64.zip` OR `dist/TalkNJ-macos-x86_64.zip`. Inspect the fresh `dist/smoke/` receipt and PNG; assert the target ran, not just a zero process exit. This smoke loads native runtimes and renders Qt but intentionally does not exercise permissions, microphone or real-model inference.

7. In the frozen app, repeat the meaningful microphone/hotkey/permission/clipboard/typing checks and actual inference with all three backends, including repeated whisper.cpp use. Source tests and model-free smoke alone cannot close this gate. Verify the ZIP after extracting into a separate directory, preserving symlinks/modes (Finder or `ditto`), then quit the original instance and launch that extracted app. Confirm selected speech weights/settings are not embedded and no source checkout/venv is required for normal launch. Use the documented per-app Open Anyway flow if needed; do not disable Gatekeeper globally.

8. Repeat native build/smoke/runtime evidence on the other architecture when available. The existing workflow is a possible build route only with authorization to publish changes/dispatch; CI model-free success still does not prove interactive permissions or typing. If only one architecture is reachable, finish it and state exactly what remains unverified for the other.

9. Repair concrete native failures within scope, add consumer-visible regressions where useful, and rerun affected tests plus actual app scenarios. Update README and `plans/20261021-portable-polish/phase-02-macos.md`, `phase-03-packaging.md` and `plan.md` with OS/architecture, commands, receipts, screenshots and actual outcomes. Mark the release complete only when every remaining native acceptance item is evidenced. Remove throwaway scripts after proof, retain appropriate ignored evidence, and report unresolved limitations. Do not commit, push or publish unless separately authorized.

## Source pointers

- `README.md`: supported setup, permissions, model formats, privacy limits, source/build commands and public JFK fixture link.
- `plans/20261021-portable-polish/plan.md` and its three phase files: current outcome, acceptance and explicit native release blocker.
- `talknj/_native_macos.py`, `talknj/native.py`: real OS boundary, permission checks, key identity/listener lifecycle, foreground capture and Unicode delivery.
- `talknj/app.py`, `talknj/ui.py`, `talknj/settings.py`: controller capture policy, shortcut chooser, recording displays and native per-user storage.
- `talknj/audio.py`, `talknj/models.py`, `talknj/transcription.py`, `talknj/_whispercpp.py`: microphone capture, model validation/order and actual CPU engines/persistent worker.
- `tests/test_native_macos.py`, `tests/test_shortcuts.py`, `tests/test_native_engines_integration.py`: platform boundary/recording regressions and opt-in real-model checks.
- `pyproject.toml`, `setup.sh`, `start.sh`, `build.sh`, `build_portable.py`, `TalkNJ.spec`, `packaging/macos-entitlements.plist`: dependency pins, native build/signing configuration and launch paths.
- `smoke_portable.py`, `.github/workflows/portable.yml`: permanent fresh-receipt frozen smoke and architecture matrix.
- `plans/journals/2026-10-21-review-follow-up-modifier-release-macos-permissions-and-froz.md`: latest historical repair/proof record; current plan/docs remain authoritative.
