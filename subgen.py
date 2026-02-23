#!/usr/bin/env python3
"""
SubGen - AI-powered subtitle generation tool
Main entry point
"""

import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()


# Create CLI group
@click.group()
def cli():
    """
    SubGen - AI-powered subtitle generation tool

    \b
    COMMANDS:
        subgen run <video>    Generate subtitles (main command)
        subgen init           Run setup wizard
        subgen auth login     Login to OAuth providers
        subgen auth logout    Logout from providers
        subgen auth status    Show login status

    \b
    QUICK START:
        subgen run movie.mp4 --from en --to zh
        subgen run movie.mp4 --llm-provider copilot
    """
    pass


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output subtitle file path')
@click.option('--from', '-f', 'source_lang', default=None, help='Source language (e.g., en, es, ja). Auto-detect if not specified')
@click.option('--to', '-t', 'target_lang', default=None, help='Target translation language (e.g., zh, ja, ko)')
@click.option('--no-translate', is_flag=True, help='Skip translation, output transcription only')
@click.option('--sentence-aware', '-s', is_flag=True, help='Use sentence-aware translation (better for split sentences)')
@click.option('--bilingual', '-b', is_flag=True, help='Generate bilingual subtitles')
@click.option('--whisper-provider', type=click.Choice(['local', 'mlx', 'openai', 'groq']), help='Override Whisper provider from config')
@click.option('--llm-provider', type=click.Choice(['openai', 'claude', 'deepseek', 'ollama', 'copilot', 'chatgpt']), help='Override LLM provider from config')
@click.option('--embed', is_flag=True, help='Burn subtitles into video')
@click.option('--config', '-c', type=click.Path(), default='config.yaml', help='Config file path')
@click.option('--force-transcribe', is_flag=True, help='Force re-transcription even if cache exists')
@click.option('--verbose', '-v', is_flag=True, help='Show verbose logs')
@click.option('--debug', '-d', is_flag=True, help='Enable debug logging')
def run(input_path, output, source_lang, target_lang, no_translate, sentence_aware, bilingual, whisper_provider, llm_provider, embed, config, force_transcribe, verbose, debug):
    """
    Generate subtitles for a video file.

    \b
    EXAMPLES:
        # Basic usage (auto-detect source, translate to Chinese)
        subgen run movie.mp4

        # Specify source and target language
        subgen run movie.mp4 --from en --to zh

        # Use GitHub Copilot for translation
        subgen run movie.mp4 --from en --to zh --llm-provider copilot

        # Generate bilingual subtitles
        subgen run movie.mp4 --from en --to zh --bilingual
        
        # Force re-transcription (ignore cache)
        subgen run movie.mp4 --to zh --force-transcribe
    """
    # Enable debug mode if requested
    if debug:
        from src.logger import set_debug
        set_debug(True)
    
    run_subtitle_generation(
        input_path, output, source_lang, target_lang, no_translate, sentence_aware,
        bilingual, whisper_provider, llm_provider, embed, config, force_transcribe, verbose
    )


def run_subtitle_generation(input_path, output, source_lang, target_lang, no_translate, sentence_aware,
                           bilingual, whisper_provider, llm_provider, embed, config, force_transcribe, verbose):
    """Main subtitle generation logic."""
    from src.config import load_config
    from src.audio import extract_audio, cleanup_temp_files, check_ffmpeg
    from src.transcribe import transcribe_audio
    from src.translate import translate_segments, translate_segments_sentence_aware
    from src.subtitle import generate_subtitle, embed_subtitle
    from src.cache import load_cache, save_cache, format_cache_info

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
            # No config found, offer to run setup wizard
            console.print("[yellow]No config file found.[/yellow]\n")
            if click.confirm("Would you like to run the setup wizard?", default=True):
                run_init_wizard(config)
                # Reload config after wizard
                config_path = Path(config)
                if not config_path.exists():
                    console.print("[red]Setup was not completed.[/red]")
                    raise SystemExit(1)
            else:
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

    # Support both 'llm' and 'translation' config keys
    if 'llm' in cfg and 'translation' not in cfg:
        cfg['translation'] = cfg['llm']

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

    # Sync language settings
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

    console.print("\n[bold blue]🎬 SubGen - AI Subtitle Generator[/bold blue]\n")
    console.print(f"Input: [cyan]{input_path}[/cyan]")
    console.print(f"Output: [cyan]{output_path}[/cyan]")
    console.print(f"Whisper: [yellow]{cfg['whisper'].get('provider', 'local')}[/yellow]")

    if no_translate:
        console.print("Translation: [dim]disabled[/dim]")
        console.print(f"Language: [yellow]{final_source_lang}[/yellow] (transcription only)")
    else:
        translation_mode = "sentence-aware" if sentence_aware else "line-by-line"
        console.print(f"Translation: [yellow]{cfg['translation'].get('provider', 'openai')}[/yellow] ({cfg['translation'].get('model', 'default')}) [{translation_mode}]")
        console.print(f"Language: [yellow]{final_source_lang}[/yellow] → [yellow]{final_target_lang}[/yellow]")
        console.print(f"Bilingual: [yellow]{'Yes' if cfg['output'].get('bilingual', False) else 'No'}[/yellow]")

    console.print()

    audio_path = None
    video_output = None
    cached_transcription = None
    
    # Check for cached transcription
    if not force_transcribe:
        cached_transcription = load_cache(input_path)
        if cached_transcription:
            cache_info = format_cache_info(cached_transcription)
            console.print(f"[green]📂 Found cached transcription[/green]")
            console.print(f"   {cache_info}")
            console.print(f"   [dim]Use --force-transcribe to re-process[/dim]")
            console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:

            # Helper to complete a task (stops spinner and timer)
            def complete_task(task_id, description):
                progress.update(task_id, description=description)
                progress.stop_task(task_id)

            # Step 1 & 2: Extract audio and transcribe (or use cache)
            if cached_transcription:
                # Use cached transcription
                task_cache = progress.add_task("[green]✓ Using cached transcription", total=None)
                progress.stop_task(task_cache)
                
                # Convert cached segments back to Segment objects
                from src.transcribe import Segment
                segments = []
                for seg_data in cached_transcription['segments']:
                    seg = Segment(
                        start=seg_data['start'],
                        end=seg_data['end'],
                        text=seg_data['text']
                    )
                    # Restore word-level data if available
                    if 'words' in seg_data:
                        seg.words = seg_data['words']
                    segments.append(seg)
                
                # Update source language from cache if not specified
                if not source_lang and cached_transcription.get('source_lang'):
                    cfg['whisper']['source_language'] = cached_transcription['source_lang']
                    cfg['output']['source_language'] = cached_transcription['source_lang']
            else:
                # Step 1: Extract audio
                task1 = progress.add_task("[cyan]Extracting audio...", total=None)
                audio_path = extract_audio(input_path, cfg)
                complete_task(task1, "[green]✓ Audio extracted")

                # Step 2: Speech recognition
                task2 = progress.add_task("[cyan]Transcribing...", total=None)
                segments = transcribe_audio(audio_path, cfg)
                
                from src.logger import debug as log_debug
                log_debug("main: transcribe_audio returned %d segments", len(segments) if segments else 0)
                
                if not segments:
                    complete_task(task2, "[yellow]⚠ No speech detected")
                    console.print("\n[yellow]Warning: No speech detected in video[/yellow]")
                    raise SystemExit(0)
                
                log_debug("main: updating progress bar...")
                complete_task(task2, f"[green]✓ Transcribed ({len(segments)} segments)")
                log_debug("main: progress bar updated")
                
                # Save transcription to cache
                log_debug("main: starting cache save...")
                try:
                    # Convert segments to serializable format
                    segments_data = []
                    for i, seg in enumerate(segments):
                        seg_dict = {
                            'start': seg.start,
                            'end': seg.end,
                            'text': seg.text,
                            'no_speech_prob': getattr(seg, 'no_speech_prob', 0.0),
                            'avg_logprob': getattr(seg, 'avg_logprob', 0.0)
                        }
                        if hasattr(seg, 'words') and seg.words:
                            # Convert Word objects to dicts for JSON serialization
                            seg_dict['words'] = [
                                {'text': w.text, 'start': w.start, 'end': w.end}
                                for w in seg.words
                            ]
                        segments_data.append(seg_dict)
                    
                    log_debug("main: converted %d segments to dicts", len(segments_data))
                    
                    save_cache(
                        video_path=input_path,
                        segments=segments_data,
                        word_segments=None,  # TODO: extract if available
                        whisper_provider=cfg['whisper'].get('provider', 'local'),
                        whisper_model=cfg['whisper'].get('local_model', 'large-v3'),
                        source_lang=cfg['whisper'].get('source_language', 'auto')
                    )
                    log_debug("main: cache saved successfully")
                except Exception as e:
                    # Cache save failure is not fatal, but always show in debug mode
                    log_debug("main: cache save failed: %s", e)
                    import traceback
                    log_debug("main: cache save traceback: %s", traceback.format_exc())
                    if verbose:
                        console.print(f"[dim]Note: Failed to save cache: {e}[/dim]")

            # Step 3: Translation (skip if --no-translate)
            if no_translate:
                translated_segments = segments
                # Set translated to original text for subtitle generation
                for seg in translated_segments:
                    seg.translated = seg.text
                progress.add_task("[dim]Skipping translation...", total=None)
            else:
                task3 = progress.add_task("[cyan]Translating...", total=len(segments))
                
                if sentence_aware:
                    # Use sentence-aware translation
                    translated_segments = translate_segments_sentence_aware(
                        segments,
                        cfg,
                        translate_fn=None,  # Will use provider from config internally
                        progress_callback=lambda n: progress.update(task3, advance=n)
                    )
                else:
                    # Standard line-by-line translation
                    translated_segments = translate_segments(
                        segments,
                        cfg,
                        progress_callback=lambda n: progress.update(task3, advance=n)
                    )
                complete_task(task3, "[green]✓ Translation complete")

            # Step 4: Generate subtitles
            task4 = progress.add_task("[cyan]Generating subtitles...", total=None)
            generate_subtitle(translated_segments, output_path, cfg)
            complete_task(task4, "[green]✓ Subtitles generated")

            # Step 5: Embed in video (optional)
            if cfg['output'].get('embed_in_video', False):
                task5 = progress.add_task("[cyan]Embedding subtitles...", total=None)
                video_output = input_path.with_stem(input_path.stem + '_subbed')
                embed_subtitle(input_path, output_path, video_output, cfg)
                complete_task(task5, "[green]✓ Video generated")

        console.print("\n[bold green]✅ Done![/bold green]")
        console.print(f"Subtitle file: [cyan]{output_path}[/cyan]")

        if video_output:
            console.print(f"Video file: [cyan]{video_output}[/cyan]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        raise SystemExit(130)

    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        # Always print traceback in debug mode
        from src.logger import is_debug
        if verbose or is_debug():
            import traceback
            console.print(traceback.format_exc())
        raise SystemExit(1)

    finally:
        # Clean up temp files
        try:
            cleanup_temp_files(cfg)
        except Exception:
            pass


def run_init_wizard(config_path: str):
    """Run the setup wizard and save config."""
    import yaml
    from src.wizard import run_setup_wizard

    cfg = run_setup_wizard()

    # Convert 'llm' to 'translation' for backward compatibility
    if 'llm' in cfg:
        cfg['translation'] = cfg.pop('llm')

    # Save config
    output_path = Path(config_path)
    with open(output_path, 'w') as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


@cli.command()
@click.option('--config', '-c', type=click.Path(), default='config.yaml', help='Config file path')
def init(config):
    """Run the setup wizard to configure SubGen."""
    console.print("\n[bold]Starting SubGen Setup Wizard...[/bold]\n")
    run_init_wizard(config)


@cli.group()
def auth():
    """Manage authentication for OAuth providers."""
    pass


@auth.command('login')
@click.argument('provider', type=click.Choice(['copilot', 'chatgpt']))
def auth_login(provider):
    """Login to an OAuth provider.

    \b
    Supported providers:
        copilot    GitHub Copilot (uses your GitHub subscription)
        chatgpt    ChatGPT Plus/Pro (uses your OpenAI subscription)
    """
    if provider == 'copilot':
        from src.auth.copilot import copilot_login, CopilotAuthError

        console.print("\n[bold]GitHub Copilot Login[/bold]\n")

        try:
            copilot_login()
            console.print("\n[green]✅ Successfully logged in to GitHub Copilot![/green]")
            console.print("You can now use: --llm-provider copilot\n")

        except CopilotAuthError as e:
            console.print(f"\n[red]Login failed: {e}[/red]")
            raise SystemExit(1)

    elif provider == 'chatgpt':
        from src.auth.openai_codex import openai_codex_login, OpenAICodexAuthError

        console.print("\n[bold]ChatGPT Plus/Pro Login[/bold]")
        console.print("[dim]A browser window will open for authentication.[/dim]\n")

        try:
            openai_codex_login()
            console.print("\n[green]✅ Successfully logged in to ChatGPT![/green]")
            console.print("You can now use: --llm-provider chatgpt\n")

        except OpenAICodexAuthError as e:
            console.print(f"\n[red]Login failed: {e}[/red]")
            raise SystemExit(1)


@auth.command('logout')
@click.argument('provider', type=click.Choice(['copilot', 'chatgpt']))
def auth_logout(provider):
    """Logout from an OAuth provider."""
    from src.auth.store import delete_credential

    # Map provider names to credential keys
    cred_key = 'openai-codex' if provider == 'chatgpt' else provider

    if delete_credential(cred_key):
        console.print(f"[green]✅ Logged out from {provider}[/green]")
    else:
        console.print(f"[yellow]Not logged in to {provider}[/yellow]")


@auth.command('status')
def auth_status():
    """Show authentication status for all providers."""
    from src.auth.store import get_credentials_path
    from src.auth.copilot import is_copilot_logged_in
    from src.auth.openai_codex import is_openai_codex_logged_in

    console.print("\n[bold]Authentication Status[/bold]\n")
    console.print(f"Credentials file: [dim]{get_credentials_path()}[/dim]\n")

    # ChatGPT
    if is_openai_codex_logged_in():
        console.print("  [green]●[/green] ChatGPT Plus/Pro: [green]logged in[/green]")
    else:
        console.print("  [dim]○[/dim] ChatGPT Plus/Pro: [dim]not logged in[/dim]")

    # Copilot
    if is_copilot_logged_in():
        console.print("  [green]●[/green] GitHub Copilot: [green]logged in[/green]")
    else:
        console.print("  [dim]○[/dim] GitHub Copilot: [dim]not logged in[/dim]")

    console.print()


# Allow direct video file as argument (shortcut for 'run')
@cli.command(name='process', hidden=True)
@click.argument('input_path', type=click.Path(exists=True))
@click.pass_context
def process_shortcut(ctx, input_path):
    """Hidden command for backward compatibility."""
    ctx.invoke(run, input_path=input_path)


def main():
    """Entry point that handles both 'subgen video.mp4' and 'subgen run video.mp4'."""
    import sys

    # If first arg looks like a file (not a command), insert 'run'
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        commands = ['run', 'init', 'auth', '--help', '-h', '--version']
        if first_arg not in commands and not first_arg.startswith('-'):
            # Check if it's a file path
            if Path(first_arg).exists() or '.' in first_arg:
                sys.argv.insert(1, 'run')

    cli()


if __name__ == '__main__':
    main()
