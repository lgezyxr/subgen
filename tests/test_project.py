"""Tests for src/project.py"""

from pathlib import Path
from src.transcribe import Segment, Word
from src.project import SubtitleProject, ProjectMetadata, ProjectState
from src.styles import StyleProfile, FontStyle


class TestSubtitleProject:
    def test_to_dict_from_dict_roundtrip(self):
        proj = SubtitleProject(
            segments=[
                Segment(start=0.0, end=1.5, text="Hello", translated="你好",
                        words=[Word(text="Hello", start=0.0, end=1.5)]),
            ],
            style=StyleProfile(name="test", primary=FontStyle(size=70)),
            metadata=ProjectMetadata(video_path="/tmp/v.mp4", source_lang="en", target_lang="zh"),
            state=ProjectState(is_transcribed=True),
        )
        d = proj.to_dict()
        proj2 = SubtitleProject.from_dict(d)

        assert len(proj2.segments) == 1
        assert proj2.segments[0].text == "Hello"
        assert proj2.segments[0].translated == "你好"
        assert len(proj2.segments[0].words) == 1
        assert proj2.style.name == "test"
        assert proj2.style.primary.size == 70
        assert proj2.metadata.video_path == "/tmp/v.mp4"
        assert proj2.state.is_transcribed is True
        assert proj2.state.is_translated is False

    def test_save_load_roundtrip(self, tmp_path: Path):
        proj = SubtitleProject(
            segments=[Segment(start=1.0, end=2.0, text="Test")],
            metadata=ProjectMetadata(source_lang="en"),
        )
        fpath = tmp_path / "test.subgen"
        proj.save(fpath)
        assert fpath.exists()

        proj2 = SubtitleProject.load(fpath)
        assert len(proj2.segments) == 1
        assert proj2.segments[0].text == "Test"
        assert proj2.metadata.source_lang == "en"
        assert proj2.metadata.created_at != ""
        assert proj2.metadata.modified_at != ""

    def test_version_in_saved_file(self, tmp_path: Path):
        proj = SubtitleProject()
        d = proj.to_dict()
        assert d["version"] == "0.2"
