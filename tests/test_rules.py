"""Translation rules loading tests"""

from unittest.mock import patch


class TestLoadTranslationRules:
    """Translation rules loading tests"""

    def test_load_zh_rules(self):
        """Test loading Chinese rules"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()
        zh_rules = rules_dir / 'zh.md'

        if zh_rules.exists():
            rules = load_translation_rules('zh')
            assert rules is not None
            # Chinese rules should contain punctuation-related content
            assert '标点符号' in rules or '半角' in rules

    def test_load_nonexistent_falls_back_to_default(self):
        """Test non-existent language falls back to default rules"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()
        default_rules = rules_dir / 'default.md'

        if default_rules.exists():
            # Load a non-existent language
            rules = load_translation_rules('xx-nonexistent')
            assert rules is not None
            # Should load default.md content
            assert 'General' in rules or 'Character' in rules

    def test_load_language_variant_fallback(self):
        """Test language variant fallback (zh-TW -> zh)"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()
        zh_rules = rules_dir / 'zh.md'

        if zh_rules.exists():
            # zh-TW should fall back to zh.md
            rules = load_translation_rules('zh-TW')
            assert rules is not None

    def test_rules_title_removed(self):
        """Test that level-1 headings are removed from rules"""
        from src.translate import load_translation_rules, _get_rules_dir

        rules_dir = _get_rules_dir()

        if (rules_dir / 'zh.md').exists():
            rules = load_translation_rules('zh')
            # Level-1 headings (lines starting with #) should be removed
            lines = rules.split('\n')
            for line in lines:
                assert not line.startswith('# '), f"Found title: {line}"


class TestBuildSystemPrompt:
    """System prompt building tests"""

    def test_prompt_without_rules(self):
        """Test prompt without rules"""
        from src.translate import _build_system_prompt

        with patch('src.translate.load_translation_rules', return_value=None):
            prompt = _build_system_prompt('English', 'English', 40, 'en')
            assert 'English' in prompt
            assert '40' in prompt
            # Should not contain rules section
            assert 'Translation Rules' not in prompt

    def test_prompt_with_rules(self):
        """Test prompt with rules"""
        from src.translate import _build_system_prompt

        mock_rules = "- Use half-width punctuation\n- Use Chinese numerals"
        with patch('src.translate.load_translation_rules', return_value=mock_rules):
            prompt = _build_system_prompt('English', '中文', 22, 'zh')
            assert '中文' in prompt
            assert 'English' in prompt
            assert '22' in prompt
            assert 'Translation Rules' in prompt
            assert 'half-width punctuation' in prompt

    def test_prompt_source_target_both_present(self):
        """Test that both source and target languages are in prompt"""
        from src.translate import _build_system_prompt

        with patch('src.translate.load_translation_rules', return_value=None):
            prompt = _build_system_prompt('Español', '日本語', 40, 'ja')
            assert 'Español' in prompt
            assert '日本語' in prompt
