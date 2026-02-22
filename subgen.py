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


@click.group(invoke_without_command=True)
@click.pass_context
@click.argument('input_path', type=click.Path(exists=True), required=False)
@click.option('--output', '-o', type=click.Path(), help='Output subtitle file path')
@click.option('--from', '-f', 'source_lang', default=None, help='Source language (e.g., en, es, ja). Auto-detect if not specified')
@click.option('--to', '-t', 'target_lang', default=None, help='Target translation language (e.g., zh, ja, ko)')
@click.option('--bilingual', '-b', is_flag=True, help='Generate bilingual subtitles')
@click.option('--whisper-provider', type=click.Choice(['local', 'openai', 'groq']), help='Override Whisper provider from config')
@click.option('--llm-provider', type=click.Choice(['openai', 'claude', 'deepseek', 'ollama', 'copilot']), help='Override LLM provider from config')
@click.option('--embed', is_flag=True, help='Burn subtitles into video')
@click.option('--config', '-c', type=click.Path(), default='config.yaml', help='Config file path')
@click.option('--verbose', '-v', is_flag=True, help='Show verbose logs')
def cli(ctx, input_path, output, source_lang, target_lang, bilingual, whisper_provider, llm_provider, embed, config, verbose):
    """
    SubGen - AI-powered subtitle generation tool

    Extract audio from video, transcribe with AI, translate, and generate subtitles.

    \b
    COMMANDS:
        subgen init           Run setup wizard
        subgen auth login     Login to OAuth providers (e.g., copilot)
        subgen auth logout    Logout from providers
        subgen auth status    Show login status

    \b
    EXAMPLES:
        # Basic usage (auto-detect source, translate to Chinese)
        python subgen.py movie.mp4

        # Specify source and target language
        python subgen.py movie.mp4 --from en --to zh

        # Use GitHub Copilot for translation
        python subgen.py movie.mp4 --from en --to zh --llm-provider copilot

        # Generate bilingual subtitles
        python subgen.py movie.mp4 --from en --to zh --bilingual
    """
    # If a subcommand is invoked, skip main processing
    if ctx.invoked_subcommand is not None:
        return

    # If no input file provided, show help
    if not input_path:
        click.echo(ctx.get_help())
        return

    # Run main subtitle generation
    run_subtitle_generation(
        input_path, output, source_lang, target_lang,
        bilingual, whisper_provider, llm_provider, embed, config, verbose
    )


def run_subtitle_generation(input_path, output, source_lang, target_lang,
                           bilingual, whisper_provider, llm_provider, embed, config, verbose):
    """Main subtitle generation logic."""
    from src.config import load_config
    from src.audio import extract_audio, cleanup_temp_files, check_ffmpeg
    from src.transcribe import transcribe_audio
    from src.translate import translate_segments
    from src.subtitle import generate_subtitle, embed_subtitle

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

        console.print("\n[bold green]✅ Done![/bold green]")
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
@click.argument('provider', type=click.Choice(['copilot']))
def auth_login(provider):
    """Login to an OAuth provider.

    \b
    Supported providers:
        copilot    GitHub Copilot (uses your GitHub subscription)
    """
    if provider == 'copilot':
        from src.auth.copilot import copilot_login, CopilotAuthError

        console.print("\n[bold]GitHub Copilot Login[/bold]\n")

        try:
            def on_waiting():
                pass  # Silent waiting

            copilot_login(on_waiting=on_waiting)
            console.print("\n[green]✅ Successfully logged in to GitHub Copilot![/green]")
            console.print("You can now use: --llm-provider copilot\n")

        except CopilotAuthError as e:
            console.print(f"\n[red]Login failed: {e}[/red]")
            raise SystemExit(1)


@auth.command('logout')
@click.argument('provider', type=click.Choice(['copilot']))
def auth_logout(provider):
    """Logout from an OAuth provider."""
    from src.auth.store import delete_credential

    if delete_credential(provider):
        console.print(f"[green]✅ Logged out from {provider}[/green]")
    else:
        console.print(f"[yellow]Not logged in to {provider}[/yellow]")


@auth.command('status')
def auth_status():
    """Show authentication status for all providers."""
    from src.auth.store import get_credentials_path
    from src.auth.copilot import is_copilot_logged_in

    console.print("\n[bold]Authentication Status[/bold]\n")
    console.print(f"Credentials file: [dim]{get_credentials_path()}[/dim]\n")

    # Copilot
    if is_copilot_logged_in():
        console.print("  [green]●[/green] GitHub Copilot: [green]logged in[/green]")
    else:
        console.print("  [dim]○[/dim] GitHub Copilot: [dim]not logged in[/dim]")

    console.print()


if __name__ == '__main__':
    cli()
