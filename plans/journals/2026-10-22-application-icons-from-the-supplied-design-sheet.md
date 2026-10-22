---
title: Application icons from the supplied design sheet
date: 2026-10-22
summary: "Integrated supplied artwork and verified Windows UI, native icon resources and portable packaging."
---

# Application icons from the supplied design sheet

## Outcome

Selected the text-free microphone/speech-bubble tile from images/design.png. Extracted transparent artwork without deleting the white interior, and generated PNG, seven-size ICO and standard/Retina ICNS assets. Qt application/window/tray icons, native packaging and wheel package data now use these assets. The original sheet remains unchanged.

## Verification

308 tests passed, 3 skipped; Ruff passed. Exercised the real Windows controller and inspected the title-bar icon and light/dark small-size previews. All 11 ICNS representations decoded. The built wheel contains byte-identical icon assets. The native EXE embeds all seven selected ICO frames. The frozen model-free smoke rendered the new icon and window with bundle-only imports: dist/smoke/icons-vpif54jk/runtime.json. The updated dist/TalkNJ-windows-x64.zip passes CRC/artwork checks and is 156029225 bytes.

## Build constraint

The existing portable app was running and locked its DLLs, so the initial standard-folder build failed. No missing old-bundle files were found. Preserved the running application and successfully built dist/branded/TalkNJ/TalkNJ.exe separately, then refreshed the ZIP. Quit the old instance before opening the new bundle. Temporary smoke scripts were removed.

## Limits

The supplied sheet embeds roughly 244 by 230 pixels of actual selected artwork; larger Mac frames are upscaled. ICNS and Mac packaging configuration are ready, but native Mac execution remains unverified. Speech inference was not rerun for this artwork-only update.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
