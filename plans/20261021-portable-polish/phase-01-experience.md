# Experience polish
- [x] whisper.cpp appears first and is preferred when no valid model selection exists; Parakeet follows, then existing catalog models in their previous order.
- [x] Existing valid explicit choices survive refresh and reload; no weights download automatically.
- [x] The main recording display and background listening indicator show remaining time from 05:00 to 00:00; boundary/rounding behavior remains coherent with the unchanged cap.
- [x] Dropdowns and scrollbars use modern coherent controls with visible hover/focus/disabled states; current layout and palette remain recognizable.
- [x] Windows UI is exercised and visually inspected, including an open dropdown, scrolling and an active countdown.

## Evidence
- Live Windows Python desktop smoke selected whisper.cpp with no saved choice, exposed whisper.cpp/Parakeet/Tiny English in order, scrolled Preferences, and recorded a real microphone session. Both displays changed from `05:00 remaining` to `04:58 remaining`; no recorder error occurred. Selecting Tiny English explicitly survived refresh.
- Actual screenshots of the model popup, preferences popup/scrollbar, recording display and nonactivating indicator were inspected. Isolated controller cases cover countdown rounding/end boundaries and missing/valid saved selection behavior.
- Cocoa aggregate modifier capture regression failed before the repair and passes after it, including opposite-side release followed by successful shortcut confirmation. Native Mac key delivery remains a separate verification limit.
