---
title: Show build version on About page
date: 2026-10-22
summary: Display talknj.__version__ on the About page with live render verification.
---

# Show build version on About page

## Request and outcome
Show the application's build version on the About page so users can identify the running build.

## Cause and change
The About card had no version display. The package already defined `talknj.__version__`, so `talknj/ui.py` now imports it and shows `Version {__version__}` under the TalkNJ heading. No new version source was introduced.

## Verification
- Rendered the live MainWindow About page at 880x700 and confirmed the label `Version 0.1.0` matches `talknj.__version__`. Screenshot: `.smoke/about-version-880.png`.
- `pytest tests/test_settings.py tests/test_native.py`: 65 passed.
- `ruff check talknj/ui.py`: passed.

## Limitations
The About display reads one value, but release metadata still hardcodes the same version separately in `pyproject.toml`, `TalkNJ.spec` (`BUNDLE version`) and `talknj/__init__.py`. Bump all of them together until they are derived from one source.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
