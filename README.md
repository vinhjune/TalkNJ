# TalkNJ

Private voice dictation for Windows 10/11 x64. Speak, release your shortcut, and get text in your clipboard or the application you were using. Audio is transcribed **on your CPU** with local Whisper or Parakeet models, not a cloud service.

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
3. Open **Preferences** to choose a microphone, language and output. For the global shortcut, click **Choose shortcut…**, press a modifier plus a letter, number, Space or F1–F12, release every key, then choose **Use shortcut** and **Apply shortcut**. Escape cancels without changing the current binding.
4. Focus a text field in another app. By default, hold **Ctrl + Alt + Space** while speaking, then release to transcribe. Alternatively select **Press to start — press again to stop**.
5. **Clipboard only** is the safe initial output: paste when ready. Select **Type into active app + keep clipboard copy** for automatic insertion.

The recording button is a preview workflow: it records into TalkNJ and copies the result without typing into a previously focused application. The latest transcript can be edited and copied again. Silence detection avoids producing text for recordings without detected speech. Recordings stop automatically after **five minutes**: an application safety guard for in-memory capture and bounded transcription work, not a universal speech-model duration limit.

Closing the window keeps the app in the system tray and leaves the global shortcut active. Use **App → Quit TalkNJ**, **Ctrl+Q**, or the tray's **Quit TalkNJ** to exit. If Ctrl+Q is your recording shortcut, it no longer also triggers TalkNJ's Quit action; the menu and tray still work. Only one instance runs per Windows user.

## Models and languages

| Model family | Approximate download | Languages in TalkNJ | Tradeoff |
|---|---:|---|---|
| Tiny / Tiny English | 78 MB | Multilingual: English and Vietnamese; `.en`: English only | Lowest resource use, less accurate |
| Base / Base English | 148 MB | Multilingual: English and Vietnamese; `.en`: English only | Balanced starting point |
| Small / Small English | 488 MB | Multilingual: English and Vietnamese; `.en`: English only | Better accuracy, more CPU/RAM and latency |
| Parakeet TDT 0.6B v2 (int8) | 662 MB | English only | Larger English model; sherpa-onnx CPU runtime |
| Whisper Base (whisper.cpp) | 148 MB | English and Vietnamese | Actual whisper.cpp CPU runtime; standard unquantized GGML Base |

Download sizes are approximate decimal MB. Inference RAM use exceeds model file size and depends on model, audio duration and runtime. The faster-whisper and Parakeet entries use CPU int8 inference; whisper.cpp Base uses the standard unquantized GGML weights. Speed varies by machine; larger models are not guaranteed to feel instantaneous. Model discovery and imported-model integrity checks run in background jobs so hashing large files does not block the interface or shortcut setup.

For Vietnamese, select a **multilingual** model and choose Vietnamese in Preferences. Small multilingual is the recommended catalog choice for Vietnamese quality; Tiny multilingual is mainly a low-resource option. Switching to an English-only model switches the language back to English with a visible notice.

The models produce natural punctuation and capitalization. **Correct recognition and punctuation are not guaranteed**; inspect important dictation. There is no separate grammar/LLM rewriting layer. Proper names, noisy audio, short fragments and Vietnamese accents can be difficult for small models.

Parakeet uses the already bundled local voice-activity detector to split recordings into bounded speech segments, following [upstream's long-audio approach](https://github.com/k2-fsa/sherpa/blob/master/docs/source/onnx/pretrained_models/offline-transducer/nemo/parakeet-tdt-0.6b-v2.rst). It processes detected speech throughout the recording, including after long pauses; it does not crop the recording to its first 30 seconds. This remains post-recording batch transcription, not streaming.

Supported imports are model **folders**, not individual files:

- **faster-whisper:** complete CTranslate2 Whisper exports with matching `model.bin`, `config.json`, `tokenizer.json`, and `vocabulary.json` or `vocabulary.txt`. A present `preprocessor_config.json` is also checked. Supported CT2 binary versions are 4–6; languages come from metadata/weights, not folder names.
- **Parakeet:** the matching `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx` and `tokens.txt` from the catalog's sherpa-onnx Parakeet TDT 0.6B v2 int8 export.
- **whisper.cpp:** standard multilingual `ggml-base.bin` from `ggerganov/whisper.cpp`, inside its own folder. English-only, quantized, GGUF and other Whisper sizes are not this supported export.

The two native exports are checked against pinned published file digests; arbitrary renamed files and mismatched graph/token sets are rejected. OpenAI `.pt` and arbitrary Transformers directories are not supported.

Downloads use [Systran faster-whisper exports](https://huggingface.co/Systran), the [sherpa-onnx Parakeet int8 export](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8), or [ggerganov/whisper.cpp](https://huggingface.co/ggerganov/whisper.cpp), pinned to a repository revision for that download. Files are checked against size and available SHA-256 metadata before an atomic install; the new native exports additionally require their known digests. Cancelling or failing a download does not expose a half-installed selectable model. Interrupted downloads restart rather than resume. Existing invalid folders are not overwritten: move them aside or choose another storage directory.

## Local data and privacy

Default settings: `%LOCALAPPDATA%\TalkNJ\settings.json`  
Default models: `%LOCALAPPDATA%\TalkNJ\models`

You can change model storage or import models from another drive. Changing the download location keeps references to previously installed models; it does not move or delete their files. A missing external model folder must be reconnected or selected again.

- Audio is held in memory and discarded after processing. No audio files or transcript history are written by TalkNJ.
- Model loading and transcription are strictly local, including the tokenizer and bundled voice-activity detection model.
- Network access occurs only during explicit model downloads in the app. Installing dependencies and packaging are separate online setup operations.
- No analytics, account, cloud fallback or update checks are included.
- Both output modes put the transcript in the **Windows clipboard**. Clipboard history, cloud clipboard sync, the target app and other software can retain it independently; disable Windows clipboard history/sync if that matters for your use.
- Settings store model folders, microphone identity, language and shortcut, not transcripts. CPU/runtime/OS memory and crash handling are outside the app's no-history guarantee.

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

Tests isolate settings and substitute OS/audio/network boundaries; they do not record your microphone or modify your real clipboard. Delivery criteria are in `plans/20261021-local-dictation/` and `plans/20261021-models-shortcut/`.

The two native integration regressions are opt-in. Install both new catalog models, obtain the public [whisper.cpp JFK fixture](https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav), then point the checks at those existing local files:

```powershell
$env:TALKNJ_NATIVE_MODELS = "$env:LOCALAPPDATA\TalkNJ\models"
$env:TALKNJ_NATIVE_SPEECH = "C:\path\to\jfk.wav"
.\.venv\Scripts\python.exe -m pytest tests/test_native_engines_integration.py -q
```

Without those environment variables, the integration cases skip rather than downloading weights or audio. They cover real five-minute tail speech and persistent-worker reuse. Fast unit cases separately cover ordered Parakeet speech-span aggregation, including empty recognition results.

### Exercised Windows verification

- In the default suite, **198 behavior tests pass**; three cases skip (the two opt-in native cases need local assets, and this Windows account lacks Developer Mode/administrator symlink permission). Both native integration cases also passed when run with local assets. Ruff reports no issues. The pinned CTranslate2 dependency emits the documented setuptools deprecation warning.
- `setup.ps1` completed in a fresh temporary project and virtual environment, then imported the desktop and native inference dependencies successfully.
- Official Tiny English, Parakeet TDT 0.6B v2 int8 and whisper.cpp Base models were downloaded and transcribed real English speech with network connections blocked during inference. Parakeet also transcribed speech at the end of a full five-minute input after several minutes of silence; repeated in-memory whisper.cpp requests reused the same native worker.
- Actual microphone capture, Unicode clipboard and foreground typing (including Vietnamese characters), and refusal after a focus change were exercised on Windows.
- Live desktop recording, the press-to-capture shortcut dialog (confirm, Apply, save and Escape cancellation), global hold/toggle shortcuts with key-repeat suppression, and selection of both new backends pass on Windows. Existing clipboard/active-app delivery and tray behavior were also exercised.
- The standalone folder bundle built, displayed its real desktop window with Python removed from `PATH`, completed microphone capture without errors and exited cleanly through Ctrl+Q with each new backend selected. Both bundled native engines also transcribed the local JFK fixture through the shipped executable's multiprocessing bootstrap, with imports restricted to the bundle; repeated whisper.cpp requests reused its native worker. This is not a separate Python-free-machine installation test.

Vietnamese speech-recognition quality, sustained long-session throughput and compatibility with every target application have not been measured. The five-minute Parakeet check covers late speech after silence, not a full five-minute continuous-speech accuracy benchmark. Punctuation is model-generated, not guaranteed grammatical correction.

## Implementation

- `talknj/ui.py`: native Qt interface.
- `talknj/app.py`: UI-thread state transitions and background jobs, tray and lifecycle.
- `talknj/models.py`: model catalog, safe local discovery and explicit downloads.
- `talknj/audio.py`: bounded PortAudio microphone capture and resampling.
- `talknj/transcription.py`: offline CPU backend routing, one-model cache and voice activity detection.
- `talknj/_whispercpp.py`: persistent spawn-safe whisper.cpp worker with checked native status and explicit shutdown.
- `talknj/_model_formats.py`: native-export integrity validation with bounded stat-fingerprint caching.
- `talknj/native.py`: Win32 global keyboard hook, clipboard and Unicode insertion.
- `talknj/settings.py`: atomic per-user preferences.

Inference uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2](https://github.com/OpenNMT/CTranslate2), [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx), and [pywhispercpp](https://github.com/absadiki/pywhispercpp). Only the currently selected engine retains speech-model weights. whisper.cpp runs in a separate persistent child process to isolate native initialization/decode failures; audio stays in memory. Failed engines are released without retrying a recording automatically; a new explicit recording can load a fresh engine.
