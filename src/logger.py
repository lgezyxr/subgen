"""Simple debug logging for SubGen."""

import sys
from typing import Any

# Global debug flag
_debug_enabled = False


def set_debug(enabled: bool):
    """Enable or disable debug logging."""
    global _debug_enabled
    _debug_enabled = enabled


def is_debug() -> bool:
    """Check if debug mode is enabled."""
    return _debug_enabled


def debug(msg: str, *args: Any):
    """Print debug message if debug mode is enabled."""
    if _debug_enabled:
        if args:
            msg = msg % args
        print(f"[DEBUG] {msg}", file=sys.stderr)


def debug_segment(label: str, seg: Any):
    """Print debug info for a segment."""
    if _debug_enabled:
        text = getattr(seg, 'text', str(seg))[:50]
        translated = getattr(seg, 'translated', None)
        trans_preview = translated[:30] + "..." if translated and len(translated) > 30 else translated
        words_count = len(seg.words) if hasattr(seg, 'words') and seg.words else 0
        print(f"[DEBUG] {label}: text={text!r}, translated={trans_preview!r}, words={words_count}", file=sys.stderr)


def debug_segments(label: str, segments: list):
    """Print summary of segments."""
    if _debug_enabled:
        total = len(segments)
        with_translation = sum(1 for s in segments if getattr(s, 'translated', None))
        with_words = sum(1 for s in segments if hasattr(s, 'words') and s.words)
        print(f"[DEBUG] {label}: total={total}, with_translation={with_translation}, with_words={with_words}", file=sys.stderr)
