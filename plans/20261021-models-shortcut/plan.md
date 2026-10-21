---
title: Additional native speech backends and press-to-capture shortcuts
status: completed
---

# Outcome
Add NVIDIA Parakeet TDT 0.6B v2 CPU/int8 via sherpa-onnx and actual whisper.cpp Whisper Base via pywhispercpp. Replace typed shortcut configuration with press-to-capture and verify global hold/toggle activation. Preserve existing privacy, download/install, model-import and output behavior.

# Phases
1. [Native engines](phase-01-engines.md): catalog, download/import validation, offline inference, runtime packaging.
2. [Shortcut interaction](phase-02-shortcut.md): key capture, registration, cancellation and actual global activation.
3. [Integration proof](phase-03-verification.md): native speech/UI smoke, regressions, packaging and docs.

# Shared contracts
Keep `download_model`, `validate_model`, `discover_models` and `Transcriber.transcribe(audio, model_path, language)` callable contracts. Models remain folders and expose supported languages. New backend metadata defaults to faster-whisper for existing models. Only explicit model downloads access the network. Native runtimes load in worker paths. Reuse atomic staged downloads with pinned revisions and available checksums.

# Scope boundaries and discussion
- Five-minute cap: existing fixed-capacity in-memory capture safety guard, not a speech-model limit. Keep unchanged in this change.
- Real time: feasible using bounded audio chunks, partial preview and final result delivery; current backends are offline/batch and need an explicit streaming/chunking loop. Discuss only; do not add streaming or modify output semantics.
- No GPU requirement, cloud inference, new rewriting layer, commits or publication.
