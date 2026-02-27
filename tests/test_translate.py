"""Translation module unit tests"""

import sys
import types

import pytest

from src.translate import _parse_translations
from src.transcribe import Segment, Word


class TestParseTranslations:
    """Translation result parsing tests"""

    def test_exact_match(self):
        """Line count matches exactly"""
        result = _parse_translations("Hello\nWorld\nTest", 3)
        assert result == ["Hello", "World", "Test"]

    def test_fewer_lines_padded(self):
        """Fewer lines should be padded with empty strings"""
        result = _parse_translations("Hello\nWorld", 4)
        assert len(result) == 4
        assert result[0] == "Hello"
        assert result[1] == "World"
        assert result[2] == ""
        assert result[3] == ""

    def test_more_lines_truncated(self):
        """More lines should be truncated"""
        result = _parse_translations("One\nTwo\nThree\nFour\nFive", 3)
        assert len(result) == 3
        assert result == ["One", "Two", "Three"]

    def test_empty_lines_preserved(self):
        """Empty lines should preserve their position"""
        result = _parse_translations("First line\n\nThird line", 3)
        assert len(result) == 3
        assert result[0] == "First line"
        assert result[1] == ""
        assert result[2] == "Third line"

    def test_numbered_prefix_removed(self):
        """Remove number prefixes like 1. 2."""
        result = _parse_translations("1. Hello\n2. World", 2)
        assert result == ["Hello", "World"]

    def test_numbered_prefix_parenthesis(self):
        """Remove number prefixes like 1) 2)"""
        result = _parse_translations("1) Hello\n2) World", 2)
        assert result == ["Hello", "World"]

    def test_numbered_prefix_chinese(self):
        """Remove Chinese number prefixes like 1、2、"""
        result = _parse_translations("1、你好\n2、世界", 2)
        assert result == ["你好", "世界"]

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped"""
        result = _parse_translations("  Hello  \n  World  ", 2)
        assert result == ["Hello", "World"]

    def test_empty_input(self):
        """Empty input"""
        result = _parse_translations("", 3)
        assert len(result) == 3
        assert all(line == "" for line in result)

    def test_single_line(self):
        """Single line input"""
        result = _parse_translations("Only one line", 1)
        assert result == ["Only one line"]

    def test_no_strip_overall(self):
        """Should not strip overall causing first empty line loss"""
        # If LLM returns "\nHello\nWorld", first line is empty
        result = _parse_translations("\nHello\nWorld", 3)
        assert len(result) == 3
        assert result[0] == ""
        assert result[1] == "Hello"
        assert result[2] == "World"


class TestNormalizeTextForLlm:
    """Tests for text normalization before LLM translation."""

    def test_newline_replaced_with_br(self):
        from src.translate import _normalize_text_for_llm
        assert _normalize_text_for_llm("Line1\nLine2") == "Line1 <BR> Line2"

    def test_multiple_newlines(self):
        from src.translate import _normalize_text_for_llm
        assert _normalize_text_for_llm("A\nB\nC") == "A <BR> B <BR> C"

    def test_no_newline(self):
        from src.translate import _normalize_text_for_llm
        assert _normalize_text_for_llm("Single line") == "Single line"

    def test_whitespace_stripped(self):
        from src.translate import _normalize_text_for_llm
        assert _normalize_text_for_llm("  text  ") == "text"


class TestRestoreLineBreaks:
    """Tests for restoring line breaks from LLM output."""

    def test_br_to_newline(self):
        from src.translate import _restore_line_breaks
        assert _restore_line_breaks("Line1 <BR> Line2") == "Line1\nLine2"

    def test_lowercase_br(self):
        from src.translate import _restore_line_breaks
        assert _restore_line_breaks("Line1 <br> Line2") == "Line1\nLine2"

    def test_no_br(self):
        from src.translate import _restore_line_breaks
        assert _restore_line_breaks("Single line") == "Single line"

    def test_cleans_spaces_around_newlines(self):
        from src.translate import _restore_line_breaks
        assert _restore_line_breaks("A  <BR>  B") == "A\nB"


class TestProgressCallbacks:
    def test_translate_segments_progress_is_cumulative(self, monkeypatch):
        from src.translate import translate_segments

        segments = [
            Segment(start=0.0, end=1.0, text="A"),
            Segment(start=1.0, end=2.0, text="B"),
            Segment(start=2.0, end=3.0, text="C"),
        ]

        def fake_translate(texts, *_args, **_kwargs):
            return [f"T:{t}" for t in texts]

        monkeypatch.setattr("src.translate._translate_openai", fake_translate)
        progress = []
        config = {
            "translation": {"provider": "openai"},
            "output": {"source_language": "en", "target_language": "zh", "max_chars_per_line": 40},
            "advanced": {"translation_batch_size": 2},
        }

        translate_segments(segments, config, progress_callback=progress.append)
        assert progress == [2, 3]

    def test_sentence_aware_progress_is_cumulative(self):
        from src.translate import translate_segments_sentence_aware

        segments = [
            Segment(start=0.0, end=1.0, text="A."),
            Segment(start=1.0, end=2.0, text="B."),
            Segment(start=2.0, end=3.0, text="C."),
        ]
        progress = []
        config = {
            "translation": {"provider": "openai"},
            "output": {"source_language": "en", "target_language": "zh", "max_chars_per_line": 40},
        }

        def fake_translate(texts, *_args, **_kwargs):
            return [f"T:{texts[0]}"]

        translate_segments_sentence_aware(
            segments,
            config,
            translate_fn=fake_translate,
            progress_callback=progress.append,
        )
        assert progress == [1, 2, 3]

    def test_proofread_progress_is_cumulative(self, monkeypatch):
        from src.translate import proofread_translations

        segments = [
            Segment(start=0.0, end=1.0, text="A", translated="甲"),
            Segment(start=1.0, end=2.0, text="B", translated="乙"),
            Segment(start=2.0, end=3.0, text="C", translated="丙"),
        ]
        config = {
            "translation": {"provider": "openai", "api_key": "k", "model": "gpt-4o-mini"},
            "output": {"source_language": "en", "target_language": "zh"},
            "advanced": {"proofread_batch_size": 2},
        }
        progress = []

        monkeypatch.setattr("src.translate._call_llm_for_proofread", lambda *_args, **_kwargs: "")
        proofread_translations(segments, config, progress_callback=progress.append)
        assert progress == [2, 3]


class TestWordAlignment:
    def test_trailing_words_are_preserved(self, monkeypatch):
        from src.translate import _translate_with_word_alignment

        words = [
            Word(text="one", start=0.0, end=0.5),
            Word(text="two", start=0.5, end=1.0),
            Word(text="three", start=1.0, end=1.5),
        ]
        group = [Segment(start=0.0, end=1.5, text="one two three", words=words)]

        monkeypatch.setattr(
            "src.translate._translate_sentence_group",
            lambda *_args, **_kwargs: ["uno dos | end: 1"],
        )
        out = _translate_with_word_alignment(
            group=group,
            all_words=words,
            source_lang="en",
            target_lang="es",
            max_chars=40,
            config={"translation": {"provider": "openai"}},
        )

        assert len(out) == 2
        assert out[0].text == "one two"
        assert out[1].text == "three"


class TestProofreadConfigFallback:
    @pytest.mark.parametrize(
        "provider,header_key,expected_url",
        [
            ("openai", "Authorization", "https://api.openai.com/v1/chat/completions"),
            ("claude", "x-api-key", "https://api.anthropic.com/v1/messages"),
            ("deepseek", "Authorization", "https://api.deepseek.com/v1/chat/completions"),
        ],
    )
    def test_proofread_uses_shared_translation_key_and_model_fallback(
        self, monkeypatch, provider, header_key, expected_url
    ):
        from src.translate import _call_llm_for_proofread
        import requests

        captured = {}

        class FakeResponse:
            ok = True
            status_code = 200

            def json(self):
                if provider == "claude":
                    return {"content": [{"text": "ok"}]}
                return {"choices": [{"message": {"content": "ok"}}]}

        def fake_post(url, headers=None, json=None, timeout=None, **_kwargs):
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["json"] = json or {}
            captured["timeout"] = timeout
            return FakeResponse()

        monkeypatch.setattr(requests, "post", fake_post)
        cfg = {
            "translation": {
                "provider": provider,
                "api_key": "shared-key",
                "model": "shared-model",
            }
        }
        result = _call_llm_for_proofread("system", "user", cfg)

        assert result == "ok"
        assert captured["url"] == expected_url
        assert captured["json"]["model"] == "shared-model"
        if header_key == "Authorization":
            assert captured["headers"]["Authorization"] == "Bearer shared-key"
        else:
            assert captured["headers"][header_key] == "shared-key"

    def test_model_settings_falls_back_to_shared_model(self):
        from src.translate import _get_model_settings

        settings = _get_model_settings(
            {"translation": {"provider": "openai", "model": "gpt-3.5-turbo"}}
        )
        assert settings["batch_size"] == 20
        assert settings["context_chars"] == 4000


class TestTranslationConfigSafety:
    def test_translate_openai_missing_translation_does_not_keyerror(self, monkeypatch):
        from src.translate import _translate_openai

        monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="OpenAI API Key not configured"):
            _translate_openai(["hello"], "en", "zh", 40, {})

    def test_translate_claude_missing_translation_does_not_keyerror(self, monkeypatch):
        from src.translate import _translate_claude

        monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=object))
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(ValueError, match="Anthropic API Key not configured"):
            _translate_claude(["hello"], "en", "zh", 40, {})

    def test_translate_deepseek_missing_translation_does_not_keyerror(self, monkeypatch):
        from src.translate import _translate_deepseek

        monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        with pytest.raises(ValueError, match="DeepSeek API Key not configured"):
            _translate_deepseek(["hello"], "en", "zh", 40, {})

    def test_translate_ollama_missing_translation_uses_defaults(self, monkeypatch):
        from src.translate import _translate_ollama

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"message": {"content": "你好"}}

        class FakeHttpx:
            class ConnectError(Exception):
                pass

            @staticmethod
            def post(_url, json=None, timeout=None):
                assert json["model"] == "qwen2.5:14b"
                return FakeResponse()

        monkeypatch.setitem(sys.modules, "httpx", FakeHttpx)
        out = _translate_ollama(["hello"], "en", "zh", 40, {})
        assert out == ["你好"]
