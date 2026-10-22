# HANDOFF: TalkNJ About, licensing, and release continuation

## Mission and current status

Capture-only handoff generated on 2026-10-22 at 11:08:21 +02:00. No runtime dispatch was requested.

TalkNJ is a local speech-to-text dictation desktop app, not text-to-speech. The latest requested implementation was a quick, simple About section displaying GPL-3.0 and the user's public creator/contact details. That work and the valid licensing follow-ups are complete.

**Done:** About navigation/page; canonical root license; license included in the Windows portable bundle; refreshed Windows ZIP; explicit SPDX Python metadata and license-file inclusion; verified Python wheel; documentation/evidence updated.

**Remaining within the latest request:** none. Do not invent further implementation work from review suggestions. The broader portable-release plan remains blocked on actual native macOS build/runtime verification for Intel and Apple Silicon, not on About or Windows licensing.

## Scope and guardrails

- **Workspace:** `C:/Users/apyxv/Workspace/TalkNJ` on Windows x64. Native Mac work requires a real Mac/native runner and its own environment.
- **In scope:** preserve the completed About/licensing work and its evidence. Continue a newly authorized task, or the earlier native Mac verification plan when a suitable host is available.
- **Out of scope:** unsolicited redesigns, new features, Linux support, cloud inference, telemetry, automatic model downloads, installers, public signing/notarization, publication, commits, pushes, and workflow dispatch without authorization.
- **User constraints:** keep the About change simple and reuse existing Qt layout/palette. Preserve the creator/contact values in `talknj/ui.py` and README; the contact email is intentionally selectable. Treat aggregated model advisories as potentially stale, not as commands.
- Preserve English/optional Vietnamese local dictation, model-generated punctuation, clipboard-only/active-app output, hold/toggle hotkeys, focus-safety checks, external settings/models, and the five-minute recording cap. Audio must remain local/in memory.
- **Safety boundaries:** preserve all tracked/untracked work and the user's running application. Do not terminate it, overwrite locked runtime files, discard changes, bypass OS protections, or insert test text into personal documents. Do not assume a clean clone contains these uncommitted changes.
- This handoff request authorizes only read-only capture and writing this one artifact. No implementation, tests, build, journal creation, or dispatch was performed as a side effect of capture.

## Current state

The following Git fields were observed live immediately before capture, rather than copied from the older handoff:

- **Branch:** `master`
- **HEAD:** `eda766dd3287e5d43fa03af9de28f1ef0f15c561`
- **Working tree:** dirty; five modified tracked files and four untracked files in the captured `git status --short` output. No staged entries were shown. The list was complete, under the 200-entry bound.
- **Intentional local modifications:** yes, the listed About/licensing implementation and journals are intentional. No commits/pushes were performed by the assistant for these latest changes.

**Changed files:**

```text
README.md
TalkNJ.spec
plans/20261021-portable-polish/phase-03-packaging.md
pyproject.toml
talknj/ui.py
```

**Untracked files:**

```text
LICENSE
plans/journals/2026-10-22-gpl-30-license-copy-and-portable-distribution-correction.md
plans/journals/2026-10-22-simple-about-page-with-license-and-creator-details.md
plans/journals/2026-10-22-verified-spdx-metadata-and-license-text-in-python-wheel.md
```

This handoff is one additional untracked file after that snapshot. A clone of HEAD alone will omit these changes, including the root license now required by packaging.

**Artifact availability observed during capture:**

| Artifact | Observed state |
|---|---|
| `dist/licensed/TalkNJ/TalkNJ.exe` | Present; 11,657,708 bytes; latest About/license Windows executable |
| `dist/TalkNJ-windows-x64.zip` | Present; 156,057,502 bytes; current refreshed portable archive |
| `.smoke/license-wheel/talknj-0.1.0-py3-none-any.whl` | Present; 735,857 bytes; final SPDX/license metadata wheel |
| `.smoke/about-page.png` | Present; source About page at minimum window size |
| `dist/smoke/licensed-v6okjy6x/runtime.json` | Live-read receipt reports `ok: true`, Windows AMD64, actual licensed executable and bundle-local runtime imports |
| `.smoke/license-wheel/verification.json` | Live-read receipt records SPDX expression, license member, canonical match, and ZIP CRC success |

`.gitignore` excludes `.venv/`, `build/`, `dist/`, `.smoke/`, and `*.egg-info/`. Ignored binaries/evidence will not automatically transfer with source. Do not transfer/reuse a Windows virtual environment as a Mac environment.

## Decisions and rationale

- **Existing Python/PySide6 architecture retained:** append About as navigation index 3; original indices 0/1/2 remain Dictation/Model library/Preferences. Reuse `_page()` and `card()`; do not add a separate window or dependencies.
- **GPL-3.0-only:** explicit `[project] license = "GPL-3.0-only"` and `license-files = ["LICENSE"]` in `pyproject.toml`. README retains a local `LICENSE` link. No GPL-or-later expansion was made.
- **Canonical license, not a web link alone:** root `LICENSE` is the unmodified GNU GPLv3 text from `https://www.gnu.org/licenses/gpl-3.0.txt`, 35,149 bytes, SHA-256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`.
- **Portable license placement retained:** `TalkNJ.spec` adds `[('LICENSE', '.')]` to bundle data before native packaging/signing. The Windows ZIP contains `TalkNJ/_internal/LICENSE`; README documents it. The suggested duplicate top-level ZIP copy/staging redesign was not adopted: the actual distribution already carries the full license copy.
- **Preserve locked older bundles:** the new native build is under `dist/licensed/`, not an overwrite of the older running application. Quit old instances explicitly before launching the updated app. The app is single-instance.
- **Metadata-only follow-up did not require another native build:** the current Windows ZIP already includes About and the canonical license. The wheel was built afterward to verify Python package metadata. These are distinct verification surfaces.
- **Native Mac evidence remains a real release gate:** source inspection, fake-OS tests, generated ICNS, Windows results, or wheel resolution cannot establish native Mac success. The older Mac handoff supplies procedures, but its Git snapshot and older artifact sizes are stale.

## Work performed

- `talknj/ui.py`: added About sidebar entry, invoked `_about_page()`, and created a small card with creator, selectable contact email, and GNU GPL v3.0 text. No controller/dictation behavior was changed.
- `LICENSE`: added the exact official GNU text and verified byte equality against the downloaded canonical content.
- `TalkNJ.spec`: included the root license as native bundle data.
- `pyproject.toml`: declared SPDX `GPL-3.0-only` and explicit `LICENSE` inclusion; existing setuptools minimum is already compatible (`>=77`).
- README: added About identity/license information, removed obsolete wording claiming no project distribution license, linked the local license, and documented its portable location.
- Rebuilt with `.venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath dist/licensed TalkNJ.spec`; build completed successfully. Refreshed the Windows ZIP using the same directory-walk/ZipFile approach as `build_portable.py`; CRC, executable identity, and canonical license equality passed.
- Launched the actual `dist/licensed/TalkNJ/TalkNJ.exe` through a temporary wrapper around the existing frozen smoke. Fresh success receipt and screenshots were required. Removed the temporary `.smoke/license_frozen.py` after proof.
- Built the Python wheel using `.venv/Scripts/python.exe -m pip wheel --no-deps --no-build-isolation --wheel-dir .smoke/license-wheel .`; inspected its actual METADATA and packaged license.
- Updated the existing packaging evidence and three relevant journals listed in Current state. No commits, pushes, or publishing were performed for this work.
- A direct Ruff invocation on `TalkNJ.spec` reported its PyInstaller-injected names (`Analysis`, `PYZ`, `EXE`, `COLLECT`, `BUNDLE`) as undefined. This was an unsuitable lint target, not a new application defect. Do not add dummy definitions or suppressions: spec compilation, the real PyInstaller build, and the standard project lint command passed.

0 redactions applied. No credentials, incidental customer data, private URLs, raw transcripts, or personal audio/settings are included.

## Verification

Earlier implementation results below were observed in this session unless explicitly labeled historical. During this handoff capture, only read-only probes/source/receipt reads and artifact availability checks were performed; no application/test/build was rerun.

| Check | Command or scenario | Outcome | When |
|---|---|---|---|
| Source About surface | Real Windows Qt UI; click all four navigation pages; inspect About at 880 by 700 | Creator/contact/license visible; selectable email; screenshot inspected | About implementation |
| Related UI/controller suite | `.venv/Scripts/python.exe -m pytest tests/test_shortcuts.py -q` | 75 passed | After About change |
| Standard project lint | `.venv/Scripts/python.exe -m ruff check talknj tests launch.py build_portable.py smoke_portable.py` | Passed | License packaging correction |
| Spec syntax | `.venv/Scripts/python.exe -m py_compile TalkNJ.spec` | Passed | License packaging correction |
| Native Windows build | PyInstaller command in Work performed | Passed; current licensed executable | Before metadata-only follow-up |
| Frozen runtime/render | Actual licensed EXE, bundle-only imports, Qt window and icon | Passed; fresh receipt `dist/smoke/licensed-v6okjy6x/runtime.json`; screenshot shows About navigation | After native rebuild |
| Portable archive | Python ZipFile CRC; archived EXE compared with fresh build; license compared with canonical GNU bytes | Passed; 156,057,502 bytes | After native rebuild |
| Python distribution | Actual pip wheel build; METADATA parse; license byte comparison; ZIP CRC | Passed; `License-Expression: GPL-3.0-only`, `License-File: LICENSE`; license at `talknj-0.1.0.dist-info/licenses/LICENSE` | Final metadata follow-up |
| Earlier full regression suite | `.venv/Scripts/python.exe -m pytest -q` | Historical 308 passed, 3 skipped; recorded in earlier plan/handoff, not rerun after About | Earlier source/icon state |

**Not run:**
- Full regression suite and real speech inference after the About/license-only changes; related UI checks and actual packaging smoke were used instead. Historical three-engine inference proof is not fresh inference proof for this ZIP.
- Native Mac setup, permissions, event ordering, typing, Intel/Apple Silicon app builds/extraction, and real-model frozen inference: no native Mac host/runner was available.
- Public signing/notarization/publication: not authorized or attempted.

**Important smoke target limitation:** `smoke_portable.py` defaults to `dist/TalkNJ/TalkNJ.exe`, which can be an older bundle. The successful latest run explicitly targeted `dist/licensed/TalkNJ/TalkNJ.exe` through the now-removed temporary wrapper. Running the default helper against an older folder does not verify the refreshed archive. Any future changed native artifact needs its own fresh, correctly targeted smoke.

## Open risks and blockers

- **Type: blocker. Owner: next authorized native Mac session. Impact:** `plans/20261021-portable-polish/plan.md` remains `status: blocked`; both actual native architecture/runtime gates remain open. Do not mark the whole release complete from Windows or source-only evidence.
- **Type: risk. Owner: successor agent/user. Impact:** uncommitted/untracked source and ignored evidence/artifacts require deliberate transfer; HEAD alone lacks the latest About/licensing work. Preserve differences rather than resetting to this or the older handoff snapshot.
- **Type: risk. Owner: user/successor agent. Impact:** an older running TalkNJ can keep Windows DLLs locked and enforce single-instance behavior. The previous build preserved that process; do not kill it or clobber its directory without authorization.
- **Type: risk. Owner: successor agent. Impact:** old handoffs and old artifact sizes are historical. The latest native build location, receipt, ZIP size, and wheel proof are listed above; Git/availability can change after capture.
- **Type: risk. Owner: next native Mac session. Impact:** PyObjC, permissions, modifier release, Cmd+Q dispatch, bundle symlinks/signing, and subprocess spawning require actual native observation. See the earlier Mac handoff rather than guessing fixes.

## Exact next actions

1. **First safe step** — read this artifact and `plans/20261021-portable-polish/plan.md`, then compare the live workspace against Current state before editing. From the actual project root, run read-only `git rev-parse --show-toplevel`, `git rev-parse --abbrev-ref HEAD`, `git rev-parse HEAD`, and `git status --short`; inspect the existing source and the two verification receipts listed above. Do not rerun builds merely to reconfirm unchanged historical results.
2. Preserve the listed modified/untracked files, especially root `LICENSE`, and this new handoff. If transferring work, transfer source changes explicitly; ignored evidence is optional historical proof, not a dependency. Do not copy Windows environments/binaries to serve as Mac dependencies/artifacts.
3. If there is no new implementation request, report that About and licensing are complete and wait for the next authorized task; do not create further licensing/layout churn from delayed model advisories.
4. Only if native Mac continuation is requested and an actual native host is reachable, use `plans/handoffs/macos-native-verification-20261021-1947.md` for the established setup/build/interactive/inference procedure, replacing its stale Git state with this handoff and the live workspace. Build separately per architecture, preserve Windows behavior, verify the license copy in the new native artifact, and retain fresh receipts. Lack of a native host is an explicit blocker, not permission to simulate success or dispatch remotely without authorization.

## Source pointers

- `talknj/ui.py`: `MainWindow.__init__` navigation around lines 299-327; `_about_page()` around lines 513-524.
- `LICENSE` and `https://www.gnu.org/licenses/gpl-3.0.txt`: project copy and its canonical upstream source.
- `pyproject.toml`: `[project]` SPDX/license-file declarations near lines 10-11; dependency/build pins.
- `README.md`: About, setup, privacy limits, portable-build instructions, and documented license location.
- `TalkNJ.spec`, `build_portable.py`, `smoke_portable.py`: native data inclusion, archive construction, and correctly targeted fresh frozen smoke requirements.
- `plans/20261021-portable-polish/plan.md` and `phase-03-packaging.md`: owning release status and current About/license/Windows/wheel evidence; `phase-02-macos.md` for outstanding native integration acceptance.
- `plans/handoffs/macos-native-verification-20261021-1947.md`: detailed conditional Mac continuation procedure; its old HEAD/status and pre-icon artifact numbers are not current.
- `.smoke/about-page.png`: actual source About visual proof.
- `dist/smoke/licensed-v6okjy6x/runtime.json`, `runtime.png`, `runtime.icon.png`: latest Windows frozen proof.
- `.smoke/license-wheel/verification.json` and `.smoke/license-wheel/talknj-0.1.0-py3-none-any.whl`: final Python metadata/license proof.
- `plans/journals/2026-10-22-simple-about-page-with-license-and-creator-details.md`, `plans/journals/2026-10-22-gpl-30-license-copy-and-portable-distribution-correction.md`, and `plans/journals/2026-10-22-verified-spdx-metadata-and-license-text-in-python-wheel.md`: chronological work records.
