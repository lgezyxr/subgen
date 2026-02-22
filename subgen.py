#!/usr/bin/env python3
"""
SubGen - AI 字幕生成工具
主程序入口
"""

import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from src.config import load_config
from src.audio import extract_audio
from src.transcribe import transcribe_audio
from src.translate import translate_segments
from src.subtitle import generate_subtitle, embed_subtitle

console = Console()


@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='输出字幕文件路径')
@click.option('--target-lang', '-t', default='zh', help='目标翻译语言 (默认: zh)')
@click.option('--bilingual', '-b', is_flag=True, help='生成双语字幕')
@click.option('--whisper-provider', type=click.Choice(['local', 'openai', 'groq']), help='覆盖配置的 Whisper 提供商')
@click.option('--llm-provider', type=click.Choice(['openai', 'claude', 'deepseek', 'ollama']), help='覆盖配置的 LLM 提供商')
@click.option('--embed', is_flag=True, help='将字幕烧录进视频')
@click.option('--config', '-c', type=click.Path(exists=True), default='config.yaml', help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='显示详细日志')
def main(input_path, output, target_lang, bilingual, whisper_provider, llm_provider, embed, config, verbose):
    """
    SubGen - AI 字幕生成工具
    
    从视频中提取音频，使用 AI 进行语音识别和翻译，生成字幕文件。
    
    示例:
    
        python subgen.py movie.mp4
        
        python subgen.py movie.mp4 --target-lang zh --bilingual
        
        python subgen.py movie.mp4 -o output.srt --whisper-provider local
    """
    
    input_path = Path(input_path)
    
    # 加载配置
    try:
        cfg = load_config(config)
    except FileNotFoundError:
        console.print("[red]错误: 找不到配置文件。请复制 config.example.yaml 为 config.yaml 并填入 API Keys[/red]")
        raise SystemExit(1)
    
    # 命令行参数覆盖配置
    if whisper_provider:
        cfg['whisper']['provider'] = whisper_provider
    if llm_provider:
        cfg['translation']['provider'] = llm_provider
    if target_lang:
        cfg['output']['target_language'] = target_lang
    if bilingual:
        cfg['output']['bilingual'] = True
    if embed:
        cfg['output']['embed_in_video'] = True
    
    # 确定输出路径
    if output:
        output_path = Path(output)
    else:
        suffix = '.srt' if cfg['output']['format'] == 'srt' else f".{cfg['output']['format']}"
        output_path = input_path.with_suffix(suffix)
    
    console.print(f"\n[bold blue]🎬 SubGen - AI 字幕生成工具[/bold blue]\n")
    console.print(f"输入: [cyan]{input_path}[/cyan]")
    console.print(f"输出: [cyan]{output_path}[/cyan]")
    console.print(f"Whisper: [yellow]{cfg['whisper']['provider']}[/yellow]")
    console.print(f"翻译: [yellow]{cfg['translation']['provider']}[/yellow] ({cfg['translation']['model']})")
    console.print(f"目标语言: [yellow]{cfg['output']['target_language']}[/yellow]")
    console.print(f"双语字幕: [yellow]{'是' if cfg['output']['bilingual'] else '否'}[/yellow]")
    console.print()
    
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
        if cfg['output']['embed_in_video']:
            task5 = progress.add_task("[cyan]嵌入字幕到视频...", total=None)
            video_output = input_path.with_stem(input_path.stem + '_subbed')
            embed_subtitle(input_path, output_path, video_output, cfg)
            progress.update(task5, completed=True, description="[green]✓ 视频生成完成")
    
    console.print(f"\n[bold green]✅ 完成！[/bold green]")
    console.print(f"字幕文件: [cyan]{output_path}[/cyan]")
    
    if cfg['output']['embed_in_video']:
        console.print(f"视频文件: [cyan]{video_output}[/cyan]")


if __name__ == '__main__':
    main()
