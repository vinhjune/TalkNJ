"""Windows clipboard, foreground-safe Unicode input, and non-suppressing hotkeys.

SendInput cannot atomically bind input to an HWND. Insertion therefore checks the
original foreground window before every Unicode scalar, but a desktop focus race
between that check and delivery remains unavoidable. No function activates a window.
Hotkey callbacks execute on the hook thread and must return promptly.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from collections.abc import Callable, Collection
from functools import lru_cache

__all__ = ["HotkeyListener", "copy_text", "foreground_window", "type_text", "validate_hotkey"]

_LOG = logging.getLogger(__name__)
_IS_WINDOWS = os.name == "nt"
_DWORD = ctypes.c_uint32
_WORD = ctypes.c_uint16
_LONG = ctypes.c_int32
_UINT = ctypes.c_uint32
_BOOL = ctypes.c_int32
_HANDLE = ctypes.c_void_p
_ULONG_PTR = ctypes.c_size_t
_LPARAM = ctypes.c_ssize_t
_LRESULT = ctypes.c_ssize_t


class _POINT(ctypes.Structure):
    _fields_ = [("x", _LONG), ("y", _LONG)]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", _HANDLE), ("message", _UINT), ("wParam", _ULONG_PTR),
        ("lParam", _LPARAM), ("time", _DWORD), ("pt", _POINT),
        ("lPrivate", _DWORD),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", _LONG), ("dy", _LONG), ("mouseData", _DWORD),
        ("dwFlags", _DWORD), ("time", _DWORD), ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", _WORD), ("wScan", _WORD), ("dwFlags", _DWORD),
        ("time", _DWORD), ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", _DWORD), ("wParamL", _WORD), ("wParamH", _WORD)]


class _INPUTUNION(ctypes.Union):
    # MOUSEINPUT is essential: a keyboard-only union has the wrong Win64 size.
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", _DWORD), ("data", _INPUTUNION)]


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", _DWORD), ("scanCode", _DWORD), ("flags", _DWORD),
        ("time", _DWORD), ("dwExtraInfo", _ULONG_PTR),
    ]


_HOOKPROC = (
    ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, _ULONG_PTR, _LPARAM)
    if _IS_WINDOWS else None
)
_MODIFIERS = {
    "ctrl": (0xA2, 0xA3),
    "alt": (0xA4, 0xA5),
    "shift": (0xA0, 0xA1),
    "win": (0x5B, 0x5C),
}
_MODIFIER_VKS = tuple(vk for group in _MODIFIERS.values() for vk in group)
_KEY_VKS = {"space": 0x20}
_KEY_VKS.update({chr(code).lower(): code for code in range(0x41, 0x5B)})
_KEY_VKS.update({str(number): 0x30 + number for number in range(10)})
_KEY_VKS.update({f"f{number}": 0x6F + number for number in range(1, 13)})
_WM_QUIT = 0x0012
_WM_TIMER = 0x0113
_KEYDOWN_MESSAGES = (0x0100, 0x0104)
_KEYUP_MESSAGES = (0x0101, 0x0105)
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004


def validate_hotkey(chord: str) -> str:
    """Validate and canonicalize one modifier chord without reserving any keys."""
    if not isinstance(chord, str):
        raise TypeError("The hotkey must be text, for example ctrl+alt+space.")
    tokens = [part.strip().lower() for part in chord.split("+")]
    if not all(tokens) or len(tokens) != len(set(tokens)):
        raise ValueError("A hotkey cannot contain empty or repeated members.")
    modifiers = [token for token in tokens if token in _MODIFIERS]
    keys = [token for token in tokens if token not in _MODIFIERS]
    if not modifiers or len(keys) != 1 or keys[0] not in _KEY_VKS:
        raise ValueError(
            "Choose at least one of ctrl, alt, shift, win and exactly one letter, "
            "number, space, or F1–F12 key."
        )
    return "+".join([name for name in _MODIFIERS if name in modifiers] + keys)


class _WindowsAPI:
    """All pointer-sized Windows signatures live in one place."""

    def __init__(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        def bind(library: object, name: str, result: object, *args: object) -> None:
            function = getattr(library, name)
            function.argtypes = list(args)
            function.restype = result
            setattr(self, name, function)

        bind(user32, "GetForegroundWindow", _HANDLE)
        bind(user32, "IsWindow", _BOOL, _HANDLE)
        bind(user32, "GetWindowThreadProcessId", _DWORD, _HANDLE, ctypes.POINTER(_DWORD))
        bind(user32, "GetAsyncKeyState", ctypes.c_int16, ctypes.c_int)
        bind(user32, "SendInput", _UINT, _UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
        bind(user32, "OpenClipboard", _BOOL, _HANDLE)
        bind(user32, "EmptyClipboard", _BOOL)
        bind(user32, "SetClipboardData", _HANDLE, _UINT, _HANDLE)
        bind(user32, "CloseClipboard", _BOOL)
        bind(user32, "CreateWindowExW", _HANDLE, _DWORD, ctypes.c_wchar_p,
             ctypes.c_wchar_p, _DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
             ctypes.c_int, _HANDLE, _HANDLE, _HANDLE, _HANDLE)
        bind(user32, "DestroyWindow", _BOOL, _HANDLE)
        bind(user32, "SetWindowsHookExW", _HANDLE, ctypes.c_int, _HOOKPROC, _HANDLE, _DWORD)
        bind(user32, "UnhookWindowsHookEx", _BOOL, _HANDLE)
        bind(user32, "CallNextHookEx", _LRESULT, _HANDLE, ctypes.c_int, _ULONG_PTR, _LPARAM)
        bind(user32, "PeekMessageW", _BOOL, ctypes.POINTER(_MSG), _HANDLE, _UINT, _UINT, _UINT)
        bind(user32, "GetMessageW", _BOOL, ctypes.POINTER(_MSG), _HANDLE, _UINT, _UINT)
        bind(user32, "TranslateMessage", _BOOL, ctypes.POINTER(_MSG))
        bind(user32, "DispatchMessageW", _LRESULT, ctypes.POINTER(_MSG))
        bind(user32, "PostThreadMessageW", _BOOL, _DWORD, _UINT, _ULONG_PTR, _LPARAM)
        bind(user32, "SetTimer", _ULONG_PTR, _HANDLE, _ULONG_PTR, _UINT, _HANDLE)
        bind(user32, "KillTimer", _BOOL, _HANDLE, _ULONG_PTR)
        bind(kernel32, "GetModuleHandleW", _HANDLE, ctypes.c_wchar_p)
        bind(kernel32, "GetCurrentThreadId", _DWORD)
        bind(kernel32, "GlobalAlloc", _HANDLE, _UINT, ctypes.c_size_t)
        bind(kernel32, "GlobalLock", _HANDLE, _HANDLE)
        bind(kernel32, "GlobalUnlock", _BOOL, _HANDLE)
        bind(kernel32, "GlobalFree", _HANDLE, _HANDLE)


@lru_cache(maxsize=1)
def _windows_api() -> _WindowsAPI:
    return _WindowsAPI()


def _get_api() -> _WindowsAPI:
    if not _IS_WINDOWS:
        raise RuntimeError("Windows 10 or 11 is required for native keyboard and clipboard access.")
    return _windows_api()


def _native_error(message: str, code: int | None = None) -> RuntimeError:
    if code is None:
        code = ctypes.get_last_error()
    detail = ctypes.FormatError(code).strip() if code else "Windows did not provide an error code."
    return RuntimeError(f"{message} {detail} (Windows error {code})")


def _text_bytes(text: str) -> bytes:
    if not isinstance(text, str):
        raise TypeError("The transcript must be text.")
    if "\x00" in text:
        raise ValueError("The transcript cannot contain NUL characters.")
    try:
        return text.encode("utf-16-le")
    except UnicodeEncodeError as exc:
        raise ValueError("The transcript contains an invalid unpaired Unicode surrogate.") from exc


def foreground_window() -> int:
    """Return the current foreground HWND, or zero if Windows has none."""
    return int(_get_api().GetForegroundWindow() or 0)


def copy_text(text: str) -> None:
    """Own a CF_UNICODETEXT allocation; Windows keeps usable text after return."""
    payload = _text_bytes(text) + b"\x00\x00"
    api = _get_api()
    memory = api.GlobalAlloc(0x0002, len(payload))  # GMEM_MOVEABLE
    if not memory:
        raise _native_error("Cannot allocate the Unicode clipboard buffer.")
    window = None
    opened = False
    try:
        pointer = api.GlobalLock(memory)
        if not pointer:
            raise _native_error("Cannot lock the Unicode clipboard buffer.")
        try:
            ctypes.memmove(pointer, payload, len(payload))
        finally:
            ctypes.set_last_error(0)
            if not api.GlobalUnlock(memory) and ctypes.get_last_error():
                raise _native_error("Cannot unlock the Unicode clipboard buffer.")
        # A real owner is required by EmptyClipboard/SetClipboardData. This
        # message-only STATIC window is invisible and never changes focus.
        window = api.CreateWindowExW(
            0, "STATIC", "TalkNJ clipboard", 0, 0, 0, 0, 0,
            _HANDLE(-3), None, api.GetModuleHandleW(None), None,
        )
        if not window:
            raise _native_error("Cannot create a clipboard owner window.")
        deadline = time.monotonic() + 0.75
        while not api.OpenClipboard(window):
            if time.monotonic() >= deadline:
                raise _native_error("The clipboard is busy. Close other clipboard tools and try again.")
            time.sleep(0.025)
        opened = True
        if not api.EmptyClipboard():
            raise _native_error("Cannot empty the clipboard before copying the transcript.")
        if not api.SetClipboardData(13, memory):  # CF_UNICODETEXT
            raise _native_error("Cannot place the Unicode transcript on the clipboard.")
        memory = None  # Ownership was transferred; never free this allocation.
    finally:
        # Cleanup failures are logged without masking a useful primary error.
        if opened and not api.CloseClipboard():
            _LOG.error("Cannot close the clipboard: %s", _native_error("CloseClipboard failed."))
        if window and not api.DestroyWindow(window):
            _LOG.error("Cannot destroy the clipboard owner: %s", _native_error("DestroyWindow failed."))
        if memory and api.GlobalFree(memory):
            _LOG.error("Cannot free the clipboard buffer: %s", _native_error("GlobalFree failed."))


def _validate_target(api: _WindowsAPI, target: int, process_id: int | None = None) -> int:
    if not api.IsWindow(target):
        raise RuntimeError("The original target window no longer exists. The transcript remains copied.")
    if int(api.GetForegroundWindow() or 0) != target:
        raise RuntimeError("The foreground window changed. Nothing further was typed; the transcript remains copied.")
    process = _DWORD()
    if not api.GetWindowThreadProcessId(target, ctypes.byref(process)):
        raise _native_error("Cannot identify the original target window.")
    if process.value == os.getpid():
        raise RuntimeError("Typing into TalkNJ itself is disabled. The transcript remains copied.")
    if process_id is not None and process.value != process_id:
        raise RuntimeError("The original window handle was reused by another process. The transcript remains copied.")
    return process.value


def _modifiers_down(api: _WindowsAPI) -> bool:
    return any(api.GetAsyncKeyState(vk) & 0x8000 for vk in _MODIFIER_VKS)


def type_text(target: int, text: str) -> None:
    """Insert UTF-16 without pasting, activating windows, or retrying partial input."""
    encoded = _text_bytes(text)
    if isinstance(target, bool) or not isinstance(target, int) or not 0 < target < 1 << (8 * ctypes.sizeof(_HANDLE)):
        raise ValueError("The target must be a nonzero Windows window handle.")
    api = _get_api()
    deadline = time.monotonic() + 3.0
    process_id: int | None = None
    while True:
        process_id = _validate_target(api, target, process_id)
        if not _modifiers_down(api):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Release Ctrl, Alt, Shift, and Windows keys before typing. The transcript remains copied.")
        time.sleep(0.01)
    # Reuse one correctly sized INPUT array. A supplementary-plane scalar's
    # high/low surrogate down/up events are always submitted together.
    inputs = (_INPUT * 4)()
    offset = 0
    while offset < len(encoded):
        first = int.from_bytes(encoded[offset:offset + 2], "little")
        units = 2 if 0xD800 <= first <= 0xDBFF else 1
        count = units * 2
        for unit_index in range(units):
            start = offset + unit_index * 2
            unit = int.from_bytes(encoded[start:start + 2], "little")
            for release in (0, 1):
                event = inputs[unit_index * 2 + release]
                event.type = 1  # INPUT_KEYBOARD
                event.ki.wVk = 0
                event.ki.wScan = unit
                event.ki.dwFlags = _KEYEVENTF_UNICODE | (_KEYEVENTF_KEYUP if release else 0)
        _validate_target(api, target, process_id)
        if _modifiers_down(api):
            raise RuntimeError("A modifier key was pressed during typing. Insertion stopped; the transcript remains copied.")
        ctypes.set_last_error(0)
        accepted = api.SendInput(count, inputs, ctypes.sizeof(_INPUT))
        if accepted != count:
            error = ctypes.get_last_error()
            cleanup_detail = ""
            if 0 < accepted < count and accepted % 2:
                # A partial call can leave VK_PACKET down. Release only; never
                # retry text, which could duplicate content or reach a new app.
                release = inputs[accepted]
                if api.SendInput(1, ctypes.byref(release), ctypes.sizeof(_INPUT)) != 1:
                    cleanup_detail = " Windows also refused the packet-key release."
            raise _native_error(
                f"Windows accepted {accepted} of {count} input events. Some text may already be inserted. "
                "The target may run as administrator or block simulated input (UIPI); "
                "use the copied transcript to paste manually." + cleanup_detail,
                error,
            )
        offset += units * 2
    _validate_target(api, target, process_id)


class _ChordState:
    """Small pure state machine, shared by hook events and lost-keyup recovery."""

    def __init__(self, chord: str) -> None:
        tokens = validate_hotkey(chord).split("+")
        self.key = _KEY_VKS[tokens[-1]]
        self.groups = tuple(_MODIFIERS[token] for token in tokens[:-1])
        self.watched = tuple(dict.fromkeys((self.key, *_MODIFIER_VKS)))
        self.active = False

    def matches(self, down: Collection[int]) -> bool:
        return self.key in down and all(any(vk in down for vk in group) for group in self.groups)

    def update(self, down: Collection[int], *, allow_press: bool = True) -> int:
        matches = self.matches(down)
        if self.active and not matches:
            self.active = False
            return -1
        if not self.active and matches and allow_press:
            self.active = True
            return 1
        return 0

    def reset(self) -> int:
        if self.active:
            self.active = False
            return -1
        return 0


def _event_vk(event: _KBDLLHOOKSTRUCT) -> int:
    """Normalize generic modifier codes without conflating left/right releases."""
    if event.vkCode == 0x10:
        return 0xA1 if event.scanCode == 0x36 else 0xA0
    if event.vkCode == 0x11:
        return 0xA3 if event.flags & 1 else 0xA2
    if event.vkCode == 0x12:
        return 0xA5 if event.flags & 1 else 0xA4
    return int(event.vkCode)


class HotkeyListener:
    """A global WH_KEYBOARD_LL hook that always forwards ordinary key events.

    Either side of each modifier matches, additional modifiers are permitted,
    and autorepeat cannot retrigger an already-active gesture. A 50 ms timer
    reconciles physical state to recover missed releases and desktop changes.
    """

    def __init__(self, chord: str, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        self.chord = validate_hotkey(chord)
        if not callable(on_press) or not callable(on_release):
            raise TypeError("Hotkey press and release callbacks must be callable.")
        self._on_press = on_press
        self._on_release = on_release
        self._state = _ChordState(self.chord)
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._error: BaseException | None = None

    def start(self) -> None:
        _get_api()  # Fail clearly on unsupported platforms, before creating a thread.
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self._stopping.is_set():
                    raise RuntimeError("The previous hotkey listener is still stopping.")
                return
            self._state.reset()
            self._ready.clear()
            self._stopping.clear()
            self._error = None
            self._thread_id = 0
            self._thread = threading.Thread(target=self._run, name="TalkNJ hotkey", daemon=True)
            self._thread.start()
        if not self._ready.wait(5.0):
            self._stopping.set()
            raise RuntimeError("Windows did not initialize the global hotkey listener in time.")
        if self._error is not None:
            raise RuntimeError(f"Cannot start the global hotkey listener: {self._error}") from self._error

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            if thread is None:
                return
            self._stopping.set()
            if thread.is_alive() and self._thread_id:
                api = _get_api()
                if not api.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0):
                    if thread.is_alive():
                        raise _native_error("Cannot stop the global hotkey listener.")
        if thread is threading.current_thread():
            return
        thread.join(5.0)
        if thread.is_alive():
            raise RuntimeError("The hotkey hook thread did not stop. Ensure callbacks do not block.")
        with self._lock:
            if self._thread is thread:
                self._thread = None
        if self._error is not None:
            raise RuntimeError(f"The global hotkey listener failed: {self._error}") from self._error

    def _notify(self, transition: int) -> None:
        if transition > 0:
            self._on_press()
        elif transition < 0:
            self._on_release()

    def _snapshot(self, api: _WindowsAPI) -> set[int]:
        return {vk for vk in self._state.watched if api.GetAsyncKeyState(vk) & 0x8000}

    def _run(self) -> None:
        hook = None
        timer = 0
        api = None
        try:
            api = _get_api()
            self._thread_id = int(api.GetCurrentThreadId())
            message = _MSG()
            api.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)

            def callback(code: int, wparam: int, lparam: int) -> int:
                try:
                    if code >= 0 and not self._stopping.is_set():
                        if wparam in _KEYDOWN_MESSAGES or wparam in _KEYUP_MESSAGES:
                            event = ctypes.cast(lparam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                            vk = _event_vk(event)
                            down = self._snapshot(api)
                            # The current event precedes the GetAsyncKeyState
                            # update; override its one physical side explicitly.
                            if wparam in _KEYDOWN_MESSAGES:
                                down.add(vk)
                            else:
                                down.discard(vk)
                            self._notify(self._state.update(down))
                except BaseException as exc:
                    self._error = exc
                    self._stopping.set()
                    _LOG.exception("Global hotkey callback failed")
                # Never swallow keys, including when user callbacks fail.
                return int(api.CallNextHookEx(hook, code, wparam, lparam))

            if _HOOKPROC is None:
                raise RuntimeError("Windows is required for the keyboard hook.")
            hook_callback = _HOOKPROC(callback)  # Keep alive until UnhookWindowsHookEx.
            hook = api.SetWindowsHookExW(13, hook_callback, api.GetModuleHandleW(None), 0)
            if not hook:
                raise _native_error("Cannot install the global keyboard hook.")
            timer = api.SetTimer(None, 0, 50, None)
            if not timer:
                raise _native_error("Cannot initialize hotkey release recovery.")
            self._ready.set()
            while not self._stopping.is_set():
                result = api.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result == -1:
                    raise _native_error("The global keyboard message loop failed.")
                if result == 0:
                    break
                if message.message == _WM_TIMER and message.wParam == timer:
                    self._notify(self._state.update(self._snapshot(api), allow_press=False))
                else:
                    api.TranslateMessage(ctypes.byref(message))
                    api.DispatchMessageW(ctypes.byref(message))
        except BaseException as exc:
            self._error = exc
            _LOG.exception("Global hotkey listener failed")
        finally:
            self._stopping.set()
            if api is not None:
                if timer and not api.KillTimer(None, timer):
                    self._error = self._error or _native_error("Cannot remove the hotkey recovery timer.")
                    _LOG.error("Cannot remove the hotkey recovery timer")
                if hook and not api.UnhookWindowsHookEx(hook):
                    self._error = self._error or _native_error("Cannot remove the global keyboard hook.")
                    _LOG.error("Cannot remove the global keyboard hook")
            try:
                self._notify(self._state.reset())
            except BaseException as exc:
                self._error = self._error or exc
                _LOG.exception("Global hotkey release callback failed during shutdown")
            self._ready.set()
