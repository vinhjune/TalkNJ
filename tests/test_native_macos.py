"""Mac consumer-visible behavior with only the PyObjC OS boundary replaced.

These run on Windows as well; they are not evidence of native macOS execution.
No real clipboard, permission prompts, input events or focus changes occur.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
import os
import threading
from types import SimpleNamespace

import pytest

from talknj import _native_macos as mac
from talknj import native


class _Process:
    def __init__(self, pid=None, launched=1):
        self.pid = pid if pid is not None else os.getpid() + 1
        self.launched = launched
        self.terminated = False

    def processIdentifier(self):
        return self.pid

    def launchDate(self):
        return self.launched

    def isTerminated(self):
        return self.terminated


class _AX:
    kAXErrorSuccess = 0
    kAXTrustedCheckOptionPrompt = "prompt"
    kAXFocusedWindowAttribute = "window"
    kAXFocusedUIElementAttribute = "element"

    def __init__(self):
        self.trusted = True
        self.requests = []
        self.application = object()
        self.attributes = {"window": object(), "element": object()}
        self.error = 0
        self.timeout_error = 0
        self.timeouts = []

    def AXIsProcessTrusted(self):
        return self.trusted

    def AXIsProcessTrustedWithOptions(self, options):
        self.requests.append(options)
        return self.trusted

    def AXUIElementCreateApplication(self, pid):
        return self.application

    def AXUIElementSetMessagingTimeout(self, app, seconds):
        self.timeouts.append((app, seconds))
        return self.timeout_error

    def AXUIElementCopyAttributeValue(self, app, name, output):
        return self.error, self.attributes.get(name)


class _Pasteboard:
    def __init__(self):
        self.cleared = 0
        self.writes = []
        self.accept = True

    def clearContents(self):
        self.cleared += 1
        return self.cleared

    def setString_forType_(self, text, kind):
        self.writes.append((text, kind))
        return self.accept


class _Quartz:
    kCGEventFlagMaskControl = 1 << 18
    kCGEventFlagMaskAlternate = 1 << 19
    kCGEventFlagMaskShift = 1 << 17
    kCGEventFlagMaskCommand = 1 << 20
    kCGEventSourceStateHIDSystemState = 1
    kCGEventSourceStatePrivate = -1
    kCGEventSourceUserData = "tag"
    kCGKeyboardEventKeycode = "code"
    kCGEventKeyDown = 10
    kCGEventKeyUp = 11
    kCGEventFlagsChanged = 12
    kCGEventTapDisabledByTimeout = 0xFFFFFFFE
    kCGEventTapDisabledByUserInput = 0xFFFFFFFF
    kCGSessionEventTap = 1
    kCGHeadInsertEventTap = 0
    kCGEventTapOptionListenOnly = 1

    def __init__(self):
        self.listen = True
        self.post = True
        self.listen_requests = 0
        self.post_requests = 0
        self.down = set()
        self.flags = 0
        self.posted = []
        self.after_post = None
        self.tap = object()
        self.enabled = False
        self.refuse_enable = False
        self.enable_calls = []
        self.tap_calls = []
        self.source = object()
        self.fail_keyboard_event = False

    def CGPreflightListenEventAccess(self):
        return self.listen

    def CGRequestListenEventAccess(self):
        self.listen_requests += 1
        return self.listen

    def CGPreflightPostEventAccess(self):
        return self.post

    def CGRequestPostEventAccess(self):
        self.post_requests += 1
        return self.post

    def CGEventSourceFlagsState(self, source):
        return self.flags

    def CGEventSourceKeyState(self, source, code):
        return code in self.down

    def CGEventSourceCreate(self, state):
        assert state == self.kCGEventSourceStatePrivate
        return self.source

    def CGEventCreateKeyboardEvent(self, source, code, down):
        if self.fail_keyboard_event:
            return None
        return {"down": down, "code": code}

    def CGEventSetFlags(self, event, flags):
        event["flags"] = flags

    def CGEventSetIntegerValueField(self, event, field, value):
        event[field] = value

    def CGEventKeyboardSetUnicodeString(self, event, length, text):
        assert length == len(text.encode("utf-16-le")) // 2
        event["unicode"] = (length, text)

    def CGEventPostToPid(self, pid, event):
        self.posted.append((pid, dict(event)))
        if self.after_post:
            self.after_post()

    def CGEventGetIntegerValueField(self, event, field):
        return event.get(field, 0)

    def CGEventGetFlags(self, event):
        return event.get("flags", 0)

    def CGEventTapCreate(self, location, placement, options, mask, callback, context):
        self.tap_calls.append((location, placement, options, mask))
        self.callback = callback
        return self.tap

    def CGEventTapEnable(self, tap, enable):
        self.enable_calls.append(enable)
        self.enabled = enable and not self.refuse_enable

    def CGEventTapIsEnabled(self, tap):
        return self.enabled


class _CF:
    kCFRunLoopDefaultMode = "default"

    def __init__(self, api):
        self.api = api
        self.source = object()
        self.runloop = object()
        self.added = []
        self.removed = []
        self.invalid_sources = []
        self.invalid_ports = []
        self.actions = []
        self.keep_running = False
        self.wake = threading.Event()

    def CFEqual(self, first, second):
        return first == second

    def CFMachPortCreateRunLoopSource(self, allocator, tap, order):
        return self.source

    def CFRunLoopGetCurrent(self):
        return self.runloop

    def CFRunLoopAddSource(self, runloop, source, mode):
        self.added.append((runloop, source, mode))

    def CFRunLoopRunInMode(self, mode, seconds, return_after_source):
        assert seconds == 0.05
        assert return_after_source is False
        if self.actions:
            self.actions.pop(0)()
        elif self.keep_running:
            self.wake.wait(0.01)
        else:
            self.api.listener._stopping.set()

    def CFRunLoopStop(self, runloop):
        self.wake.set()

    def CFRunLoopRemoveSource(self, runloop, source, mode):
        self.removed.append((runloop, source, mode))

    def CFRunLoopSourceInvalidate(self, source):
        self.invalid_sources.append(source)

    def CFMachPortInvalidate(self, tap):
        self.invalid_ports.append(tap)


class _API:
    def __init__(self):
        self.process = _Process()
        self.frontmost = self.process
        self.ax = _AX()
        self.quartz = _Quartz()
        self.pasteboard = _Pasteboard()
        self.workspace = SimpleNamespace(frontmostApplication=lambda: self.frontmost)
        self.local_monitors = {}
        self.appkit = SimpleNamespace(
            NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: self.workspace),
            NSPasteboard=SimpleNamespace(generalPasteboard=lambda: self.pasteboard),
            NSPasteboardTypeString="public.utf8-plain-text",
            NSEvent=SimpleNamespace(
                eventWithCGEvent_=lambda event: SimpleNamespace(
                    charactersIgnoringModifiers=lambda: event.get("characters", ""),
                    characters=lambda: event.get("actual", event.get("characters", ""))),
                addLocalMonitorForEventsMatchingMask_handler_=self.add_local_monitor,
                removeMonitor_=lambda token: self.local_monitors.pop(token)),
        )
        self.appkit.NSEventMaskKeyDown = 1 << 10
        self.objc = SimpleNamespace(autorelease_pool=nullcontext)
        self.cf = _CF(self)
        self.listener = None

    def listener_for(self, chord="ctrl+alt+space", press=None, release=None):
        notifications = []
        listener = mac.HotkeyListener(chord, press or (lambda: notifications.append("press")),
                                     release or (lambda: notifications.append("release")))
        self.listener = listener
        return listener, notifications

    def add_local_monitor(self, mask, handler):
        token = object()
        self.local_monitors[token] = handler
        return token

    def local_key(self, text="q", flags=None):
        if flags is None:
            flags = self.quartz.kCGEventFlagMaskCommand
        event = SimpleNamespace(characters=lambda: text, modifierFlags=lambda: flags)
        for handler in tuple(self.local_monitors.values()):
            event = handler(event)
            if event is None:
                break
        return event

    def event(self, kind, code=0, characters="", flags=None, tag=0, actual=None):
        if kind == self.quartz.kCGEventKeyDown:
            self.quartz.down.add(code)
        elif kind == self.quartz.kCGEventKeyUp:
            self.quartz.down.discard(code)
        if flags is not None:
            self.quartz.flags = flags
        event = {"code": code, "characters": characters, "flags": self.quartz.flags, "tag": tag}
        if actual is not None:
            event["actual"] = actual
        assert self.listener._event(self, kind, event) is event
        return event


@pytest.fixture
def api(monkeypatch):
    api = _API()
    monkeypatch.setattr(mac, "_get_api", lambda: api)
    return api


def test_canonical_command_display_and_shared_validation(monkeypatch):
    monkeypatch.setattr(native.sys, "platform", "darwin")
    assert native.format_hotkey("win+shift+f12") == "Shift + Cmd + F12"
    assert native.validate_hotkey("SPACE+WIN+CTRL") == "ctrl+win+space"
    with pytest.raises(TypeError):
        mac.HotkeyListener("win+a", None, lambda: None)


def test_clipboard_persists_unicode_without_permissions_or_key_events(api):
    api.ax.trusted = False
    api.quartz.listen = api.quartz.post = False
    mac.copy_text("Tiếng Việt 😀")
    assert api.pasteboard.writes == [("Tiếng Việt 😀", "public.utf8-plain-text")]
    assert api.quartz.posted == []
    assert api.ax.requests == []
    assert api.quartz.listen_requests == api.quartz.post_requests == 0


@pytest.mark.parametrize("text", ["x\x00y", "\ud800", "\udfff", 1])
def test_invalid_clipboard_text_never_clears_existing_contents(api, text):
    with pytest.raises((ValueError, TypeError)):
        mac.copy_text(text)
    assert api.pasteboard.cleared == 0


def test_clipboard_refusal_is_not_silent_success(api):
    api.pasteboard.accept = False
    with pytest.raises(RuntimeError, match="refused.*clipboard"):
        mac.copy_text("text")


def test_foreground_capture_is_exact_and_own_process_is_never_targeted(api):
    target = mac.foreground_window()
    assert target.pid == api.process.pid
    assert target.window is api.ax.attributes["window"]
    assert target.element is api.ax.attributes["element"]
    assert api.ax.timeouts == [(api.ax.application, 0.1)]
    api.frontmost = _Process(os.getpid())
    api.ax.trusted = False
    assert mac.foreground_window() == 0
    api.frontmost = None
    assert mac.foreground_window() == 0


def test_accessibility_refusal_preserves_clipboard_and_reports_typing_refusal(api):
    api.ax.trusted = False
    target = mac.foreground_window()
    assert api.ax.requests == [{"prompt": True}]
    mac.copy_text("Recoverable dictation")
    with pytest.raises(RuntimeError, match="Accessibility.*System Settings.*terminal/Python"):
        mac.type_text(target, "Recoverable dictation")
    assert api.pasteboard.writes[0][0] == "Recoverable dictation"
    assert api.quartz.posted == []


def test_typing_still_requires_accessibility_for_a_previously_captured_target(api):
    target = mac.foreground_window()
    api.ax.trusted = False
    with pytest.raises(RuntimeError, match="Accessibility.*System Settings"):
        mac.type_text(target, "must not type")
    assert api.ax.requests == [{"prompt": True}]
    assert api.quartz.posted == []


def test_unsupported_ax_focus_preserves_clipboard_dictation_but_refuses_typing(api):
    del api.ax.attributes["element"]
    target = mac.foreground_window()
    assert target
    mac.copy_text("recoverable")
    with pytest.raises(RuntimeError, match="accessible focus.*manual pasting"):
        mac.type_text(target, "recoverable")
    assert api.quartz.posted == []
    assert api.pasteboard.writes[0][0] == "recoverable"


def test_ax_error_and_timeout_failure_are_never_treated_as_valid_targets(api):
    api.ax.error = -25202
    target = mac.foreground_window()
    with pytest.raises(RuntimeError, match="AX error -25202"):
        mac.type_text(target, "text")
    api.ax.error = 0
    api.ax.timeout_error = -1
    target = mac.foreground_window()
    with pytest.raises(RuntimeError, match="safe timeout"):
        mac.type_text(target, "text")
    assert api.quartz.posted == []


def test_unicode_typing_keeps_surrogate_pairs_together_and_posts_only_to_original_pid(api):
    target = mac.foreground_window()
    mac.type_text(target, "ệ😀Z")
    assert [(event["down"], event["unicode"]) for pid, event in api.quartz.posted] == [
        (True, (1, "ệ")), (False, (1, "ệ")),
        (True, (2, "😀")), (False, (2, "😀")),
        (True, (1, "Z")), (False, (1, "Z")),
    ]
    assert all(pid == target.pid and event["flags"] == 0 and event["tag"] == mac._EVENT_TAG
               for pid, event in api.quartz.posted)


@pytest.mark.parametrize("change, message", [
    (lambda api: setattr(api, "frontmost", _Process(api.process.pid + 1)), "foreground application changed"),
    (lambda api: api.ax.attributes.update(window=object()), "focused window or text field changed"),
    (lambda api: api.ax.attributes.update(element=object()), "focused window or text field changed"),
    (lambda api: setattr(api.process, "terminated", True), "no longer exists"),
    (lambda api: setattr(api, "frontmost", _Process(api.process.pid, launched=2)), "identifier was reused"),
])
def test_typing_revalidates_process_window_and_focused_element_before_input(api, change, message):
    target = mac.foreground_window()
    change(api)
    with pytest.raises(RuntimeError, match=message):
        mac.type_text(target, "must not type")
    assert api.quartz.posted == []


@pytest.mark.parametrize("text", ["ab", "a"])
def test_focus_changes_stop_before_next_scalar_and_are_detected_after_final_scalar(api, text):
    target = mac.foreground_window()
    api.quartz.after_post = lambda: api.ax.attributes.update(element=object())
    with pytest.raises(RuntimeError, match="focused window or text field changed"):
        mac.type_text(target, text)
    assert len(api.quartz.posted) == 2  # Finish only the original scalar's down/up pair.


def test_modifier_pressed_mid_typing_stops_without_releasing_physical_keys(api):
    target = mac.foreground_window()
    api.quartz.after_post = lambda: setattr(api.quartz, "flags", api.quartz.kCGEventFlagMaskCommand)
    with pytest.raises(RuntimeError, match="modifier key was pressed"):
        mac.type_text(target, "abc")
    assert len(api.quartz.posted) == 2
    assert api.quartz.flags == api.quartz.kCGEventFlagMaskCommand


def test_held_modifiers_wait_and_focus_is_checked_during_wait(api, monkeypatch):
    target = mac.foreground_window()
    api.quartz.flags = api.quartz.kCGEventFlagMaskAlternate
    sleeps = []

    def release(seconds):
        sleeps.append(seconds)
        api.quartz.flags = 0

    monkeypatch.setattr(mac.time, "sleep", release)
    mac.type_text(target, "a")
    assert sleeps == [0.01]
    api.quartz.posted.clear()
    api.quartz.flags = api.quartz.kCGEventFlagMaskShift
    monkeypatch.setattr(mac.time, "sleep", lambda seconds: api.ax.attributes.update(window=object()))
    with pytest.raises(RuntimeError, match="focused window or text field changed"):
        mac.type_text(target, "a")
    assert api.quartz.posted == []


def test_held_modifier_timeout_never_posts_input(api, monkeypatch):
    target = mac.foreground_window()
    api.quartz.flags = api.quartz.kCGEventFlagMaskControl
    clock = [0.0]
    monkeypatch.setattr(mac.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(mac.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    with pytest.raises(RuntimeError, match="Release Control, Option, Shift and Command"):
        mac.type_text(target, "text")
    assert 3.0 <= clock[0] < 3.02
    assert api.quartz.posted == []


def test_post_permission_failure_and_revocation_never_retry_text(api):
    target = mac.foreground_window()
    api.quartz.post = False
    with pytest.raises(RuntimeError, match="System Settings.*Accessibility"):
        mac.type_text(target, "text")
    assert api.quartz.post_requests == 1
    assert api.quartz.posted == []
    api.quartz.post = True
    api.quartz.after_post = lambda: setattr(api.quartz, "post", False)
    with pytest.raises(RuntimeError, match="permission was revoked"):
        mac.type_text(target, "ab")
    assert len(api.quartz.posted) == 2


def test_invalid_own_and_empty_typing_targets(api):
    target = mac.foreground_window()
    for invalid in (0, True, 12, object()):
        with pytest.raises(ValueError):
            mac.type_text(invalid, "text")
    with pytest.raises(RuntimeError, match="TalkNJ itself"):
        mac.type_text(replace(target, pid=os.getpid()), "text")
    with pytest.raises(ValueError):
        mac.type_text(target, "x\x00y")
    mac.type_text(target, "")
    assert api.quartz.posted == []


def test_keyboard_allocation_failures_do_not_silently_succeed(api):
    target = mac.foreground_window()
    api.quartz.source = None
    with pytest.raises(RuntimeError, match="event source"):
        mac.type_text(target, "text")
    api.quartz.source = object()
    api.quartz.fail_keyboard_event = True
    with pytest.raises(RuntimeError, match="Unicode keyboard events"):
        mac.type_text(target, "text")
    assert api.quartz.posted == []


@pytest.mark.parametrize("chord, code, characters, modifier", [
    ("alt+s", 1, "s", "alt"),  # Option's actual text may be ß; use ignoring-modifier identity.
    ("ctrl+shift+a", 12, "A", "ctrl"),
    ("win+7", 26, "7", "win"),
    ("ctrl+space", 49, " ", "ctrl"),
    ("win+f12", 111, "", "win"),
    ("alt+.", 47, ".", "alt"),
    ("alt+,", 43, ",", "alt"),
    ("ctrl+;", 41, ";", "ctrl"),
])
def test_logical_hotkey_identity_and_autorepeat_are_independent_of_mac_keycodes(api, chord, code, characters, modifier):
    listener, notifications = api.listener_for(chord)
    flag = mac._modifier_flags(api)[modifier]
    if "shift" in chord:
        flag |= api.quartz.kCGEventFlagMaskShift
    api.quartz.flags = flag
    api.event(api.quartz.kCGEventKeyDown, code, characters)
    api.event(api.quartz.kCGEventKeyDown, code, characters)
    api.event(api.quartz.kCGEventKeyUp, code, characters)
    assert notifications == ["press", "release"]
    assert listener._error is None


def test_trigger_before_modifiers_and_either_side_release_match_shared_state_machine(api):
    listener, notifications = api.listener_for("win+a")
    api.event(api.quartz.kCGEventKeyDown, 0, "a")
    command = api.quartz.kCGEventFlagMaskCommand
    api.quartz.down.add(54)
    api.event(api.quartz.kCGEventFlagsChanged, 54, flags=command)
    api.quartz.down.add(55)
    api.event(api.quartz.kCGEventFlagsChanged, 55, flags=command)
    api.quartz.down.remove(54)
    api.event(api.quartz.kCGEventFlagsChanged, 54, flags=command)
    assert notifications == ["press"]
    api.quartz.down.remove(55)
    api.event(api.quartz.kCGEventFlagsChanged, 55, flags=0)
    assert notifications == ["press", "release"]


def test_modifier_only_chord_uses_flags_and_waits_for_final_modifier_side(api):
    listener, notifications = api.listener_for("ctrl+win")
    q = api.quartz
    control, command = q.kCGEventFlagMaskControl, q.kCGEventFlagMaskCommand
    q.down.add(59)
    api.event(q.kCGEventFlagsChanged, 59, flags=control)
    assert notifications == []
    q.down.add(55)
    api.event(q.kCGEventFlagsChanged, 55, flags=control | command)
    api.event(q.kCGEventFlagsChanged, 55, flags=control | command)
    q.down.add(62)
    api.event(q.kCGEventFlagsChanged, 62, flags=control | command)
    q.down.remove(59)
    api.event(q.kCGEventFlagsChanged, 59, flags=control | command)
    assert notifications == ["press"]
    q.down.remove(62)
    api.event(q.kCGEventFlagsChanged, 62, flags=command)
    q.down.remove(55)
    api.event(q.kCGEventFlagsChanged, 55, flags=0)
    assert notifications == ["press", "release"]
    assert listener._error is None


def test_lost_keyup_recovers_release_without_synthesizing_new_press(api):
    listener, notifications = api.listener_for("ctrl+a")
    api.quartz.flags = api.quartz.kCGEventFlagMaskControl
    api.event(api.quartz.kCGEventKeyDown, 0, "a")
    api.quartz.down.clear()
    listener._update(listener._snapshot(api), allow_press=False)
    assert notifications == ["press", "release"]
    api.quartz.down.add(0)
    listener._update(listener._snapshot(api), allow_press=False)
    assert notifications == ["press", "release"]


def test_suspend_is_silent_and_resume_waits_for_keys_held_before_listener_started(api):
    listener, notifications = api.listener_for("ctrl+a")
    api.quartz.flags = api.quartz.kCGEventFlagMaskControl
    api.event(api.quartz.kCGEventKeyDown, 0, "a")
    listener.suspend()
    api.quartz.down.add(12)  # Unknown held key has no observed key-down in this listener.
    listener.resume()
    api.event(api.quartz.kCGEventKeyUp, 0, "a", flags=0)
    listener._update(listener._snapshot(api), allow_press=False)
    assert notifications == ["press"]
    api.quartz.down.clear()
    listener._update(listener._snapshot(api), allow_press=False)
    api.event(api.quartz.kCGEventKeyDown, 0, "a", flags=api.quartz.kCGEventFlagMaskControl)
    api.event(api.quartz.kCGEventKeyUp, 0, "a")
    assert notifications == ["press", "press", "release"]


def test_own_unicode_events_never_activate_a_hotkey(api):
    listener, notifications = api.listener_for("ctrl+a")
    api.quartz.flags = api.quartz.kCGEventFlagMaskControl
    api.event(api.quartz.kCGEventKeyDown, 0, "a", tag=mac._EVENT_TAG)
    assert notifications == []
    assert listener._keys == {}


def test_disabled_tap_releases_active_hold_and_waits_for_complete_release(api):
    listener, notifications = api.listener_for("ctrl+a")
    listener._tap = api.quartz.tap
    api.quartz.flags = api.quartz.kCGEventFlagMaskControl
    api.event(api.quartz.kCGEventKeyDown, 0, "a")
    api.event(api.quartz.kCGEventTapDisabledByTimeout)
    api.event(api.quartz.kCGEventKeyDown, 0, "a")
    assert notifications == ["press", "release"]
    api.event(api.quartz.kCGEventKeyUp, 0, "a", flags=0)
    api.event(api.quartz.kCGEventKeyDown, 0, "a", flags=api.quartz.kCGEventFlagMaskControl)
    assert notifications == ["press", "release", "press"]
    assert api.quartz.enable_calls == [True]


def test_listener_input_monitoring_refusal_is_actionable_before_hook_install(api):
    listener, notifications = api.listener_for()
    api.quartz.listen = False
    with pytest.raises(RuntimeError, match="Input Monitoring.*System Settings"):
        listener.start()
    assert api.quartz.listen_requests == 1
    assert api.ax.requests == []
    assert api.quartz.tap_calls == []
    assert listener._thread is None


@pytest.mark.parametrize("initial_accessibility", [False, True])
def test_listener_delivers_gestures_without_accessibility_and_after_its_revocation(api, initial_accessibility):
    api.ax.trusted = initial_accessibility
    api.quartz.post = False
    api.cf.keep_running = True
    listener, notifications = api.listener_for("ctrl+a")
    delivered = threading.Event()
    api.cf.actions = [
        lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a", flags=api.quartz.kCGEventFlagMaskControl),
        lambda: setattr(api.ax, "trusted", False),
        lambda: api.event(api.quartz.kCGEventKeyUp, 0, "a"),
        lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a"),
        lambda: api.event(api.quartz.kCGEventKeyUp, 0, "a"),
        delivered.set,
    ]
    listener.start()
    try:
        assert delivered.wait(2.0)
        assert notifications == ["press", "release", "press", "release"]
        assert listener._error is None
        assert api.ax.requests == []
        assert api.quartz.post_requests == 0
    finally:
        listener.stop()
    assert api.cf.invalid_sources == [api.cf.source]
    assert api.cf.invalid_ports == [api.quartz.tap]


def test_real_runloop_uses_passive_tap_and_cleans_all_resources_and_active_hold(api):
    listener, notifications = api.listener_for("ctrl+a")
    api.cf.actions = [lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a",
                                       flags=api.quartz.kCGEventFlagMaskControl)]
    listener._run()
    assert notifications == ["press", "release"]
    assert api.quartz.tap_calls == [(1, 0, 1, (1 << 10) | (1 << 11) | (1 << 12))]
    assert api.cf.removed == api.cf.added
    assert api.cf.invalid_sources == [api.cf.source]
    assert api.cf.invalid_ports == [api.quartz.tap]
    assert api.quartz.enable_calls == [True, False]
    assert listener._tap is None
    assert listener._runloop is None
    assert listener._error is None


def test_callback_failure_preserves_event_and_cleans_up(api):
    def fail():
        raise ValueError("consumer failed")

    listener, notifications = api.listener_for("ctrl+a", press=fail)
    api.cf.actions = [lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a",
                                       flags=api.quartz.kCGEventFlagMaskControl)]
    listener._run()
    assert isinstance(listener._error, ValueError)
    assert notifications == ["release"]
    assert api.cf.invalid_ports == [api.quartz.tap]
    assert api.cf.invalid_sources == [api.cf.source]


@pytest.mark.parametrize("failure, message", [("tap", "passive macOS keyboard listener"),
                                               ("source", "release recovery"),
                                               ("enable", "refused to enable")])
def test_partial_startup_failure_removes_every_created_resource(api, failure, message):
    listener, notifications = api.listener_for()
    if failure == "tap":
        api.quartz.tap = None
    elif failure == "source":
        api.cf.source = None
    else:
        api.quartz.refuse_enable = True
    with pytest.raises(RuntimeError, match=message):
        listener.start()
    with pytest.raises(RuntimeError, match="listener failed"):
        listener.stop()
    assert api.cf.invalid_ports == ([] if failure == "tap" else [api.quartz.tap])
    assert api.cf.invalid_sources == ([] if failure in ("tap", "source") else [api.cf.source])
    assert notifications == []


def test_input_monitoring_revoked_during_runloop_releases_hold_and_removes_tap(api):
    listener, notifications = api.listener_for("ctrl+a")
    api.cf.actions = [
        lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a", flags=api.quartz.kCGEventFlagMaskControl),
        lambda: setattr(api.quartz, "listen", False),
    ]
    listener._run()
    assert notifications == ["press", "release"]
    assert "Input Monitoring permission was revoked" in str(listener._error)
    assert "System Settings" in str(listener._error)
    assert listener._stopping.is_set()
    assert api.cf.removed == api.cf.added
    assert api.cf.invalid_sources == [api.cf.source]
    assert api.cf.invalid_ports == [api.quartz.tap]
    assert api.quartz.enable_calls == [True, False]


def test_command_q_is_reserved_only_locally_while_its_listener_is_active(api):
    api.cf.keep_running = True
    listener, notifications = api.listener_for("win+q")
    listener.start()
    try:
        # Local key dispatch precedes Cocoa's Quit accelerator, with or without
        # a focused Qt widget. The global tap must still observe the gesture.
        api.event(api.quartz.kCGEventKeyDown, 12, "q", flags=api.quartz.kCGEventFlagMaskCommand)
        assert api.local_key() is None
        api.event(api.quartz.kCGEventKeyUp, 12, "q")
        assert notifications == ["press", "release"]
        assert api.local_key("a") is not None
        assert api.local_key(flags=api.quartz.kCGEventFlagMaskControl) is not None
        assert api.local_key(flags=(api.quartz.kCGEventFlagMaskCommand |
                                    api.quartz.kCGEventFlagMaskShift)) is not None
        listener.suspend()
        assert api.local_key() is not None
        listener.resume()
        assert api.local_key() is None
    finally:
        listener.stop()
    assert api.local_key() is not None

    api.cf.wake.clear()
    rebound, _ = api.listener_for("ctrl+q")
    rebound.start()
    try:
        assert api.local_key() is not None
    finally:
        rebound.stop()


def test_start_stop_restart_are_idempotent_and_callbacks_stay_on_listener_thread(api):
    callback_threads = []
    pressed = threading.Event()

    def press():
        callback_threads.append(threading.get_ident())
        pressed.set()

    listener, notifications = api.listener_for("ctrl+a", press=press)
    api.cf.keep_running = True
    api.cf.actions = [lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a",
                                       flags=api.quartz.kCGEventFlagMaskControl)]
    listener.start()
    assert pressed.wait(2.0)
    first = listener._thread
    listener.start()
    assert listener._thread is first
    listener.stop()
    listener.stop()
    assert not first.is_alive()
    assert callback_threads == [first.ident]
    assert notifications == ["release"]
    api.cf.wake.clear()
    api.quartz.down.clear()
    api.quartz.flags = 0
    listener.start()
    second = listener._thread
    assert second is not first
    listener.stop()
    assert not second.is_alive()
    assert api.cf.invalid_ports == [api.quartz.tap, api.quartz.tap]
    assert api.cf.invalid_sources == [api.cf.source, api.cf.source]


def test_option_dead_keys_and_command_specific_layouts_match_qt_logical_characters(api):
    listener, notifications = api.listener_for("alt+s")
    api.event(api.quartz.kCGEventKeyDown, 1, "s", flags=api.quartz.kCGEventFlagMaskAlternate, actual="ß")
    api.event(api.quartz.kCGEventKeyUp, 1, "s", actual="ß")
    assert notifications == ["press", "release"]
    listener, notifications = api.listener_for("win+k")
    api.event(api.quartz.kCGEventKeyDown, 0, "a", flags=api.quartz.kCGEventFlagMaskCommand, actual="k")
    api.event(api.quartz.kCGEventKeyUp, 0, "a", actual="k")
    assert notifications == ["press", "release"]


def test_shifted_punctuation_never_reuses_a_previous_digit_mapping(api):
    listener, notifications = api.listener_for("shift+1")
    api.event(api.quartz.kCGEventKeyDown, 18, "1")
    api.event(api.quartz.kCGEventKeyUp, 18, "1")
    api.event(api.quartz.kCGEventKeyDown, 18, "!", flags=api.quartz.kCGEventFlagMaskShift)
    assert notifications == []
    assert 18 not in listener._keys


def test_post_failure_still_releases_unicode_key_without_retrying_text(api, monkeypatch):
    target = mac.foreground_window()
    post = api.quartz.CGEventPostToPid

    def interrupted(pid, event):
        post(pid, event)
        if event["down"]:
            raise RuntimeError("OS event posting failed")

    monkeypatch.setattr(api.quartz, "CGEventPostToPid", interrupted)
    with pytest.raises(RuntimeError, match="OS event posting failed"):
        mac.type_text(target, "ab")
    assert [event["down"] for pid, event in api.quartz.posted] == [True, False]
    assert [event["unicode"][1] for pid, event in api.quartz.posted] == ["a", "a"]


def test_release_callback_failure_does_not_skip_resource_cleanup(api):
    def fail_release():
        raise ValueError("release failed")

    listener, notifications = api.listener_for("ctrl+a", release=fail_release)
    api.cf.actions = [lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a",
                                       flags=api.quartz.kCGEventFlagMaskControl)]
    listener._run()
    assert notifications == ["press"]
    assert isinstance(listener._error, ValueError)
    assert api.cf.invalid_ports == [api.quartz.tap]
    assert api.cf.invalid_sources == [api.cf.source]


def test_missing_pyobjc_dependencies_have_actionable_install_error(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def without_appkit(name, *args, **kwargs):
        if name == "AppKit":
            raise ImportError("AppKit unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_appkit)
    with pytest.raises(RuntimeError, match="Reinstall TalkNJ with its macOS dependencies"):
        mac._MacAPI()


def test_stop_from_press_callback_never_joins_itself_and_releases_hold(api):
    pressed = threading.Event()

    def press():
        api.listener.stop()
        pressed.set()

    listener, notifications = api.listener_for("ctrl+a", press=press)
    api.cf.keep_running = True
    api.cf.actions = [lambda: api.event(api.quartz.kCGEventKeyDown, 0, "a",
                                       flags=api.quartz.kCGEventFlagMaskControl)]
    listener.start()
    assert pressed.wait(2.0)
    listener.stop()
    assert notifications == ["release"]
    assert listener._thread is None
    assert api.cf.invalid_ports == [api.quartz.tap]


def test_cleanup_failure_still_invalidates_remaining_resources(api, monkeypatch):
    listener, notifications = api.listener_for()

    def cannot_remove(*args):
        raise RuntimeError("runloop source removal failed")

    monkeypatch.setattr(api.cf, "CFRunLoopRemoveSource", cannot_remove)
    listener._run()
    assert "runloop source removal failed" in str(listener._error)
    assert api.cf.invalid_sources == [api.cf.source]
    assert api.cf.invalid_ports == [api.quartz.tap]


def test_local_reservation_failure_stops_the_started_global_listener(api):
    api.cf.keep_running = True
    api.appkit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_ = lambda mask, handler: None
    listener, notifications = api.listener_for("win+q")
    with pytest.raises(RuntimeError, match="Cannot reserve Cmd\\+Q"):
        listener.start()
    assert listener._thread is None
    assert api.cf.invalid_ports == [api.quartz.tap]
    assert api.local_key() is not None
    assert notifications == []
