"""Comprehensive tests for benchmark.scripts.translation_eval.

All HTTP calls to copilot-api are mocked to avoid real network requests.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from benchmark.scripts.translation_eval import (
    _aggregate_scores,
    _batch_triples,
    _build_prompt,
    _call_llm,
    _detect_language,
    _parse_response,
    evaluate_translation,
)


# ===================================================================
# Unit tests — _build_prompt
# ===================================================================


class TestBuildPrompt:
    def test_contains_triples(self):
        triples = [
            ("こんにちは", "Hello", "Hi"),
            ("ありがとう", "Thank you", "Thanks"),
        ]
        prompt = _build_prompt(triples, "Japanese", "English")
        assert "こんにちは" in prompt
        assert "Hello" in prompt
        assert "Hi" in prompt
        assert "ありがとう" in prompt
        assert "Thank you" in prompt
        assert "Thanks" in prompt

    def test_contains_languages(self):
        triples = [("src", "ref", "gen")]
        prompt = _build_prompt(triples, "Japanese", "English")
        assert "Japanese" in prompt
        assert "English" in prompt

    def test_contains_scoring_dimensions(self):
        triples = [("src", "ref", "gen")]
        prompt = _build_prompt(triples, "Japanese", "English")
        assert "accuracy" in prompt
        assert "naturalness" in prompt
        assert "terminology" in prompt
        assert "cultural_adaptation" in prompt

    def test_requests_json_output(self):
        triples = [("src", "ref", "gen")]
        prompt = _build_prompt(triples, "Japanese", "English")
        assert "JSON" in prompt

    def test_segment_numbering(self):
        triples = [("a", "b", "c"), ("d", "e", "f"), ("g", "h", "i")]
        prompt = _build_prompt(triples, "Source", "Target")
        assert "Segment 1" in prompt
        assert "Segment 2" in prompt
        assert "Segment 3" in prompt

    def test_labels_source_reference_generated(self):
        triples = [("source_text", "ref_text", "gen_text")]
        prompt = _build_prompt(triples, "Japanese", "English")
        assert "Source" in prompt
        assert "Reference" in prompt
        assert "Generated" in prompt

    def test_proper_structure(self):
        triples = [("src", "ref", "gen")]
        prompt = _build_prompt(triples, "Japanese", "English")
        # Should contain evaluation instructions
        assert "evaluator" in prompt.lower() or "evaluate" in prompt.lower()
        # Should mention scale
        assert "1-10" in prompt or "scale" in prompt.lower()


# ===================================================================
# Unit tests — _batch_triples
# ===================================================================


class TestBatchTriples:
    def test_exact_batch_size(self):
        triples = [("a", "b", "c")] * 20
        batches = _batch_triples(triples, batch_size=20)
        assert len(batches) == 1
        assert len(batches[0]) == 20

    def test_multiple_batches(self):
        triples = [("a", "b", "c")] * 45
        batches = _batch_triples(triples, batch_size=20)
        assert len(batches) == 3
        assert len(batches[0]) == 20
        assert len(batches[1]) == 20
        assert len(batches[2]) == 5

    def test_empty_filtering(self):
        triples = [
            ("a", "b", "c"),
            ("", "", ""),       # all empty → filtered
            ("  ", " ", "  "),  # whitespace-only → filtered
            ("d", "e", "f"),
        ]
        batches = _batch_triples(triples, batch_size=20)
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_empty_input(self):
        assert _batch_triples([]) == []

    def test_all_empty_triples(self):
        triples = [("", "", ""), ("  ", " ", "")]
        assert _batch_triples(triples) == []

    def test_single_item(self):
        triples = [("a", "b", "c")]
        batches = _batch_triples(triples, batch_size=20)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_custom_batch_size(self):
        triples = [("a", "b", "c")] * 10
        batches = _batch_triples(triples, batch_size=3)
        assert len(batches) == 4  # 3, 3, 3, 1
        assert len(batches[3]) == 1


# ===================================================================
# Unit tests — _parse_response
# ===================================================================


class TestParseResponse:
    def test_valid_json(self):
        response = json.dumps({
            "accuracy": 8.5,
            "naturalness": 7.0,
            "terminology": 9.0,
            "cultural_adaptation": 6.5,
        })
        result = _parse_response(response)
        assert result is not None
        assert result["accuracy"] == pytest.approx(8.5)
        assert result["naturalness"] == pytest.approx(7.0)
        assert result["terminology"] == pytest.approx(9.0)
        assert result["cultural_adaptation"] == pytest.approx(6.5)

    def test_json_with_extra_text(self):
        response = (
            'Here is my evaluation:\n'
            '{"accuracy": 8.0, "naturalness": 7.0, '
            '"terminology": 9.0, "cultural_adaptation": 6.0}\n'
            'I hope this helps!'
        )
        result = _parse_response(response)
        assert result is not None
        assert result["accuracy"] == pytest.approx(8.0)

    def test_malformed_json(self):
        result = _parse_response("this is not json at all")
        assert result is None

    def test_missing_keys(self):
        response = json.dumps({"accuracy": 8.0, "naturalness": 7.0})
        result = _parse_response(response)
        assert result is None

    def test_json_with_whitespace(self):
        response = '  \n  {"accuracy": 8.0, "naturalness": 7.0, "terminology": 9.0, "cultural_adaptation": 6.0}  \n  '
        result = _parse_response(response)
        assert result is not None

    def test_integer_values_converted_to_float(self):
        response = json.dumps({
            "accuracy": 8,
            "naturalness": 7,
            "terminology": 9,
            "cultural_adaptation": 6,
        })
        result = _parse_response(response)
        assert result is not None
        assert isinstance(result["accuracy"], float)

    def test_empty_string(self):
        result = _parse_response("")
        assert result is None

    def test_empty_json_object(self):
        result = _parse_response("{}")
        assert result is None


# ===================================================================
# Unit tests — _aggregate_scores
# ===================================================================


class TestAggregateScores:
    def test_single_batch(self):
        scores = [{"accuracy": 8.0, "naturalness": 7.0, "terminology": 9.0, "cultural_adaptation": 6.0}]
        result = _aggregate_scores(scores)
        assert result["accuracy"] == pytest.approx(8.0)
        assert result["naturalness"] == pytest.approx(7.0)
        assert result["terminology"] == pytest.approx(9.0)
        assert result["cultural_adaptation"] == pytest.approx(6.0)
        # composite = 0.4*8 + 0.3*7 + 0.15*9 + 0.15*6 = 3.2 + 2.1 + 1.35 + 0.9 = 7.55
        assert result["composite"] == pytest.approx(7.55)

    def test_multiple_batches_averaged(self):
        scores = [
            {"accuracy": 8.0, "naturalness": 6.0, "terminology": 8.0, "cultural_adaptation": 6.0},
            {"accuracy": 6.0, "naturalness": 8.0, "terminology": 6.0, "cultural_adaptation": 8.0},
        ]
        result = _aggregate_scores(scores)
        assert result["accuracy"] == pytest.approx(7.0)
        assert result["naturalness"] == pytest.approx(7.0)
        assert result["terminology"] == pytest.approx(7.0)
        assert result["cultural_adaptation"] == pytest.approx(7.0)
        # composite = 0.4*7 + 0.3*7 + 0.15*7 + 0.15*7 = 7.0
        assert result["composite"] == pytest.approx(7.0)

    def test_empty_input(self):
        result = _aggregate_scores([])
        assert result["composite"] == pytest.approx(0.0)

    def test_weighted_average_math(self):
        """Verify the exact weight formula."""
        scores = [{"accuracy": 10.0, "naturalness": 10.0, "terminology": 10.0, "cultural_adaptation": 10.0}]
        result = _aggregate_scores(scores)
        # All 10s → composite = 0.4*10 + 0.3*10 + 0.15*10 + 0.15*10 = 10.0
        assert result["composite"] == pytest.approx(10.0)

    def test_weights_sum_to_one(self):
        """Verify weights: 0.4 + 0.3 + 0.15 + 0.15 = 1.0."""
        scores = [{"accuracy": 1.0, "naturalness": 1.0, "terminology": 1.0, "cultural_adaptation": 1.0}]
        result = _aggregate_scores(scores)
        assert result["composite"] == pytest.approx(1.0)


# ===================================================================
# Unit tests — _detect_language
# ===================================================================


class TestDetectLanguage:
    def test_english_text(self):
        pairs = [
            ({}, {"source": "Hello world, how are you?"}),
            ({}, {"source": "This is a test sentence."}),
        ]
        assert _detect_language(pairs, "source") == "English"

    def test_chinese_text(self):
        pairs = [
            ({}, {"source": "你好世界"}),
            ({}, {"source": "今天天气很好"}),
        ]
        assert _detect_language(pairs, "source") == "Chinese"

    def test_japanese_text(self):
        pairs = [
            ({}, {"source": "こんにちは世界"}),
            ({}, {"source": "ありがとうございます"}),
        ]
        assert _detect_language(pairs, "source") == "Japanese"

    def test_korean_text(self):
        pairs = [
            ({}, {"source": "안녕하세요"}),
            ({}, {"source": "감사합니다"}),
        ]
        assert _detect_language(pairs, "source") == "Korean"

    def test_empty_pairs(self):
        assert _detect_language([], "source") == "English"

    def test_translation_field(self):
        pairs = [
            ({}, {"translation": "你好世界"}),
        ]
        assert _detect_language(pairs, "translation") == "Chinese"

    def test_missing_field(self):
        pairs = [({}, {"other": "text"})]
        assert _detect_language(pairs, "source") == "English"


# ===================================================================
# Unit tests — _call_llm (mocked)
# ===================================================================


class TestCallLlm:
    @patch("benchmark.scripts.translation_eval.httpx")
    def test_successful_call(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": '{"accuracy": 8.0}'}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response

        result = _call_llm("test prompt")
        assert result == '{"accuracy": 8.0}'
        mock_httpx.post.assert_called_once()

    @patch("benchmark.scripts.translation_eval.httpx")
    def test_connection_error(self, mock_httpx):
        mock_httpx.HTTPError = Exception
        mock_httpx.TimeoutException = Exception
        mock_httpx.post.side_effect = ConnectionError("Connection refused")

        result = _call_llm("test prompt")
        assert result is None

    @patch("benchmark.scripts.translation_eval.httpx")
    def test_timeout(self, mock_httpx):
        mock_httpx.HTTPError = Exception
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
        mock_httpx.post.side_effect = mock_httpx.TimeoutException("timeout")

        result = _call_llm("test prompt")
        assert result is None

    @patch("benchmark.scripts.translation_eval.httpx")
    def test_http_error(self, mock_httpx):
        mock_httpx.HTTPError = type("HTTPError", (Exception,), {})
        mock_httpx.TimeoutException = Exception
        mock_httpx.post.side_effect = mock_httpx.HTTPError("500 Server Error")

        result = _call_llm("test prompt")
        assert result is None

    @patch("benchmark.scripts.translation_eval.httpx")
    def test_empty_content(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": []}
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response

        result = _call_llm("test prompt")
        assert result is None

    @patch("benchmark.scripts.translation_eval.httpx")
    def test_uses_correct_model(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": "response"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response

        _call_llm("test prompt")
        call_args = mock_httpx.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert payload["model"] == "claude-opus-4.6"

    @patch("benchmark.scripts.translation_eval.httpx")
    def test_uses_correct_endpoint(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": "response"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response

        _call_llm("test prompt")
        call_args = mock_httpx.post.call_args
        url = call_args[0][0]
        assert url == "http://localhost:4141/v1/messages"


# ===================================================================
# Integration test — evaluate_translation (mocked LLM)
# ===================================================================


class TestEvaluateTranslation:
    @patch("benchmark.scripts.translation_eval._call_llm")
    def test_basic_evaluation(self, mock_call):
        mock_call.return_value = json.dumps({
            "accuracy": 8.0,
            "naturalness": 7.0,
            "terminology": 9.0,
            "cultural_adaptation": 6.0,
        })

        pairs = [
            (
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
            ),
        ]
        result = evaluate_translation(pairs)
        assert result is not None
        assert "composite" in result
        assert result["accuracy"] == pytest.approx(8.0)

    @patch("benchmark.scripts.translation_eval._call_llm")
    def test_lyrics_excluded(self, mock_call):
        mock_call.return_value = json.dumps({
            "accuracy": 8.0,
            "naturalness": 7.0,
            "terminology": 9.0,
            "cultural_adaptation": 6.0,
        })

        pairs = [
            (
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
            ),
            (
                {"source": "La la la", "translation": "啦啦啦", "type": "lyrics"},
                {"source": "La la la", "translation": "啦啦啦", "type": "lyrics"},
            ),
        ]
        result = evaluate_translation(pairs)
        assert result is not None
        # LLM should only be called once (only dialogue pairs)
        mock_call.assert_called_once()

    @patch("benchmark.scripts.translation_eval._call_llm")
    def test_llm_failure_returns_none(self, mock_call):
        mock_call.return_value = None

        pairs = [
            (
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
            ),
        ]
        result = evaluate_translation(pairs)
        assert result is None

    def test_no_dialogue_returns_none(self):
        pairs = [
            (
                {"source": "La la", "translation": "啦啦", "type": "lyrics"},
                {"source": "La la", "translation": "啦啦", "type": "lyrics"},
            ),
        ]
        result = evaluate_translation(pairs)
        assert result is None

    def test_empty_pairs_returns_none(self):
        result = evaluate_translation([])
        assert result is None

    @patch("benchmark.scripts.translation_eval._call_llm")
    def test_malformed_response_returns_none(self, mock_call):
        mock_call.return_value = "This is not JSON at all"

        pairs = [
            (
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
                {"source": "Hello", "translation": "你好", "type": "dialogue"},
            ),
        ]
        result = evaluate_translation(pairs)
        assert result is None

    @patch("benchmark.scripts.translation_eval._call_llm")
    def test_auto_language_detection(self, mock_call):
        mock_call.return_value = json.dumps({
            "accuracy": 8.0,
            "naturalness": 7.0,
            "terminology": 9.0,
            "cultural_adaptation": 6.0,
        })

        pairs = [
            (
                {"source": "こんにちは", "translation": "Hello", "type": "dialogue"},
                {"source": "こんにちは", "translation": "Hello", "type": "dialogue"},
            ),
        ]
        result = evaluate_translation(pairs, source_lang="auto", target_lang="auto")
        assert result is not None
        # Prompt should have been built with detected languages
        call_args = mock_call.call_args[0][0]
        assert "Japanese" in call_args or "Chinese" in call_args
