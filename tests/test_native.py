"""Deterministic tests; no real hooks, clipboard changes, focus changes, or typing."""

from __future__ import annotations

import ctypes
import os
import threading
import unittest
from unittest.mock import Mock, patch

from talknj import native


class HotkeyValidationTests(unittest.TestCase):
    def test_canonical_order_case_and_whitespace(self) -> None:
        self.assertEqual(native.validate_hotkey(" SPACE + ALT + Ctrl "), "ctrl+alt+space")
        self.assertEqual(native.validate_hotkey("win+f12+shift+ctrl"), "ctrl+shift+win+f12")
        self.assertEqual(native.validate_hotkey("Alt+7"), "alt+7")
        self.assertEqual(native.validate_hotkey("SHIFT+Z"), "shift+z")

    def test_all_supported_trigger_keys(self) -> None:
        keys = [*"abcdefghijklmnopqrstuvwxyz0123456789", "space"]
        keys.extend(f"f{number}" for number in range(1, 13))
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(native.validate_hotkey(f"ctrl+{key}"), f"ctrl+{key}")

    def test_rejects_ambiguous_unsupported_and_incomplete_chords(self) -> None:
        invalid = [
            "", " ", "+", "ctrl", "a", "ctrl+alt", "ctrl+a+b", "ctrl++a",
            "ctrl+ctrl+a", "CTRL+ctrl+a", "ctrl+a+a", "control+a", "meta+a",
            "ctrl+enter", "ctrl+f0", "ctrl+f13", "ctrl+é", "ctrl+ab",
            "ctrl+space+", "ctrl+num1", "ctrl+1.0",
        ]
        for chord in invalid:
            with self.subTest(chord=chord), self.assertRaises(ValueError):
                native.validate_hotkey(chord)

    def test_non_text_is_rejected(self) -> None:
        for value in (None, 3, ["ctrl", "a"]):
            with self.subTest(value=value), self.assertRaises(TypeError):
                native.validate_hotkey(value)  # type: ignore[arg-type]

    def test_callbacks_must_be_callable(self) -> None:
        with self.assertRaises(TypeError):
            native.HotkeyListener("ctrl+a", None, lambda: None)  # type: ignore[arg-type]

    def test_unsupported_platform_fails_clearly(self) -> None:
        with patch.object(native, "_IS_WINDOWS", False):
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                native.foreground_window()
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                native.copy_text("text")
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                native.type_text(10, "text")
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                native.HotkeyListener("ctrl+a", lambda: None, lambda: None).start()


class ChordStateTests(unittest.TestCase):
    def test_autorepeat_fires_once_and_last_modifier_side_releases(self) -> None:
        state = native._ChordState("ctrl+alt+space")
        self.assertEqual(state.update({0xA2}), 0)
        self.assertEqual(state.update({0xA2, 0xA5}), 0)
        down = {0xA2, 0xA5, 0x20}
        self.assertEqual(state.update(down), 1)
        for _ in range(10):
            self.assertEqual(state.update(down), 0)
        self.assertEqual(state.update(down | {0xA3}), 0)
        self.assertEqual(state.update({0xA3, 0xA5, 0x20}), 0)
        self.assertEqual(state.update({0xA5, 0x20}), -1)
        self.assertEqual(state.update(set()), 0)

    def test_each_logical_member_can_end_the_gesture(self) -> None:
        for released in (0xA3, 0xA4, 0x20):
            with self.subTest(released=released):
                state = native._ChordState("ctrl+alt+space")
                down = {0xA3, 0xA4, 0x20}
                self.assertEqual(state.update(down), 1)
                self.assertEqual(state.update(down - {released}), -1)
                self.assertEqual(state.update(down - {released}), 0)
                self.assertEqual(state.update(down), 1)

    def test_trigger_can_be_pressed_before_modifier(self) -> None:
        state = native._ChordState("win+f2")
        self.assertEqual(state.update({0x71}), 0)
        self.assertEqual(state.update({0x71, 0x5C}), 1)
        self.assertEqual(state.update({0x71}), -1)

    def test_additional_modifiers_do_not_break_an_active_chord(self) -> None:
        state = native._ChordState("ctrl+a")
        self.assertEqual(state.update({0xA3, 0x41}), 1)
        self.assertEqual(state.update({0xA3, 0x41, 0xA1, 0x5B}), 0)
        self.assertEqual(state.update({0xA3, 0x41}), 0)

    def test_polling_recovers_missing_release_but_never_synthesizes_press(self) -> None:
        state = native._ChordState("ctrl+a")
        self.assertEqual(state.update({0xA2, 0x41}, allow_press=False), 0)
        self.assertEqual(state.update({0xA2, 0x41}), 1)
        self.assertEqual(state.update({0x41}, allow_press=False), -1)
        self.assertEqual(state.update(set(), allow_press=False), 0)
        self.assertEqual(state.update({0xA2, 0x41}, allow_press=False), 0)

    def test_reset_emits_at_most_one_release(self) -> None:
        state = native._ChordState("shift+2")
        self.assertEqual(state.reset(), 0)
        self.assertEqual(state.update({0xA1, 0x32}), 1)
        self.assertEqual(state.reset(), -1)
        self.assertEqual(state.reset(), 0)

    def test_generic_modifier_event_normalization(self) -> None:
        cases = [(0x10, 0x2A, 0, 0xA0), (0x10, 0x36, 0, 0xA1),
                 (0x11, 0, 0, 0xA2), (0x11, 0, 1, 0xA3),
                 (0x12, 0, 0, 0xA4), (0x12, 0, 1, 0xA5),
                 (0x5C, 0, 0, 0x5C)]
        for vk, scan, flags, expected in cases:
            with self.subTest(vk=vk, scan=scan, flags=flags):
                event = native._KBDLLHOOKSTRUCT(vk, scan, flags, 0, 0)
                self.assertEqual(native._event_vk(event), expected)


class InputLayoutTests(unittest.TestCase):
    def test_input_union_matches_windows_abi(self) -> None:
        is_64bit = ctypes.sizeof(ctypes.c_void_p) == 8
        self.assertEqual(ctypes.sizeof(native._INPUT), 40 if is_64bit else 28)
        self.assertEqual(ctypes.sizeof(native._MOUSEINPUT), 32 if is_64bit else 24)
        self.assertEqual(ctypes.sizeof(native._KEYBDINPUT), 24 if is_64bit else 16)
        self.assertEqual(native._INPUT.data.offset, 8 if is_64bit else 4)
        self.assertEqual(ctypes.sizeof(native._KBDLLHOOKSTRUCT), 24 if is_64bit else 20)

    def test_text_rejects_nul_and_unpaired_surrogates(self) -> None:
        for text in ("before\x00after", "\ud800", "\udfff", "a\ud800z"):
            with self.subTest(text=repr(text)), self.assertRaises(ValueError):
                native._text_bytes(text)

    def test_valid_unicode_encoding_and_empty_text(self) -> None:
        self.assertEqual(native._text_bytes(""), b"")
        self.assertEqual(native._text_bytes("Tiếng Việt 😀"), "Tiếng Việt 😀".encode("utf-16-le"))
        with self.assertRaises(TypeError):
            native._text_bytes(b"not text")  # type: ignore[arg-type]


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []
        self.on_sleep = None

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.sleeps.append(seconds)
        if self.on_sleep is not None:
            self.on_sleep()


class _InputAPI:
    def __init__(self) -> None:
        self.target = 0x1234567887654321 if ctypes.sizeof(ctypes.c_void_p) == 8 else 0x1234
        self.foreground = self.target
        self.exists = True
        self.pid = os.getpid() + 1
        self.down: set[int] = set()
        self.sent: list[list[tuple[int, int, int]]] = []
        self.sizes: list[int] = []
        self.accepted: int | None = None
        self.after_send = None

    def IsWindow(self, target: int) -> int:
        return int(self.exists)

    def GetForegroundWindow(self) -> int:
        return self.foreground

    def GetWindowThreadProcessId(self, target: int, process: object) -> int:
        ctypes.cast(process, ctypes.POINTER(native._DWORD)).contents.value = self.pid
        return 1

    def GetAsyncKeyState(self, vk: int) -> int:
        return -32768 if vk in self.down else 0

    def SendInput(self, count: int, inputs: object, size: int) -> int:
        pointer = ctypes.cast(inputs, ctypes.POINTER(native._INPUT))
        self.sent.append([(pointer[i].ki.wVk, pointer[i].ki.wScan, pointer[i].ki.dwFlags) for i in range(count)])
        self.sizes.append(size)
        if self.after_send is not None:
            self.after_send()
        return count if self.accepted is None else self.accepted


@unittest.skipUnless(os.name == "nt", "ctypes last-error semantics require Windows")
class UnicodeTypingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = _InputAPI()
        self.clock = _Clock()
        self.enterContext(patch.object(native, "_get_api", return_value=self.api))
        self.enterContext(patch.object(native.time, "monotonic", self.clock.monotonic))
        self.enterContext(patch.object(native.time, "sleep", self.clock.sleep))

    def test_unicode_surrogate_pair_is_one_atomic_submission(self) -> None:
        native.type_text(self.api.target, "ệ😀Z")
        self.assertEqual(self.api.sent, [
            [(0, 0x1EC7, 4), (0, 0x1EC7, 6)],
            [(0, 0xD83D, 4), (0, 0xD83D, 6), (0, 0xDE00, 4), (0, 0xDE00, 6)],
            [(0, ord("Z"), 4), (0, ord("Z"), 6)],
        ])
        self.assertTrue(all(size == ctypes.sizeof(native._INPUT) for size in self.api.sizes))
        self.assertEqual(self.clock.sleeps, [])

    def test_empty_text_does_not_send_any_input(self) -> None:
        native.type_text(self.api.target, "")
        self.assertEqual(self.api.sent, [])

    def test_waits_for_both_sides_of_every_trigger_modifier(self) -> None:
        for vk in native._MODIFIER_VKS:
            with self.subTest(vk=vk):
                self.api.sent.clear()
                self.api.down = {vk}
                self.clock.on_sleep = self.api.down.clear
                native.type_text(self.api.target, "x")
                self.assertEqual(len(self.api.sent), 1)
        self.assertEqual(len(self.clock.sleeps), len(native._MODIFIER_VKS))

    def test_held_modifier_times_out_without_output(self) -> None:
        self.api.down = {0xA3}
        with self.assertRaisesRegex(RuntimeError, "Release Ctrl"):
            native.type_text(self.api.target, "must not type")
        self.assertGreaterEqual(self.clock.now, 3.0)
        self.assertLess(self.clock.now, 3.02)
        self.assertEqual(self.api.sent, [])

    def test_changed_foreground_while_waiting_aborts_immediately(self) -> None:
        self.api.down = {0xA2}
        self.clock.on_sleep = lambda: setattr(self.api, "foreground", 999)
        with self.assertRaisesRegex(RuntimeError, "foreground window changed"):
            native.type_text(self.api.target, "must not type")
        self.assertEqual(self.api.sent, [])
        self.assertLess(self.clock.now, 0.1)

    def test_changed_foreground_during_insertion_stops_before_next_scalar(self) -> None:
        self.api.after_send = lambda: setattr(self.api, "foreground", 999)
        with self.assertRaisesRegex(RuntimeError, "foreground window changed"):
            native.type_text(self.api.target, "abc")
        self.assertEqual(len(self.api.sent), 1)
        self.assertEqual(self.api.sent[0][0][1], ord("a"))

    def test_focus_change_after_final_submission_is_reported(self) -> None:
        self.api.after_send = lambda: setattr(self.api, "foreground", 999)
        with self.assertRaisesRegex(RuntimeError, "foreground window changed"):
            native.type_text(self.api.target, "x")
        self.assertEqual(len(self.api.sent), 1)

    def test_reused_handle_from_another_process_is_rejected(self) -> None:
        self.api.after_send = lambda: setattr(self.api, "pid", os.getpid() + 2)
        with self.assertRaisesRegex(RuntimeError, "reused by another process"):
            native.type_text(self.api.target, "abc")
        self.assertEqual(len(self.api.sent), 1)

    def test_modifier_pressed_during_insertion_stops_before_next_scalar(self) -> None:
        self.api.after_send = lambda: self.api.down.add(0x5C)
        with self.assertRaisesRegex(RuntimeError, "modifier key was pressed"):
            native.type_text(self.api.target, "abc")
        self.assertEqual(len(self.api.sent), 1)

    def test_rejects_closed_foreign_or_own_window_before_typing(self) -> None:
        self.api.exists = False
        with self.assertRaisesRegex(RuntimeError, "no longer exists"):
            native.type_text(self.api.target, "abc")
        self.api.exists = True
        self.api.foreground = 999
        with self.assertRaisesRegex(RuntimeError, "foreground window changed"):
            native.type_text(self.api.target, "abc")
        self.api.foreground = self.api.target
        self.api.pid = os.getpid()
        with self.assertRaisesRegex(RuntimeError, "TalkNJ itself"):
            native.type_text(self.api.target, "abc")
        self.assertEqual(self.api.sent, [])

    def test_invalid_handles_and_invalid_text_never_reach_sendinput(self) -> None:
        for target in (0, -1, True, "123", 1 << (8 * ctypes.sizeof(ctypes.c_void_p))):
            with self.subTest(target=target), self.assertRaises(ValueError):
                native.type_text(target, "x")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            native.type_text(self.api.target, "x\x00y")
        self.assertEqual(self.api.sent, [])

    def test_uipi_refusal_is_actionable_and_never_retried(self) -> None:
        self.api.accepted = 0
        with self.assertRaisesRegex(RuntimeError, "0 of 2.*UIPI.*paste manually"):
            native.type_text(self.api.target, "abc")
        self.assertEqual(len(self.api.sent), 1)

    def test_partial_submission_releases_packet_but_never_retries_text(self) -> None:
        self.api.accepted = 1
        with self.assertRaisesRegex(RuntimeError, "1 of 4"):
            native.type_text(self.api.target, "😀z")
        self.assertEqual(len(self.api.sent), 2)
        self.assertEqual(self.api.sent[1], [(0, 0xD83D, 6)])

    def test_foreground_handle_is_not_truncated(self) -> None:
        self.assertEqual(native.foreground_window(), self.api.target)
        self.api.foreground = 0
        self.assertEqual(native.foreground_window(), 0)


class _ClipboardAPI:
    def __init__(self) -> None:
        self.buffer = None
        self.memory = 0x1234567887654321 if ctypes.sizeof(ctypes.c_void_p) == 8 else 0x1234
        self.copied = b""
        self.open_attempts = 0
        self.busy_attempts = 0
        self.freed: list[int] = []
        self.closed = 0
        self.destroyed: list[int] = []
        self.owner_args = None
        self.fail_set = False
        self.fail_lock = False

    def GlobalAlloc(self, flags: int, size: int) -> int:
        self.buffer = ctypes.create_string_buffer(size)
        return self.memory

    def GlobalLock(self, memory: int) -> int:
        return 0 if self.fail_lock else ctypes.addressof(self.buffer)

    def GlobalUnlock(self, memory: int) -> int:
        return 0  # Success: lock count reached zero, last error remains zero.

    def GlobalFree(self, memory: int) -> int:
        self.freed.append(memory)
        return 0

    def GetModuleHandleW(self, name: str | None) -> int:
        return 123

    def CreateWindowExW(self, *args: object) -> int:
        self.owner_args = args
        return 456

    def DestroyWindow(self, window: int) -> int:
        self.destroyed.append(window)
        return 1

    def OpenClipboard(self, window: int) -> int:
        self.open_attempts += 1
        return int(self.open_attempts > self.busy_attempts)

    def EmptyClipboard(self) -> int:
        return 1

    def SetClipboardData(self, format_id: int, memory: int) -> int:
        if self.fail_set:
            return 0
        self.copied = self.buffer.raw
        return memory

    def CloseClipboard(self) -> int:
        self.closed += 1
        return 1


@unittest.skipUnless(os.name == "nt", "ctypes last-error semantics require Windows")
class ClipboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = _ClipboardAPI()
        self.clock = _Clock()
        self.enterContext(patch.object(native, "_get_api", return_value=self.api))
        self.enterContext(patch.object(native.time, "monotonic", self.clock.monotonic))
        self.enterContext(patch.object(native.time, "sleep", self.clock.sleep))

    def test_unicode_text_retained_with_terminator_and_owner_transfer(self) -> None:
        native.copy_text("Tiếng Việt 😀")
        self.assertEqual(self.api.copied, "Tiếng Việt 😀".encode("utf-16-le") + b"\x00\x00")
        self.assertEqual(self.api.freed, [])
        self.assertEqual(self.api.closed, 1)
        self.assertEqual(self.api.destroyed, [456])
        self.assertEqual(self.api.owner_args[1], "STATIC")
        self.assertEqual(self.api.owner_args[8].value, ctypes.c_void_p(-3).value)
        self.assertEqual(self.api.owner_args[3], 0)  # No WS_VISIBLE, no activation.

    def test_empty_string_still_produces_usable_unicode_clipboard(self) -> None:
        native.copy_text("")
        self.assertEqual(self.api.copied, b"\x00\x00")
        self.assertEqual(self.api.freed, [])

    def test_busy_clipboard_retries_then_succeeds(self) -> None:
        self.api.busy_attempts = 3
        native.copy_text("retained")
        self.assertEqual(self.api.open_attempts, 4)
        self.assertEqual(len(self.clock.sleeps), 3)
        self.assertEqual(self.api.closed, 1)

    def test_busy_clipboard_eventually_fails_and_frees_unowned_memory(self) -> None:
        self.api.busy_attempts = 1000
        with self.assertRaisesRegex(RuntimeError, "clipboard is busy"):
            native.copy_text("not transferred")
        self.assertGreaterEqual(self.clock.now, 0.75)
        self.assertEqual(self.api.freed, [self.api.memory])
        self.assertEqual(self.api.closed, 0)
        self.assertEqual(self.api.destroyed, [456])

    def test_failed_transfer_closes_clipboard_and_frees_memory(self) -> None:
        self.api.fail_set = True
        with self.assertRaisesRegex(RuntimeError, "Cannot place"):
            native.copy_text("not transferred")
        self.assertEqual(self.api.closed, 1)
        self.assertEqual(self.api.freed, [self.api.memory])
        self.assertEqual(self.api.destroyed, [456])

    def test_failed_lock_frees_memory_without_opening_clipboard(self) -> None:
        self.api.fail_lock = True
        with self.assertRaisesRegex(RuntimeError, "Cannot lock"):
            native.copy_text("not transferred")
        self.assertEqual(self.api.freed, [self.api.memory])
        self.assertEqual(self.api.open_attempts, 0)

    def test_invalid_text_never_allocates_or_changes_clipboard(self) -> None:
        with self.assertRaises(ValueError):
            native.copy_text("truncated\x00text")
        self.assertIsNone(self.api.buffer)
        self.assertEqual(self.api.open_attempts, 0)


class _HookAPI:
    def __init__(self, events: list[tuple]) -> None:
        self.events = iter(events)
        self.callback = None
        self.down: set[int] = set()
        self.forwarded: list[tuple[int, int]] = []
        self.results: list[int] = []
        self.unhooked: list[int] = []
        self.killed: list[int] = []
        self.installed = None

    def GetCurrentThreadId(self) -> int:
        return 77

    def PeekMessageW(self, *args: object) -> int:
        return 0

    def GetModuleHandleW(self, name: str | None) -> int:
        return 123

    def SetWindowsHookExW(self, kind: int, callback: object, module: int, thread: int) -> int:
        self.callback = callback
        self.installed = (kind, module, thread)
        return 321

    def SetTimer(self, *args: object) -> int:
        return 555

    def GetAsyncKeyState(self, vk: int) -> int:
        return -32768 if vk in self.down else 0

    def GetMessageW(self, message: object, *args: object) -> int:
        item = next(self.events, None)
        if item is None:
            return 0
        if item[0] == "physical":
            self.down = set(item[1])
        else:
            _, vk, down, code, syskey = item
            event = native._KBDLLHOOKSTRUCT(vk, 0, 0, 0, 0)
            message_id = (0x0104 if down else 0x0105) if syskey else (0x0100 if down else 0x0101)
            self.results.append(self.callback(code, message_id, ctypes.addressof(event)))
            if down:
                self.down.add(vk)
            else:
                self.down.discard(vk)
        pointer = ctypes.cast(message, ctypes.POINTER(native._MSG))
        pointer.contents.message = native._WM_TIMER
        pointer.contents.wParam = 555
        return 1

    def CallNextHookEx(self, hook: int, code: int, wparam: int, lparam: int) -> int:
        self.forwarded.append((code, wparam))
        return 99

    def KillTimer(self, window: object, timer: int) -> int:
        self.killed.append(timer)
        return 1

    def UnhookWindowsHookEx(self, hook: int) -> int:
        self.unhooked.append(hook)
        return 1


class HookBehaviorTests(unittest.TestCase):
    def run_hook(self, events: list[tuple], *, fail_press: bool = False) -> tuple[list[str], _HookAPI, native.HotkeyListener]:
        api = _HookAPI(events)
        notifications: list[str] = []

        def press() -> None:
            notifications.append("press")
            if fail_press:
                raise ValueError("consumer callback failed")

        listener = native.HotkeyListener("ctrl+alt+space", press, lambda: notifications.append("release"))
        # These tests exercise the real hook callback and message-loop logic,
        # replacing only the OS boundary, including the ctypes callback thunk.
        with patch.object(native, "_get_api", return_value=api), patch.object(native, "_HOOKPROC", lambda callback: callback):
            listener._run()
        return notifications, api, listener

    def test_repeat_syskeys_and_mixed_sides_forward_every_event(self) -> None:
        events = [
            ("key", 0xA3, True, 0, False),
            ("key", 0xA4, True, 0, True),
            ("key", 0x20, True, 0, False),
            ("key", 0x20, True, 0, False),
            ("key", 0x20, True, 0, False),
            ("key", 0xA4, False, 0, True),
            ("key", 0x20, False, 0, False),
            ("key", 0xA3, False, 0, False),
        ]
        notifications, api, listener = self.run_hook(events)
        self.assertEqual(notifications, ["press", "release"])
        self.assertEqual(len(api.forwarded), len(events))
        self.assertEqual(api.results, [99] * len(events))
        self.assertEqual(api.installed, (13, 123, 0))
        self.assertEqual(api.killed, [555])
        self.assertEqual(api.unhooked, [321])
        self.assertIsNone(listener._error)

    def test_lost_modifier_release_is_recovered_by_poll(self) -> None:
        events = [
            ("key", 0xA2, True, 0, False), ("key", 0xA5, True, 0, True),
            ("key", 0x20, True, 0, False), ("physical", set()),
        ]
        notifications, _, _ = self.run_hook(events)
        self.assertEqual(notifications, ["press", "release"])

    def test_shutdown_releases_an_active_hold_once(self) -> None:
        events = [
            ("key", 0xA2, True, 0, False), ("key", 0xA4, True, 0, True),
            ("key", 0x20, True, 0, False),
        ]
        notifications, _, listener = self.run_hook(events)
        self.assertEqual(notifications, ["press", "release"])
        self.assertFalse(listener._state.active)

    def test_negative_hook_codes_are_forwarded_without_activation(self) -> None:
        events = [("key", 0x20, True, -1, False)]
        notifications, api, _ = self.run_hook(events)
        self.assertEqual(notifications, [])
        self.assertEqual(api.forwarded, [(-1, 0x0100)])
        self.assertEqual(api.results, [99])

    def test_consumer_exception_does_not_swallow_event_and_unhooks(self) -> None:
        events = [
            ("key", 0xA2, True, 0, False), ("key", 0xA4, True, 0, True),
            ("key", 0x20, True, 0, False),
        ]
        with self.assertLogs(native._LOG, level="ERROR"):
            notifications, api, listener = self.run_hook(events, fail_press=True)
        self.assertEqual(notifications, ["press", "release"])
        self.assertEqual(api.results, [99, 99, 99])
        self.assertIsInstance(listener._error, ValueError)
        self.assertEqual(api.unhooked, [321])

    def test_callbacks_execute_on_the_hook_thread(self) -> None:
        api = _HookAPI([
            ("key", 0xA2, True, 0, False), ("key", 0xA4, True, 0, True),
            ("key", 0x20, True, 0, False),
        ])
        callback_threads: list[int] = []
        listener = native.HotkeyListener(
            "ctrl+alt+space", lambda: callback_threads.append(threading.get_ident()),
            lambda: callback_threads.append(threading.get_ident()),
        )
        with patch.object(native, "_get_api", return_value=api), patch.object(native, "_HOOKPROC", lambda callback: callback):
            thread = threading.Thread(target=listener._run)
            thread.start()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(callback_threads, [thread.ident, thread.ident])
        self.assertNotEqual(thread.ident, threading.get_ident())

    def test_startup_failure_reaches_caller_and_stop_reports_error(self) -> None:
        api = _HookAPI([])
        listener = native.HotkeyListener("ctrl+a", Mock(), Mock())
        with (
            patch.object(native, "_get_api", return_value=api),
            patch.object(native, "_HOOKPROC", lambda callback: callback),
            patch.object(native, "_native_error", return_value=RuntimeError("hook installation refused")),
            patch.object(api, "SetWindowsHookExW", return_value=0),
            self.assertLogs(native._LOG, level="ERROR"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Cannot start.*hook installation refused"):
                listener.start()
            with self.assertRaisesRegex(RuntimeError, "listener failed"):
                listener.stop()
        self.assertEqual(api.unhooked, [])
        self.assertEqual(api.killed, [])

    def test_recovery_timer_failure_removes_installed_hook(self) -> None:
        api = _HookAPI([])
        listener = native.HotkeyListener("ctrl+a", Mock(), Mock())
        with (
            patch.object(native, "_get_api", return_value=api),
            patch.object(native, "_HOOKPROC", lambda callback: callback),
            patch.object(native, "_native_error", return_value=RuntimeError("timer creation refused")),
            patch.object(api, "SetTimer", return_value=0),
            self.assertLogs(native._LOG, level="ERROR"),
        ):
            listener._run()
        self.assertIsInstance(listener._error, RuntimeError)
        self.assertEqual(api.unhooked, [321])
        self.assertEqual(api.killed, [])

    def test_message_loop_failure_removes_hook_and_timer(self) -> None:
        api = _HookAPI([])
        listener = native.HotkeyListener("ctrl+a", Mock(), Mock())
        with (
            patch.object(native, "_get_api", return_value=api),
            patch.object(native, "_HOOKPROC", lambda callback: callback),
            patch.object(native, "_native_error", return_value=RuntimeError("message loop failed")),
            patch.object(api, "GetMessageW", return_value=-1),
            self.assertLogs(native._LOG, level="ERROR"),
        ):
            listener._run()
        self.assertIsInstance(listener._error, RuntimeError)
        self.assertEqual(api.unhooked, [321])
        self.assertEqual(api.killed, [555])

    def test_start_stop_and_restart_are_clean_and_idempotent(self) -> None:
        class BlockingAPI(_HookAPI):
            def __init__(self) -> None:
                super().__init__([])
                self.quit = threading.Event()

            def SetWindowsHookExW(self, kind: int, callback: object, module: int, thread: int) -> int:
                self.quit.clear()
                return super().SetWindowsHookExW(kind, callback, module, thread)

            def GetMessageW(self, message: object, *args: object) -> int:
                self.quit.wait(2)
                return 0

            def PostThreadMessageW(self, thread: int, message: int, wparam: int, lparam: int) -> int:
                self.quit.set()
                return 1

        api = BlockingAPI()
        listener = native.HotkeyListener("ctrl+a", Mock(), Mock())
        with patch.object(native, "_get_api", return_value=api), patch.object(native, "_HOOKPROC", lambda callback: callback):
            listener.start()
            first_thread = listener._thread
            listener.start()
            self.assertIs(listener._thread, first_thread)
            listener.stop()
            listener.stop()
            self.assertFalse(first_thread.is_alive())
            listener.start()
            second_thread = listener._thread
            self.assertIsNot(first_thread, second_thread)
            listener.stop()
            self.assertFalse(second_thread.is_alive())
        self.assertEqual(api.unhooked, [321, 321])
        self.assertEqual(api.killed, [555, 555])
