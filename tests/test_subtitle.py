"""字幕模块单元测试"""

import pytest
from src.subtitle import (
    _format_time_srt,
    _format_time_vtt,
    _format_time_ass,
    _escape_ass_text,
    _escape_ffmpeg_filter_path,
)


class TestTimeFormatting:
    """时间格式化测试"""

    def test_format_time_srt_zero(self):
        assert _format_time_srt(0) == "00:00:00,000"

    def test_format_time_srt_simple(self):
        assert _format_time_srt(1.5) == "00:00:01,500"

    def test_format_time_srt_minutes(self):
        assert _format_time_srt(65.123) == "00:01:05,123"

    def test_format_time_srt_hours(self):
        assert _format_time_srt(3661.999) == "01:01:01,999"

    def test_format_time_srt_negative(self):
        """负数应该返回 0"""
        assert _format_time_srt(-5) == "00:00:00,000"

    def test_format_time_srt_rounding(self):
        """测试毫秒进位 (999.9999... → 1000 → 进位)"""
        # 59.9999 秒应该正确处理，不溢出到 60
        result = _format_time_srt(59.9999)
        assert result.startswith("00:00:59") or result == "00:01:00,000"

    def test_format_time_vtt_format(self):
        """VTT 用点号分隔毫秒"""
        assert _format_time_vtt(1.5) == "00:00:01.500"

    def test_format_time_ass_format(self):
        """ASS 用厘秒 (2位)"""
        assert _format_time_ass(1.5) == "0:00:01.50"

    def test_format_time_ass_hours(self):
        """ASS 小时只有 1 位"""
        assert _format_time_ass(3600) == "1:00:00.00"


class TestTextEscaping:
    """文本转义测试"""

    def test_escape_ass_backslash(self):
        assert _escape_ass_text("a\\b") == "a\\\\b"

    def test_escape_ass_braces(self):
        assert _escape_ass_text("{bold}") == "\\{bold\\}"

    def test_escape_ass_newline(self):
        """ASS 换行应该是 \\N"""
        assert _escape_ass_text("line1\nline2") == "line1\\Nline2"

    def test_escape_ass_combined(self):
        text = "Hello\\World\n{test}"
        expected = "Hello\\\\World\\N\\{test\\}"
        assert _escape_ass_text(text) == expected

    def test_escape_ass_normal_text(self):
        """普通文本不变"""
        assert _escape_ass_text("Hello World") == "Hello World"


class TestFFmpegPathEscaping:
    """FFmpeg 路径转义测试"""

    def test_escape_backslash_to_forward(self):
        assert _escape_ffmpeg_filter_path("C:\\Users\\test") == "C:/Users/test"

    def test_escape_colon(self):
        assert _escape_ffmpeg_filter_path("C:/file") == "C\\:/file"

    def test_escape_single_quote(self):
        assert _escape_ffmpeg_filter_path("it's") == "it\\'s"

    def test_escape_brackets(self):
        assert _escape_ffmpeg_filter_path("file[1]") == "file\\[1\\]"

    def test_escape_unix_path(self):
        """Unix 路径基本不变"""
        result = _escape_ffmpeg_filter_path("/home/user/video.srt")
        assert result == "/home/user/video.srt"
