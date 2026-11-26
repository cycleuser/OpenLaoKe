from __future__ import annotations

import json

from openlaoke.types.providers import ProviderConfig, ProviderType
from openlaoke.utils import config as config_module


def test_custom_provider_roundtrips(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")

    config = config_module.AppConfig()
    config.providers.providers["my-custom"] = ProviderConfig(
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        api_key="secret",
        base_url="https://example.test/v1",
        default_model="model-a",
        models=["model-a", "model-b"],
        model_labels={"model-a": "Model A"},
    )
    config_module.save_config(config)

    reloaded = config_module.load_config()
    provider = reloaded.providers.providers["my-custom"]
    assert provider.base_url == "https://example.test/v1"
    assert provider.default_model == "model-a"
    assert provider.models == ["model-a", "model-b"]
    assert provider.model_labels == {"model-a": "Model A"}
    assert provider.is_ready()


def test_preset_provider_roundtrips(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")

    from openlaoke.core.provider_presets import get_preset

    config = config_module.AppConfig()
    config.providers.providers["cycleuser-llm"] = get_preset("cycleuser-llm").build("secret")
    config_module.save_config(config)

    reloaded = config_module.load_config()
    provider = reloaded.providers.providers["cycleuser-llm"]
    assert provider.base_url == "https://llm.cycleuser.com/v1"
    assert provider.models == ["halogen", "halogen-master"]
    assert provider.default_model == "halogen"


def test_builtin_models_are_not_frozen_by_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")

    data = {
        "providers": {
            "providers": {
                "ollama": {
                    "api_key": "",
                    "base_url": "http://localhost:11434/v1",
                    "default_model": "stale",
                    "models": ["stale"],
                    "enabled": True,
                }
            }
        }
    }
    (tmp_path / "config.json").write_text(json.dumps(data), encoding="utf-8")

    reloaded = config_module.load_config()
    provider = reloaded.providers.providers["ollama"]
    assert "stale" not in provider.models
    assert provider.default_model != "stale"


# --------------------------------------------------------------------------- #
# rebuilding a custom provider, the accessors and the single-value helpers
# --------------------------------------------------------------------------- #
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")


def test_an_unknown_provider_type_falls_back_to_openai_compatible(tmp_path, monkeypatch) -> None:
    _isolated(tmp_path, monkeypatch)

    provider = config_module._provider_from_saved(
        "handmade", {"api_key": "k", "provider_type": "no-such-kind", "base_url": "https://x/v1"}
    )

    assert provider.provider_type == ProviderType.OPENAI_COMPATIBLE
    assert provider.base_url == "https://x/v1"


def test_a_custom_provider_without_a_type_uses_the_default(tmp_path, monkeypatch) -> None:
    _isolated(tmp_path, monkeypatch)

    provider = config_module._provider_from_saved("handmade", {"api_key": "k"})

    assert provider.provider_type == ProviderType.OPENAI_COMPATIBLE
    assert provider.models == []


def test_the_config_accessors_read_through_to_the_providers(tmp_path, monkeypatch) -> None:
    _isolated(tmp_path, monkeypatch)

    config = config_module.AppConfig()
    config.providers.providers["main"] = ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key="k",
        base_url="https://api.example.com/v1",
        default_model="m",
        models=["m"],
    )
    config.providers.active_provider = "main"
    config.providers.active_model = "m"

    assert config.get_active_provider_name() == "main"
    assert config.get_active_model() == "m"
    assert config.is_configured() is True
    assert config.get_theme() is not None
    assert config.validate_theme() is True
    assert isinstance(config.get_available_themes(), list)


def test_an_unknown_theme_does_not_validate(tmp_path, monkeypatch) -> None:
    _isolated(tmp_path, monkeypatch)

    config = config_module.AppConfig()
    config.theme = "ghost-theme"

    assert config.validate_theme() is False


def test_a_corrupt_config_file_falls_back_to_defaults(tmp_path, monkeypatch, caplog) -> None:
    _isolated(tmp_path, monkeypatch)
    (tmp_path / "config.json").write_text("{not json", encoding="utf-8")

    config = config_module.load_config()

    assert isinstance(config, config_module.AppConfig)
    assert config.first_run is True


def test_single_values_can_be_read_and_written(tmp_path, monkeypatch) -> None:
    _isolated(tmp_path, monkeypatch)

    assert config_module.get_config_value("language", "en") == "en"
    assert config_module.get_config_value("does_not_exist", "fallback") == "fallback"

    config_module.set_config_value("language", "zh")
    assert config_module.get_config_value("language") == "zh"

    # An unknown key is ignored rather than added.
    config_module.set_config_value("does_not_exist", 1)
    assert config_module.get_config_value("does_not_exist") is None


def test_marking_the_first_run_complete_persists(tmp_path, monkeypatch) -> None:
    _isolated(tmp_path, monkeypatch)

    config_module.save_config(config_module.AppConfig())
    assert config_module.load_config().first_run is True

    config_module.mark_first_run_complete()

    assert config_module.load_config().first_run is False
