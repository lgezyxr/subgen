#!/usr/bin/env python3
"""
SubGen - AI-powered subtitle generation tool
Main entry point (CLI thin shell)
"""

import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from src import __version__

console = Console()


# Create CLI group
@click.group()
@click.version_option(version=__version__, prog_name='subgen')
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
@click.option('--proofread', '-p', is_flag=True, help='Add proofreading pass after translation (uses full story context)')
@click.option('--proofread-only', is_flag=True, help='Only run proofreading on existing translated subtitles (requires cache or .srt)')
@click.option('--bilingual', '-b', is_flag=True, help='Generate bilingual subtitles')
@click.option('--whisper-provider', type=click.Choice(['local', 'mlx', 'openai', 'groq', 'cpp']), help='Override Whisper provider from config')
@click.option('--llm-provider', type=click.Choice(['openai', 'claude', 'deepseek', 'ollama', 'copilot', 'chatgpt']), help='Override LLM provider from config')
@click.option('--embed', is_flag=True, help='Burn subtitles into video')
@click.option('--config', '-c', type=click.Path(), default='config.yaml', help='Config file path')
@click.option('--force-transcribe', is_flag=True, help='Force re-transcription even if cache exists')
@click.option('--verbose', '-v', is_flag=True, help='Show verbose logs')
@click.option('--debug', '-d', is_flag=True, help='Enable debug logging')
@click.option('--style-preset', type=click.Choice(['default', 'netflix', 'fansub', 'minimal']), default=None, help='Style preset for subtitle rendering')
@click.option('--primary-font', default=None, help='Override primary subtitle font')
@click.option('--primary-color', default=None, help='Override primary subtitle color (hex e.g. #FFFFFF)')
@click.option('--secondary-font', default=None, help='Override secondary subtitle font')
@click.option('--secondary-color', default=None, help='Override secondary subtitle color (hex e.g. #AAAAAA)')
@click.option('--save-project', type=click.Path(), default=None, help='Save .subgen project file')
@click.option('--load-project', type=click.Path(exists=True), default=None, help='Load from .subgen project file')
def run(input_path, output, source_lang, target_lang, no_translate, sentence_aware, proofread, proofread_only, bilingual, whisper_provider, llm_provider, embed, config, force_transcribe, verbose, debug,
        style_preset, primary_font, primary_color, secondary_font, secondary_color, save_project, load_project):
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
        input_path, output, source_lang, target_lang, no_translate, sentence_aware, proofread, proofread_only,
        bilingual, whisper_provider, llm_provider, embed, config, force_transcribe, verbose,
        style_preset=style_preset, primary_font=primary_font, primary_color=primary_color,
        secondary_font=secondary_font, secondary_color=secondary_color,
        save_project=save_project, load_project=load_project,
    )


def run_subtitle_generation(input_path, output, source_lang, target_lang, no_translate, sentence_aware, proofread, proofread_only,
                           bilingual, whisper_provider, llm_provider, embed, config, force_transcribe, verbose,
                           style_preset=None, primary_font=None, primary_color=None,
                           secondary_font=None, secondary_color=None,
                           save_project=None, load_project=None):
    """Main subtitle generation logic — thin CLI shell over SubGenEngine."""
    from src.config import load_config
    from src.audio import check_ffmpeg
    from src.engine import SubGenEngine
    from src.styles import PRESETS, StyleProfile
    from src.project import SubtitleProject

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
        alt_paths = [
            Path.home() / '.subgen' / 'config.yaml',
            Path.home() / '.config' / 'subgen' / 'config.yaml',
            Path(__file__).parent / 'config.yaml',
        ]
        for alt in alt_paths:
            if alt.exists():
                config_path = alt
                break
        else:
            console.print("[yellow]No config file found.[/yellow]\n")
            if click.confirm("Would you like to run the setup wizard?", default=True):
                run_init_wizard(config)
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

    # Ensure config structure
    cfg.setdefault('whisper', {})
    cfg.setdefault('translation', {})
    cfg.setdefault('output', {})
    cfg.setdefault('advanced', {})

    if 'llm' in cfg and 'translation' not in cfg:
        cfg['translation'] = cfg['llm']

    # CLI overrides
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

    # Style overrides in config
    if style_preset:
        cfg.setdefault('styles', {})['preset'] = style_preset
    if primary_font:
        cfg.setdefault('styles', {}).setdefault('primary', {})['font'] = primary_font
    if primary_color:
        cfg.setdefault('styles', {}).setdefault('primary', {})['color'] = primary_color
    if secondary_font:
        cfg.setdefault('styles', {}).setdefault('secondary', {})['font'] = secondary_font
    if secondary_color:
        cfg.setdefault('styles', {}).setdefault('secondary', {})['color'] = secondary_color

    # Sync language settings
    whisper_source = cfg['whisper'].get('source_language', 'auto')
    output_source = cfg['output'].get('source_language', 'auto')
    if whisper_source != 'auto' and output_source == 'auto':
        cfg['output']['source_language'] = whisper_source
    elif output_source != 'auto' and whisper_source == 'auto':
        cfg['whisper']['source_language'] = output_source

    final_source_lang = cfg['output'].get('source_language', 'auto')
    final_target_lang = cfg['output'].get('target_language', 'zh')

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        suffix = cfg['output'].get('format', 'srt')
        lang_suffix = f"_{final_target_lang}" if not no_translate else ""
        proofread_suffix = ".proofread" if proofread_only else ""
        output_path = input_path.parent / f"{input_path.stem}{lang_suffix}{proofread_suffix}.{suffix}"

    # Print header
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

    # --- Load project if requested ---
    if load_project:
        project = SubtitleProject.load(Path(load_project))
        console.print(f"[green]📂 Loaded project: {load_project}[/green]")
        console.print(f"   {len(project.segments)} segments")
        console.print()
        # Export directly
        from src.styles import load_style
        style = load_style(cfg)
        from src.engine import SubGenEngine
        engine = SubGenEngine(cfg)
        engine.export(project, output_path, format=cfg['output'].get('format', 'srt'), style=style)
        console.print(f"\n[bold green]✅ Done![/bold green]")
        console.print(f"Subtitle file: [cyan]{output_path}[/cyan]")
        if save_project:
            project.save(Path(save_project))
            console.print(f"Project file: [cyan]{save_project}[/cyan]")
        return

    # --- Check cache info for display ---
    if not force_transcribe and not proofread_only:
        from src.cache import load_cache, format_cache_info
        cached = load_cache(input_path)
        if cached:
            cache_info = format_cache_info(cached)
            console.print("[green]📂 Found cached transcription[/green]")
            console.print(f"   {cache_info}")
            console.print("   [dim]Use --force-transcribe to re-process[/dim]")
            console.print()

    # --- Check embedded subtitles info for display ---
    if not force_transcribe and not proofread_only:
        from src.cache import load_cache
        cached = load_cache(input_path)
        if not cached:
            from src.embedded import check_embedded_subtitles
            embed_check = check_embedded_subtitles(input_path, final_source_lang, final_target_lang)
            if embed_check['tracks']:
                track_list = ", ".join([
                    f"{t.language or 'und'}({t.codec})" for t in embed_check['tracks']
                ])
                console.print(f"[green]📀 Found embedded subtitles: {track_list}[/green]")
                if embed_check['action'] == 'use_target':
                    console.print(f"   [bold green]✓ Target language ({final_target_lang}) already exists![/bold green]")
                elif embed_check['action'] == 'use_source':
                    track = embed_check['track']
                    console.print(f"   [cyan]Using {track.language or 'embedded'} subtitle as source (skipping Whisper)[/cyan]")
                console.print()

    # --- Proofread-only display ---
    if proofread_only:
        from src.cache import load_cache
        cached = load_cache(input_path)
        if cached and cached.get('segments'):
            has_translations = any(seg.get('translated') for seg in cached['segments'])
            if has_translations:
                console.print("[green]📂 Loading from cache (with translations)[/green]")
                console.print(f"   Loaded {len(cached['segments'])} segments with translations")
            else:
                console.print("[yellow]⚠️  Loading from .srt (no original text for context)[/yellow]")
        else:
            existing_srt = input_path.parent / f"{input_path.stem}_{final_target_lang}.srt"
            if not existing_srt.exists():
                existing_srt = input_path.with_suffix('.srt')
            if existing_srt.exists():
                console.print("[yellow]⚠️  Loading from .srt (no original text for context)[/yellow]")
                console.print(f"   File: {existing_srt.name}")
            else:
                console.print("[red]Error: No cache or subtitle file found[/red]")
                console.print("[dim]Run translation first: subgen run video.mp4 -s --to zh[/dim]")
                raise SystemExit(1)

        console.print()
        console.print(f"[dim]Proofreading segments with provider: {cfg.get('translation', {}).get('provider', 'openai')}[/dim]")

    # --- Build progress callback using rich ---
    progress_state = {}

    def make_rich_progress():
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        )

    _stage_labels = {
        'extracting': ('[cyan]Extracting audio...', '[green]✓ Audio extracted'),
        'transcribing': ('[cyan]Transcribing...', '[green]✓ Transcribed'),
        'translating': ('[cyan]Translating...', '[green]✓ Translation complete'),
        'proofreading': ('[cyan]Proofreading...', '[green]✓ Proofreading complete'),
        'exporting': ('[cyan]Generating subtitles...', '[green]✓ Subtitles generated'),
    }

    try:
        with make_rich_progress() as progress:
            current_task = [None]
            current_stage = [None]

            def on_progress(stage: str, current: int, total: int) -> None:
                labels = _stage_labels.get(stage, (f'[cyan]{stage}...', f'[green]✓ {stage}'))
                if stage != current_stage[0]:
                    # Complete previous task
                    if current_task[0] is not None:
                        prev_labels = _stage_labels.get(current_stage[0], ('', f'[green]✓ Done'))
                        progress.update(current_task[0], description=prev_labels[1])
                        progress.stop_task(current_task[0])
                    # Start new task
                    current_stage[0] = stage
                    task_total = total if total > 1 else None
                    current_task[0] = progress.add_task(labels[0], total=task_total)
                else:
                    if total > 1:
                        progress.update(current_task[0], advance=current)

                # If this is the final update for the stage
                if total > 0 and current >= total and total <= 1:
                    progress.update(current_task[0], description=labels[1])
                    progress.stop_task(current_task[0])

            engine = SubGenEngine(cfg, on_progress=on_progress)

            project = engine.run(
                input_path,
                source_lang=source_lang,
                target_lang=target_lang,
                no_translate=no_translate,
                sentence_aware=sentence_aware,
                proofread=proofread,
                proofread_only=proofread_only,
                bilingual=bilingual,
                force_transcribe=force_transcribe,
            )

            # Handle use_target embedded case: project may have pre-translated segments
            # where translated == text (extracted target lang subs)
            # In that case the engine already returned, just export.

            # Export
            engine.export(project, output_path, format=cfg['output'].get('format', 'srt'))

            # Complete last task
            if current_task[0] is not None:
                labels = _stage_labels.get(current_stage[0], ('', '[green]✓ Done'))
                progress.update(current_task[0], description=labels[1])
                progress.stop_task(current_task[0])

            # Embed in video
            video_output = None
            if cfg['output'].get('embed_in_video', False):
                task5 = progress.add_task("[cyan]Embedding subtitles...", total=None)
                video_output = input_path.with_stem(input_path.stem + '_subbed')
                engine.export_video(project, input_path, video_output, embed_mode='hard')
                progress.update(task5, description="[green]✓ Video generated")
                progress.stop_task(task5)

        console.print("\n[bold green]✅ Done![/bold green]")
        console.print(f"Subtitle file: [cyan]{output_path}[/cyan]")

        if video_output:
            console.print(f"Video file: [cyan]{video_output}[/cyan]")

        # Save project if requested
        if save_project:
            project.save(Path(save_project))
            console.print(f"Project file: [cyan]{save_project}[/cyan]")

    except FileNotFoundError as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise SystemExit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        raise SystemExit(130)

    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        from src.logger import is_debug
        if verbose or is_debug():
            import traceback
            console.print(traceback.format_exc())
        raise SystemExit(1)

    finally:
        try:
            from src.audio import cleanup_temp_files
            cleanup_temp_files(cfg)
        except Exception:
            pass


def run_init_wizard(config_path: str):
    """Run the setup wizard and save config."""
    import yaml
    from src.wizard import run_setup_wizard

    cfg = run_setup_wizard()

    if 'llm' in cfg:
        cfg['translation'] = cfg.pop('llm')

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

    if is_openai_codex_logged_in():
        console.print("  [green]●[/green] ChatGPT Plus/Pro: [green]logged in[/green]")
    else:
        console.print("  [dim]○[/dim] ChatGPT Plus/Pro: [dim]not logged in[/dim]")

    if is_copilot_logged_in():
        console.print("  [green]●[/green] GitHub Copilot: [green]logged in[/green]")
    else:
        console.print("  [dim]○[/dim] GitHub Copilot: [dim]not logged in[/dim]")

    console.print()


@cli.command(name='process', hidden=True)
@click.argument('input_path', type=click.Path(exists=True))
@click.pass_context
def process_shortcut(ctx, input_path):
    """Hidden command for backward compatibility."""
    ctx.invoke(run, input_path=input_path)


@cli.command()
@click.argument('component', type=str)
@click.argument('variant', type=str, required=False)
@click.option('--with-model', is_flag=True, help='Also install recommended model (for whisper)')
def install(component, variant, with_model):
    """Install a component (whisper, model, ffmpeg).

    \b
    EXAMPLES:
        subgen install whisper           Install whisper.cpp engine
        subgen install whisper --with-model  Install engine + recommended model
        subgen install model large-v3    Install a specific Whisper model
        subgen install ffmpeg            Install FFmpeg
    """
    from src.components import ComponentManager
    from src.hardware import detect_hardware
    from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

    cm = ComponentManager()

    def make_progress_callback(progress, task_id):
        def callback(downloaded, total):
            if total > 0:
                progress.update(task_id, completed=downloaded, total=total)
        return callback

    if component == 'whisper':
        console.print("\n🔍 Detecting hardware...")
        hw = detect_hardware()
        if hw.has_nvidia_gpu and hw.has_cuda:
            engine_variant = "cuda"
            console.print(f"  ✓ {hw.nvidia_gpu_name} ({hw.nvidia_vram_gb:.0f}GB VRAM)")
        elif hw.is_apple_silicon:
            engine_variant = "metal"
            console.print("  ✓ Apple Silicon detected")
        else:
            engine_variant = "cpu"
            console.print("  ℹ️  No GPU detected, using CPU variant")

        comp_id = f"whisper-cpp-{engine_variant}"
        console.print(f"\n📥 Installing whisper.cpp ({engine_variant})...")

        with Progress(BarColumn(), DownloadColumn(), TransferSpeedColumn(), console=console) as progress:
            task = progress.add_task("Downloading", total=0)
            cm.install(comp_id, on_progress=make_progress_callback(progress, task))

        console.print("[green]  ✓ Installed![/green]")

        if with_model:
            # Recommend model based on hardware
            if hw.has_nvidia_gpu and hw.nvidia_vram_gb and hw.nvidia_vram_gb >= 8:
                model = "large-v3"
            elif hw.is_apple_silicon:
                model = "large-v3"
            elif hw.has_nvidia_gpu and hw.nvidia_vram_gb and hw.nvidia_vram_gb >= 5:
                model = "medium"
            else:
                model = "small"

            console.print(f"\n📥 Installing Whisper model ({model})...")
            with Progress(BarColumn(), DownloadColumn(), TransferSpeedColumn(), console=console) as progress:
                task = progress.add_task("Downloading", total=0)
                cm.install_model(model, on_progress=make_progress_callback(progress, task))
            console.print("[green]  ✓ Installed![/green]")

    elif component == 'model':
        model_name = variant or "large-v3"
        console.print(f"\n📥 Installing Whisper model ({model_name})...")
        with Progress(BarColumn(), DownloadColumn(), TransferSpeedColumn(), console=console) as progress:
            task = progress.add_task("Downloading", total=0)
            cm.install_model(model_name, on_progress=make_progress_callback(progress, task))
        console.print("[green]  ✓ Installed![/green]")

    elif component == 'ffmpeg':
        console.print("\n📥 Installing FFmpeg...")
        with Progress(BarColumn(), DownloadColumn(), TransferSpeedColumn(), console=console) as progress:
            task = progress.add_task("Downloading", total=0)
            cm.install("ffmpeg", on_progress=make_progress_callback(progress, task))
        console.print("[green]  ✓ Installed![/green]")

    else:
        # Try direct component ID
        try:
            console.print(f"\n📥 Installing {component}...")
            with Progress(BarColumn(), DownloadColumn(), TransferSpeedColumn(), console=console) as progress:
                task = progress.add_task("Downloading", total=0)
                cm.install(component, on_progress=make_progress_callback(progress, task))
            console.print("[green]  ✓ Installed![/green]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise SystemExit(1)


@cli.command()
def doctor():
    """Diagnose the SubGen environment."""
    from src.components import ComponentManager
    from src.hardware import detect_hardware
    from src.auth.store import get_credential

    cm = ComponentManager()
    hw = detect_hardware()

    console.print("\n🏥 SubGen Environment Check")
    console.print("═" * 30)

    # Config
    from src.config import get_subgen_dir
    config_locations = [Path("config.yaml"), get_subgen_dir() / "config.yaml"]
    config_found = None
    for loc in config_locations:
        if loc.exists():
            config_found = loc
            break
    if config_found:
        console.print(f"  Config:     {config_found} [green]✓[/green]")
    else:
        console.print("  Config:     Not found [red]✗[/red] (run: subgen init)")

    # FFmpeg
    ffmpeg = cm.find_ffmpeg()
    if ffmpeg:
        console.print(f"  FFmpeg:     {ffmpeg} [green]✓[/green]")
    else:
        console.print("  FFmpeg:     Not found [red]✗[/red] (run: subgen install ffmpeg)")

    # Whisper engine
    engine = cm.find_whisper_engine()
    if engine:
        console.print(f"  Whisper:    {engine} [green]✓[/green]")
    else:
        console.print("  Whisper:    Not found [red]✗[/red] (run: subgen install whisper)")

    # Models
    model_found = False
    for name in ["large-v3", "medium", "small", "base", "tiny"]:
        model = cm.find_whisper_model(name)
        if model:
            size_mb = model.stat().st_size / (1024 * 1024)
            console.print(f"  Model:      {name} ({size_mb:.0f}MB) [green]✓[/green]")
            model_found = True
            break
    if not model_found:
        console.print("  Model:      Not found [red]✗[/red] (run: subgen install model large-v3)")

    # LLM auth
    copilot = get_credential("copilot")
    chatgpt = get_credential("openai-codex")
    if copilot:
        console.print("  LLM:        Copilot (authenticated) [green]✓[/green]")
    elif chatgpt:
        console.print("  LLM:        ChatGPT (authenticated) [green]✓[/green]")
    else:
        console.print("  LLM:        Not configured [yellow]○[/yellow]")

    # GPU
    if hw.has_nvidia_gpu:
        vram = f" ({hw.nvidia_vram_gb:.0f}GB)" if hw.nvidia_vram_gb else ""
        console.print(f"  GPU:        {hw.nvidia_gpu_name}{vram} [green]✓[/green]")
    elif hw.is_apple_silicon:
        console.print("  GPU:        Apple Silicon [green]✓[/green]")
    else:
        console.print("  GPU:        Not detected [dim]○[/dim]")

    # Disk usage
    usage = cm.disk_usage()
    total = sum(usage.values())
    if total > 0:
        console.print(f"  Disk:       {total / (1024 * 1024):.1f} MB")
    else:
        console.print("  Disk:       (no components installed)")

    # Overall status
    if config_found and ffmpeg:
        console.print("\n  Status: [green]✅ Ready to go![/green]")
    else:
        console.print("\n  Status: [red]❌ Run 'subgen init' to get started[/red]")
    console.print()


@cli.command()
@click.argument('component', type=str)
@click.argument('variant', type=str, required=False)
def uninstall(component, variant):
    """Uninstall a component.

    \b
    EXAMPLES:
        subgen uninstall model large-v3   Remove a model
        subgen uninstall whisper           Remove whisper.cpp engine
        subgen uninstall ffmpeg            Remove FFmpeg
    """
    from src.components import ComponentManager

    cm = ComponentManager()

    if component == 'model' and variant:
        comp_id = f"model-whisper-{variant}"
    elif component == 'whisper':
        # Find which whisper variant is installed
        for suffix in ["cuda", "metal", "cpu"]:
            cid = f"whisper-cpp-{suffix}"
            if cm.is_installed(cid):
                comp_id = cid
                break
        else:
            console.print("[yellow]No whisper engine installed[/yellow]")
            return
    else:
        comp_id = component

    if cm.uninstall(comp_id):
        console.print(f"[green]✓ Uninstalled {comp_id}[/green]")
    else:
        console.print(f"[yellow]{comp_id} is not installed[/yellow]")


def main():
    """Entry point that handles both 'subgen video.mp4' and 'subgen run video.mp4'."""
    import sys

    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        commands = ['run', 'init', 'auth', 'install', 'uninstall', 'doctor', '--help', '-h', '--version']
        if first_arg not in commands and not first_arg.startswith('-'):
            if Path(first_arg).exists() or '.' in first_arg:
                sys.argv.insert(1, 'run')

    cli()


if __name__ == '__main__':
    main()
