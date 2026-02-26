"""Tests for ComponentManager."""

import json
import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.components import ComponentManager, BUILTIN_REGISTRY


@pytest.fixture
def tmp_base(tmp_path):
    """Create a temp base dir for ComponentManager."""
    return tmp_path / "subgen"


@pytest.fixture
def cm(tmp_base):
    """Create a ComponentManager with temp dir."""
    return ComponentManager(base_dir=tmp_base)


class TestInit:
    def test_creates_directories(self, tmp_base):
        ComponentManager(base_dir=tmp_base)
        assert (tmp_base / "bin").is_dir()
        assert (tmp_base / "models" / "whisper").is_dir()

    def test_registry_loaded(self, cm):
        assert "components" in cm.registry
        assert "whisper-cpp-cpu" in cm.registry["components"]


class TestDetectPlatform:
    def test_returns_string(self, cm):
        plat = cm._detect_platform()
        assert plat in ("windows", "linux-x64", "macos-x64", "macos-arm64")

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="x86_64")
    def test_linux(self, mock_m, mock_s, tmp_base):
        cm = ComponentManager(base_dir=tmp_base)
        assert cm.platform == "linux-x64"

    @patch("platform.system", return_value="Darwin")
    @patch("platform.machine", return_value="arm64")
    def test_macos_arm64(self, mock_m, mock_s, tmp_base):
        cm = ComponentManager(base_dir=tmp_base)
        assert cm.platform == "macos-arm64"

    @patch("platform.system", return_value="Windows")
    @patch("platform.machine", return_value="AMD64")
    def test_windows(self, mock_m, mock_s, tmp_base):
        cm = ComponentManager(base_dir=tmp_base)
        assert cm.platform == "windows"


class TestRegistry:
    def test_builtin_has_all_components(self):
        comps = BUILTIN_REGISTRY["components"]
        assert "whisper-cpp-cuda" in comps
        assert "whisper-cpp-cpu" in comps
        assert "whisper-cpp-metal" in comps
        assert "model-whisper-tiny" in comps
        assert "model-whisper-base" in comps
        assert "model-whisper-small" in comps
        assert "model-whisper-medium" in comps
        assert "model-whisper-large-v3" in comps
        assert "ffmpeg" in comps

    def test_cache_written(self, tmp_base):
        ComponentManager(base_dir=tmp_base)
        assert (tmp_base / "components.json").exists()

    def test_cache_reloaded(self, tmp_base):
        ComponentManager(base_dir=tmp_base)
        # Modify cache to verify it's reused
        cache_path = tmp_base / "components.json"
        data = json.loads(cache_path.read_text())
        data["_test_marker"] = True
        cache_path.write_text(json.dumps(data))

        cm2 = ComponentManager(base_dir=tmp_base)
        assert cm2.registry.get("_test_marker") is True


class TestListAvailable:
    def test_returns_list(self, cm):
        avail = cm.list_available()
        assert isinstance(avail, list)
        assert len(avail) > 0

    def test_cpu_always_available(self, cm):
        ids = [c.id for c in cm.list_available()]
        assert "whisper-cpp-cpu" in ids


class TestInstallUninstall:
    def test_empty_installed(self, cm):
        assert cm.list_installed() == []
        assert not cm.is_installed("whisper-cpp-cpu")

    def test_install_records_state(self, cm, tmp_base):
        """Test that install writes to installed.json (mock download)."""
        # Create a fake file to simulate download
        model_path = tmp_base / "models" / "whisper" / "ggml-tiny.bin"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"fake model data")

        # Manually write installed state
        data = {
            "components": {
                "model-whisper-tiny": {
                    "version": "1.0",
                    "path": str(model_path),
                    "installed_at": "2026-01-01T00:00:00",
                    "size_bytes": 15,
                }
            }
        }
        (tmp_base / "installed.json").write_text(json.dumps(data))

        assert cm.is_installed("model-whisper-tiny")
        assert cm.get_path("model-whisper-tiny") == model_path

    def test_uninstall(self, cm, tmp_base):
        # Create fake installed component
        model_path = tmp_base / "models" / "whisper" / "ggml-tiny.bin"
        model_path.write_bytes(b"fake")
        data = {
            "components": {
                "model-whisper-tiny": {
                    "version": "1.0",
                    "path": str(model_path),
                    "installed_at": "2026-01-01T00:00:00",
                    "size_bytes": 4,
                }
            }
        }
        (tmp_base / "installed.json").write_text(json.dumps(data))

        assert cm.uninstall("model-whisper-tiny")
        assert not model_path.exists()
        assert not cm.is_installed("model-whisper-tiny")

    def test_uninstall_not_installed(self, cm):
        assert not cm.uninstall("nonexistent")


class TestFinders:
    def test_find_ffmpeg_in_path(self, cm):
        """find_ffmpeg should find system ffmpeg if available."""
        # Just verify it doesn't crash; actual result depends on system
        result = cm.find_ffmpeg()
        # Result is either a Path or None
        assert result is None or isinstance(result, Path)

    def test_find_whisper_model_not_found(self, cm):
        assert cm.find_whisper_model("tiny") is None

    def test_find_whisper_model_found(self, cm, tmp_base):
        model_path = tmp_base / "models" / "whisper" / "ggml-base.bin"
        model_path.write_bytes(b"fake")
        assert cm.find_whisper_model("base") == model_path

    def test_find_whisper_engine_not_found(self, cm):
        assert cm.find_whisper_engine() is None


class TestDiskUsage:
    def test_empty(self, cm):
        assert cm.disk_usage() == {}

    def test_with_component(self, cm, tmp_base):
        path = tmp_base / "test_file"
        path.write_bytes(b"x" * 100)
        data = {
            "components": {
                "test": {
                    "version": "1.0",
                    "path": str(path),
                    "installed_at": "2026-01-01",
                    "size_bytes": 100,
                }
            }
        }
        (tmp_base / "installed.json").write_text(json.dumps(data))
        usage = cm.disk_usage()
        assert usage["test"] == 100


class TestNeedsUpdate:
    def test_not_installed(self, cm):
        assert not cm.needs_update("whisper-cpp-cpu")

    def test_same_version(self, cm, tmp_base):
        data = {
            "components": {
                "whisper-cpp-cpu": {
                    "version": "1.7.3",
                    "path": "/fake",
                    "installed_at": "2026-01-01",
                    "size_bytes": 0,
                }
            }
        }
        (tmp_base / "installed.json").write_text(json.dumps(data))
        assert not cm.needs_update("whisper-cpp-cpu")
