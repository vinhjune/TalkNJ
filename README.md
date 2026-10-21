# TalkNJ

Private voice dictation for Windows 10/11 x64. Speak, release your shortcut, and get text in your clipboard or the application you were using. Audio is transcribed **on your CPU** with a local Whisper model, not a cloud service.

This is **speech-to-text**, not text-to-speech. Recognition happens after recording stops; it is not live word-by-word streaming.

## Run from source

Install **Python 3.11–3.13 x64** with the Windows Python launcher, then run in PowerShell:

```powershell
.\start.ps1
```

On first run, `start.ps1` invokes `setup.ps1` to create `.venv` and install dependencies. Later launches do not invoke pip and work offline with an installed model. Run `.\setup.ps1` explicitly after updating source dependencies, or `.\setup.ps1 -Dev` to install development tools. Setup probes Python 3.13, 3.12, then 3.11, rejecting 32-bit interpreters. If PowerShell blocks local scripts, use the commands directly instead of changing machine-wide policy:

```powershell
py -3.13 -m venv .venv  # or -3.12 / -3.11, matching your installation
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m talknj
```

No CUDA, GPU, separately installed FFmpeg, API key, account or administrator privilege is required. PyAV 16.0.1, CTranslate2 4.6.0 and its compatible setuptools runtime are pinned after Windows import verification; CTranslate2 currently emits a dependency deprecation warning that does not affect inference. If a Windows native dependency fails to load, install the Microsoft Visual C++ 2015–2022 x64 Redistributable from Microsoft.

## First dictation

1. Open **Model library**. Optionally choose a download location, then download **Tiny English** for the quickest start or **Base English** for a better accuracy/speed balance.
2. Select the installed model. To reuse existing files, choose **Use existing model folder**. Imports reference that folder; they do not copy it.
3. Open **Preferences** to choose a microphone, language, output and global shortcut.
4. Focus a text field in another app. By default, hold **Ctrl + Alt + Space** while speaking, then release to transcribe. Alternatively select **Press to start — press again to stop**.
5. **Clipboard only** is the safe initial output: paste when ready. Select **Type into active app + keep clipboard copy** for automatic insertion.

The recording button is a preview workflow: it records into TalkNJ and copies the result without typing into a previously focused application. The latest transcript can be edited and copied again. Silence detection avoids producing text for recordings without detected speech. Recordings stop automatically after **five minutes**.

Closing the window keeps the app in the system tray and leaves the global shortcut active. Use **App → Quit TalkNJ**, **Ctrl+Q**, or the tray's **Quit TalkNJ** to exit. Only one instance runs per Windows user.

## Models and languages

| Model family | Approximate download | Languages in TalkNJ | Tradeoff |
|---|---:|---|---|
| Tiny / Tiny English | 78 MB | Multilingual: English and Vietnamese; `.en`: English only | Lowest resource use, less accurate |
| Base / Base English | 148 MB | Multilingual: English and Vietnamese; `.en`: English only | Balanced starting point |
| Small / Small English | 488 MB | Multilingual: English and Vietnamese; `.en`: English only | Better accuracy, more CPU/RAM and latency |

Download sizes are approximate decimal MB. Inference RAM use exceeds model file size and depends on model, audio duration and runtime. All models use CPU int8 inference. Speed varies by machine; Small is not guaranteed to feel instantaneous.

For Vietnamese, select a **multilingual** model and choose Vietnamese in Preferences. Small multilingual is the recommended catalog choice for Vietnamese quality; Tiny multilingual is mainly a low-resource option. Switching to an English-only model switches the language back to English with a visible notice.

Whisper produces natural punctuation and capitalization. **Correct recognition and punctuation are not guaranteed**; inspect important dictation. There is no separate grammar/LLM rewriting layer. Proper names, noisy audio, short fragments and Vietnamese accents can be difficult for small models.

Compatible imports are complete **CTranslate2 Whisper exports**, with matching `model.bin`, `config.json`, `tokenizer.json`, and `vocabulary.json` or `vocabulary.txt`. A present `preprocessor_config.json` is also checked. OpenAI `.pt`, GGML/GGUF files and arbitrary Hugging Face Transformers directories are not compatible. Supported CT2 binary versions are 4–6. Model languages are validated from metadata/weights rather than folder names.

Downloads fetch official [Systran faster-whisper models](https://huggingface.co/Systran) from Hugging Face, pinned to a repository revision for that download. Files are checked against size and available SHA-256 metadata before an atomic install. Cancelling or failing a download does not expose a half-installed selectable model. Interrupted downloads restart rather than resume. Existing invalid folders are not overwritten: move them aside or choose another storage directory.

## Local data and privacy

Default settings: `%LOCALAPPDATA%\TalkNJ\settings.json`  
Default models: `%LOCALAPPDATA%\TalkNJ\models`

You can change model storage or import models from another drive. Changing the download location keeps references to previously installed models; it does not move or delete their files. A missing external model folder must be reconnected or selected again.

- Audio is held in memory and discarded after processing. No audio files or transcript history are written by TalkNJ.
- Model loading and transcription are strictly local, including the tokenizer and bundled voice-activity detection model.
- Network access occurs only during explicit model downloads in the app. Installing dependencies and packaging are separate online setup operations.
- No analytics, account, cloud fallback or update checks are included.
- Both output modes put the transcript in the **Windows clipboard**. Clipboard history, cloud clipboard sync, the target app and other software can retain it independently; disable Windows clipboard history/sync if that matters for your use.
- Settings store model folders, microphone index, language and shortcut, not transcripts. CPU/runtime/OS memory and crash handling are outside the app's no-history guarantee.

## Windows input limitations

- Automatic insertion sends Unicode keyboard input, including Vietnamese, rather than pasting or taking focus. It works with conventional text fields that accept simulated Unicode input; games, terminals and custom controls may behave differently.
- TalkNJ checks that the original foreground window remains selected, waits up to three seconds for Ctrl/Alt/Shift/Windows keys to be released, and stops if it observes changed focus or modifiers. Windows `SendInput` cannot atomically target a specific window: **a tiny focus-change race remains**. Do not switch applications during insertion; use clipboard-only mode for sensitive contexts.
- Elevated/admin applications, secure desktops, password fields and apps that reject simulated input may block insertion. TalkNJ does not elevate itself or bypass those restrictions. Recover the complete transcript from the clipboard; some characters may already have been inserted if a failure occurs partway through.
- The shortcut observes normal keyboard events; it does not suppress the chord in other applications. Choose an unused shortcut to avoid conflicts. The recording indicator does not activate another window.
- If microphone setup fails, check **Windows Settings → Privacy & security → Microphone**, including desktop-app access. Close apps using exclusive audio mode, choose the correct input and refresh devices. Selection is saved by device name plus host API, then resolved to the current PortAudio index. Missing or duplicate identities require explicit reselection instead of silently recording another microphone.
- Quitting discards an active recording only after confirmation. In-flight inference finishes before the process exits; model downloads receive a cancellation request.

## Build a standalone Windows app

```powershell
.\build.ps1
```

Or run these commands after creating `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm TalkNJ.spec
```

Run `dist\TalkNJ\TalkNJ.exe`. **Distribute the entire `dist\TalkNJ` folder**, not just the executable. Models stay outside the bundle and are downloaded/selected inside the app. The unsigned executable can trigger Windows SmartScreen; code signing and an installer are not included. PySide6/Qt and models have their own licenses; review bundled dependency/model terms before distribution. No project distribution license has been chosen.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check talknj tests launch.py
```

Tests isolate settings and substitute OS/audio/network boundaries; they do not record your microphone or modify your real clipboard. See `plans/20261021-local-dictation/` for delivery acceptance criteria.

### Exercised Windows verification

- 128 behavior tests pass; Ruff reports no issues. The pinned CTranslate2 dependency emits the documented setuptools deprecation warning.
- `setup.ps1` completed in a fresh temporary project and virtual environment, then imported the desktop and native inference dependencies successfully.
- An official Tiny English model was downloaded and transcribed a real English speech fixture with punctuation while socket connections were blocked.
- Actual microphone capture, Unicode clipboard and foreground typing (including Vietnamese characters), and refusal after a focus change were exercised on Windows.
- Live desktop recording, global hold/toggle shortcuts with key-repeat suppression, clipboard/active-app delivery, saved preferences and tray hide/reopen pass.
- The standalone folder bundle built, displayed its real desktop window with Python removed from `PATH`, and exited cleanly through Ctrl+Q. This is not a separate Python-free-machine installation test.

Vietnamese speech-recognition quality, long-session performance and compatibility with every target application have not been measured. Whisper punctuation is model-generated, not guaranteed grammatical correction.

## Implementation

- `talknj/ui.py`: native Qt interface.
- `talknj/app.py`: UI-thread state transitions and background jobs, tray and lifecycle.
- `talknj/models.py`: model catalog, safe local discovery and explicit downloads.
- `talknj/audio.py`: bounded PortAudio microphone capture and resampling.
- `talknj/transcription.py`: offline CPU Whisper and voice activity detection.
- `talknj/native.py`: Win32 global keyboard hook, clipboard and Unicode insertion.
- `talknj/settings.py`: atomic per-user preferences.

Inference uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2](https://github.com/OpenNMT/CTranslate2), and the [Whisper](https://github.com/openai/whisper) model family.
