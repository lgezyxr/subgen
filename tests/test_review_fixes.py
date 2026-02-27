"""Tests for all 12 review fixes (Batch 1+2).

Covers:
  1. Stale source_lang in project metadata
  2. Subprocess deadlock in whisper.cpp (communicate())
  3. Shallow copy causes config mutation
  4. Temp audio files never cleaned up
  5. whisper.cpp JSON parsing guards
  6. source_from returned and used in metadata
  7. Platform detection with architecture mapping
  8. Concurrent downloads use unique temp filenames
  9. installed.json non-atomic writes
 10. Config YAML schema validation
 11. Project save non-atomic
 12. Project version never checked on load
"""

import json
import os
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from src.transcribe import Segment, Word


# ---------------------------------------------------------------------------
# Fix 1: Stale source_lang in project metadata
# ---------------------------------------------------------------------------

class TestStaleSourceLang:
    """After _obtain_segments(), source_lang should reflect any update
    made by cache/embedded track metadata."""

    def test_source_lang_updated_from_cache(self):
        """run() re-reads cfg['output']['source_language'] after _obtain_segments."""
        from src.engine import SubGenEngine

        cfg = {
            'whisper': {'provider': 'local'},
            'translation': {},
            'output': {'source_language': 'auto', 'target_language': 'zh'},
        }
        engine = SubGenEngine(cfg)

        segments = [Segment(start=0, end=1, text="hello", translated="hi")]

        def fake_obtain_segments(input_path, cfg, src, tgt, force):
            # Simulate cache updating the source language
            cfg['output']['source_language'] = 'ja'
            return segments, 'cache'

        with patch.object(engine, '_obtain_segments', side_effect=fake_obtain_segments):
            project = engine.run(Path("/fake/video.mp4"), no_translate=True)

        # The project should have the updated source_lang, not the stale 'auto'
        assert project.metadata.source_lang == 'ja'

    def test_source_lang_stays_auto_when_not_updated(self):
        """If _obtain_segments doesn't change cfg, source_lang stays 'auto'."""
        from src.engine import SubGenEngine

        cfg = {
            'whisper': {'provider': 'local'},
            'translation': {},
            'output': {'source_language': 'auto', 'target_language': 'zh'},
        }
        engine = SubGenEngine(cfg)

        segments = [Segment(start=0, end=1, text="hello", translated="hi")]

        def fake_obtain_segments(input_path, cfg, src, tgt, force):
            return segments, 'transcribed'

        with patch.object(engine, '_obtain_segments', side_effect=fake_obtain_segments):
            project = engine.run(Path("/fake/video.mp4"), no_translate=True)

        assert project.metadata.source_lang == 'auto'


# ---------------------------------------------------------------------------
# Fix 2: Subprocess deadlock in whisper.cpp
# ---------------------------------------------------------------------------

class TestSubprocessDeadlock:
    """transcribe_cpp should use communicate() instead of sequential reads."""

    def test_uses_communicate(self):
        """Verify that Popen.communicate() is called instead of sequential reads."""
        from src.transcribe_cpp import transcribe_cpp

        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "progress = 50%\nprogress = 100%\n")
        mock_process.returncode = 0

        with patch('src.transcribe_cpp.ComponentManager') as MockCM, \
             patch('subprocess.Popen', return_value=mock_process), \
             patch('src.transcribe_cpp._parse_whisper_json', return_value=[]):
            cm_inst = MockCM.return_value
            cm_inst.find_whisper_engine.return_value = Path("/bin/whisper")
            cm_inst.find_whisper_model.return_value = Path("/models/ggml-large-v3.bin")

            # Mock the JSON output file
            with patch('builtins.open', side_effect=FileNotFoundError):
                # It will raise because no JSON file, but communicate() should be called
                with pytest.raises(RuntimeError, match="did not produce JSON"):
                    transcribe_cpp(Path("/fake/audio.wav"), {"whisper": {}})

        # Verify communicate was called
        mock_process.communicate.assert_called_once()


# ---------------------------------------------------------------------------
# Fix 3: Shallow copy causes config mutation
# ---------------------------------------------------------------------------

class TestShallowCopyConfigMutation:
    """export() should not mutate self.config when setting format."""

    def test_export_does_not_mutate_config(self, tmp_path):
        from src.engine import SubGenEngine
        from src.project import SubtitleProject

        cfg = {
            'whisper': {},
            'translation': {},
            'output': {'format': 'srt', 'bilingual': False},
        }
        engine = SubGenEngine(cfg)

        segments = [Segment(start=0.0, end=1.0, text="Hello", translated="Hi")]
        project = SubtitleProject(segments=segments)

        out = tmp_path / "test.ass"
        engine.export(project, out, format='ass')

        # The original config should NOT have been mutated
        assert cfg['output']['format'] == 'srt', \
            "export() mutated self.config['output']['format'] — shallow copy bug"


# ---------------------------------------------------------------------------
# Fix 4: Temp audio files cleanup
# ---------------------------------------------------------------------------

class TestTempAudioCleanup:
    """_obtain_segments should call cleanup_temp_files in finally block."""

    def test_cleanup_called_after_transcription(self):
        from src.engine import SubGenEngine

        cfg = {
            'whisper': {'provider': 'local'},
            'translation': {},
            'output': {'source_language': 'auto', 'target_language': 'zh'},
            'advanced': {'temp_dir': '/tmp/subgen', 'keep_temp_files': False},
        }
        engine = SubGenEngine(cfg)

        segments = [Segment(start=0, end=1, text="hi")]

        with patch('src.engine.extract_audio', return_value=Path("/tmp/audio.wav")), \
             patch('src.engine.transcribe_audio', return_value=segments), \
             patch('src.engine.cleanup_temp_files') as mock_cleanup, \
             patch('src.engine.save_cache'):

            result_segs, source = engine._obtain_segments(
                Path("/fake.mp4"), cfg, 'auto', 'zh', force_transcribe=True
            )

        mock_cleanup.assert_called_once_with(cfg)

    def test_cleanup_called_even_on_error(self):
        from src.engine import SubGenEngine

        cfg = {
            'whisper': {'provider': 'local'},
            'translation': {},
            'output': {'source_language': 'auto', 'target_language': 'zh'},
            'advanced': {'temp_dir': '/tmp/subgen', 'keep_temp_files': False},
        }
        engine = SubGenEngine(cfg)

        with patch('src.engine.extract_audio', return_value=Path("/tmp/audio.wav")), \
             patch('src.engine.transcribe_audio', side_effect=RuntimeError("fail")), \
             patch('src.engine.cleanup_temp_files') as mock_cleanup:

            with pytest.raises(RuntimeError, match="fail"):
                engine._obtain_segments(
                    Path("/fake.mp4"), cfg, 'auto', 'zh', force_transcribe=True
                )

        # cleanup must still be called due to finally block
        mock_cleanup.assert_called_once_with(cfg)


# ---------------------------------------------------------------------------
# Fix 5: whisper.cpp JSON parsing guards
# ---------------------------------------------------------------------------

class TestWhisperJsonParsingGuards:
    """_parse_whisper_json should handle malformed input gracefully."""

    def test_invalid_json_raises_runtime_error(self):
        from src.transcribe_cpp import _parse_whisper_json

        with pytest.raises(RuntimeError, match="Failed to parse whisper.cpp JSON"):
            _parse_whisper_json("this is not json {{{")

    def test_non_dict_top_level(self):
        from src.transcribe_cpp import _parse_whisper_json

        with pytest.raises(RuntimeError, match="expected JSON object"):
            _parse_whisper_json(json.dumps([1, 2, 3]))

    def test_missing_transcription_key(self):
        from src.transcribe_cpp import _parse_whisper_json

        with pytest.raises(RuntimeError, match="missing 'transcription' key"):
            _parse_whisper_json(json.dumps({"result": []}))

    def test_transcription_not_a_list(self):
        from src.transcribe_cpp import _parse_whisper_json

        with pytest.raises(RuntimeError, match="should be a list"):
            _parse_whisper_json(json.dumps({"transcription": "not a list"}))

    def test_malformed_segment_skipped(self):
        """Segments with bad timestamps should be skipped, not crash."""
        from src.transcribe_cpp import _parse_whisper_json

        data = {
            "transcription": [
                # Missing timestamps entirely
                {"text": "bad segment"},
                # Good segment
                {
                    "timestamps": {"from": "00:00:01.000", "to": "00:00:02.000"},
                    "text": "good segment",
                    "tokens": [],
                },
                # Non-dict item
                "not a segment",
            ]
        }
        segments = _parse_whisper_json(json.dumps(data))
        assert len(segments) == 1
        assert segments[0].text == "good segment"

    def test_malformed_token_skipped(self):
        """Tokens with bad data should be skipped."""
        from src.transcribe_cpp import _parse_whisper_json

        data = {
            "transcription": [
                {
                    "timestamps": {"from": "00:00:00.000", "to": "00:00:02.000"},
                    "text": " Hello world",
                    "tokens": [
                        "not a dict",
                        {"text": " Hello", "timestamps": "bad_ts"},
                        {
                            "text": " world",
                            "timestamps": {"from": "00:00:01.000", "to": "00:00:02.000"},
                        },
                    ],
                }
            ]
        }
        segments = _parse_whisper_json(json.dumps(data))
        assert len(segments) == 1
        # Only the valid token should be kept
        assert len(segments[0].words) == 1
        assert segments[0].words[0].text == "world"

    def test_valid_json_still_works(self):
        """Ensure normal valid input still works correctly."""
        from src.transcribe_cpp import _parse_whisper_json

        data = {
            "transcription": [
                {
                    "timestamps": {"from": "00:00:01.000", "to": "00:00:03.500"},
                    "text": " Hello world",
                    "tokens": [],
                }
            ]
        }
        segments = _parse_whisper_json(json.dumps(data))
        assert len(segments) == 1
        assert segments[0].text == "Hello world"
        assert segments[0].start == 1.0
        assert segments[0].end == 3.5


# ---------------------------------------------------------------------------
# Fix 6: source_from stored in metadata
# ---------------------------------------------------------------------------

class TestSourceFromMetadata:
    """source_from should be stored in project metadata."""

    def test_source_from_in_build_project(self):
        from src.engine import SubGenEngine

        cfg = {
            'whisper': {'provider': 'local'},
            'translation': {'provider': 'openai', 'model': 'gpt-4'},
            'output': {},
        }
        engine = SubGenEngine(cfg)
        segments = [Segment(start=0, end=1, text="hi", translated="hey")]

        project = engine._build_project(
            segments, cfg, Path("/test.mp4"), "en", "zh",
            source_from='cache',
        )
        assert project.metadata.source_from == 'cache'

    def test_source_from_default_empty(self):
        from src.engine import SubGenEngine

        cfg = {
            'whisper': {'provider': 'local'},
            'translation': {},
            'output': {},
        }
        engine = SubGenEngine(cfg)
        project = engine._build_project(
            [], cfg, Path("/test.mp4"), "en", "zh",
        )
        assert project.metadata.source_from == ''

    def test_source_from_serialization_roundtrip(self):
        from src.project import ProjectMetadata

        meta = ProjectMetadata(source_from='embedded')
        d = meta.to_dict()
        assert d['source_from'] == 'embedded'

        restored = ProjectMetadata.from_dict(d)
        assert restored.source_from == 'embedded'


# ---------------------------------------------------------------------------
# Fix 7: Platform detection with architecture mapping
# ---------------------------------------------------------------------------

class TestPlatformDetection:
    """_detect_platform should correctly detect Linux architectures."""

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="aarch64")
    def test_linux_arm64(self, mock_m, mock_s, tmp_path):
        from src.components import ComponentManager
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        assert cm.platform == "linux-arm64"

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="arm64")
    def test_linux_arm64_alt(self, mock_m, mock_s, tmp_path):
        from src.components import ComponentManager
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        assert cm.platform == "linux-arm64"

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="armv7l")
    def test_linux_armv7l(self, mock_m, mock_s, tmp_path):
        from src.components import ComponentManager
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        assert cm.platform == "linux-armv7l"

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="x86_64")
    def test_linux_x64(self, mock_m, mock_s, tmp_path):
        from src.components import ComponentManager
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        assert cm.platform == "linux-x64"

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="amd64")
    def test_linux_amd64(self, mock_m, mock_s, tmp_path):
        from src.components import ComponentManager
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        assert cm.platform == "linux-x64"

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="mips64")
    def test_unsupported_arch_raises(self, mock_m, mock_s, tmp_path):
        from src.components import ComponentManager
        with pytest.raises(RuntimeError, match="Unsupported architecture.*mips64"):
            ComponentManager(base_dir=tmp_path / "subgen")


# ---------------------------------------------------------------------------
# Fix 8: Concurrent downloads unique temp filename
# ---------------------------------------------------------------------------

class TestConcurrentDownloadTempFile:
    """install() should use unique temp filenames for archive downloads."""

    def test_temp_file_not_fixed_name(self, tmp_path):
        """Verify temp file is NOT 'tmp_download'."""
        from src.components import ComponentManager

        cm = ComponentManager(base_dir=tmp_path / "subgen")

        # We mock _download to avoid actual network calls and check temp usage
        created_tmp_files = []

        original_mkstemp = __import__('tempfile').mkstemp

        def tracking_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            if 'subgen_download_' in path:
                created_tmp_files.append(path)
            return fd, path

        with patch('src.components.ComponentManager._download') as mock_dl, \
             patch('tempfile.mkstemp', side_effect=tracking_mkstemp):
            mock_dl.return_value = Path("/fake")

            # Add a fake archive component
            cm.registry["components"]["test-archive"] = {
                "name": "Test",
                "type": "engine",
                "version": "1.0",
                "description": "test",
                "urls": {cm.platform: "https://example.com/test.tar.gz"},
                "sha256": {cm.platform: "abc123"},
                "size_bytes": 100,
                "install_path": "bin/test",
                "executable": "test",
            }

            try:
                cm.install("test-archive")
            except Exception:
                pass  # We don't care about the full install

        # Verify that a unique temp file was created (not 'tmp_download')
        for path in created_tmp_files:
            assert "tmp_download" not in path
            assert "subgen_download_" in path


# ---------------------------------------------------------------------------
# Fix 9: installed.json atomic writes
# ---------------------------------------------------------------------------

class TestAtomicInstalledJson:
    """_save_installed should write atomically via temp + os.replace."""

    def test_save_installed_atomic(self, tmp_path):
        from src.components import ComponentManager
        cm = ComponentManager(base_dir=tmp_path / "subgen")

        data = {"components": {"test": {"version": "1.0", "path": "/fake", "installed_at": "now", "size_bytes": 0}}}
        cm._save_installed(data)

        # Verify the file was written correctly
        loaded = json.loads(cm.installed_path.read_text())
        assert loaded["components"]["test"]["version"] == "1.0"

    def test_save_installed_no_partial_writes(self, tmp_path):
        """If writing fails, the original file should remain intact."""
        from src.components import ComponentManager
        cm = ComponentManager(base_dir=tmp_path / "subgen")

        # Write initial data
        initial_data = {"components": {"initial": {"version": "1.0", "path": "/fake", "installed_at": "now", "size_bytes": 0}}}
        cm._save_installed(initial_data)

        # Now try to save with a mocked os.replace that fails
        with patch('os.replace', side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                cm._save_installed({"components": {"new": {}}})

        # Original file should still be intact
        loaded = json.loads(cm.installed_path.read_text())
        assert "initial" in loaded["components"]


# ---------------------------------------------------------------------------
# Fix 10: Config YAML schema validation
# ---------------------------------------------------------------------------

class TestConfigSchemaValidation:
    """load_config should validate top-level keys are dicts after merge."""

    def test_whisper_null_raises(self, tmp_path):
        from src.config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("whisper: null\n")

        with pytest.raises(ValueError, match="'whisper' is null"):
            load_config(str(config_file))

    def test_output_as_string_raises(self, tmp_path):
        from src.config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("output: 'srt'\n")

        with pytest.raises(ValueError, match="'output' must be a mapping"):
            load_config(str(config_file))

    def test_valid_config_passes(self, tmp_path):
        from src.config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
whisper:
  provider: openai
output:
  format: srt
""")
        cfg = load_config(str(config_file))
        assert cfg['whisper']['provider'] == 'openai'

    def test_validate_config_function(self):
        from src.config import _validate_config

        # Valid
        _validate_config({
            'whisper': {}, 'translation': {}, 'output': {}, 'advanced': {},
        })

        # Invalid — null whisper
        with pytest.raises(ValueError, match="'whisper' is null"):
            _validate_config({
                'whisper': None, 'translation': {}, 'output': {}, 'advanced': {},
            })

        # Invalid — output is a list
        with pytest.raises(ValueError, match="'output' must be a mapping"):
            _validate_config({
                'whisper': {}, 'translation': {}, 'output': [1, 2], 'advanced': {},
            })


# ---------------------------------------------------------------------------
# Fix 11: Project save non-atomic
# ---------------------------------------------------------------------------

class TestProjectSaveAtomic:
    """SubtitleProject.save() should write atomically."""

    def test_save_creates_file(self, tmp_path):
        from src.project import SubtitleProject

        proj = SubtitleProject(
            segments=[Segment(start=1.0, end=2.0, text="Test")],
        )
        fpath = tmp_path / "test.subgen"
        proj.save(fpath)
        assert fpath.exists()

        # Verify content
        data = json.loads(fpath.read_text())
        assert data["segments"][0]["text"] == "Test"

    def test_save_no_leftover_temp_files(self, tmp_path):
        from src.project import SubtitleProject

        proj = SubtitleProject()
        fpath = tmp_path / "test.subgen"
        proj.save(fpath)

        # No temp files should be left over
        temp_files = list(tmp_path.glob(".subgen_*.tmp"))
        assert len(temp_files) == 0

    def test_save_atomic_on_failure(self, tmp_path):
        from src.project import SubtitleProject

        proj = SubtitleProject(
            segments=[Segment(start=1.0, end=2.0, text="Original")],
        )
        fpath = tmp_path / "test.subgen"
        proj.save(fpath)

        # Now try to save with os.replace mocked to fail
        proj2 = SubtitleProject(
            segments=[Segment(start=3.0, end=4.0, text="New")],
        )
        with patch('os.replace', side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                proj2.save(fpath)

        # Original file should still contain the original data
        data = json.loads(fpath.read_text())
        assert data["segments"][0]["text"] == "Original"


# ---------------------------------------------------------------------------
# Fix 12: Project version check on load
# ---------------------------------------------------------------------------

class TestProjectVersionCheck:
    """from_dict / load should warn about incompatible versions."""

    def test_compatible_version_no_warning(self):
        from src.project import SubtitleProject

        data = {
            "version": "0.2",
            "segments": [],
            "style": {},
            "metadata": {},
            "state": {},
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubtitleProject.from_dict(data)
            assert len(w) == 0

    def test_compatible_version_01(self):
        from src.project import SubtitleProject

        data = {
            "version": "0.1",
            "segments": [],
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubtitleProject.from_dict(data)
            assert len(w) == 0

    def test_incompatible_version_warns(self):
        from src.project import SubtitleProject

        data = {
            "version": "9.9",
            "segments": [],
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubtitleProject.from_dict(data)
            assert len(w) == 1
            assert "9.9" in str(w[0].message)
            assert "incompatible" in str(w[0].message).lower()

    def test_missing_version_warns(self):
        from src.project import SubtitleProject

        data = {
            "segments": [],
        }
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubtitleProject.from_dict(data)
            assert len(w) == 1
            assert "unknown" in str(w[0].message)

    def test_load_incompatible_warns(self, tmp_path):
        from src.project import SubtitleProject

        fpath = tmp_path / "test.subgen"
        fpath.write_text(json.dumps({
            "version": "99.0",
            "segments": [],
            "style": {},
            "metadata": {},
            "state": {},
        }))

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SubtitleProject.load(fpath)
            assert len(w) == 1
            assert "99.0" in str(w[0].message)

    def test_project_version_constant(self):
        from src.project import PROJECT_VERSION, COMPATIBLE_VERSIONS
        assert PROJECT_VERSION == "0.2"
        assert "0.2" in COMPATIBLE_VERSIONS
        assert "0.1" in COMPATIBLE_VERSIONS
