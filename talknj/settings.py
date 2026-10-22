"""Small, atomic, per-user settings. Audio and transcripts are never saved here."""

from dataclasses import asdict, dataclass, field, fields
import json
import os
from pathlib import Path
import sys
import tempfile


def data_directory() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TalkNJ"
    return _legacy_data_directory()


def _legacy_data_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return base / "TalkNJ"


@dataclass
class Settings:
    model_root: str = field(default_factory=lambda: str(data_directory() / "models"))
    model_path: str = ""
    imported_models: list[str] = field(default_factory=list)
    language: str = "en"
    output_mode: str = "clipboard"
    hotkey: str = "ctrl+alt+space"
    hotkey_mode: str = "hold"
    microphone: str | None = None


def load_settings(path: Path | None = None) -> tuple[Settings, str]:
    default_path = path is None
    path = path or data_directory() / "settings.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Expected a settings object")
        defaults = Settings()
        allowed = {f.name for f in fields(Settings)}
        values = {k: v for k, v in raw.items() if k in allowed}
        for key in ("model_root", "model_path", "language", "output_mode", "hotkey", "hotkey_mode"):
            if key in values and not isinstance(values[key], str):
                raise ValueError(f"Invalid {key}")
        if not values.get("model_root", defaults.model_root).strip():
            raise ValueError("Model storage cannot be empty")
        if "imported_models" in values and (
            not isinstance(values["imported_models"], list)
            or not all(isinstance(p, str) for p in values["imported_models"])
        ):
            raise ValueError("Invalid imported model folders")
        mic = values.get("microphone")
        if mic is not None and (not isinstance(mic, str) or not mic.strip()):
            raise ValueError("Invalid microphone")
        settings = Settings(**values)
        if settings.language not in ("en", "vi"):
            settings.language = defaults.language
        if settings.output_mode not in ("clipboard", "type"):
            settings.output_mode = defaults.output_mode
        if settings.hotkey_mode not in ("hold", "toggle"):
            settings.hotkey_mode = defaults.hotkey_mode
        return settings, ""
    except FileNotFoundError:
        if default_path and sys.platform == "darwin":
            legacy = _legacy_data_directory() / "settings.json"
            if legacy.is_file():
                settings, warning = load_settings(legacy)
                if warning:
                    return settings, warning
                return settings, (
                    f"Existing settings loaded from {legacy}. Future saves use {path}; "
                    "existing model folders have not been moved."
                )
        return Settings(), ""
    except (OSError, ValueError, TypeError) as exc:
        return Settings(), f"Could not read settings; defaults loaded. Original file kept. {exc}"


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or data_directory() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(asdict(settings), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
