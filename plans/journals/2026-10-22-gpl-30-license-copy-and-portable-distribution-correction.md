---
title: GPL-3.0 license copy and portable distribution correction
date: 2026-10-22
summary: Added canonical project LICENSE and verified its inclusion in a refreshed Windows portable ZIP.
---

# GPL-3.0 license copy and portable distribution correction

## Finding and correction

The README contradiction was already fixed, but the repository and portable distribution still lacked the actual project license copy. Added the unmodified GNU GPLv3 text as LICENSE, linked it from README and included it through TalkNJ.spec bundle data.

## Verification

The 35,149-byte root license and Windows bundled/archive copies match the canonical GNU download byte-for-byte. SHA-256: 3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986. Built the current source with PyInstaller into dist/licensed/TalkNJ, preserving the older running application. Refreshed dist/TalkNJ-windows-x64.zip: 156,057,502 bytes, ZIP CRC passed, archived executable matches the fresh build.

Frozen-runtime smoke passed with all imports inside the bundle and rendered UI/icon proof at dist/smoke/licensed-v6okjy6x/runtime.json and its screenshots. The rendered sidebar includes About. Standard project Ruff and spec syntax compilation passed. Updated the owning packaging evidence and removed the temporary launcher.

## Limits

Native macOS runtime verification remains outstanding. Speech inference was not rerun because this change only adds UI/license distribution content. No commit or publication.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
