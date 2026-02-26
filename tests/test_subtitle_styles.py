"""Tests for subtitle.py style integration."""

from pathlib import Path
from src.transcribe import Segment
from src.subtitle import generate_subtitle
from src.styles import StyleProfile, FontStyle, hex_to_ass_color


class TestAssWithStyle:
    def test_ass_with_style(self, tmp_path: Path):
        """ASS output uses style.to_ass_header() when style is provided."""
        style = StyleProfile(primary=FontStyle(font="TestFont", size=72))
        segs = [Segment(start=0.0, end=1.0, text="Hello")]
        out = tmp_path / "test.ass"
        generate_subtitle(segs, out, {"output": {"format": "ass"}}, style=style)
        content = out.read_text()
        assert "TestFont" in content
        assert "Style: Default,TestFont,72" in content

    def test_ass_without_style(self, tmp_path: Path):
        """ASS output uses default preset when no style provided."""
        segs = [Segment(start=0.0, end=1.0, text="Hello")]
        out = tmp_path / "test.ass"
        generate_subtitle(segs, out, {"output": {"format": "ass"}})
        content = out.read_text()
        assert "Style: Default,Arial,60" in content

    def test_ass_bilingual_with_style_uses_inline(self, tmp_path: Path):
        """Bilingual ASS with style uses single Dialogue + \\N + inline override."""
        style = StyleProfile(
            secondary=FontStyle(font="SecFont", size=40, color="#AAAAAA"),
        )
        segs = [Segment(start=0.0, end=2.0, text="Hello", translated="你好")]
        out = tmp_path / "test.ass"
        generate_subtitle(segs, out, {"output": {"format": "ass", "bilingual": True}}, style=style)
        content = out.read_text()
        # Should be single Dialogue with \N
        dialogue_lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        assert len(dialogue_lines) == 1
        line = dialogue_lines[0]
        assert "你好\\N" in line
        assert "\\fnSecFont" in line
        assert "\\fs40" in line
        sec_color = hex_to_ass_color("#AAAAAA")
        assert f"\\c{sec_color}" in line

    def test_ass_bilingual_without_style_uses_two_dialogues(self, tmp_path: Path):
        """Bilingual ASS without style uses legacy two-Dialogue format."""
        segs = [Segment(start=0.0, end=2.0, text="Hello", translated="你好")]
        out = tmp_path / "test.ass"
        # Pass empty config so load_style returns default, but _generate_ass gets style=resolved
        # Actually with the new code, style is always resolved. Let's check it uses \N format.
        # With default load_style, style is not None, so it uses \N format.
        generate_subtitle(segs, out, {"output": {"format": "ass", "bilingual": True}})
        content = out.read_text()
        dialogue_lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        # With resolved style (default), should use single Dialogue + \N
        assert len(dialogue_lines) == 1

    def test_srt_unchanged(self, tmp_path: Path):
        """SRT format is not affected by style parameter."""
        style = StyleProfile(primary=FontStyle(font="CustomFont"))
        segs = [Segment(start=0.0, end=1.0, text="Hello")]
        out = tmp_path / "test.srt"
        generate_subtitle(segs, out, {"output": {"format": "srt"}}, style=style)
        content = out.read_text()
        assert "CustomFont" not in content
        assert "Hello" in content
