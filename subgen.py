#!/usr/bin/env python3
"""
SubGen - AI-powered subtitle generation tool
Main entry point
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
@click.option('--output', '-o', type=click.Path(), help='Output subtitle file path')
@click.option('--from', '-f', 'source_lang', default=None, help='Source language (e.g., en, es, ja). Auto-detect if not specified')
@click.option('--to', '-t', 'target_lang', default=None, help='Target translation language (e.g., zh, ja, ko)')
@click.option('--bilingual', '-b', is_flag=True, help='Generate bilingual subtitles')
@click.option('--whisper-provider', type=click.Choice(['local', 'openai', 'groq']), help='Override Whisper provider from config')
@click.option('--llm-provider', type=click.Choice(['openai', 'claude', 'deepseek', 'ollama']), help='Override LLM provider from config')
@click.option('--embed', is_flag=True, help='Burn subtitles into video')
@click.option('--config', '-c', type=click.Path(), default='config.yaml', help='Config file path')
@click.option('--verbose', '-v', is_flag=True, help='Show verbose logs')
def main(input_path, output, source_lang, target_lang, bilingual, whisper_provider, llm_provider, embed, config, verbose):
    """
    SubGen - AI-powered subtitle generation tool

    Extract audio from video, transcribe with AI, translate, and generate subtitles.

    Examples:

    \b
        # Basic usage (auto-detect source, translate to Chinese)
        python subgen.py movie.mp4

        # Specify source and target language
        python subgen.py movie.mp4 --from en --to zh

        # Spanish to Japanese
        python subgen.py movie.mp4 -f es -t ja

        # Generate bilingual subtitles
        python subgen.py movie.mp4 --from en --to zh --bilingual

        # Use local Whisper
        python subgen.py movie.mp4 -f en -t zh --whisper-provider local
    """

    input_path = Path(input_path)

    # Check FFmpeg
    if not check_ffmpeg():
        console.print("[red]Error: FFmpeg not installed[/red]")
        console.print("Please install FFmpeg:")
        console.print("  macOS: brew install ffmpeg")
        console.print("  Ubuntu: sudo apt install ffmpeg")
        console.print("  Windows: https://ffmpeg.org/download.html")
        raise SystemExit(1)

    # Load config
    config_path = Path(config)
    if not config_path.exists():
        # Try to find config file
        alt_paths = [
            Path.home() / '.config' / 'subgen' / 'config.yaml',
            Path(__file__).parent / 'config.yaml',
        ]
        for alt in alt_paths:
            if alt.exists():
                config_path = alt
                break
        else:
            console.print("[red]Error: Config file not found[/red]")
            console.print("Please copy config.example.yaml to config.yaml and add your API keys:")
            console.print("  cp config.example.yaml config.yaml")
            raise SystemExit(1)

    try:
        cfg = load_config(str(config_path))
    except Exception as e:
        console.print(f"[red]Error: Failed to load config: {e}[/red]")
        raise SystemExit(1)

    # Ensure config structure is complete
    cfg.setdefault('whisper', {})
    cfg.setdefault('translation', {})
    cfg.setdefault('output', {})
    cfg.setdefault('advanced', {})

    # CLI arguments override config
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

    # Sync language settings: if only one place has source language set, sync to the other
    whisper_source = cfg['whisper'].get('source_language', 'auto')
    output_source = cfg['output'].get('source_language', 'auto')
    if whisper_source != 'auto' and output_source == 'auto':
        cfg['output']['source_language'] = whisper_source
    elif output_source != 'auto' and whisper_source == 'auto':
        cfg['whisper']['source_language'] = output_source

    # Get final language settings
    final_source_lang = cfg['output'].get('source_language', 'auto')
    final_target_lang = cfg['output'].get('target_language', 'zh')

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        suffix = f".{cfg['output'].get('format', 'srt')}"
        output_path = input_path.with_suffix(suffix)

    console.print(f"\n[bold blue]🎬 SubGen - AI Subtitle Generator[/bold blue]\n")
    console.print(f"Input: [cyan]{input_path}[/cyan]")
    console.print(f"Output: [cyan]{output_path}[/cyan]")
    console.print(f"Whisper: [yellow]{cfg['whisper'].get('provider', 'local')}[/yellow]")
    console.print(f"Translation: [yellow]{cfg['translation'].get('provider', 'openai')}[/yellow] ({cfg['translation'].get('model', 'default')})")
    console.print(f"Language: [yellow]{final_source_lang}[/yellow] → [yellow]{final_target_lang}[/yellow]")
    console.print(f"Bilingual: [yellow]{'Yes' if cfg['output'].get('bilingual', False) else 'No'}[/yellow]")
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

            # Step 1: Extract audio
            task1 = progress.add_task("[cyan]Extracting audio...", total=None)
            audio_path = extract_audio(input_path, cfg)
            progress.update(task1, completed=True, description="[green]✓ Audio extracted")

            # Step 2: Speech recognition
            task2 = progress.add_task("[cyan]Transcribing...", total=None)
            segments = transcribe_audio(audio_path, cfg)
            if not segments:
                progress.update(task2, completed=True, description="[yellow]⚠ No speech detected")
                console.print("\n[yellow]Warning: No speech detected in video[/yellow]")
                raise SystemExit(0)
            progress.update(task2, completed=True, description=f"[green]✓ Transcribed ({len(segments)} segments)")

            # Step 3: Translation
            task3 = progress.add_task("[cyan]Translating...", total=len(segments))
            translated_segments = translate_segments(
                segments,
                cfg,
                progress_callback=lambda n: progress.update(task3, advance=n)
            )
            progress.update(task3, completed=len(segments), description="[green]✓ Translation complete")

            # Step 4: Generate subtitles
            task4 = progress.add_task("[cyan]Generating subtitles...", total=None)
            generate_subtitle(translated_segments, output_path, cfg)
            progress.update(task4, completed=True, description="[green]✓ Subtitles generated")

            # Step 5: Embed in video (optional)
            if cfg['output'].get('embed_in_video', False):
                task5 = progress.add_task("[cyan]Embedding subtitles...", total=None)
                video_output = input_path.with_stem(input_path.stem + '_subbed')
                embed_subtitle(input_path, output_path, video_output, cfg)
                progress.update(task5, completed=True, description="[green]✓ Video generated")

        console.print(f"\n[bold green]✅ Done![/bold green]")
        console.print(f"Subtitle file: [cyan]{output_path}[/cyan]")

        if video_output:
            console.print(f"Video file: [cyan]{video_output}[/cyan]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        raise SystemExit(130)

    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise SystemExit(1)

    finally:
        # Clean up temp files
        try:
            cleanup_temp_files(cfg)
        except Exception:
            pass


if __name__ == '__main__':
    main()
