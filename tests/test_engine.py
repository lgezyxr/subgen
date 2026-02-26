"""Tests for SubGenEngine."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.engine import SubGenEngine, _segments_to_cache_dicts, _cache_dicts_to_segments
from src.transcribe import Segment, Word
from src.project import SubtitleProject
from src.styles import StyleProfile, PRESETS


class TestEngineInit:
    """Test engine initialization."""

    def test_init_default(self):
        cfg = {'whisper': {}, 'translation': {}, 'output': {}}
        engine = SubGenEngine(cfg)
        assert engine.config is cfg
        # Default progress callback should be a no-op
        engine.on_progress('test', 0, 1)  # should not raise

    def test_init_with_callback(self):
        calls = []
        def cb(stage, cur, tot):
            calls.append((stage, cur, tot))
        engine = SubGenEngine({}, on_progress=cb)
        engine.on_progress('extracting', 0, 1)
        assert calls == [('extracting', 0, 1)]


class TestSegmentConversion:
    """Test segment serialization helpers."""

    def test_roundtrip(self):
        seg = Segment(start=1.0, end=2.0, text="hello", translated="你好")
        seg.words = [Word(text="hello", start=1.0, end=2.0)]
        dicts = _segments_to_cache_dicts([seg])
        restored = _cache_dicts_to_segments(dicts)
        assert len(restored) == 1
        assert restored[0].text == "hello"
        assert restored[0].translated == "你好"
        assert len(restored[0].words) == 1

    def test_empty(self):
        assert _cache_dicts_to_segments([]) == []
        assert _segments_to_cache_dicts([]) == []


class TestExport:
    """Test engine export."""

    def test_export_srt(self, tmp_path):
        cfg = {'whisper': {}, 'translation': {}, 'output': {'format': 'srt', 'bilingual': False}}
        engine = SubGenEngine(cfg)

        segments = [
            Segment(start=0.0, end=1.0, text="Hello", translated="你好"),
            Segment(start=1.5, end=3.0, text="World", translated="世界"),
        ]
        project = SubtitleProject(segments=segments)

        out = tmp_path / "test.srt"
        result = engine.export(project, out, format='srt')
        assert result == out
        assert out.exists()
        content = out.read_text()
        assert "你好" in content

    def test_export_with_style_override(self, tmp_path):
        cfg = {'whisper': {}, 'translation': {}, 'output': {'format': 'ass', 'bilingual': False}}
        engine = SubGenEngine(cfg)

        segments = [
            Segment(start=0.0, end=1.0, text="Hello", translated="你好"),
        ]
        project = SubtitleProject(segments=segments)
        style = PRESETS['netflix']

        out = tmp_path / "test.ass"
        engine.export(project, out, format='ass', style=style)
        assert out.exists()
        content = out.read_text()
        assert "Netflix Sans" in content


class TestBuildProject:
    """Test project building."""

    def test_build_project(self):
        cfg = {
            'whisper': {'provider': 'local'},
            'translation': {'provider': 'openai', 'model': 'gpt-4'},
            'output': {},
        }
        engine = SubGenEngine(cfg)
        segments = [Segment(start=0.0, end=1.0, text="hi", translated="嗨")]
        project = engine._build_project(segments, cfg, Path("/tmp/test.mp4"), "en", "zh")

        assert isinstance(project, SubtitleProject)
        assert len(project.segments) == 1
        assert project.metadata.source_lang == "en"
        assert project.state.is_transcribed is True
        assert project.state.is_translated is True
