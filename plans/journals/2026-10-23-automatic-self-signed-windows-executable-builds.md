---
title: Automatic self-signed Windows executable builds
date: 2026-10-23
summary: "Created a local non-exportable code-signing identity and verified automatic signing, tamper rejection, and the frozen Windows artifact."
---

# Automatic self-signed Windows executable builds

## Outcome
Created a self-signed CN=TalkNJ code-signing certificate (SHA-256/RSA-3072, expires 2029-10-23) and made Windows PyInstaller builds sign the collected executable before ZIP creation. The non-exportable private key stays in the current-user Windows key store; only TalkNJ-signing.cer is distributed. No trust-store entries or global execution-policy settings were changed.

## Verification and review
- Real signed native build completed: dist/TalkNJ/TalkNJ.exe and dist/TalkNJ-windows-x64.zip (156,060,708 bytes).
- ZIP CRC and archived executable/public certificate/license equality passed; no PFX/P12 files were bundled.
- Repeat signing reused the certificate. The exported certificate contains no private key; the CNG private key export policy is None.
- Windows reports UnknownError for the untrusted self-signed root. The helper checks WinVerifyTrust's exact result instead of swallowing UnknownError: expected untrusted root accepted, tampered executable returned 0x80096010, unsigned bootloader returned 0x800B0100.
- Signed frozen import/render/icon smoke passed: dist/smoke/bundle-azrzdl6b/runtime.json.
- Full suite: 330 passed, 3 skipped; existing pkg_resources warning. Ruff and spec syntax checks passed.
- Inline review covered fail-closed packaging, signer identity, certificate reuse, private-key isolation, paths with subprocess argument lists, and the unchanged macOS branch. Simplification skipped: scoped changes are below the default thresholds.

## Limits
Self-signing is not publicly trusted and does not eliminate SmartScreen warnings. No timestamp is used. Hosted Windows runners create their own ephemeral identity; stable CI/public signing requires separate provisioning. CI was not dispatched, macOS was not exercised, and no commit or publication was requested. Updated README and the existing packaging evidence; the unrelated macOS release blocker remains open.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
