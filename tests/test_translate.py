"""Translation module unit tests"""

from src.translate import _parse_translations


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
