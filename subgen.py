#!/usr/bin/env python3
"""
SubGen - AI 字幕生成工具
主程序入口
"""

import sys
import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from src.config import load_config
from src.audio import extract_audio, cleanup_temp_files, check_ffmpeg
from src.transcribe import transcribe_audio
from src.translate import translate_segments
from src.subtitle import generate_subtitle, embed_subtitle

console = Console()


@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='输出字幕文件路径')
@click.option('--from', '-f', 'source_lang', default=None, help='源语言 (如: en, es, ja)，不指定则自动检测')
@click.option('--to', '-t', 'target_lang', default=None, help='目标翻译语言 (如: zh, ja, ko)')
@click.option('--bilingual', '-b', is_flag=True, help='生成双语字幕')
@click.option('--whisper-provider', type=click.Choice(['local', 'openai', 'groq']), help='覆盖配置的 Whisper 提供商')
@click.option('--llm-provider', type=click.Choice(['openai', 'claude', 'deepseek', 'ollama']), help='覆盖配置的 LLM 提供商')
@click.option('--embed', is_flag=True, help='将字幕烧录进视频')
@click.option('--config', '-c', type=click.Path(), default='config.yaml', help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='显示详细日志')
def main(input_path, output, source_lang, target_lang, bilingual, whisper_provider, llm_provider, embed, config, verbose):
    """
    SubGen - AI 字幕生成工具
    
    从视频中提取音频，使用 AI 进行语音识别和翻译，生成字幕文件。
    
    示例:
    
    \b
        # 基本用法（自动检测源语言，翻译成中文）
        python subgen.py movie.mp4
        
        # 指定源语言和目标语言
        python subgen.py movie.mp4 --from en --to zh
        
        # 西班牙语翻译成日语
        python subgen.py movie.mp4 -f es -t ja
        
        # 生成双语字幕
        python subgen.py movie.mp4 --from en --to zh --bilingual
        
        # 使用本地 Whisper
        python subgen.py movie.mp4 -f en -t zh --whisper-provider local
    """
    
    input_path = Path(input_path)
    
    # 检查 FFmpeg
    if not check_ffmpeg():
        console.print("[red]错误: FFmpeg 未安装[/red]")
        console.print("请安装 FFmpeg:")
        console.print("  macOS: brew install ffmpeg")
        console.print("  Ubuntu: sudo apt install ffmpeg")
        console.print("  Windows: https://ffmpeg.org/download.html")
        raise SystemExit(1)
    
    # 加载配置
    config_path = Path(config)
    if not config_path.exists():
        # 尝试查找配置文件
        alt_paths = [
            Path.home() / '.config' / 'subgen' / 'config.yaml',
            Path(__file__).parent / 'config.yaml',
        ]
        for alt in alt_paths:
            if alt.exists():
                config_path = alt
                break
        else:
            console.print("[red]错误: 找不到配置文件[/red]")
            console.print("请复制 config.example.yaml 为 config.yaml 并填入 API Keys:")
            console.print("  cp config.example.yaml config.yaml")
            raise SystemExit(1)
    
    try:
        cfg = load_config(str(config_path))
    except Exception as e:
        console.print(f"[red]错误: 配置文件加载失败: {e}[/red]")
        raise SystemExit(1)
    
    # 确保配置结构完整
    cfg.setdefault('whisper', {})
    cfg.setdefault('translation', {})
    cfg.setdefault('output', {})
    cfg.setdefault('advanced', {})
    
    # 命令行参数覆盖配置
    if whisper_provider:
        cfg['whisper']['provider'] = whisper_provider
    if llm_provider:
        cfg['translation']['provider'] = llm_provider
    if source_lang:
        cfg['whisper']['source_language'] = source_lang
        cfg['output']['source_language'] = source_lang
    if target_lang:
        cfg['output']['target_language'] = target_lang
    if bilingual:
        cfg['output']['bilingual'] = True
    if embed:
        cfg['output']['embed_in_video'] = True
    
    # 获取最终的语言设置
    final_source_lang = cfg['whisper'].get('source_language', 'auto')
    final_target_lang = cfg['output'].get('target_language', 'zh')
    
    # 确定输出路径
    if output:
        output_path = Path(output)
    else:
        suffix = f".{cfg['output'].get('format', 'srt')}"
        output_path = input_path.with_suffix(suffix)
    
    console.print(f"\n[bold blue]🎬 SubGen - AI 字幕生成工具[/bold blue]\n")
    console.print(f"输入: [cyan]{input_path}[/cyan]")
    console.print(f"输出: [cyan]{output_path}[/cyan]")
    console.print(f"Whisper: [yellow]{cfg['whisper'].get('provider', 'local')}[/yellow]")
    console.print(f"翻译: [yellow]{cfg['translation'].get('provider', 'openai')}[/yellow] ({cfg['translation'].get('model', 'default')})")
    console.print(f"语言: [yellow]{final_source_lang}[/yellow] → [yellow]{final_target_lang}[/yellow]")
    console.print(f"双语字幕: [yellow]{'是' if cfg['output'].get('bilingual', False) else '否'}[/yellow]")
    console.print()
    
    audio_path = None
    video_output = None
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            
            # Step 1: 提取音频
            task1 = progress.add_task("[cyan]提取音频...", total=None)
            audio_path = extract_audio(input_path, cfg)
            progress.update(task1, completed=True, description="[green]✓ 音频提取完成")
            
            # Step 2: 语音识别
            task2 = progress.add_task("[cyan]语音识别中...", total=None)
            segments = transcribe_audio(audio_path, cfg)
            if not segments:
                progress.update(task2, completed=True, description="[yellow]⚠ 未检测到语音")
                console.print("\n[yellow]警告: 视频中未检测到语音[/yellow]")
                raise SystemExit(0)
            progress.update(task2, completed=True, description=f"[green]✓ 识别完成 ({len(segments)} 条字幕)")
            
            # Step 3: 翻译
            task3 = progress.add_task("[cyan]翻译中...", total=len(segments))
            translated_segments = translate_segments(
                segments, 
                cfg, 
                progress_callback=lambda n: progress.update(task3, advance=n)
            )
            progress.update(task3, completed=len(segments), description="[green]✓ 翻译完成")
            
            # Step 4: 生成字幕
            task4 = progress.add_task("[cyan]生成字幕...", total=None)
            generate_subtitle(translated_segments, output_path, cfg)
            progress.update(task4, completed=True, description="[green]✓ 字幕生成完成")
            
            # Step 5: 嵌入视频 (可选)
            if cfg['output'].get('embed_in_video', False):
                task5 = progress.add_task("[cyan]嵌入字幕到视频...", total=None)
                video_output = input_path.with_stem(input_path.stem + '_subbed')
                embed_subtitle(input_path, output_path, video_output, cfg)
                progress.update(task5, completed=True, description="[green]✓ 视频生成完成")
        
        console.print(f"\n[bold green]✅ 完成！[/bold green]")
        console.print(f"字幕文件: [cyan]{output_path}[/cyan]")
        
        if video_output:
            console.print(f"视频文件: [cyan]{video_output}[/cyan]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消[/yellow]")
        raise SystemExit(130)
    
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise SystemExit(1)
    
    finally:
        # 清理临时文件
        try:
            cleanup_temp_files(cfg)
        except Exception:
            pass


if __name__ == '__main__':
    main()
