import json
from pathlib import Path

from talknj.settings import Settings, load_settings, save_settings


def test_preferences_round_trip_with_unicode_and_imports(tmp_path):
    path = tmp_path / "config" / "settings.json"
    settings = Settings(model_root=str(tmp_path / "Mô hình"), language="vi",
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
    assert settings == Settings()
    assert path.read_bytes() == original


def test_unknown_language_and_activation_mode_use_supported_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "xx", "hotkey_mode": "repeat"}), encoding="utf-8")
    settings, warning = load_settings(path)
    assert (settings.language, settings.hotkey_mode) == ("en", "hold")


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


def test_windows_data_directory_keeps_localappdata(tmp_path, monkeypatch):
    from talknj import settings as storage

    monkeypatch.setattr(storage.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert storage.data_directory() == tmp_path / "local" / "TalkNJ"
    assert Settings().model_root == str(tmp_path / "local" / "TalkNJ" / "models")


def test_macos_data_directory_ignores_windows_environment(tmp_path, monkeypatch):
    from talknj import settings as storage

    monkeypatch.setattr(storage.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "windows"))
    expected = tmp_path / "Library" / "Application Support" / "TalkNJ"
    assert storage.data_directory() == expected
    assert Settings().model_root == str(expected / "models")


def test_macos_legacy_preferences_preserve_external_models_without_moving_files(tmp_path, monkeypatch):
    from talknj import settings as storage

    monkeypatch.setattr(storage.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    legacy = tmp_path / "AppData" / "Local" / "TalkNJ" / "settings.json"
    existing = Settings(model_root=str(tmp_path / "external models"), model_path="/Volumes/Voice/model",
                        imported_models=["/Volumes/Archive/weights"], hotkey="win+shift+f2",
                        language="vi", hotkey_mode="toggle")
    save_settings(existing, legacy)
    original = legacy.read_bytes()
    restored, warning = load_settings()
    assert restored == existing
    assert "have not been moved" in warning
    current = storage.data_directory() / "settings.json"
    assert not current.exists()
    assert legacy.read_bytes() == original
    save_settings(restored)
    assert current.exists()
    assert load_settings() == (existing, "")
    assert legacy.read_bytes() == original
    assert not Path(existing.model_root).exists()


def test_existing_macos_preferences_take_precedence_over_legacy(tmp_path, monkeypatch):
    from talknj import settings as storage

    monkeypatch.setattr(storage.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "legacy"))
    save_settings(Settings(language="vi"), tmp_path / "legacy" / "TalkNJ" / "settings.json")
    current = Settings(hotkey="win+f3")
    save_settings(current)
    assert load_settings() == (current, "")


def test_corrupt_macos_legacy_preferences_are_not_rewritten_or_migrated(tmp_path, monkeypatch):
    from talknj import settings as storage

    monkeypatch.setattr(storage.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "legacy"))
    legacy = tmp_path / "legacy" / "TalkNJ" / "settings.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"model_root":', encoding="utf-8")
    restored, warning = load_settings()
    assert warning
    assert restored == Settings()
    assert legacy.read_text(encoding="utf-8") == '{"model_root":'
    assert not (storage.data_directory() / "settings.json").exists()


def test_explicit_missing_settings_path_never_probes_legacy(tmp_path, monkeypatch):
    from talknj import settings as storage

    monkeypatch.setattr(storage.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "legacy"))
    save_settings(Settings(language="vi"), tmp_path / "legacy" / "TalkNJ" / "settings.json")
    assert load_settings(tmp_path / "explicit.json") == (Settings(), "")


def test_legacy_delivery_preference_does_not_discard_other_saved_settings(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"output_mode": "clipboard", "language": "vi",
                                "hotkey": "ctrl+f2", "hotkey_mode": "toggle"}), encoding="utf-8")
    restored, warning = load_settings(path)
    assert not warning
    assert (restored.language, restored.hotkey, restored.hotkey_mode) == ("vi", "ctrl+f2", "toggle")
    save_settings(restored, path)
    assert "output_mode" not in json.loads(path.read_text(encoding="utf-8"))
