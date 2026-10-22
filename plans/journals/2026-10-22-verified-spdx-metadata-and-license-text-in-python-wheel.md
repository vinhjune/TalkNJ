---
title: Verified SPDX metadata and license text in Python wheel
date: 2026-10-22
summary: Declared GPL-3.0-only and verified the built wheel carries correct metadata and canonical license text.
---

# Verified SPDX metadata and license text in Python wheel

## Review assessment

Kept the portable license copy at its existing documented TalkNJ/_internal/LICENSE location. It is already included in the archive and byte-matches the canonical GNU text; no duplicate top-level copy or native rebuild is needed for this metadata-only correction.

## Change

Added project license = GPL-3.0-only and explicit license-files = [LICENSE] to pyproject.toml. README uses the same precise SPDX identifier and retains its local LICENSE link. Updated existing packaging evidence.

## Verification

Built the real wheel with pip wheel --no-deps --no-build-isolation. Its METADATA contains License-Expression: GPL-3.0-only and License-File: LICENSE. The wheel carries talknj-0.1.0.dist-info/licenses/LICENSE, byte-identical to the official GNU GPLv3 text and root LICENSE. ZIP CRC passed. Machine-readable receipt: .smoke/license-wheel/verification.json. No application behavior changed; no application tests or native rebuild were repeated.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
