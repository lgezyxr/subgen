"""Comprehensive tests for benchmark.scripts.asr_eval."""

from __future__ import annotations

import pytest

from benchmark.scripts.asr_eval import (
    align_segments,
    compute_cer,
    compute_timestamp_metrics,
    compute_wer,
    detect_metric_type,
    evaluate_asr,
    temporal_overlap,
    text_similarity,
)


# ===================================================================
# Unit tests — temporal_overlap (IoU)
# ===================================================================


class TestTemporalOverlap:
    def test_identical_segments(self):
        seg = {"start": 1.0, "end": 3.0}
        assert temporal_overlap(seg, seg) == pytest.approx(1.0)

    def test_no_overlap(self):
        a = {"start": 1.0, "end": 2.0}
        b = {"start": 3.0, "end": 4.0}
        assert temporal_overlap(a, b) == pytest.approx(0.0)

    def test_partial_overlap(self):
        a = {"start": 1.0, "end": 3.0}
        b = {"start": 2.0, "end": 4.0}
        # intersection = 1.0 (2-3), union = 3.0 (1-4)
        assert temporal_overlap(a, b) == pytest.approx(1.0 / 3.0)

    def test_contained_segment(self):
        outer = {"start": 0.0, "end": 10.0}
        inner = {"start": 3.0, "end": 7.0}
        # intersection = 4.0, union = 10.0
        assert temporal_overlap(outer, inner) == pytest.approx(0.4)

    def test_adjacent_segments(self):
        a = {"start": 1.0, "end": 2.0}
        b = {"start": 2.0, "end": 3.0}
        # intersection = 0.0, union = 2.0
        assert temporal_overlap(a, b) == pytest.approx(0.0)

    def test_symmetric(self):
        a = {"start": 1.0, "end": 4.0}
        b = {"start": 2.0, "end": 5.0}
        assert temporal_overlap(a, b) == pytest.approx(temporal_overlap(b, a))

    def test_zero_duration_segment(self):
        a = {"start": 1.0, "end": 1.0}
        b = {"start": 1.0, "end": 3.0}
        # intersection = 0, union = 2
        assert temporal_overlap(a, b) == pytest.approx(0.0)

    def test_large_overlap(self):
        a = {"start": 0.0, "end": 10.0}
        b = {"start": 1.0, "end": 9.0}
        # intersection = 8.0, union = 10.0
        assert temporal_overlap(a, b) == pytest.approx(0.8)


# ===================================================================
# Unit tests — text_similarity
# ===================================================================


class TestTextSimilarity:
    def test_identical_strings(self):
        assert text_similarity("Hello world", "Hello world") == pytest.approx(1.0)

    def test_empty_strings(self):
        assert text_similarity("", "") == pytest.approx(0.0)

    def test_one_empty(self):
        assert text_similarity("Hello", "") == pytest.approx(0.0)

    def test_partial_match(self):
        sim = text_similarity("Hello world", "Hello there")
        assert 0.0 < sim < 1.0

    def test_completely_different(self):
        sim = text_similarity("abc", "xyz")
        assert sim == pytest.approx(0.0)

    def test_case_sensitive(self):
        sim = text_similarity("Hello", "hello")
        # SequenceMatcher is case-sensitive
        assert sim < 1.0

    def test_single_char_match(self):
        sim = text_similarity("a", "a")
        assert sim == pytest.approx(1.0)


# ===================================================================
# Unit tests — detect_metric_type
# ===================================================================


class TestDetectMetricType:
    def test_english_text(self):
        assert detect_metric_type("Hello world, how are you?") == "wer"

    def test_chinese_text(self):
        assert detect_metric_type("你好世界，今天天气怎么样？") == "cer"

    def test_japanese_text(self):
        assert detect_metric_type("こんにちは世界") == "cer"

    def test_korean_text(self):
        assert detect_metric_type("안녕하세요 세계") == "cer"

    def test_mixed_mostly_latin(self):
        # Much more Latin than CJK
        assert detect_metric_type("Hello world, this is a test 你") == "wer"

    def test_empty_text(self):
        assert detect_metric_type("") == "wer"

    def test_numbers_only(self):
        assert detect_metric_type("12345") == "wer"


# ===================================================================
# Unit tests — compute_wer / compute_cer
# ===================================================================


class TestComputeWer:
    def test_identical(self):
        assert compute_wer("hello world", "hello world") == pytest.approx(0.0)

    def test_completely_wrong(self):
        wer = compute_wer("foo bar baz", "hello world test")
        assert wer == pytest.approx(1.0)

    def test_one_word_error(self):
        # Reference: "hello world", Hypothesis: "hello there"
        # 1 substitution out of 2 words → WER = 0.5
        wer = compute_wer("hello there", "hello world")
        assert wer == pytest.approx(0.5)

    def test_insertion(self):
        # Reference: "hello world", Hypothesis: "hello beautiful world"
        # 1 insertion out of 2 words → WER = 0.5
        wer = compute_wer("hello beautiful world", "hello world")
        assert wer == pytest.approx(0.5)

    def test_deletion(self):
        # Reference: "hello world", Hypothesis: "hello"
        # 1 deletion out of 2 words → WER = 0.5
        wer = compute_wer("hello", "hello world")
        assert wer == pytest.approx(0.5)

    def test_empty_reference_empty_hypothesis(self):
        assert compute_wer("", "") == pytest.approx(0.0)

    def test_empty_reference_non_empty_hypothesis(self):
        assert compute_wer("some text", "") == pytest.approx(1.0)


class TestComputeCer:
    def test_identical(self):
        assert compute_cer("你好世界", "你好世界") == pytest.approx(0.0)

    def test_one_char_error(self):
        # Reference: "你好世界" (4 chars), Hypothesis: "你好世人" (1 sub)
        cer = compute_cer("你好世人", "你好世界")
        assert cer == pytest.approx(0.25)

    def test_completely_wrong(self):
        cer = compute_cer("aaaa", "bbbb")
        assert cer == pytest.approx(1.0)

    def test_empty_reference_empty_hypothesis(self):
        assert compute_cer("", "") == pytest.approx(0.0)


# ===================================================================
# Unit tests — align_segments
# ===================================================================


class TestAlignSegments:
    def test_perfect_alignment(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "Hello"},
            {"start": 4.0, "end": 6.0, "source": "World"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello"},
            {"start": 4.0, "end": 6.0, "source": "World"},
        ]
        pairs = align_segments(gen, ref)
        assert len(pairs) == 2
        # Each gen should match its exact ref
        gen_sources = {p[0]["source"] for p in pairs}
        ref_sources = {p[1]["source"] for p in pairs}
        assert gen_sources == {"Hello", "World"}
        assert ref_sources == {"Hello", "World"}

    def test_shifted_timing(self):
        gen = [
            {"start": 1.5, "end": 3.5, "source": "Hello"},
            {"start": 4.5, "end": 6.5, "source": "World"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello"},
            {"start": 4.0, "end": 6.0, "source": "World"},
        ]
        pairs = align_segments(gen, ref)
        assert len(pairs) == 2
        # Text matching should still link correctly
        for gen_seg, ref_seg in pairs:
            assert gen_seg["source"] == ref_seg["source"]

    def test_missing_generated_segments(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "Hello"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello"},
            {"start": 4.0, "end": 6.0, "source": "World"},
        ]
        pairs = align_segments(gen, ref)
        # Only 1 generated → at most 1 pair
        assert len(pairs) == 1

    def test_missing_reference_segments(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "Hello"},
            {"start": 4.0, "end": 6.0, "source": "World"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello"},
        ]
        pairs = align_segments(gen, ref)
        assert len(pairs) == 1

    def test_empty_generated(self):
        ref = [{"start": 1.0, "end": 3.0, "source": "Hello"}]
        assert align_segments([], ref) == []

    def test_empty_reference(self):
        gen = [{"start": 1.0, "end": 3.0, "source": "Hello"}]
        assert align_segments(gen, []) == []

    def test_both_empty(self):
        assert align_segments([], []) == []

    def test_no_duplicate_pairing(self):
        """Each reference segment should be used at most once."""
        gen = [
            {"start": 1.0, "end": 3.0, "source": "A"},
            {"start": 1.0, "end": 3.0, "source": "A"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "A"},
        ]
        pairs = align_segments(gen, ref)
        assert len(pairs) == 1

    def test_text_drives_alignment(self):
        """Text similarity should dominate alignment (0.6 weight)."""
        gen = [
            {"start": 10.0, "end": 12.0, "source": "Hello world"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello world"},
            {"start": 10.0, "end": 12.0, "source": "Goodbye everyone"},
        ]
        pairs = align_segments(gen, ref)
        assert len(pairs) == 1
        # Should match by text despite timing mismatch
        assert pairs[0][1]["source"] == "Hello world"


# ===================================================================
# Unit tests — compute_timestamp_metrics
# ===================================================================


class TestComputeTimestampMetrics:
    def test_empty_pairs(self):
        result = compute_timestamp_metrics([])
        assert result["mean_start_offset"] is None
        assert result["median_start_offset"] is None
        assert result["mean_end_offset"] is None
        assert result["median_end_offset"] is None
        assert result["mean_iou"] is None

    def test_perfect_timestamps(self):
        pairs = [
            ({"start": 1.0, "end": 3.0}, {"start": 1.0, "end": 3.0}),
            ({"start": 4.0, "end": 6.0}, {"start": 4.0, "end": 6.0}),
        ]
        result = compute_timestamp_metrics(pairs)
        assert result["mean_start_offset"] == pytest.approx(0.0)
        assert result["median_start_offset"] == pytest.approx(0.0)
        assert result["mean_end_offset"] == pytest.approx(0.0)
        assert result["median_end_offset"] == pytest.approx(0.0)
        assert result["mean_iou"] == pytest.approx(1.0)

    def test_known_offsets(self):
        pairs = [
            # gen starts 0.5s late, ends 0.5s late
            ({"start": 1.5, "end": 3.5}, {"start": 1.0, "end": 3.0}),
            # gen starts 1.0s late, ends 1.0s late
            ({"start": 2.0, "end": 4.0}, {"start": 1.0, "end": 3.0}),
        ]
        result = compute_timestamp_metrics(pairs)
        assert result["mean_start_offset"] == pytest.approx(0.75)
        assert result["median_start_offset"] == pytest.approx(0.75)
        assert result["mean_end_offset"] == pytest.approx(0.75)
        assert result["median_end_offset"] == pytest.approx(0.75)

    def test_single_pair(self):
        pairs = [
            ({"start": 1.0, "end": 5.0}, {"start": 2.0, "end": 4.0}),
        ]
        result = compute_timestamp_metrics(pairs)
        assert result["mean_start_offset"] == pytest.approx(1.0)
        assert result["mean_end_offset"] == pytest.approx(1.0)

    def test_iou_computed(self):
        pairs = [
            # seg_a: [1, 3], seg_b: [2, 4]  → IoU = 1/3
            ({"start": 1.0, "end": 3.0}, {"start": 2.0, "end": 4.0}),
        ]
        result = compute_timestamp_metrics(pairs)
        assert result["mean_iou"] == pytest.approx(1.0 / 3.0)


# ===================================================================
# Integration test — evaluate_asr
# ===================================================================


class TestEvaluateAsr:
    def test_basic_evaluation(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "Hello world", "type": "dialogue"},
            {"start": 4.0, "end": 6.0, "source": "How are you", "type": "dialogue"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello world", "type": "dialogue"},
            {"start": 4.0, "end": 6.0, "source": "How are you", "type": "dialogue"},
        ]
        result = evaluate_asr(gen, ref)
        assert "text_metrics" in result
        assert "timestamp_metrics" in result
        assert "lyrics_bonus" in result
        assert result["text_metrics"]["score"] == pytest.approx(0.0)  # perfect match
        assert result["timestamp_metrics"]["mean_iou"] == pytest.approx(1.0)
        assert result["lyrics_bonus"] is None

    def test_lyrics_separated(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "Hello world", "type": "dialogue"},
            {"start": 10.0, "end": 12.0, "source": "La la la", "type": "lyrics"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello world", "type": "dialogue"},
            {"start": 10.0, "end": 12.0, "source": "La la la", "type": "lyrics"},
        ]
        result = evaluate_asr(gen, ref)
        # Dialogue has 1 segment
        assert result["text_metrics"]["num_segments"] == 1
        # Lyrics should be scored separately
        assert result["lyrics_bonus"] is not None
        assert result["lyrics_bonus"]["score"] == pytest.approx(0.0)

    def test_no_lyrics_bonus_when_no_lyrics(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "Hello", "type": "dialogue"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello", "type": "dialogue"},
        ]
        result = evaluate_asr(gen, ref)
        assert result["lyrics_bonus"] is None

    def test_empty_inputs(self):
        result = evaluate_asr([], [])
        assert result["text_metrics"]["score"] is None
        assert result["text_metrics"]["num_segments"] == 0
        assert result["timestamp_metrics"]["mean_iou"] is None
        assert result["lyrics_bonus"] is None

    def test_imperfect_match(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "Hello there", "type": "dialogue"},
            {"start": 4.0, "end": 6.0, "source": "Good morning", "type": "dialogue"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "Hello world", "type": "dialogue"},
            {"start": 4.0, "end": 6.0, "source": "Good evening", "type": "dialogue"},
        ]
        result = evaluate_asr(gen, ref)
        # WER should be > 0 since text doesn't match perfectly
        assert result["text_metrics"]["score"] > 0.0

    def test_corpus_level_wer(self):
        """WER should be computed corpus-level (concatenate then compute)."""
        gen = [
            {"start": 1.0, "end": 3.0, "source": "the cat sat", "type": "dialogue"},
            {"start": 4.0, "end": 6.0, "source": "on the mat", "type": "dialogue"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "the cat sat", "type": "dialogue"},
            {"start": 4.0, "end": 6.0, "source": "on the mat", "type": "dialogue"},
        ]
        result = evaluate_asr(gen, ref)
        assert result["text_metrics"]["score"] == pytest.approx(0.0)
        assert result["text_metrics"]["metric_type"] == "wer"

    def test_chinese_uses_cer(self):
        gen = [
            {"start": 1.0, "end": 3.0, "source": "你好世界", "type": "dialogue"},
        ]
        ref = [
            {"start": 1.0, "end": 3.0, "source": "你好世界", "type": "dialogue"},
        ]
        result = evaluate_asr(gen, ref)
        assert result["text_metrics"]["metric_type"] == "cer"

    def test_only_lyrics_no_dialogue(self):
        gen = [
            {"start": 10.0, "end": 12.0, "source": "Sing song", "type": "lyrics"},
        ]
        ref = [
            {"start": 10.0, "end": 12.0, "source": "Sing song", "type": "lyrics"},
        ]
        result = evaluate_asr(gen, ref)
        # No dialogue → text_metrics has no segments
        assert result["text_metrics"]["num_segments"] == 0
        # But lyrics_bonus should exist
        assert result["lyrics_bonus"] is not None
