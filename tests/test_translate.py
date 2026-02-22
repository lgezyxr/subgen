"""翻译模块单元测试"""

from src.translate import _parse_translations


class TestParseTranslations:
    """翻译结果解析测试"""

    def test_exact_match(self):
        """行数完全匹配"""
        result = _parse_translations("你好\n世界\n测试", 3)
        assert result == ["你好", "世界", "测试"]

    def test_fewer_lines_padded(self):
        """返回行数不足，应补空"""
        result = _parse_translations("你好\n世界", 4)
        assert len(result) == 4
        assert result[0] == "你好"
        assert result[1] == "世界"
        assert result[2] == ""
        assert result[3] == ""

    def test_more_lines_truncated(self):
        """返回行数过多，应截断"""
        result = _parse_translations("一\n二\n三\n四\n五", 3)
        assert len(result) == 3
        assert result == ["一", "二", "三"]

    def test_empty_lines_preserved(self):
        """空行应该保留位置"""
        result = _parse_translations("第一行\n\n第三行", 3)
        assert len(result) == 3
        assert result[0] == "第一行"
        assert result[1] == ""
        assert result[2] == "第三行"

    def test_numbered_prefix_removed(self):
        """移除序号前缀 1. 2. 等"""
        result = _parse_translations("1. 你好\n2. 世界", 2)
        assert result == ["你好", "世界"]

    def test_numbered_prefix_parenthesis(self):
        """移除序号前缀 1) 2) 等"""
        result = _parse_translations("1) 你好\n2) 世界", 2)
        assert result == ["你好", "世界"]

    def test_numbered_prefix_chinese(self):
        """移除中文序号 1、2、等"""
        result = _parse_translations("1、你好\n2、世界", 2)
        assert result == ["你好", "世界"]

    def test_whitespace_stripped(self):
        """每行首尾空白应去除"""
        result = _parse_translations("  你好  \n  世界  ", 2)
        assert result == ["你好", "世界"]

    def test_empty_input(self):
        """空输入"""
        result = _parse_translations("", 3)
        assert len(result) == 3
        assert all(line == "" for line in result)

    def test_single_line(self):
        """单行输入"""
        result = _parse_translations("只有一行", 1)
        assert result == ["只有一行"]

    def test_no_strip_overall(self):
        """不应该 strip 整体导致首行空行丢失"""
        # 如果 LLM 返回 "\n你好\n世界"，第一行是空的
        result = _parse_translations("\n你好\n世界", 3)
        assert len(result) == 3
        assert result[0] == ""
        assert result[1] == "你好"
        assert result[2] == "世界"
