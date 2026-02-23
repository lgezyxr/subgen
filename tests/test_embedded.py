"""Tests for embedded subtitle detection and extraction."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from src.embedded import (
    normalize_language,
    SubtitleTrack,
    detect_subtitle_tracks,
    find_best_subtitle_track,
    check_embedded_subtitles,
)


class TestNormalizeLanguage:
    """Tests for language code normalization."""
    
    def test_common_codes(self):
        assert normalize_language('eng') == 'en'
        assert normalize_language('jpn') == 'ja'
        assert normalize_language('chi') == 'zh'
        assert normalize_language('kor') == 'ko'
    
    def test_short_codes(self):
        assert normalize_language('en') == 'en'
        assert normalize_language('ja') == 'ja'
        assert normalize_language('zh') == 'zh'
    
    def test_case_insensitive(self):
        assert normalize_language('ENG') == 'en'
        assert normalize_language('JPN') == 'ja'
    
    def test_undefined(self):
        assert normalize_language('und') is None
        assert normalize_language(None) is None
        assert normalize_language('') is None
    
    def test_unknown_keeps_first_two(self):
        assert normalize_language('xyz') == 'xy'


class TestFindBestSubtitleTrack:
    """Tests for finding the best subtitle track."""
    
    def make_track(self, lang, codec='subrip', is_default=False):
        return SubtitleTrack(
            index=0,
            stream_index=0,
            codec=codec,
            language=lang,
            title=None,
            is_text=codec in ('subrip', 'ass'),
            is_default=is_default,
            is_forced=False
        )
    
    def test_empty_tracks(self):
        track, reason = find_best_subtitle_track([], 'en', 'zh')
        assert track is None
        assert reason == 'none'
    
    def test_target_exists(self):
        tracks = [
            self.make_track('en'),
            self.make_track('zh'),
        ]
        track, reason = find_best_subtitle_track(tracks, 'en', 'zh')
        assert track.language == 'zh'
        assert reason == 'target_exists'
    
    def test_single_track(self):
        tracks = [self.make_track('en')]
        track, reason = find_best_subtitle_track(tracks, 'en', 'zh')
        assert track.language == 'en'
        assert reason == 'single_track'
    
    def test_source_match(self):
        tracks = [
            self.make_track('en'),
            self.make_track('ja'),
        ]
        track, reason = find_best_subtitle_track(tracks, 'en', 'zh')
        assert track.language == 'en'
        assert reason == 'source_match'
    
    def test_default_track(self):
        tracks = [
            self.make_track('en', is_default=False),
            self.make_track('ja', is_default=True),
        ]
        track, reason = find_best_subtitle_track(tracks, 'ko', 'zh')
        assert track.language == 'ja'
        assert reason == 'default_track'
    
    def test_image_subtitles_excluded(self):
        tracks = [
            self.make_track('en', codec='hdmv_pgs_subtitle'),  # PGS (image)
        ]
        track, reason = find_best_subtitle_track(tracks, 'en', 'zh')
        assert track is None
        assert reason == 'none'


class TestCheckEmbeddedSubtitles:
    """Tests for the main check function."""
    
    @patch('src.embedded.detect_subtitle_tracks')
    @patch('src.embedded.detect_video_language')
    def test_no_subtitles(self, mock_video_lang, mock_detect):
        mock_detect.return_value = []
        mock_video_lang.return_value = 'en'
        
        result = check_embedded_subtitles(Path('test.mkv'), 'auto', 'zh')
        
        assert result['action'] == 'transcribe'
        assert result['track'] is None
    
    @patch('src.embedded.detect_subtitle_tracks')
    @patch('src.embedded.detect_video_language')
    def test_target_exists(self, mock_video_lang, mock_detect):
        mock_detect.return_value = [
            SubtitleTrack(0, 0, 'subrip', 'zh', None, True, False, False)
        ]
        mock_video_lang.return_value = 'en'
        
        result = check_embedded_subtitles(Path('test.mkv'), 'en', 'zh')
        
        assert result['action'] == 'use_target'
        assert result['track'].language == 'zh'
    
    @patch('src.embedded.detect_subtitle_tracks')
    @patch('src.embedded.detect_video_language')
    def test_use_source(self, mock_video_lang, mock_detect):
        mock_detect.return_value = [
            SubtitleTrack(0, 0, 'subrip', 'en', None, True, False, False)
        ]
        mock_video_lang.return_value = 'en'
        
        result = check_embedded_subtitles(Path('test.mkv'), 'en', 'zh')
        
        assert result['action'] == 'use_source'
        assert result['track'].language == 'en'
