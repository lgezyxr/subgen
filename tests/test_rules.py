"""翻译规则加载测试"""

from unittest.mock import patch


class TestLoadTranslationRules:
    """翻译规则加载测试"""

    def test_load_zh_rules(self):
        """测试加载中文规则"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()
        zh_rules = rules_dir / 'zh.md'

        if zh_rules.exists():
            rules = load_translation_rules('zh')
            assert rules is not None
            assert '标点符号' in rules or '半角' in rules

    def test_load_nonexistent_falls_back_to_default(self):
        """测试不存在的语言回退到默认规则"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()
        default_rules = rules_dir / 'default.md'

        if default_rules.exists():
            # 加载一个不存在的语言
            rules = load_translation_rules('xx-nonexistent')
            assert rules is not None
            # 应该加载 default.md 的内容
            assert 'General' in rules or 'Character' in rules

    def test_load_language_variant_fallback(self):
        """测试语言变体回退 (zh-TW -> zh)"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()
        zh_rules = rules_dir / 'zh.md'

        if zh_rules.exists():
            # zh-TW 应该回退到 zh.md
            rules = load_translation_rules('zh-TW')
            assert rules is not None

    def test_rules_title_removed(self):
        """测试规则文件的一级标题被移除"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()

        if (rules_dir / 'zh.md').exists():
            rules = load_translation_rules('zh')
            # 一级标题（以 # 开头的行）应该被移除
            lines = rules.split('\n')
            for line in lines:
                assert not line.startswith('# '), f"Found title: {line}"


class TestBuildSystemPrompt:
    """系统提示词构建测试"""

    def test_prompt_without_rules(self):
        """测试没有规则时的提示词"""
        from src.translate import _build_system_prompt

        with patch('src.translate.load_translation_rules', return_value=None):
            prompt = _build_system_prompt('English', 'English', 40, 'en')
            assert 'English' in prompt
            assert '40' in prompt
            # 不应该包含规则部分
            assert '翻译规则（必须严格遵守）' not in prompt

    def test_prompt_with_rules(self):
        """测试有规则时的提示词"""
        from src.translate import _build_system_prompt

        mock_rules = "- 使用半角标点\n- 数字用中文"
        with patch('src.translate.load_translation_rules', return_value=mock_rules):
            prompt = _build_system_prompt('English', '中文', 22, 'zh')
            assert '中文' in prompt
            assert 'English' in prompt
            assert '22' in prompt
            assert '翻译规则（必须严格遵守）' in prompt
            assert '使用半角标点' in prompt

    def test_prompt_source_target_both_present(self):
        """测试源语言和目标语言都在提示词中"""
        from src.translate import _build_system_prompt

        with patch('src.translate.load_translation_rules', return_value=None):
            prompt = _build_system_prompt('Español', '日本語', 40, 'ja')
            assert 'Español' in prompt
            assert '日本語' in prompt
