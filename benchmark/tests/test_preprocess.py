"""Comprehensive tests for benchmark.scripts.preprocess.

Uses fixture files for integration tests and inline strings for unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.scripts.preprocess import (
    _classify_script,
    _detect_lyrics_styles,
    _detect_main_style,
    _filter_noise,
    _is_credits,
    _lang_to_script,
    _parse_ass,
    _parse_ass_timestamp,
    _parse_srt,
    _split_bilingual,
    _strip_ass_tags,
    preprocess,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ===================================================================
# Unit tests — _parse_ass_timestamp
# ===================================================================


class TestParseAssTimestamp:
    def test_standard_format(self):
        assert _parse_ass_timestamp("0:00:01.00") == 1.0

    def test_hours(self):
        assert _parse_ass_timestamp("1:00:00.00") == 3600.0

    def test_centiseconds(self):
        assert _parse_ass_timestamp("0:00:01.50") == 1.5

    def test_minutes_and_seconds(self):
        assert _parse_ass_timestamp("0:02:30.00") == 150.0

    def test_complex_timestamp(self):
        ts = _parse_ass_timestamp("1:23:45.67")
        expected = 1 * 3600 + 23 * 60 + 45.67
        assert abs(ts - expected) < 0.01

    def test_malformed_returns_zero(self):
        assert _parse_ass_timestamp("invalid") == 0.0

    def test_empty_returns_zero(self):
        assert _parse_ass_timestamp("") == 0.0

    def test_with_whitespace(self):
        assert _parse_ass_timestamp("  0:00:01.00  ") == 1.0


# ===================================================================
# Unit tests — _strip_ass_tags
# ===================================================================


class TestStripAssTags:
    def test_no_tags(self):
        assert _strip_ass_tags("Hello world") == "Hello world"

    def test_bold_tags(self):
        assert _strip_ass_tags(r"{\b1}Bold text{\b0}") == "Bold text"

    def test_multiple_tags(self):
        result = _strip_ass_tags(r"{\an8\pos(960,50)}Some text")
        assert result == "Some text"

    def test_complex_tags(self):
        result = _strip_ass_tags(r"{\fad(200,200)\pos(960,540)\fs24}Hello")
        assert result == "Hello"

    def test_only_tags_returns_empty(self):
        result = _strip_ass_tags(r"{\fad(200,200)\pos(960,540)}")
        assert result == ""

    def test_karaoke_tags(self):
        result = _strip_ass_tags(r"{\kf50}Ki{\kf50}ra{\kf50}ri")
        assert result == "Kirari"

    def test_inline_style_override(self):
        result = _strip_ass_tags(
            r"Hello\N{\fn微软雅黑\fs36\c&H00FFFFFF&}你好"
        )
        assert result == r"Hello\N你好"

    def test_empty_tag_block(self):
        assert _strip_ass_tags("{}text") == "text"

    def test_nested_braces_not_expected(self):
        # ASS doesn't use nested braces; just verify no crash
        result = _strip_ass_tags(r"{\b1}text")
        assert result == "text"


# ===================================================================
# Unit tests — _classify_script
# ===================================================================


class TestClassifyScript:
    def test_pure_english(self):
        assert _classify_script("Hello world") == "latin"

    def test_pure_chinese(self):
        assert _classify_script("你好世界") == "cjk"

    def test_pure_japanese_hiragana(self):
        assert _classify_script("こんにちは") == "cjk"

    def test_pure_japanese_katakana(self):
        assert _classify_script("カタカナ") == "cjk"

    def test_pure_korean(self):
        assert _classify_script("안녕하세요") == "cjk"

    def test_mixed_mostly_cjk(self):
        # 4 CJK + 1 Latin char → 80% CJK
        assert _classify_script("你好世界x") == "cjk"

    def test_mixed_mostly_latin(self):
        # 1 CJK + many Latin → < 30% CJK
        assert _classify_script("Hello world 你") == "latin"

    def test_empty_string(self):
        assert _classify_script("") == "latin"

    def test_whitespace_only(self):
        assert _classify_script("   ") == "latin"

    def test_numbers_and_punctuation(self):
        assert _classify_script("12345!?") == "latin"

    def test_cjk_with_punctuation(self):
        # CJK punctuation falls in CJK ranges
        assert _classify_script("你好！世界？") == "cjk"


# ===================================================================
# Unit tests — _lang_to_script
# ===================================================================


class TestLangToScript:
    def test_cjk_codes(self):
        for code in ("ja", "zh", "ko", "jp", "cn", "cjk"):
            assert _lang_to_script(code) == "cjk", f"Failed for {code}"

    def test_full_names(self):
        for name in ("chinese", "japanese", "korean"):
            assert _lang_to_script(name) == "cjk", f"Failed for {name}"

    def test_latin_codes(self):
        for code in ("en", "fr", "de", "es", "latin"):
            assert _lang_to_script(code) == "latin", f"Failed for {code}"

    def test_case_insensitive(self):
        assert _lang_to_script("JA") == "cjk"
        assert _lang_to_script("EN") == "latin"

    def test_auto_is_latin(self):
        assert _lang_to_script("auto") == "latin"


# ===================================================================
# Unit tests — _split_bilingual
# ===================================================================


class TestSplitBilingual:
    def test_bilingual_backslash_n(self):
        source, trans = _split_bilingual(r"Hello\N你好", "en")
        assert source == "Hello"
        assert trans == "你好"

    def test_bilingual_cjk_source(self):
        source, trans = _split_bilingual(r"你好\NHello", "zh")
        assert source == "你好"
        assert trans == "Hello"

    def test_monolingual(self):
        source, trans = _split_bilingual("Just English text", "en")
        assert source == "Just English text"
        assert trans == ""

    def test_monolingual_cjk(self):
        source, trans = _split_bilingual("只有中文", "zh")
        assert source == "只有中文"
        assert trans == ""

    def test_bilingual_newline(self):
        source, trans = _split_bilingual("Hello\n你好", "en")
        assert source == "Hello"
        assert trans == "你好"

    def test_same_script_both_parts(self):
        # Both parts Latin — can't distinguish, first = source
        source, trans = _split_bilingual(r"Hello\NWorld", "en")
        assert source == "Hello"
        assert trans == "World"

    def test_empty_after_separator(self):
        source, trans = _split_bilingual(r"Hello\N", "en")
        assert source == "Hello"
        assert trans == ""

    def test_three_parts(self):
        # Three parts: take first two meaningful
        source, trans = _split_bilingual(r"Hello\N你好\NBonjour", "en")
        assert source == "Hello"
        assert trans == "你好"

    def test_cjk_first_latin_source(self):
        """When source_lang is Latin but CJK appears first, swap correctly."""
        source, trans = _split_bilingual(r"中文\NEnglish", "en")
        assert source == "English"
        assert trans == "中文"

    def test_empty_string(self):
        source, trans = _split_bilingual("", "en")
        assert source == ""
        assert trans == ""


# ===================================================================
# Unit tests — _detect_main_style
# ===================================================================


class TestDetectMainStyle:
    def test_single_style(self):
        segs = [
            {"style": "Default", "line_type": "dialogue"},
            {"style": "Default", "line_type": "dialogue"},
        ]
        assert _detect_main_style(segs) == "Default"

    def test_most_frequent(self):
        segs = [
            {"style": "Default", "line_type": "dialogue"},
            {"style": "Default", "line_type": "dialogue"},
            {"style": "Default", "line_type": "dialogue"},
            {"style": "Sign", "line_type": "dialogue"},
        ]
        assert _detect_main_style(segs) == "Default"

    def test_comments_excluded(self):
        segs = [
            {"style": "Comment", "line_type": "comment"},
            {"style": "Comment", "line_type": "comment"},
            {"style": "Comment", "line_type": "comment"},
            {"style": "Default", "line_type": "dialogue"},
        ]
        assert _detect_main_style(segs) == "Default"

    def test_empty_list(self):
        assert _detect_main_style([]) is None


# ===================================================================
# Unit tests — _detect_lyrics_styles
# ===================================================================


class TestDetectLyricsStyles:
    def test_op_style(self):
        segs = [{"style": "OP", "line_type": "dialogue"}]
        assert "OP" in _detect_lyrics_styles(segs)

    def test_ed_style(self):
        segs = [{"style": "ED", "line_type": "dialogue"}]
        assert "ED" in _detect_lyrics_styles(segs)

    def test_karaoke_style(self):
        segs = [{"style": "Karaoke", "line_type": "dialogue"}]
        assert "Karaoke" in _detect_lyrics_styles(segs)

    def test_song_insert_style(self):
        segs = [{"style": "Song-Insert", "line_type": "dialogue"}]
        assert "Song-Insert" in _detect_lyrics_styles(segs)

    def test_no_lyrics(self):
        segs = [
            {"style": "Default", "line_type": "dialogue"},
            {"style": "Sign", "line_type": "dialogue"},
        ]
        assert _detect_lyrics_styles(segs) == set()

    def test_chinese_keyword(self):
        segs = [{"style": "片头歌词", "line_type": "dialogue"}]
        assert "片头歌词" in _detect_lyrics_styles(segs)

    def test_multiple_lyrics_styles(self):
        segs = [
            {"style": "OP", "line_type": "dialogue"},
            {"style": "ED", "line_type": "dialogue"},
            {"style": "Default", "line_type": "dialogue"},
        ]
        result = _detect_lyrics_styles(segs)
        assert result == {"OP", "ED"}

    def test_case_insensitive(self):
        segs = [{"style": "opening", "line_type": "dialogue"}]
        assert "opening" in _detect_lyrics_styles(segs)


# ===================================================================
# Unit tests — _filter_noise
# ===================================================================


class TestFilterNoise:
    def test_removes_comments(self):
        segs = [
            {"start": 1, "end": 3, "text": "Hello", "style": "Default",
             "line_type": "comment"},
            {"start": 4, "end": 6, "text": "World", "style": "Default",
             "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", set())
        assert len(result) == 1
        assert result[0]["text"] == "World"

    def test_removes_vector_drawings(self):
        segs = [
            {"start": 1, "end": 3, "text": r"{\p1}m 0 0 l 100 0", "style": "Default",
             "line_type": "dialogue"},
            {"start": 4, "end": 6, "text": "Clean", "style": "Default",
             "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", set())
        assert len(result) == 1
        assert result[0]["text"] == "Clean"

    def test_removes_long_duration(self):
        segs = [
            {"start": 0, "end": 700, "text": "Watermark", "style": "Default",
             "line_type": "dialogue"},
            {"start": 1, "end": 3, "text": "Normal", "style": "Default",
             "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", set())
        assert len(result) == 1
        assert result[0]["text"] == "Normal"

    def test_removes_pure_tags(self):
        segs = [
            {"start": 1, "end": 3, "text": r"{\fad(200,200)\pos(960,540)}",
             "style": "Default", "line_type": "dialogue"},
            {"start": 4, "end": 6, "text": "Visible", "style": "Default",
             "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", set())
        assert len(result) == 1
        assert result[0]["text"] == "Visible"

    def test_removes_credits_at_start(self):
        segs = [
            {"start": 0.5, "end": 2, "text": "Translated by TeamX",
             "style": "Default", "line_type": "dialogue"},
            {"start": 5, "end": 8, "text": "Actual dialogue",
             "style": "Default", "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", set())
        assert len(result) == 1
        assert result[0]["text"] == "Actual dialogue"

    def test_removes_credits_at_end(self):
        segs = [
            {"start": 5, "end": 8, "text": "Some dialogue",
             "style": "Default", "line_type": "dialogue"},
            {"start": 98, "end": 100, "text": "Encoder: SomeGuy",
             "style": "Default", "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", set())
        assert len(result) == 1
        assert result[0]["text"] == "Some dialogue"

    def test_filters_non_main_styles(self):
        segs = [
            {"start": 1, "end": 3, "text": "Main line", "style": "Default",
             "line_type": "dialogue"},
            {"start": 4, "end": 6, "text": "Sign text", "style": "Sign",
             "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", set())
        assert len(result) == 1
        assert result[0]["text"] == "Main line"

    def test_keeps_lyrics_styles(self):
        segs = [
            {"start": 1, "end": 3, "text": "Dialogue", "style": "Default",
             "line_type": "dialogue"},
            {"start": 4, "end": 6, "text": "Song lyric", "style": "OP",
             "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, "Default", {"OP"})
        assert len(result) == 2

    def test_empty_input(self):
        assert _filter_noise([], None, set()) == []

    def test_no_main_style_keeps_all_styles(self):
        segs = [
            {"start": 1, "end": 3, "text": "Line A", "style": "StyleA",
             "line_type": "dialogue"},
            {"start": 4, "end": 6, "text": "Line B", "style": "StyleB",
             "line_type": "dialogue"},
        ]
        result = _filter_noise(segs, None, set())
        assert len(result) == 2


# ===================================================================
# Unit tests — _is_credits
# ===================================================================


class TestIsCredits:
    def test_credit_at_start(self):
        seg = {"start": 0.5, "end": 2.0}
        assert _is_credits(seg, "Translated by TeamX", 0.0, 100.0)

    def test_credit_at_end(self):
        seg = {"start": 98.0, "end": 100.0}
        assert _is_credits(seg, "Timer: SomeGuy", 0.0, 100.0)

    def test_not_credit_in_middle(self):
        seg = {"start": 50.0, "end": 52.0}
        assert not _is_credits(seg, "Translated by TeamX", 0.0, 100.0)

    def test_not_credit_no_keyword(self):
        seg = {"start": 0.5, "end": 2.0}
        assert not _is_credits(seg, "Hello world", 0.0, 100.0)

    def test_chinese_credit(self):
        seg = {"start": 0.5, "end": 2.0}
        assert _is_credits(seg, "翻译: 小明", 0.0, 100.0)

    def test_typesetter_credit(self):
        seg = {"start": 98.0, "end": 100.0}
        assert _is_credits(seg, "Typesetting by Artist", 0.0, 100.0)


# ===================================================================
# Unit tests — _parse_ass (inline)
# ===================================================================


class TestParseAssInline:
    def test_basic_dialogue(self, tmp_path):
        content = """\
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello world
"""
        f = tmp_path / "test.ass"
        f.write_text(content)
        result = _parse_ass(f)
        assert len(result) == 1
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 3.0
        assert result[0]["text"] == "Hello world"
        assert result[0]["style"] == "Default"
        assert result[0]["line_type"] == "dialogue"

    def test_comment_line(self, tmp_path):
        content = """\
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Comment: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,A comment
Dialogue: 0,0:00:04.00,0:00:06.00,Default,,0,0,0,,Real dialogue
"""
        f = tmp_path / "test.ass"
        f.write_text(content)
        result = _parse_ass(f)
        assert len(result) == 2
        assert result[0]["line_type"] == "comment"
        assert result[1]["line_type"] == "dialogue"

    def test_text_with_commas(self, tmp_path):
        content = """\
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello, world, how are you?
"""
        f = tmp_path / "test.ass"
        f.write_text(content)
        result = _parse_ass(f)
        assert result[0]["text"] == "Hello, world, how are you?"

    def test_different_field_order(self, tmp_path):
        """Some ASS files have different column ordering."""
        content = """\
[Events]
Format: Start, End, Style, Text
Dialogue: 0:00:01.00,0:00:03.00,Custom,Some text here
"""
        f = tmp_path / "test.ass"
        f.write_text(content)
        result = _parse_ass(f)
        assert len(result) == 1
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 3.0
        assert result[0]["style"] == "Custom"
        assert result[0]["text"] == "Some text here"

    def test_multiple_sections(self, tmp_path):
        content = """\
[Script Info]
Title: Test

[V4+ Styles]
Format: Name, Fontname, Fontsize
Style: Default,Arial,48

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Line one
Dialogue: 0,0:00:04.00,0:00:06.00,Default,,0,0,0,,Line two
"""
        f = tmp_path / "test.ass"
        f.write_text(content)
        result = _parse_ass(f)
        assert len(result) == 2

    def test_utf8_bom(self, tmp_path):
        content = "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,BOM test\n"
        f = tmp_path / "test.ass"
        f.write_bytes(content.encode("utf-8-sig"))
        result = _parse_ass(f)
        assert len(result) == 1
        assert result[0]["text"] == "BOM test"


# ===================================================================
# Unit tests — _parse_srt (inline)
# ===================================================================


class TestParseSrtInline:
    def test_basic_srt(self, tmp_path):
        content = """\
1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
How are you?
"""
        f = tmp_path / "test.srt"
        f.write_text(content)
        result = _parse_srt(f)
        assert len(result) == 2
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 3.0
        assert result[0]["text"] == "Hello world"

    def test_srt_with_dots(self, tmp_path):
        content = """\
1
00:00:01.000 --> 00:00:03.000
Dot separator
"""
        f = tmp_path / "test.srt"
        f.write_text(content)
        result = _parse_srt(f)
        assert len(result) == 1
        assert result[0]["start"] == 1.0

    def test_multiline_text(self, tmp_path):
        content = """\
1
00:00:01,000 --> 00:00:03,000
Line one
Line two
"""
        f = tmp_path / "test.srt"
        f.write_text(content)
        result = _parse_srt(f)
        assert result[0]["text"] == "Line one\nLine two"

    def test_srt_without_index(self, tmp_path):
        content = """\
00:00:01,000 --> 00:00:03,000
No index line
"""
        f = tmp_path / "test.srt"
        f.write_text(content)
        result = _parse_srt(f)
        assert len(result) == 1
        assert result[0]["text"] == "No index line"

    def test_srt_style_is_default(self, tmp_path):
        content = """\
1
00:00:01,000 --> 00:00:03,000
Test
"""
        f = tmp_path / "test.srt"
        f.write_text(content)
        result = _parse_srt(f)
        assert result[0]["style"] == "Default"


# ===================================================================
# Integration tests — fixture files
# ===================================================================


class TestSimpleFixture:
    """Tests using simple.ass — 5-line clean ASS."""

    def test_returns_five_segments(self):
        result = preprocess(FIXTURES / "simple.ass")
        assert len(result) == 5

    def test_all_dialogue_type(self):
        result = preprocess(FIXTURES / "simple.ass")
        for seg in result:
            assert seg["type"] == "dialogue"

    def test_all_default_style(self):
        result = preprocess(FIXTURES / "simple.ass")
        for seg in result:
            assert seg["style"] == "Default"

    def test_timestamps_correct(self):
        result = preprocess(FIXTURES / "simple.ass")
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 3.0
        assert result[4]["start"] == 13.0
        assert result[4]["end"] == 15.0

    def test_source_text(self):
        result = preprocess(FIXTURES / "simple.ass")
        assert result[0]["source"] == "Hello world"
        assert result[4]["source"] == "Goodbye everyone."

    def test_no_translation(self):
        result = preprocess(FIXTURES / "simple.ass")
        for seg in result:
            assert seg["translation"] == ""

    def test_output_dict_keys(self):
        result = preprocess(FIXTURES / "simple.ass")
        expected_keys = {"start", "end", "source", "translation", "type", "style"}
        for seg in result:
            assert set(seg.keys()) == expected_keys


class TestNoisyFixture:
    """Tests using noisy_reference.ass — ~15 lines with all noise types."""

    def test_comments_filtered(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "This is a comment line" not in sources

    def test_vector_drawings_filtered(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        for seg in result:
            assert r"\p1" not in seg["source"]

    def test_watermark_filtered(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "Watermark text displayed forever" not in sources

    def test_pure_tag_lines_filtered(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        for seg in result:
            assert seg["source"].strip() != ""

    def test_credits_filtered(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "Subtitles by FansubGroup" not in sources

    def test_sign_style_filtered(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "Shop Sign Translation" not in sources

    def test_title_style_filtered(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "Episode Title Card" not in sources

    def test_tags_stripped_from_kept_lines(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        for seg in result:
            assert "{" not in seg["source"]
            assert "}" not in seg["source"]

    def test_dialogue_lines_kept(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "What a beautiful day!" in sources
        assert "I agree completely." in sources
        assert "Regular dialogue here." in sources
        assert "Another clean line." in sources
        assert "Let me check that sign." in sources
        assert "The adventure begins!" in sources

    def test_bold_text_preserved_without_tags(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "This has bold tags" in sources

    def test_italic_text_preserved_without_tags(self):
        result = preprocess(FIXTURES / "noisy_reference.ass")
        sources = [seg["source"] for seg in result]
        assert "Thinking to myself" in sources


class TestBilingualFixture:
    """Tests using bilingual.ass — bilingual with \\N separator."""

    def test_bilingual_split(self):
        result = preprocess(FIXTURES / "bilingual.ass", source_lang="en")
        # First line: Hello everyone\N大家好
        assert result[0]["source"] == "Hello everyone"
        assert result[0]["translation"] == "大家好"

    def test_all_bilingual_have_translation(self):
        result = preprocess(FIXTURES / "bilingual.ass", source_lang="en")
        bilingual_count = sum(1 for seg in result if seg["translation"])
        # Lines 1-4 and 6-7 are bilingual; line 5 is monolingual
        assert bilingual_count >= 5

    def test_monolingual_line_no_translation(self):
        result = preprocess(FIXTURES / "bilingual.ass", source_lang="en")
        # Line 5: "This is a monolingual line"
        mono = [s for s in result if s["source"] == "This is a monolingual line"]
        assert len(mono) == 1
        assert mono[0]["translation"] == ""

    def test_source_lang_zh(self):
        result = preprocess(FIXTURES / "bilingual.ass", source_lang="zh")
        # With source_lang=zh, CJK should be source, Latin translation
        assert result[0]["source"] == "大家好"
        assert result[0]["translation"] == "Hello everyone"

    def test_tags_stripped_before_split(self):
        result = preprocess(FIXTURES / "bilingual.ass", source_lang="zh")
        for seg in result:
            assert r"{\fn" not in seg["source"]
            assert r"{\fn" not in seg["translation"]

    def test_auto_detection(self):
        result = preprocess(FIXTURES / "bilingual.ass", source_lang="auto")
        # Auto-detect should classify script and split accordingly
        # The text content determines which part is source
        for seg in result:
            assert isinstance(seg["source"], str)
            assert isinstance(seg["translation"], str)


class TestLyricsFixture:
    """Tests using lyrics.ass — has OP/ED style lyrics."""

    def test_lyrics_type_detected(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        lyrics = [s for s in result if s["type"] == "lyrics"]
        assert len(lyrics) > 0

    def test_op_is_lyrics(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        op_segs = [s for s in result if s["style"] == "OP"]
        for seg in op_segs:
            assert seg["type"] == "lyrics"

    def test_ed_is_lyrics(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        ed_segs = [s for s in result if s["style"] == "ED"]
        for seg in ed_segs:
            assert seg["type"] == "lyrics"

    def test_song_insert_is_lyrics(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        insert_segs = [s for s in result if s["style"] == "Song-Insert"]
        for seg in insert_segs:
            assert seg["type"] == "lyrics"

    def test_dialogue_type_for_default(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        default_segs = [s for s in result if s["style"] == "Default"]
        for seg in default_segs:
            assert seg["type"] == "dialogue"

    def test_karaoke_tags_stripped(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        for seg in result:
            assert r"{\kf" not in seg["source"]
            assert r"{\k" not in seg["source"]

    def test_lyrics_text_preserved(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        sources = [s["source"] for s in result]
        assert "Kirari" in sources
        assert "Yume wo mite ita" in sources

    def test_mixed_dialogue_and_lyrics(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        types = {s["type"] for s in result}
        assert "dialogue" in types
        assert "lyrics" in types

    def test_total_segment_count(self):
        result = preprocess(FIXTURES / "lyrics.ass")
        # 3 OP + 3 dialogue + 2 insert + 3 ED = 11
        assert len(result) == 11


# ===================================================================
# Integration tests — SRT via preprocess()
# ===================================================================


class TestPreprocessSrt:
    def test_basic_srt(self, tmp_path):
        content = """\
1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
How are you?
"""
        f = tmp_path / "test.srt"
        f.write_text(content)
        result = preprocess(f)
        assert len(result) == 2
        assert result[0]["source"] == "Hello world"
        assert result[0]["type"] == "dialogue"
        assert result[0]["style"] == "Default"

    def test_bilingual_srt(self, tmp_path):
        content = """\
1
00:00:01,000 --> 00:00:03,000
Hello
你好

2
00:00:04,000 --> 00:00:06,000
Goodbye
再见
"""
        f = tmp_path / "test.srt"
        f.write_text(content)
        result = preprocess(f, source_lang="en")
        assert result[0]["source"] == "Hello"
        assert result[0]["translation"] == "你好"

    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "test.vtt"
        f.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello")
        with pytest.raises(ValueError, match="Unsupported"):
            preprocess(f)


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_empty_ass_file(self, tmp_path):
        f = tmp_path / "empty.ass"
        f.write_text("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        result = preprocess(f)
        assert result == []

    def test_only_comments(self, tmp_path):
        content = """\
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Comment: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Only comments here
"""
        f = tmp_path / "comments.ass"
        f.write_text(content)
        result = preprocess(f)
        assert result == []

    def test_path_as_string(self):
        result = preprocess(str(FIXTURES / "simple.ass"))
        assert len(result) == 5

    def test_empty_srt(self, tmp_path):
        f = tmp_path / "empty.srt"
        f.write_text("")
        result = preprocess(f)
        assert result == []
