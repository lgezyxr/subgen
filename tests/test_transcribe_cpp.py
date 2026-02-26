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
