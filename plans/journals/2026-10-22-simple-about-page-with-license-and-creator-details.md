---
title: Simple About page with license and creator details
date: 2026-10-22
summary: "Added GPL-3.0, Vinh Hoang and contact email to a verified About page."
---

# Simple About page with license and creator details

## Change

Added an About sidebar page using the existing Qt page/card layout. It displays GPL-3.0, creator Vinh Hoang and the requested selectable email address. Existing three navigation indices and dictation/controller behavior are unchanged. README now includes the same identity/license information and removes the obsolete no-project-license statement.

## Evidence

Before: actual Windows MainWindow exposed only Dictation, Model library and Preferences. After: clicked through all four pages and verified About content at the minimum 880 by 700 window size; screenshot .smoke/about-page.png was visually inspected. The related UI/controller suite passes 75 tests and Ruff passes for talknj/ui.py.

## Scope

Kept this a small source/UI change. No new dependencies, release artifacts, commits or publishing. The existing portable ZIP was not rebuilt.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
