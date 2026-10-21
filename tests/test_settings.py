import json
from pathlib import Path

from talknj.settings import Settings, load_settings, save_settings


def test_preferences_round_trip_with_unicode_and_imports(tmp_path):
    path = tmp_path / "config" / "settings.json"
    settings = Settings(model_root=str(tmp_path / "Mô hình"), language="vi", output_mode="type",
                        hotkey_mode="toggle", imported_models=[str(tmp_path / "existing")],
                        microphone="Microphone tiếng Việt [Windows WASAPI]")
    save_settings(settings, path)
    restored, warning = load_settings(path)
    assert restored == settings
    assert warning == ""


def test_corrupt_file_is_preserved_for_recovery(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"model_root":', encoding="utf-8")
    original = path.read_bytes()
    settings, warning = load_settings(path)
    assert warning
    assert settings.output_mode == "clipboard"
    assert path.read_bytes() == original


def test_unknown_values_cannot_enable_automatic_typing(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"output_mode": "execute", "language": "xx", "hotkey_mode": "repeat"}), encoding="utf-8")
    settings, warning = load_settings(path)
    assert (settings.output_mode, settings.language, settings.hotkey_mode) == ("clipboard", "en", "hold")


def test_invalid_import_list_does_not_reach_model_scanner(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"imported_models": [42]}), encoding="utf-8")
    settings, warning = load_settings(path)
    assert warning
    assert settings.imported_models == []


def test_save_failure_leaves_existing_preferences_intact(tmp_path, monkeypatch):
    import os
    import pytest

    path = tmp_path / "settings.json"
    save_settings(Settings(language="vi"), path)
    original = path.read_bytes()

    def cannot_replace(source, destination):
        raise PermissionError("settings locked")

    monkeypatch.setattr(os, "replace", cannot_replace)
    with pytest.raises(PermissionError):
        save_settings(Settings(language="en"), path)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [Path(path)]
