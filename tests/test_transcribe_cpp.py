"""Tests for whisper.cpp backend (transcribe_cpp)."""

import json
import pytest

from src.transcribe_cpp import _parse_whisper_json, _timestamp_to_seconds


class TestTimestampToSeconds:
    def test_zero(self):
        assert _timestamp_to_seconds("00:00:00.000") == 0.0

    def test_seconds_only(self):
        assert _timestamp_to_seconds("00:00:05.500") == 5.5

    def test_minutes(self):
        assert _timestamp_to_seconds("00:02:30.000") == 150.0

    def test_hours(self):
        assert _timestamp_to_seconds("01:00:00.000") == 3600.0

    def test_complex(self):
        result = _timestamp_to_seconds("01:23:45.678")
        expected = 3600 + 23 * 60 + 45.678
        assert abs(result - expected) < 0.001


class TestParseWhisperJson:
    def test_basic(self):
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

    def test_empty_text_skipped(self):
        data = {
            "transcription": [
                {
                    "timestamps": {"from": "00:00:00.000", "to": "00:00:01.000"},
                    "text": "  ",
                    "tokens": [],
                }
            ]
        }
        segments = _parse_whisper_json(json.dumps(data))
        assert len(segments) == 0

    def test_with_tokens(self):
        data = {
            "transcription": [
                {
                    "timestamps": {"from": "00:00:00.000", "to": "00:00:02.000"},
                    "text": " Hello world",
                    "tokens": [
                        {
                            "text": " Hello",
                            "timestamps": {"from": "00:00:00.000", "to": "00:00:01.000"},
                        },
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
        assert len(segments[0].words) == 2
        assert segments[0].words[0].text == "Hello"
        assert segments[0].words[1].text == "world"
        assert segments[0].words[0].start == 0.0
        assert segments[0].words[1].end == 2.0

    def test_multiple_segments(self):
        data = {
            "transcription": [
                {
                    "timestamps": {"from": "00:00:00.000", "to": "00:00:02.000"},
                    "text": " First",
                    "tokens": [],
                },
                {
                    "timestamps": {"from": "00:00:02.500", "to": "00:00:05.000"},
                    "text": " Second",
                    "tokens": [],
                },
            ]
        }
        segments = _parse_whisper_json(json.dumps(data))
        assert len(segments) == 2
        assert segments[0].text == "First"
        assert segments[1].text == "Second"

    def test_no_speech_prob(self):
        data = {
            "transcription": [
                {
                    "timestamps": {"from": "00:00:00.000", "to": "00:00:01.000"},
                    "text": " Test",
                    "tokens": [],
                    "no_speech_prob": 0.42,
                }
            ]
        }
        segments = _parse_whisper_json(json.dumps(data))
        assert segments[0].no_speech_prob == 0.42

    def test_empty_transcription(self):
        data = {"transcription": []}
        segments = _parse_whisper_json(json.dumps(data))
        assert segments == []


class TestBpeTokenMerging:
    """Tests for BPE subword token merging and special token filtering."""

    def _make_segment(self, tokens):
        """Helper: wrap a token list into a minimal transcription payload."""
        return {
            "transcription": [
                {
                    "timestamps": {"from": "00:00:00.000", "to": "00:00:05.000"},
                    "text": " some text",
                    "tokens": tokens,
                }
            ]
        }

    def test_bpe_merge_two_fragments(self):
        """[' escal', 'ates'] should produce a single Word 'escalates'."""
        tokens = [
            {"text": " escal", "timestamps": {"from": "00:00:01.000", "to": "00:00:01.500"}},
            {"text": "ates", "timestamps": {"from": "00:00:01.500", "to": "00:00:02.000"}},
        ]
        segments = _parse_whisper_json(json.dumps(self._make_segment(tokens)))
        words = segments[0].words
        assert len(words) == 1
        assert words[0].text == "escalates"
        assert words[0].start == 1.0
        assert words[0].end == 2.0

    def test_special_token_filtered(self):
        """[_BEG_] token must not appear in words output."""
        tokens = [
            {"text": "[_BEG_]", "timestamps": {"from": "00:00:00.000", "to": "00:00:00.000"}},
            {"text": " Hello", "timestamps": {"from": "00:00:00.100", "to": "00:00:00.500"}},
        ]
        segments = _parse_whisper_json(json.dumps(self._make_segment(tokens)))
        words = segments[0].words
        assert all(w.text != "[_BEG_]" for w in words)
        assert len(words) == 1
        assert words[0].text == "Hello"

    def test_multi_word_with_bpe_suffix(self):
        """[' El', ' Men', 'cho'] -> words 'El', 'Mencho'."""
        tokens = [
            {"text": " El", "timestamps": {"from": "00:00:00.000", "to": "00:00:00.300"}},
            {"text": " Men", "timestamps": {"from": "00:00:00.400", "to": "00:00:00.700"}},
            {"text": "cho", "timestamps": {"from": "00:00:00.700", "to": "00:00:01.000"}},
        ]
        segments = _parse_whisper_json(json.dumps(self._make_segment(tokens)))
        words = segments[0].words
        assert len(words) == 2
        assert words[0].text == "El"
        assert words[0].start == 0.0
        assert words[0].end == 0.3
        assert words[1].text == "Mencho"
        assert words[1].start == 0.4
        assert words[1].end == 1.0

    def test_single_token_word_unchanged(self):
        """Single-token words (with leading space) must still work correctly."""
        tokens = [
            {"text": " Hello", "timestamps": {"from": "00:00:00.000", "to": "00:00:00.500"}},
            {"text": " world", "timestamps": {"from": "00:00:00.600", "to": "00:00:01.000"}},
        ]
        segments = _parse_whisper_json(json.dumps(self._make_segment(tokens)))
        words = segments[0].words
        assert len(words) == 2
        assert words[0].text == "Hello"
        assert words[1].text == "world"

    def test_various_special_tokens_filtered(self):
        """[_EOT_], [_SOT_], [_TT_250] etc. must all be filtered."""
        tokens = [
            {"text": "[_SOT_]", "timestamps": {"from": "00:00:00.000", "to": "00:00:00.000"}},
            {"text": " test", "timestamps": {"from": "00:00:00.100", "to": "00:00:00.400"}},
            {"text": "[_TT_250]", "timestamps": {"from": "00:00:00.400", "to": "00:00:00.400"}},
            {"text": "[_EOT_]", "timestamps": {"from": "00:00:00.400", "to": "00:00:00.400"}},
        ]
        segments = _parse_whisper_json(json.dumps(self._make_segment(tokens)))
        words = segments[0].words
        assert len(words) == 1
        assert words[0].text == "test"

    def test_bpe_fragment_no_leading_space_at_start(self):
        """A fragment without a leading space as the first token starts a word."""
        tokens = [
            {"text": "Hello", "timestamps": {"from": "00:00:00.000", "to": "00:00:00.400"}},
            {"text": " world", "timestamps": {"from": "00:00:00.500", "to": "00:00:01.000"}},
        ]
        segments = _parse_whisper_json(json.dumps(self._make_segment(tokens)))
        words = segments[0].words
        assert len(words) == 2
        assert words[0].text == "Hello"
        assert words[1].text == "world"
