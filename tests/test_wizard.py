"""Tests for setup wizard configuration output."""

import sys
import types

from src.hardware import HardwareInfo
from src import wizard


class _FakeComponentManager:
    def is_installed(self, _comp_id):
        return True

    def install(self, _comp_id):
        return None

    def find_ffmpeg(self):
        return "/usr/bin/ffmpeg"


def _patch_common(monkeypatch, hw: HardwareInfo, choices):
    import src.components as components

    monkeypatch.setattr(components, "ComponentManager", _FakeComponentManager)
    monkeypatch.setattr(wizard, "print_header", lambda: None)
    monkeypatch.setattr(wizard, "print_hardware_summary", lambda _hw: None)
    monkeypatch.setattr(wizard, "detect_hardware", lambda: hw)
    monkeypatch.setattr(wizard, "recommend_whisper_config", lambda _hw: ("local", "cpu", "small"))
    monkeypatch.setattr(wizard, "get_install_instructions", lambda _hw: None)
    monkeypatch.setattr(wizard, "is_bundled", lambda: False)
    monkeypatch.setattr(wizard, "get_api_key", lambda _info: "dummy-key")

    choice_iter = iter(choices)
    monkeypatch.setattr(wizard, "get_choice", lambda _prompt, _max: next(choice_iter))

    # Step 4 prompts: target language, bilingual, format
    user_inputs = iter(["zh", "n", "srt"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(user_inputs))


def test_wizard_writes_translation_config(monkeypatch):
    hw = HardwareInfo(
        platform="linux",
        arch="x86_64",
        is_apple_silicon=False,
        has_nvidia_gpu=True,
        nvidia_gpu_name="RTX",
        nvidia_vram_gb=8.0,
        has_cuda=True,
        cuda_version="12.1",
    )
    # Whisper: openai(5), LLM: openai(4)
    _patch_common(monkeypatch, hw, choices=[5, 4])

    config = wizard.run_setup_wizard()

    assert "translation" in config
    assert "llm" not in config
    assert config["translation"]["provider"] == "openai"
    assert config["translation"]["api_key"] == "dummy-key"
    assert config["translation"]["model"] == "gpt-4o-mini"


def test_wizard_local_no_nvidia_uses_cpu_and_smaller_model(monkeypatch):
    hw = HardwareInfo(
        platform="linux",
        arch="x86_64",
        is_apple_silicon=False,
        has_nvidia_gpu=False,
        nvidia_gpu_name=None,
        nvidia_vram_gb=None,
        has_cuda=False,
        cuda_version=None,
    )
    # Make faster_whisper import succeed.
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace())
    # Whisper: local(1), LLM: openai(4)
    _patch_common(monkeypatch, hw, choices=[1, 4])

    config = wizard.run_setup_wizard()

    assert config["whisper"]["device"] == "cpu"
    assert config["whisper"]["local_model"] == "small"
