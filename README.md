# TalkNJ

Private voice dictation for Windows 10/11 x64 and macOS 14+ (Apple Silicon or Intel). Speak, release your shortcut, and get text in your clipboard or the application you were using. Audio is transcribed **on your CPU** with local Whisper or Parakeet models, not a cloud service. Windows is runtime-verified; the macOS implementation/build path still requires verification on a real Mac.

This is **speech-to-text**, not text-to-speech. Recognition happens after recording stops; it is not live word-by-word streaming.

## About

- **License:** [GPL-3.0-only](LICENSE)
- **Creator:** Vinh Hoang
- **Email:** [hoangthevinh.htv@gmail.com](mailto:hoangthevinh.htv@gmail.com)

These details are also available in the app's **About** section.

## Run from source

### Windows

Install **Python 3.11 or newer, 64-bit** with the Windows Python launcher, then run in PowerShell:

```powershell
.\start.ps1
```

On first run, `start.ps1` invokes `setup.ps1` to create `.venv` and install dependencies. Later launches do not invoke pip and work offline with an installed model. Run `.\setup.ps1` explicitly after updating source dependencies, or `.\setup.ps1 -Dev` to install development tools. Setup uses the default `py -3` interpreter when it is 3.11 or newer, otherwise the newest installed 3.11+ release. It rejects 32-bit interpreters. If PowerShell blocks local scripts, use the commands directly instead of changing machine-wide policy:

```powershell
py -3 -m venv .venv  # or py -3.14 / -3.13 / -3.12 / -3.11, matching your installation
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m talknj
```

No CUDA, GPU, separately installed FFmpeg, API key, account or administrator privilege is required. PySide6 6.12.0, PyAV 16.0.1 and CTranslate2 4.8.0 are pinned; the Python 3.14 and 3.13 wheel sets for these pins were verified on Windows, and CTranslate2 currently emits a dependency deprecation warning that does not affect inference. If a Windows native dependency fails to load, install the Microsoft Visual C++ 2015–2022 x64 Redistributable from Microsoft.

### macOS

Install native **Python 3.11 or newer, 64-bit**, then run `sh start.sh` in Terminal. Initial setup uses `setup.sh`; run `sh setup.sh --dev` for development/build tools. Later launches do not invoke pip. Direct Python execution remains available with `.venv/bin/python -m talknj` or `.venv/bin/python launch.py`.

The pinned PyAV Apple Silicon wheel requires **macOS 14 or newer**. Intel Macs also need Xcode Command Line Tools (`xcode-select --install`): the pinned whisper.cpp binding has no Intel Mac wheel, so setup builds its CPU extension from source with portable static-library flags. Use native Python for the target architecture, not a mixed Rosetta environment.

## First dictation

1. Open **Preferences**. Under **Model library**, optionally change the storage folder, then download **Whisper Base (whisper.cpp)**, the preferred default, or choose another catalog model. **Parakeet** follows it; the existing faster-whisper models retain their previous order. Downloads are always explicit.
2. Select the installed model. To reuse existing files, choose **Use existing folder**. Imports reference that folder; they do not copy it. Choose your microphone in the same Preferences screen.
3. Open **Dictation**. Its compact **Dictation settings** row groups the self-labeled **Push to talk** toggle and **Language** dropdown on the left, with **Hotkey**, the shortcut, and the pencil **Edit** button together on the right. The selected toggle is highlighted; the language dropdown shrinks to fit the row. Click **Edit** to change the hotkey. Press **two or more distinct modifiers** (for example **Ctrl + Win**), or a modifier plus a letter, number, punctuation (for example **Alt + .**), Space or F1–F12. Release every key, then choose **Use shortcut** to activate and save. A single modifier or unmodified key is not accepted. Escape cancels; an unavailable shortcut leaves the previous binding active. Long hotkeys shorten visually at narrow widths; hover to see the full shortcut.
4. Focus a text field in another app. By default, **Push to talk** is on: hold **Ctrl + Alt + Space** while speaking, then release to transcribe. Turn it off to press once to start and again to stop.
5. TalkNJ automatically types into the original active app and keeps a **clipboard copy**. There is no text-delivery preference; old clipboard-only settings are ignored. If focus changes or typing is blocked, recover the transcript from the clipboard.

The recording button is a preview workflow: it records into TalkNJ and copies the result without typing into a previously focused application. The latest transcript can be edited and copied again. Silence detection avoids producing text for recordings without detected speech. Both the main display and background listening indicator count down from **05:00 remaining**. Recordings still stop automatically after **five minutes**: an unchanged application safety guard for in-memory capture and bounded transcription work, not a universal speech-model duration limit.

Closing the window keeps the app in the system tray/menu bar and leaves the global hotkey active. Use the tray/menu-bar **Quit TalkNJ** or **Ctrl+Q** (**Cmd+Q** on macOS) to exit; the keyboard quit shortcut is disabled when assigned to dictation. There is no App menu. Only one instance runs per user.

The tray/menu-bar menu shows the current dictation shortcut as a read-only label and includes a **Push to talk** toggle that switches between hold and press-to-start/stop modes.

## Models and languages

| Model family | Approximate download | Languages in TalkNJ | Tradeoff |
|---|---:|---|---|
| Whisper Base (whisper.cpp) | 148 MB | English and Vietnamese | Preferred default; actual whisper.cpp CPU runtime; standard unquantized GGML Base |
| Parakeet TDT 0.6B v2 (int8) | 662 MB | English only | Second preference; larger English model with sherpa-onnx CPU runtime |
| Tiny / Tiny English | 78 MB | Multilingual: English and Vietnamese; `.en`: English only | Lowest resource use, less accurate |
| Base / Base English | 148 MB | Multilingual: English and Vietnamese; `.en`: English only | Balanced starting point |
| Small / Small English | 488 MB | Multilingual: English and Vietnamese; `.en`: English only | Better accuracy, more CPU/RAM and latency |

Download sizes are approximate decimal MB. Inference RAM use exceeds model file size and depends on model, audio duration and runtime. The faster-whisper and Parakeet entries use CPU int8 inference; whisper.cpp Base uses the standard unquantized GGML weights. Speed varies by machine; larger models are not guaranteed to feel instantaneous. Model discovery and imported-model integrity checks run in background jobs so hashing large files does not block the interface or shortcut setup.

Without a valid selection, TalkNJ chooses the first available preferred model; a valid explicit choice survives discovery and refresh. Imported models are prioritized by their detected backend, even if their folders have been renamed. No missing model is downloaded automatically.

For Vietnamese, select a **multilingual** model in Preferences and choose Vietnamese in **Dictation → Language**. Small multilingual is the recommended catalog choice for Vietnamese quality; Tiny multilingual is mainly a low-resource option. Switching to an English-only model switches the language back to English with a visible notice.

The models produce natural punctuation and capitalization. **Correct recognition and punctuation are not guaranteed**; inspect important dictation. There is no separate grammar/LLM rewriting layer. Proper names, noisy audio, short fragments and Vietnamese accents can be difficult for small models.

Parakeet uses the already bundled local voice-activity detector to split recordings into bounded speech segments, following [upstream's long-audio approach](https://github.com/k2-fsa/sherpa/blob/master/docs/source/onnx/pretrained_models/offline-transducer/nemo/parakeet-tdt-0.6b-v2.rst). It processes detected speech throughout the recording, including after long pauses; it does not crop the recording to its first 30 seconds. This remains post-recording batch transcription, not streaming.

Supported imports are model **folders**, not individual files:

- **faster-whisper:** complete CTranslate2 Whisper exports with matching `model.bin`, `config.json`, `tokenizer.json`, and `vocabulary.json` or `vocabulary.txt`. A present `preprocessor_config.json` is also checked. Supported CT2 binary versions are 4–6; languages come from metadata/weights, not folder names.
- **Parakeet:** the matching `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx` and `tokens.txt` from the catalog's sherpa-onnx Parakeet TDT 0.6B v2 int8 export.
- **whisper.cpp:** standard multilingual `ggml-base.bin` from `ggerganov/whisper.cpp`, inside its own folder. English-only, quantized, GGUF and other Whisper sizes are not this supported export.

The two native exports are checked against pinned published file digests; arbitrary renamed files and mismatched graph/token sets are rejected. OpenAI `.pt` and arbitrary Transformers directories are not supported.

Downloads use [Systran faster-whisper exports](https://huggingface.co/Systran), the [sherpa-onnx Parakeet int8 export](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8), or [ggerganov/whisper.cpp](https://huggingface.co/ggerganov/whisper.cpp), pinned to a repository revision for that download. Files are checked against size and available SHA-256 metadata before an atomic install; the new native exports additionally require their known digests. Cancelling or failing a download does not expose a half-installed selectable model. Interrupted downloads restart rather than resume. Existing invalid folders are not overwritten: move them aside or choose another storage directory.

## Local data and privacy

Windows settings and models default to `%LOCALAPPDATA%\TalkNJ\settings.json` and `%LOCALAPPDATA%\TalkNJ\models`. macOS uses `~/Library/Application Support/TalkNJ/` for the same files/folders. Legacy macOS settings under the old Windows-style location are read without moving model files or rewriting explicit paths; the next save uses the native location.

You can change model storage or import models from another drive. Changing the download location keeps references to previously installed models; it does not move or delete their files. A missing external model folder must be reconnected or selected again.

- Audio is held in memory and discarded after processing. No audio files or transcript history are written by TalkNJ.
- Model loading and transcription are strictly local, including the tokenizer and bundled voice-activity detection model.
- Network access occurs only during explicit model downloads in the app. Installing dependencies and packaging are separate online setup operations.
- No analytics, account, cloud fallback or update checks are included.
- Every transcript goes to the **system clipboard**, including when automatic typing fails. Clipboard history/sync, the target app and other software can retain it independently; disable those services if that matters for your use.
- Settings store model folders, microphone identity, language and shortcut, not transcripts. CPU/runtime/OS memory and crash handling are outside the app's no-history guarantee.

## Windows input limitations

- Automatic insertion sends Unicode keyboard input, including Vietnamese, rather than pasting or taking focus. It works with conventional text fields that accept simulated Unicode input; games, terminals and custom controls may behave differently.
- TalkNJ checks that the original foreground window remains selected, waits up to three seconds for Ctrl/Alt/Shift/Windows keys to be released, and stops if it observes changed focus or modifiers. Windows `SendInput` cannot atomically target a specific window: **a tiny focus-change race remains**. Do not switch applications during insertion. For a manual-paste workflow, use the recording button inside TalkNJ instead of the global hotkey.
- Elevated/admin applications, secure desktops, password fields and apps that reject simulated input may block insertion. TalkNJ does not elevate itself or bypass those restrictions. Recover the complete transcript from the clipboard; some characters may already have been inserted if a failure occurs partway through.
- The shortcut observes normal keyboard events; it does not suppress the chord in other applications. Choose an unused shortcut to avoid conflicts. Modifier-only chords cannot be checked with Windows' shortcut-reservation API, so Windows or other apps may still respond to them. The recording indicator does not activate another window.
- If microphone setup fails, check **Windows Settings → Privacy & security → Microphone**, including desktop-app access. Close apps using exclusive audio mode, choose the correct input and refresh devices. Selection is saved by device name plus host API, then resolved to the current PortAudio index. Missing or duplicate identities require explicit reselection instead of silently recording another microphone.
- Quitting discards an active recording only after confirmation. In-flight inference finishes before the process exits; model downloads receive a cancellation request.

## macOS permissions and input limitations

- Allow **Microphone** and **Input Monitoring** for the global hotkey in **System Settings → Privacy & Security**. **Accessibility** is additionally required for foreground-target capture/automatic typing; if only Accessibility is denied, hotkey dictation still records and copies the transcript, with an actionable typing-refusal notice. The in-app recording button remains a clipboard preview. For source execution, permissions may belong to the launching Terminal/Python host; for a bundle, grant them to TalkNJ. Relaunch after granting permissions if macOS requires it. A denied global shortcut leaves the recording button available.
- The passive Quartz listener does not suppress shortcuts in other apps. Use an unused chord. The chooser displays **Cmd/Option/Control/Shift**; Control and Command remain distinct despite Qt's macOS modifier translation.
- If **Cmd+Q** is configured for recording, TalkNJ reserves that key only inside its own application; tray/menu-bar Quit remains available. It does not suppress Cmd+Q in other applications.
- Unicode delivery checks the original application process, window and focused accessibility element, waits for held modifiers, and refuses changed or inaccessible targets. PID-targeted events narrow but **cannot eliminate an asynchronous focus-change race**. Secure input, password fields and inaccessible/custom controls can block listening or typing. The full transcript remains in the clipboard; partial insertion is possible. Use the in-app recording button for a manual-paste workflow.
- Microphone privacy prompts, native event delivery, keyboard layouts and app-specific Accessibility behavior have not yet been exercised on a real Mac. Cross-platform boundary regressions do not substitute for that verification.

## Build portable native apps

Build **on the target OS**; these are not cross-compilers. See [build_portable.py](build_portable.py), [TalkNJ.spec](TalkNJ.spec) and the manually triggered [native build workflow](.github/workflows/portable.yml).

On Windows, run `.\build.ps1`. It creates `dist\TalkNJ\TalkNJ.exe` and `dist\TalkNJ-windows-x64.zip`. Run the executable from its folder; **distribute/extract the entire archive**, not just the `.exe`.

On macOS, run `sh build.sh`. It creates `dist/TalkNJ.app` and an architecture-specific `dist/TalkNJ-macos-arm64.zip` or `dist/TalkNJ-macos-x86_64.zip`. Extract the archive and open the app. Intel builds have the source-compiler prerequisite described above; Apple Silicon and Intel are separate native artifacts, not one universal app.

Both bundles include their Python/native runtimes and UI assets, **not speech weights**. Models/settings remain in external per-user storage, so portable distribution does not imply self-contained user data. Python launch support is retained.

The full [GPL-3.0 license](LICENSE) is included in portable bundles (`TalkNJ/_internal/LICENSE` in the Windows ZIP).

Application, window and tray icons use the text-free microphone/speech-bubble artwork from `images/design.png`. Qt uses portable PNG assets; native builds embed the Windows ICO or macOS ICNS.

Setup/build imports the whisper.cpp native extension before proceeding; macOS also reports its Mach-O architecture with `file`. Setup rejects a Python interpreter whose architecture differs from the launching shell.

After a native build, run `python smoke_portable.py` with the build environment's Python. It starts the **frozen executable**, loads all three speech runtimes and the native integration, and renders the Qt window and application icon without downloading weights, recording audio or requesting permissions. Each run writes a fresh receipt and screenshots under `dist/smoke/`; missing receipts, unreadable icons or runtime errors fail the check. The native workflow runs this check on every matrix target before uploading its archive. It is not a microphone, hotkey-permission or real-model inference test.

Windows executables are unsigned and may trigger SmartScreen. macOS builds are ad-hoc signed, not Developer ID-signed or notarized; Gatekeeper can block them. For a trusted local build, use the macOS Privacy & Security **Open Anyway** flow rather than disabling Gatekeeper system-wide. Public distribution requires an appropriate signing/notarization process. No installer is included; review bundled dependency/model terms before redistribution.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check talknj tests launch.py build_portable.py smoke_portable.py
```

Use `.venv/bin/python` for those commands on macOS. Tests isolate settings and substitute OS/audio/network boundaries; they do not record your microphone or modify your real clipboard. Current delivery criteria and platform verification limits are in [the portable polish plan](plans/20261021-portable-polish/plan.md).

The two native integration regressions are opt-in. Install both new catalog models, obtain the public [whisper.cpp JFK fixture](https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav), then point the checks at those existing local files:

```powershell
$env:TALKNJ_NATIVE_MODELS = "$env:LOCALAPPDATA\TalkNJ\models"
$env:TALKNJ_NATIVE_SPEECH = "C:\path\to\jfk.wav"
.\.venv\Scripts\python.exe -m pytest tests/test_native_engines_integration.py -q
```

Without those environment variables, the integration cases skip rather than downloading weights or audio. They cover real five-minute tail speech and persistent-worker reuse. Fast unit cases separately cover ordered Parakeet speech-span aggregation, including empty recognition results.

### Exercised Windows verification

- Run the development checks above for the current suite result. The two opt-in native cases need local assets; Windows symlink coverage also needs Developer Mode/administrator symlink permission. macOS boundary regressions run with fake OS APIs and do not claim native Mac execution. The pinned CTranslate2 dependency emits the documented setuptools deprecation warning.
- `setup.ps1` completed in a fresh temporary project and virtual environment, then imported the desktop and native inference dependencies successfully.
- Official Tiny English, Parakeet TDT 0.6B v2 int8 and whisper.cpp Base models were downloaded and transcribed real English speech with network connections blocked during inference. Parakeet also transcribed speech at the end of a full five-minute input after several minutes of silence; repeated in-memory whisper.cpp requests reused the same native worker.
- Actual microphone capture, Unicode clipboard and foreground typing (including Vietnamese characters), and refusal after a focus change were exercised on Windows.
- Live desktop checks cover the consolidated Dictation/Preferences screens at default and minimum window sizes, language and Push to talk persistence, immediate hotkey edit/confirm/save, cancellation, and App menu removal. A disposable external text app received Vietnamese Unicode through the real delivery worker with a clipboard copy; changing focus refused further insertion while retaining the clipboard, and the in-app preview did not type externally. **Ctrl + Win** and **Alt + .** were captured and saved through the real shortcut dialog, then exercised in both hold and toggle modes through the real Windows keyboard hook using `SendInput`. Those shortcut checks simulated microphone capture and inference with an empty transcript; they did not exercise speech recognition or text delivery.
- The previously built standalone folder bundle displayed its real desktop window with Python removed from `PATH`, completed microphone capture without errors and exited cleanly through Ctrl+Q with each new backend selected. Both bundled native engines also transcribed the local JFK fixture through the shipped executable's multiprocessing bootstrap, with imports restricted to the bundle; repeated whisper.cpp requests reused its native worker. This is not a rebuild of the latest UI or a separate Python-free-machine installation test.

Vietnamese speech-recognition quality, sustained long-session throughput and compatibility with every target application have not been measured. The five-minute Parakeet check covers late speech after silence, not a full five-minute continuous-speech accuracy benchmark. Punctuation is model-generated, not guaranteed grammatical correction.

## Implementation

- `talknj/ui.py`: native Qt interface.
- `talknj/app.py`: UI-thread state transitions and background jobs, tray and lifecycle.
- `talknj/models.py`: model catalog, safe local discovery and explicit downloads.
- `talknj/audio.py`: bounded PortAudio microphone capture and resampling.
- `talknj/transcription.py`: offline CPU backend routing, one-model cache and voice activity detection.
- `talknj/_whispercpp.py`: persistent spawn-safe whisper.cpp worker with checked native status and explicit shutdown.
- `talknj/_model_formats.py`: native-export integrity validation with bounded stat-fingerprint caching.
- `talknj/native.py` and `talknj/_native_macos.py`: Windows/macOS global keyboard listening, clipboard and focus-checked Unicode insertion.
- `talknj/settings.py`: atomic per-user preferences.

Inference uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2](https://github.com/OpenNMT/CTranslate2), [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx), and [pywhispercpp](https://github.com/absadiki/pywhispercpp). Only the currently selected engine retains speech-model weights. whisper.cpp runs in a separate persistent child process to isolate native initialization/decode failures; audio stays in memory. Failed engines are released without retrying a recording automatically; a new explicit recording can load a fresh engine.
