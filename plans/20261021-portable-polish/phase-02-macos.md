# macOS integration
- [x] Windows native behavior and existing public native integration interfaces are preserved.
- [x] macOS uses actual OS keyboard listening, foreground-target capture, Unicode typing and clipboard APIs, with explicit permission requirements rather than fake fallbacks.
- [x] Hold/toggle and listener pause/resume/stop semantics remain coherent; typing refuses stale/changed targets and avoids held modifiers.
- [x] macOS settings/models use the platform-appropriate per-user data location; Windows paths remain unchanged.
- [x] Platform edge cases have meaningful isolated regressions and honest native-runtime verification limits.

## Evidence and native verification blocker
- Cross-platform fake-OS regressions exercise foreground process/window/element revalidation, Unicode scalars, clipboard failures, permissions, modifier/layout identity, lost-release recovery, tap shutdown, settings migration and listener replacement. These prove application-owned boundary behavior, not execution of PyObjC on macOS.
- Independent review identified Cocoa aggregate modifier events and Qt's native Cmd+Q accelerator overriding a cleared QAction shortcut. Both source defects were repaired. A local AppKit key-down monitor reserves Cmd+Q only when configured as TalkNJ's recording shortcut; the passive global tap and foreign applications remain unaffected. Monitor startup failure tears down the newly started tap.
- Delayed feedback exposed a partial-release edge case: normalized Darwin modifier identities now remain held until the raw aggregate modifier mask clears. The chooser reads `QInputEvent.modifiers`, avoiding `QKeyEvent`'s own-modifier bit toggle; both physical release orders are covered.
- Clipboard-only shortcuts require Input Monitoring, not Accessibility. Listener startup/revocation checks no longer require AX, and the controller avoids foreground target capture for Darwin clipboard-only recording. Actual foreground-target capture and Unicode typing still require AX permission.
- The final full suite passes **308 cases, 3 skipped**; Ruff passes. A real-controller regression reaches recording with AX-denied target capture in clipboard mode, rather than asserting mock signal forwarding. The original modifier and permission reproductions failed before repair.
- **Blocked:** no real Mac, configured Mac SSH host, or runnable remote Mac build was available. Native permissions/prompts, actual Cocoa dispatch, Unicode delivery to applications and global-tap/local-monitor ordering remain unverified. A native release must exercise these before claiming macOS verification.
