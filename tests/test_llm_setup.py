"""
Tests for interactive LLM backend setup (wizard) and api_key config passthrough.

Covers:
- apply_llm_settings: shared-config application to multiple bots
- apply_llm_settings: optional base_url / api_key handling
- apply_llm_settings: dict independence (no shared mutation between bots)
- LLMRouter.from_config: api_key from swarm-config.json passed to router
- LLMRouter.from_config: api_key absent falls back to env vars
"""

import os
import copy
import json

import core.wizard
from core.wizard import apply_llm_settings, find_existing_missions, BOT_ORDER
from core.config import DEFAULT_SWARM_CONFIG
from core.llm_router import LLMRouter


def _fresh_config():
    return copy.deepcopy(DEFAULT_SWARM_CONFIG)


class TestApplyLLMSettings:
    def test_applies_to_all_bots(self):
        config = _fresh_config()
        settings = {"provider": "openai", "model": "glm-5.2",
                    "base_url": "https://ollama.com/v1"}
        apply_llm_settings(config, BOT_ORDER, settings)
        assert len(config["bots"]) == 9
        for bot in BOT_ORDER:
            assert config["bots"][bot]["provider"] == "openai"
            assert config["bots"][bot]["model"] == "glm-5.2"
            assert config["bots"][bot]["base_url"] == "https://ollama.com/v1"

    def test_applies_to_single_bot(self):
        config = _fresh_config()
        settings = {"provider": "anthropic", "model": "claude-opus-4-6"}
        apply_llm_settings(config, ["warchief"], settings)
        assert config["bots"]["warchief"]["provider"] == "anthropic"
        # Others untouched
        assert config["bots"]["aria"]["provider"] == "openai"

    def test_optional_fields_omitted_when_empty(self):
        config = _fresh_config()
        settings = {"provider": "ollama", "model": "qwen2.5:14b",
                    "base_url": "", "api_key": ""}
        apply_llm_settings(config, ["aria"], settings)
        entry = config["bots"]["aria"]
        assert "base_url" not in entry
        assert "api_key" not in entry

    def test_api_key_carried_when_present(self):
        config = _fresh_config()
        settings = {"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"}
        apply_llm_settings(config, ["warchief", "aria"], settings)
        assert config["bots"]["warchief"]["api_key"] == "sk-test"
        assert config["bots"]["aria"]["api_key"] == "sk-test"

    def test_entries_are_independent_dicts(self):
        config = _fresh_config()
        settings = {"provider": "ollama", "model": "llama3"}
        apply_llm_settings(config, ["warchief", "aria"], settings)
        config["bots"]["warchief"]["model"] = "mutated"
        assert config["bots"]["aria"]["model"] == "llama3"

    def test_creates_bots_dict_if_missing(self):
        config = {}
        settings = {"provider": "ollama", "model": "llama3"}
        apply_llm_settings(config, ["warchief"], settings)
        assert config["bots"]["warchief"]["provider"] == "ollama"


class TestMissionDiscovery:
    def test_finds_mission_dirs(self, tmp_path):
        (tmp_path / "alpha").mkdir()
        (tmp_path / "alpha" / "swarm-config.json").write_text("{}")
        (tmp_path / "beta").mkdir()  # no config — not a mission
        found = find_existing_missions(tmp_path)
        assert found == [tmp_path / "alpha"]

    def test_empty_when_none(self, tmp_path):
        assert find_existing_missions(tmp_path) == []


class TestRunMissionSetupPath:
    def test_returns_config_and_actual_config_path(self, tmp_path, monkeypatch):
        """run_mission_setup must return the path where the config was
        actually written — the mission dir may differ from the default."""
        monkeypatch.setattr(core.wizard, "interactive_setup", lambda: {
            "mission_name": "T", "objectives": "o", "scope": "s",
            "roe": "r", "dir": str(tmp_path / "my-mission"),
        })
        monkeypatch.setattr(core.wizard.Confirm, "ask",
                            staticmethod(lambda *a, **k: False))  # skip LLM cfg
        config, config_path = core.wizard.run_mission_setup(tmp_path)
        assert config_path == tmp_path / "my-mission" / "swarm-config.json"
        assert config_path.exists()
        assert json.loads(config_path.read_text())["mission_name"] == "T"
        assert config["mission_name"] == "T"


class TestFromConfigApiKey:
    def test_api_key_from_config_wins(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = _fresh_config()
        config["bots"]["warchief"]["api_key"] = "sk-config"
        router = LLMRouter.from_config("warchief", config)
        assert router.api_key == "sk-config"

    def test_env_fallback_when_no_config_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = _fresh_config()
        router = LLMRouter.from_config("warchief", config)
        assert router.api_key == "sk-env"

    def test_no_key_anywhere(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        config = _fresh_config()
        router = LLMRouter.from_config("warchief", config)
        assert router.api_key is None
