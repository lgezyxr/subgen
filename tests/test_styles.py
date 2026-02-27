"""Tests for src/styles.py"""

import pytest

from src.styles import hex_to_ass_color, FontStyle, StyleProfile, PRESETS, load_style


class TestHexToAssColor:
    def test_rrggbb_white(self):
        assert hex_to_ass_color("#FFFFFF") == "&H00FFFFFF"

    def test_rrggbb_red(self):
        assert hex_to_ass_color("#FF0000") == "&H000000FF"

    def test_rrggbb_cyan(self):
        assert hex_to_ass_color("#00FFFF") == "&H00FFFF00"

    def test_aarrggbb(self):
        assert hex_to_ass_color("#80000000") == "&H80000000"

    def test_aarrggbb_semi_transparent_red(self):
        assert hex_to_ass_color("#80FF0000") == "&H800000FF"

    def test_invalid_hex_characters(self):
        with pytest.raises(ValueError):
            hex_to_ass_color("#GGGGGG")


class TestFontStyleSerialization:
    def test_roundtrip(self):
        fs = FontStyle(font="Test", size=30, color="#FF0000", bold=True)
        d = fs.to_dict()
        fs2 = FontStyle.from_dict(d)
        assert fs2.font == "Test"
        assert fs2.size == 30
        assert fs2.bold is True


class TestStyleProfile:
    def test_default_preset(self):
        sp = PRESETS["default"]
        assert sp.primary.font == "Arial"
        assert sp.play_res_x == 1920

    def test_roundtrip(self):
        sp = PRESETS["netflix"]
        d = sp.to_dict()
        sp2 = StyleProfile.from_dict(d)
        assert sp2.name == "netflix"
        assert sp2.primary.font == "Netflix Sans"
        assert sp2.secondary.size == 40

    def test_to_ass_header_contains_sections(self):
        sp = StyleProfile()
        header = sp.to_ass_header()
        assert "[Script Info]" in header
        assert "[V4+ Styles]" in header
        assert "[Events]" in header
        assert "Style: Default," in header
        assert "Style: Secondary," in header
        assert "PlayResX: 1920" in header

    def test_to_ass_header_color_format(self):
        sp = StyleProfile(primary=FontStyle(color="#FF0000"))
        header = sp.to_ass_header()
        assert "&H000000FF" in header  # red in ASS


class TestLoadStyle:
    def test_empty_config(self):
        sp = load_style({})
        assert sp.name == "default"

    def test_preset_only(self):
        sp = load_style({"styles": {"preset": "netflix"}})
        assert sp.primary.font == "Netflix Sans"

    def test_preset_with_override(self):
        sp = load_style({"styles": {
            "preset": "netflix",
            "primary": {"size": 70},
            "margin_bottom": 50,
        }})
        assert sp.primary.font == "Netflix Sans"  # inherited
        assert sp.primary.size == 70  # overridden
        assert sp.margin_bottom == 50  # overridden

    def test_unknown_preset_falls_back(self):
        sp = load_style({"styles": {"preset": "nonexistent"}})
        assert sp.primary.font == "Arial"  # default

    def test_non_dict_styles_falls_back(self):
        sp = load_style({"styles": ["not", "a", "dict"]})
        assert sp.name == "default"
