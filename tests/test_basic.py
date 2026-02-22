"""基础测试"""



def test_config_load():
    """测试配置加载"""
    from src.config import load_config

    # 使用示例配置
    config = load_config("config.example.yaml")

    assert "whisper" in config
    assert "translation" in config
    assert "output" in config


def test_segment_dataclass():
    """测试 Segment 数据类"""
    from src.transcribe import Segment

    seg = Segment(start=0.0, end=2.5, text="Hello world")

    assert seg.start == 0.0
    assert seg.end == 2.5
    assert seg.text == "Hello world"
    assert seg.translated == ""


def test_time_formatting():
    """测试时间格式化"""
    from src.subtitle import _format_time_srt, _format_time_vtt

    # SRT 格式
    assert _format_time_srt(0) == "00:00:00,000"
    assert _format_time_srt(3661.5) == "01:01:01,500"

    # VTT 格式
    assert _format_time_vtt(0) == "00:00:00.000"
    assert _format_time_vtt(3661.5) == "01:01:01.500"


def test_lang_name():
    """测试语言名称转换"""
    from src.translate import _get_lang_name

    assert _get_lang_name("zh") == "中文"
    assert _get_lang_name("en") == "English"
    assert _get_lang_name("unknown") == "unknown"
