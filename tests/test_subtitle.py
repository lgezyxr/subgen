"""Subtitle module unit tests"""

from src.subtitle import (
    _format_time_srt,
    _format_time_vtt,
    _format_time_ass,
    _escape_ass_text,
    _escape_ffmpeg_filter_path,
)


class TestTimeFormatting:
    """Time formatting tests"""

    def test_format_time_srt_zero(self):
        assert _format_time_srt(0) == "00:00:00,000"

    def test_format_time_srt_simple(self):
        assert _format_time_srt(1.5) == "00:00:01,500"

    def test_format_time_srt_minutes(self):
        assert _format_time_srt(65.123) == "00:01:05,123"

    def test_format_time_srt_hours(self):
        assert _format_time_srt(3661.999) == "01:01:01,999"

    def test_format_time_srt_negative(self):
        """Negative numbers should return 0"""
        assert _format_time_srt(-5) == "00:00:00,000"

    def test_format_time_srt_rounding(self):
        """Test millisecond carry (999.9999... → 1000 → carry)"""
        # 59.9999 seconds should be handled correctly, not overflow to 60
        result = _format_time_srt(59.9999)
        assert result.startswith("00:00:59") or result == "00:01:00,000"

    def test_format_time_vtt_format(self):
        """VTT uses dot for milliseconds"""
        assert _format_time_vtt(1.5) == "00:00:01.500"

    def test_format_time_ass_format(self):
        """ASS uses centiseconds (2 digits)"""
        assert _format_time_ass(1.5) == "0:00:01.50"

    def test_format_time_ass_hours(self):
        """ASS hours only have 1 digit"""
        assert _format_time_ass(3600) == "1:00:00.00"


class TestTextEscaping:
    """Text escaping tests"""

    def test_escape_ass_backslash(self):
        # r"a\b" = 'a\b' (3 chars) → r"a\\b" = 'a\\b' (4 chars)
        assert _escape_ass_text(r"a\b") == r"a\\b"

    def test_escape_ass_braces(self):
        assert _escape_ass_text("{bold}") == r"\{bold\}"

    def test_escape_ass_newline(self):
        """ASS newline should be \\N"""
        assert _escape_ass_text("line1\nline2") == r"line1\Nline2"

    def test_escape_ass_combined(self):
        # Input: Hello\World + newline + {test}
        text = "Hello" + "\\" + "World\n{test}"
        # Output: Hello\\World\N\{test\}
        expected = r"Hello\\World\N\{test\}"
        assert _escape_ass_text(text) == expected

    def test_escape_ass_normal_text(self):
        """Normal text should remain unchanged"""
        assert _escape_ass_text("Hello World") == "Hello World"


class TestFFmpegPathEscaping:
    """FFmpeg path escaping tests"""

    def test_escape_backslash_to_forward(self):
        # Backslash to forward slash, but colon also needs escaping
        assert _escape_ffmpeg_filter_path("C:\\Users\\test") == r"C\:/Users/test"

    def test_escape_colon(self):
        assert _escape_ffmpeg_filter_path("C:/file") == r"C\:/file"

    def test_escape_single_quote(self):
        assert _escape_ffmpeg_filter_path("it's") == r"it\'s"

    def test_escape_brackets(self):
        assert _escape_ffmpeg_filter_path("file[1]") == r"file\[1\]"

    def test_escape_unix_path(self):
        """Unix paths only escape colon (if any)"""
        result = _escape_ffmpeg_filter_path("/home/user/video.srt")
        assert result == "/home/user/video.srt"
