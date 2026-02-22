"""音频模块单元测试"""

import pytest
from unittest.mock import patch
from src.audio import check_ffmpeg, check_ffprobe


class TestFFmpegCheck:
    """FFmpeg/FFprobe 检查测试"""

    @patch('shutil.which')
    def test_ffmpeg_found(self, mock_which):
        mock_which.return_value = '/usr/bin/ffmpeg'
        assert check_ffmpeg() is True
        mock_which.assert_called_with('ffmpeg')

    @patch('shutil.which')
    def test_ffmpeg_not_found(self, mock_which):
        mock_which.return_value = None
        assert check_ffmpeg() is False

    @patch('shutil.which')
    def test_ffprobe_found(self, mock_which):
        mock_which.return_value = '/usr/bin/ffprobe'
        assert check_ffprobe() is True
        mock_which.assert_called_with('ffprobe')

    @patch('shutil.which')
    def test_ffprobe_not_found(self, mock_which):
        mock_which.return_value = None
        assert check_ffprobe() is False
