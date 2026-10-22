"""Passive Quartz hotkeys and focus-checked AppKit/Accessibility text delivery.

PyObjC is imported only at the OS boundary. A target retains the original running
application, AX window and focused element: a different window or text field in
that same application is not an acceptable substitute. CGEventPostToPid narrows
but cannot eliminate the race between validation and asynchronous OS delivery.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import threading
import time


_LOG = logging.getLogger(__name__)
_EVENT_TAG = 0x54414C4B4E4A
# Physical modifier sides are translated to the existing _ChordState identities.
_MODIFIER_CODES = {
    59: (0xA2, "ctrl"), 62: (0xA3, "ctrl"),
    58: (0xA4, "alt"), 61: (0xA5, "alt"),
    56: (0xA0, "shift"), 60: (0xA1, "shift"),
    55: (0x5B, "win"), 54: (0x5C, "win"),
}
_FUNCTION_CODES = dict(zip((122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111), range(0x70, 0x7C)))
_PERMISSION_HELP = (
    "Open System Settings > Privacy & Security > {permission}, enable TalkNJ "
    "(or the terminal/Python application used to launch it), then quit and reopen TalkNJ."
)


class _MacAPI:
    def __init__(self) -> None:
        try:
            import AppKit
            import ApplicationServices
            import CoreFoundation
            import Quartz
            import objc
        except ImportError as exc:
            raise RuntimeError(
                "macOS native integration requires the Cocoa, Quartz and ApplicationServices "
                "PyObjC packages. Reinstall TalkNJ with its macOS dependencies."
            ) from exc
        self.appkit = AppKit
        self.ax = ApplicationServices
        self.cf = CoreFoundation
        self.quartz = Quartz
        self.objc = objc


@lru_cache(maxsize=1)
def _get_api() -> _MacAPI:
    return _MacAPI()


def _require_accessibility(api: _MacAPI) -> None:
    if api.ax.AXIsProcessTrusted():
        return
    api.ax.AXIsProcessTrustedWithOptions({api.ax.kAXTrustedCheckOptionPrompt: True})
    if not api.ax.AXIsProcessTrusted():
        raise RuntimeError("Accessibility permission is required for safe target capture and typing. " +
                           _PERMISSION_HELP.format(permission="Accessibility"))


def _require_listening(api: _MacAPI) -> None:
    if api.quartz.CGPreflightListenEventAccess():
        return
    api.quartz.CGRequestListenEventAccess()
    if not api.quartz.CGPreflightListenEventAccess():
        raise RuntimeError("Input Monitoring permission is required for the global shortcut. " +
                           _PERMISSION_HELP.format(permission="Input Monitoring"))


def _require_posting(api: _MacAPI) -> None:
    _require_accessibility(api)
    if api.quartz.CGPreflightPostEventAccess():
        return
    api.quartz.CGRequestPostEventAccess()
    if not api.quartz.CGPreflightPostEventAccess():
        raise RuntimeError("macOS has not allowed simulated keyboard input. " +
                           _PERMISSION_HELP.format(permission="Accessibility"))


def _attribute(api: _MacAPI, element: object, name: str) -> object:
    error, value = api.ax.AXUIElementCopyAttributeValue(element, name, None)
    if error != api.ax.kAXErrorSuccess or value is None:
        raise RuntimeError(
            "Cannot inspect the original focused window or text field through Accessibility "
            f"(macOS AX error {error}). The application may not expose an accessible focus; "
            "the transcript remains copied for manual pasting."
        )
    return value


@dataclass(frozen=True, slots=True, eq=False)
class _Target:
    pid: int
    process: object
    launched: object
    application: object
    window: object
    element: object
    failure: str = ""


def foreground_window() -> _Target | int:
    """Capture the frontmost foreign application's exact AX window and focus."""
    api = _get_api()
    with api.objc.autorelease_pool():
        process = api.appkit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if process is None or process.isTerminated():
            return 0
        pid = int(process.processIdentifier())
        if pid == os.getpid():
            return 0
        _require_accessibility(api)
        application = api.ax.AXUIElementCreateApplication(pid)
        try:
            if application is None:
                raise RuntimeError("Cannot inspect the foreground application. The transcript remains copied for manual pasting.")
            # Bound callback work even if the foreground app is unresponsive.
            if api.ax.AXUIElementSetMessagingTimeout(application, 0.1) != api.ax.kAXErrorSuccess:
                raise RuntimeError("Cannot set a safe timeout for foreground Accessibility inspection.")
            window = _attribute(api, application, api.ax.kAXFocusedWindowAttribute)
            element = _attribute(api, application, api.ax.kAXFocusedUIElementAttribute)
            target = _Target(pid, process, process.launchDate(), application, window, element)
            _validate_target(api, target)
            return target
        except RuntimeError as exc:
            # Clipboard-only dictation must still work in apps without AX focus.
            # Retain the reason so type mode reports refusal instead of guessing.
            return _Target(pid, process, process.launchDate(), application, None, None, str(exc))


def copy_text(text: str) -> None:
    """Write persistent Unicode text to the system pasteboard without key events."""
    from talknj.native import _text_bytes

    _text_bytes(text)
    api = _get_api()
    with api.objc.autorelease_pool():
        pasteboard = api.appkit.NSPasteboard.generalPasteboard()
        if pasteboard is None:
            raise RuntimeError("Cannot access the macOS system clipboard.")
        pasteboard.clearContents()
        if not pasteboard.setString_forType_(text, api.appkit.NSPasteboardTypeString):
            raise RuntimeError("macOS refused the Unicode transcript on the clipboard.")


def _validate_target(api: _MacAPI, target: _Target) -> None:
    if target.failure:
        raise RuntimeError(target.failure)
    if target.pid == os.getpid():
        raise RuntimeError("Typing into TalkNJ itself is disabled. The transcript remains copied.")
    current = api.appkit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if target.process.isTerminated():
        raise RuntimeError("The original target application no longer exists. The transcript remains copied.")
    if current is None or current.isTerminated() or int(current.processIdentifier()) != target.pid:
        raise RuntimeError("The foreground application changed. Nothing further was typed; the transcript remains copied.")
    if current.launchDate() != target.launched:
        raise RuntimeError("The original process identifier was reused. The transcript remains copied.")
    for original, attribute in ((target.window, api.ax.kAXFocusedWindowAttribute),
                                (target.element, api.ax.kAXFocusedUIElementAttribute)):
        focused = _attribute(api, target.application, attribute)
        if not api.cf.CFEqual(original, focused):
            raise RuntimeError("The focused window or text field changed. Nothing further was typed; the transcript remains copied.")


def _modifier_flags(api: _MacAPI) -> dict[str, int]:
    q = api.quartz
    return {"ctrl": q.kCGEventFlagMaskControl, "alt": q.kCGEventFlagMaskAlternate,
            "shift": q.kCGEventFlagMaskShift, "win": q.kCGEventFlagMaskCommand}


def _apply_modifier_flags(api: _MacAPI, down: set[int], flags: int, changed_code: int | None = None) -> None:
    """Reconcile aggregate flags with known modifier sides, preferring the event's side."""
    side = _MODIFIER_CODES.get(changed_code) if changed_code is not None else None
    for name, flag in _modifier_flags(api).items():
        group = [key for key, modifier in _MODIFIER_CODES.values() if modifier == name]
        if not flags & flag:
            down.difference_update(group)
        elif not down.intersection(group):
            down.add(side[0] if side is not None and side[1] == name else group[0])


def _modifiers_down(api: _MacAPI) -> bool:
    q = api.quartz
    return bool(q.CGEventSourceFlagsState(q.kCGEventSourceStateHIDSystemState) &
                sum(_modifier_flags(api).values()))


def type_text(target: object, text: str) -> None:
    """Post Unicode scalars only while the original application and AX focus match."""
    from talknj.native import _text_bytes

    _text_bytes(text)
    if not isinstance(target, _Target):
        raise ValueError("The target must be a captured macOS application/window token.")
    api = _get_api()
    with api.objc.autorelease_pool():
        _require_posting(api)
        deadline = time.monotonic() + 3.0
        while True:
            _validate_target(api, target)
            if not _modifiers_down(api):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Release Control, Option, Shift and Command keys before typing. The transcript remains copied.")
            time.sleep(0.01)
        q = api.quartz
        source = q.CGEventSourceCreate(q.kCGEventSourceStatePrivate)
        if source is None:
            raise RuntimeError("Cannot create a macOS keyboard event source. The transcript remains copied.")
        # Reuse the pair and keep both UTF-16 units of an emoji in one event.
        down = q.CGEventCreateKeyboardEvent(source, 0, True)
        up = q.CGEventCreateKeyboardEvent(source, 0, False)
        if down is None or up is None:
            raise RuntimeError("Cannot create macOS Unicode keyboard events. The transcript remains copied.")
        for event in (down, up):
            q.CGEventSetFlags(event, 0)
            q.CGEventSetIntegerValueField(event, q.kCGEventSourceUserData, _EVENT_TAG)
        for scalar in text:
            length = 2 if ord(scalar) > 0xFFFF else 1
            for event in (down, up):
                q.CGEventKeyboardSetUnicodeString(event, length, scalar)
            _validate_target(api, target)
            if _modifiers_down(api):
                raise RuntimeError("A modifier key was pressed during typing. Insertion stopped; the transcript remains copied.")
            if not q.CGPreflightPostEventAccess():
                raise RuntimeError("Accessibility keyboard permission was revoked. Insertion stopped; the transcript remains copied. " +
                                   _PERMISSION_HELP.format(permission="Accessibility"))
            # Address the original PID, never the new foreground application.
            # The API returns void; do not retry text that may already be delivered.
            try:
                q.CGEventPostToPid(target.pid, down)
            finally:
                q.CGEventPostToPid(target.pid, up)
        _validate_target(api, target)


def _key_identity(api: _MacAPI, event: object, code: int) -> int | None:
    if code in _FUNCTION_CODES:
        return _FUNCTION_CODES[code]
    if code == 49:
        return 0x20
    native = api.appkit.NSEvent.eventWithCGEvent_(event)
    if native is None:
        return None
    # Match Qt's Cocoa translation: Control/Option ignore their text transforms
    # (including dead keys), while Command-specific layouts retain characters().
    # Both paths preserve Shift; punctuation is not guessed back into a digit.
    q = api.quartz
    flags = q.CGEventGetFlags(event)
    characters = (native.charactersIgnoringModifiers() if flags &
                  (q.kCGEventFlagMaskControl | q.kCGEventFlagMaskAlternate) else native.characters())
    characters = str(characters or "").lower()
    if len(characters) == 1 and ("a" <= characters <= "z" or "0" <= characters <= "9"):
        return ord(characters.upper())
    if characters == " ":
        return 0x20
    return None


class HotkeyListener:
    """Listen-only CGEvent tap; all physical events continue to other apps."""

    def __init__(self, chord: str, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        from talknj.native import _ChordState, validate_hotkey

        self.chord = validate_hotkey(chord)
        if not callable(on_press) or not callable(on_release):
            raise TypeError("Hotkey press and release callbacks must be callable.")
        self._state = _ChordState(self.chord)
        self._on_press = on_press
        self._on_release = on_release
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None
        self._suspended = False
        self._waiting_for_release = False
        self._keys: dict[int, int] = {}
        self._resume_keys: set[int] = set()
        self._runloop = None
        self._tap = None
        self._local_monitor = None

    def start(self) -> None:
        api = _get_api()
        # Prompt on the caller/UI thread, before installing a partially working tap.
        _require_listening(api)
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self._stopping.is_set():
                    raise RuntimeError("The previous hotkey listener is still stopping.")
                return
            self._state.reset()
            self._keys.clear()
            self._ready.clear()
            self._stopping.clear()
            self._error = None
            self._thread = threading.Thread(target=self._run, name="TalkNJ hotkey", daemon=True)
            self._thread.start()
        if not self._ready.wait(5.0):
            self._stopping.set()
            if self._runloop is not None:
                api.cf.CFRunLoopStop(self._runloop)
            raise RuntimeError("macOS did not initialize the global hotkey listener in time.")
        if self._error is not None:
            raise RuntimeError(f"Cannot start the global hotkey listener: {self._error}") from self._error
        if self.chord == "win+q":
            # Cocoa's native Quit menu restores Cmd+Q even when QAction's
            # shortcut is cleared. Reserve it only in our own application;
            # the passive global tap still receives the physical gesture.
            modifiers = _modifier_flags(api)
            modifier_mask = sum(modifiers.values())

            def local_key(event):
                with self._lock:
                    if self._suspended or self._stopping.is_set() or self._error is not None:
                        return event
                    flags = int(event.modifierFlags()) & modifier_mask
                    if flags == modifiers["win"] and (event.characters() or "").lower() == "q":
                        return None
                return event

            try:
                self._local_monitor = api.appkit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                    api.appkit.NSEventMaskKeyDown, local_key)
                if self._local_monitor is None:
                    raise RuntimeError("Cannot reserve Cmd+Q for the recording shortcut in TalkNJ.")
            except BaseException:
                self.stop()
                raise

    def stop(self) -> None:
        with self._lock:
            self._stopping.set()
            if self._local_monitor is not None:
                try:
                    _get_api().appkit.NSEvent.removeMonitor_(self._local_monitor)
                except BaseException as exc:
                    self._error = self._error or exc
                finally:
                    self._local_monitor = None
            thread = self._thread
            if thread is None:
                return
            if self._runloop is not None:
                _get_api().cf.CFRunLoopStop(self._runloop)
        if thread is threading.current_thread():
            return
        thread.join(5.0)
        if thread.is_alive():
            raise RuntimeError("The hotkey listener did not stop. Ensure callbacks do not block.")
        with self._lock:
            if self._thread is thread:
                self._thread = None
        if self._error is not None:
            raise RuntimeError(f"The global hotkey listener failed: {self._error}") from self._error

    def suspend(self) -> None:
        with self._lock:
            self._suspended = True
            self._state.reset()

    def resume(self) -> None:
        api = _get_api()
        with self._lock:
            self._state.reset()
            self._waiting_for_release = True
            # Include keys already held when capture was opened or the tap started.
            self._resume_keys = {code for code in range(128) if api.quartz.CGEventSourceKeyState(
                api.quartz.kCGEventSourceStateHIDSystemState, code)}
            self._suspended = False

    def _notify(self, transition: int) -> None:
        if transition > 0:
            self._on_press()
        elif transition < 0:
            self._on_release()

    def _update(self, down: Collection[int], *, allow_press: bool = True) -> None:
        with self._lock:
            if self._suspended:
                return
            if self._waiting_for_release:
                if not self._resume_keys and not any(key in down for key in self._state.watched):
                    self._waiting_for_release = False
                return
            self._notify(self._state.update(down, allow_press=allow_press))

    def _snapshot(self, api: _MacAPI) -> set[int]:
        q = api.quartz
        state = q.kCGEventSourceStateHIDSystemState
        with self._lock:
            self._resume_keys = {code for code in self._resume_keys if q.CGEventSourceKeyState(state, code)}
            down = {key for code, key in self._keys.items() if q.CGEventSourceKeyState(state, code)}
        flags = q.CGEventSourceFlagsState(state)
        for code, (key, name) in _MODIFIER_CODES.items():
            if q.CGEventSourceKeyState(state, code):
                down.add(key)
        _apply_modifier_flags(api, down, flags)
        return down

    def _rearm_tap(self, api: _MacAPI) -> None:
        with self._lock:
            self._notify(self._state.reset())
            self._waiting_for_release = True
        _require_listening(api)
        api.quartz.CGEventTapEnable(self._tap, True)
        if not api.quartz.CGEventTapIsEnabled(self._tap):
            raise RuntimeError("macOS disabled the global keyboard listener. " +
                               _PERMISSION_HELP.format(permission="Input Monitoring"))

    def _event(self, api: _MacAPI, kind: int, event: object) -> object:
        q = api.quartz
        try:
            if self._stopping.is_set():
                return event
            if kind in (q.kCGEventTapDisabledByTimeout, q.kCGEventTapDisabledByUserInput):
                self._rearm_tap(api)
                return event
            if q.CGEventGetIntegerValueField(event, q.kCGEventSourceUserData) == _EVENT_TAG:
                return event
            code = int(q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventKeycode))
            with self._lock:
                if kind == q.kCGEventKeyDown:
                    self._keys.pop(code, None)
                    key = _key_identity(api, event, code)
                    if key is not None:
                        self._keys[code] = key
                down = self._snapshot(api)
                if kind == q.kCGEventKeyDown and code in self._keys:
                    down.add(self._keys[code])
                elif kind == q.kCGEventKeyUp:
                    key = self._keys.get(code)
                    if key is not None:
                        down.discard(key)
                    self._resume_keys.discard(code)
                elif kind == q.kCGEventFlagsChanged:
                    flags = q.CGEventGetFlags(event)
                    _apply_modifier_flags(api, down, flags, code)
                self._update(down)
        except BaseException as exc:
            self._error = exc
            self._stopping.set()
            _LOG.exception("Global macOS hotkey callback failed")
        return event  # A listen-only tap cannot suppress or replace physical input.

    def _run(self) -> None:
        api = None
        source = None
        try:
            api = _get_api()
            with api.objc.autorelease_pool():
                q, cf = api.quartz, api.cf
                mask = sum(1 << kind for kind in (q.kCGEventKeyDown, q.kCGEventKeyUp, q.kCGEventFlagsChanged))

                def callback(proxy: object, kind: int, event: object, context: object) -> object:
                    with api.objc.autorelease_pool():
                        return self._event(api, kind, event)

                # Keep callback alive through port invalidation, even on partial startup.
                self._tap = q.CGEventTapCreate(q.kCGSessionEventTap, q.kCGHeadInsertEventTap,
                                              q.kCGEventTapOptionListenOnly, mask, callback, None)
                if self._tap is None:
                    raise RuntimeError("Cannot install the passive macOS keyboard listener. " +
                                       _PERMISSION_HELP.format(permission="Input Monitoring"))
                source = cf.CFMachPortCreateRunLoopSource(None, self._tap, 0)
                if source is None:
                    raise RuntimeError("Cannot initialize macOS hotkey release recovery.")
                with self._lock:
                    self._runloop = cf.CFRunLoopGetCurrent()
                    cf.CFRunLoopAddSource(self._runloop, source, cf.kCFRunLoopDefaultMode)
                q.CGEventTapEnable(self._tap, True)
                if not q.CGEventTapIsEnabled(self._tap):
                    raise RuntimeError("macOS refused to enable the passive keyboard listener. " +
                                       _PERMISSION_HELP.format(permission="Input Monitoring"))
                self._ready.set()
                while not self._stopping.is_set():
                    with api.objc.autorelease_pool():
                        cf.CFRunLoopRunInMode(cf.kCFRunLoopDefaultMode, 0.05, False)
                        if self._stopping.is_set():
                            break
                        if not q.CGPreflightListenEventAccess():
                            raise RuntimeError("macOS Input Monitoring permission was revoked. " +
                                               _PERMISSION_HELP.format(permission="Input Monitoring"))
                        if not q.CGEventTapIsEnabled(self._tap):
                            self._rearm_tap(api)
                        self._update(self._snapshot(api), allow_press=False)
        except BaseException as exc:
            self._error = exc
            _LOG.exception("Global macOS hotkey listener failed")
        finally:
            self._stopping.set()
            if api is not None:
                # Continue cleanup even if an individual OS cleanup operation fails.
                cleanups = []
                if self._tap is not None:
                    cleanups.append(lambda: api.quartz.CGEventTapEnable(self._tap, False))
                if source is not None and self._runloop is not None:
                    cleanups.append(lambda: api.cf.CFRunLoopRemoveSource(self._runloop, source, api.cf.kCFRunLoopDefaultMode))
                if source is not None:
                    cleanups.append(lambda: api.cf.CFRunLoopSourceInvalidate(source))
                if self._tap is not None:
                    cleanups.append(lambda: api.cf.CFMachPortInvalidate(self._tap))
                for cleanup in cleanups:
                    try:
                        cleanup()
                    except BaseException as exc:
                        self._error = self._error or exc
                        _LOG.exception("Cannot remove macOS hotkey resources")
            with self._lock:
                self._runloop = None
                self._tap = None
                try:
                    self._notify(self._state.reset())
                except BaseException as exc:
                    self._error = self._error or exc
                    _LOG.exception("Global hotkey release callback failed during shutdown")
            self._ready.set()
