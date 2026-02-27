"""Setup wizard for SubGen first-run configuration."""

import sys
from pathlib import Path
from typing import Optional

from .auth.copilot import copilot_login, CopilotAuthError
from .config import is_bundled
from .hardware import detect_hardware, recommend_whisper_config, print_hardware_summary, get_install_instructions


# Provider definitions
WHISPER_PROVIDERS = {
    "local": {
        "name": "Local (faster-whisper)",
        "description": "Free, requires NVIDIA GPU",
        "requires_key": False
    },
    "cpp": {
        "name": "Local (whisper.cpp)",
        "description": "Free, offline, downloads engine + model (~3GB)",
        "requires_key": False
    },
    "mlx": {
        "name": "MLX (Apple Silicon)",
        "description": "Free, optimized for M1/M2/M3 Mac",
        "requires_key": False,
        "mac_only": True
    },
    "groq": {
        "name": "Groq (Cloud)",
        "description": "Free tier, very fast, no GPU needed",
        "requires_key": True,
        "key_name": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys",
    },
    "openai": {
        "name": "OpenAI Whisper API",
        "description": "$0.006/min, most stable",
        "requires_key": True,
        "key_name": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys"
    },
}

LLM_PROVIDERS = {
    "chatgpt": {
        "name": "ChatGPT Plus/Pro (OAuth)",
        "description": "Use your ChatGPT subscription, browser login",
        "requires_key": False,
        "requires_oauth": "chatgpt",
    },
    "copilot": {
        "name": "GitHub Copilot (OAuth)",
        "description": "Use your GitHub Copilot subscription",
        "requires_key": False,
        "requires_oauth": "copilot",
    },
    "deepseek": {
        "name": "DeepSeek",
        "description": "Very cheap (~¥1/M tokens), good for Chinese, free credits",
        "requires_key": True,
        "key_name": "DEEPSEEK_API_KEY",
        "key_url": "https://platform.deepseek.com/"
    },
    "openai": {
        "name": "OpenAI API",
        "description": "gpt-4o-mini ~$0.15/M tokens",
        "requires_key": True,
        "key_name": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys"
    },
    "ollama": {
        "name": "Ollama (Local)",
        "description": "Free, requires local setup",
        "requires_key": False
    },
    "claude": {
        "name": "Claude",
        "description": "claude-3-haiku ~$0.25/M tokens",
        "requires_key": True,
        "key_name": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/"
    }
}


def print_header():
    """Print wizard header."""
    print("\n" + "=" * 50)
    print("  🎬 SubGen Setup Wizard")
    print("=" * 50)
    print("\nSubGen needs two services to work:\n")
    print("  📢 Speech Recognition (Whisper)")
    print("     Converts audio to text\n")
    print("  🌍 Translation (LLM)")
    print("     Translates text to target language\n")
    print("-" * 50)


def print_provider_options(providers: dict, category: str):
    """Print provider options."""
    print(f"\n{category}:\n")

    for i, (key, info) in enumerate(providers.items(), 1):
        rec = " ⭐ recommended" if info.get("recommended") else ""
        print(f"  {i}. {info['name']}")
        print(f"     {info['description']}{rec}\n")


def get_choice(prompt: str, max_choice: int) -> int:
    """Get a numeric choice from user."""
    while True:
        try:
            choice = input(f"{prompt} [1-{max_choice}]: ").strip()
            num = int(choice)
            if 1 <= num <= max_choice:
                return num
            print(f"  Please enter a number between 1 and {max_choice}")
        except ValueError:
            print(f"  Please enter a number between 1 and {max_choice}")
        except (EOFError, KeyboardInterrupt):
            print("\n\nSetup cancelled.")
            sys.exit(1)


def get_api_key(provider_info: dict) -> str:
    """Prompt user for API key."""
    key_name = provider_info.get("key_name", "API_KEY")
    key_url = provider_info.get("key_url", "")

    print(f"\n  Get your API key from: {key_url}")

    while True:
        try:
            key = input(f"  Enter {key_name}: ").strip()
            if key:
                return key
            print("  API key cannot be empty")
        except (EOFError, KeyboardInterrupt):
            print("\n\nSetup cancelled.")
            sys.exit(1)


def setup_copilot_oauth() -> bool:
    """Run Copilot OAuth flow."""
    print("\n  Starting GitHub Copilot login...")

    try:
        def on_waiting():
            print(".", end="", flush=True)

        copilot_login(on_waiting=on_waiting)
        print("\n  ✅ GitHub Copilot authorized successfully!")
        return True
    except CopilotAuthError as e:
        print(f"\n  ❌ Copilot login failed: {e}")
        return False


def setup_chatgpt_oauth() -> bool:
    """Run ChatGPT OAuth flow."""
    print("\n  Starting ChatGPT login...")
    print("  A browser window will open. Log in with your OpenAI account.")

    try:
        from .auth.openai_codex import openai_codex_login
        openai_codex_login()
        print("\n  ✅ ChatGPT authorized successfully!")
        return True
    except Exception as e:
        print(f"\n  ❌ ChatGPT login failed: {e}")
        return False


def run_setup_wizard(config_path: Optional[Path] = None) -> dict:
    """
    Run the interactive setup wizard.

    Returns:
        dict with configuration values
    """
    print_header()

    # Auto-detect hardware
    print("Detecting hardware...")
    hw = detect_hardware()
    print_hardware_summary(hw)

    # Get recommended config
    rec_provider, rec_device, rec_model = recommend_whisper_config(hw)

    # Check if dependencies are installed
    install_cmd = get_install_instructions(hw)
    if install_cmd and not is_bundled():
        print("📦 To use local processing, install:")
        print(f"   {install_cmd}")
        print()

    config = {
        "whisper": {},
        "llm": {},
        "output": {
            "format": "srt",
            "target_language": "zh",
            "bilingual": False
        }
    }

    # Step 1: Whisper provider
    # Filter providers for exe mode (no local/mlx)
    if is_bundled():
        available_providers = {k: v for k, v in WHISPER_PROVIDERS.items() if k in ("cpp", "groq", "openai")}
    else:
        available_providers = WHISPER_PROVIDERS

    # Mark recommended provider
    for key in available_providers:
        available_providers[key]["recommended"] = (key == rec_provider)

    print_provider_options(available_providers, "📢 Speech Recognition (Whisper)")

    # Show auto-detected recommendation
    print(f"  💡 Auto-detected recommendation: {rec_provider}")
    if rec_provider == "local" and hw.nvidia_vram_gb:
        print(f"     (GPU: {hw.nvidia_gpu_name}, {hw.nvidia_vram_gb:.0f}GB VRAM → {rec_model})")
    elif rec_provider == "mlx":
        print("     (Apple Silicon detected)")
    print()

    whisper_keys = list(available_providers.keys())
    whisper_choice = get_choice("Select speech recognition", len(whisper_keys))
    whisper_provider = whisper_keys[whisper_choice - 1]
    whisper_info = available_providers[whisper_provider]

    config["whisper"]["provider"] = whisper_provider
    print(f"\n  ✅ Selected: {whisper_info['name']}")

    if whisper_info.get("requires_key"):
        key = get_api_key(whisper_info)
        config["whisper"][f"{whisper_provider}_key"] = key

    if whisper_provider == "cpp":
        # Install whisper.cpp engine + model
        from .components import ComponentManager
        cm = ComponentManager()

        # Pick engine variant based on hardware
        if hw.has_nvidia_gpu:
            engine_variant = "cuda"
        elif hw.is_apple_silicon:
            engine_variant = "metal"
        else:
            engine_variant = "cpu"

        comp_id = f"whisper-cpp-{engine_variant}"
        if cm.is_installed(comp_id):
            print(f"\n  ✅ whisper.cpp engine ({engine_variant}) already installed")
        else:
            print(f"\n  📥 Downloading whisper.cpp engine ({engine_variant})...")
            try:
                cm.install(comp_id)
                print("  ✅ Engine installed")
            except Exception as e:
                print(f"  ⚠️  Engine install failed: {e}")
                print("  You can install later: subgen install whisper")

        # Recommend and download model
        if hw.has_nvidia_gpu and hw.nvidia_vram_gb and hw.nvidia_vram_gb >= 8:
            rec_model = "large-v3"
        elif hw.is_apple_silicon:
            rec_model = "large-v3"
        elif hw.has_nvidia_gpu and hw.nvidia_vram_gb and hw.nvidia_vram_gb >= 5:
            rec_model = "medium"
        else:
            rec_model = "small"

        print(f"\n  Recommended model: {rec_model}")
        try:
            dl_response = input(f"  Download {rec_model} model? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            dl_response = "y"

        if dl_response != "n":
            model_comp_id = f"model-whisper-{rec_model}"
            if cm.is_installed(model_comp_id):
                print(f"  ✅ {rec_model} model already installed")
            else:
                print(f"  📥 Downloading Whisper {rec_model} model...")
                try:
                    cm.install_model(rec_model)
                    print("  ✅ Model installed")
                except Exception as e:
                    print(f"  ⚠️  Model install failed: {e}")
                    print(f"  You can install later: subgen install model {rec_model}")

        config["whisper"]["cpp_model"] = rec_model
        config["whisper"]["cpp_threads"] = 4

    if whisper_provider == "local":
        # Check if faster-whisper is installed
        try:
            import faster_whisper
            print("  ✅ faster-whisper is installed")
        except ImportError:
            print("\n  ⚠️  faster-whisper is not installed!")
            print("  Run this command to install:")
            if hw.platform == "windows":
                print("    pip install torch --index-url https://download.pytorch.org/whl/cu118")
                print("    pip install faster-whisper")
            else:
                print("    pip install torch faster-whisper")
            print("\n  After installing, run 'subgen init' again.")
            response = input("\n  Continue anyway? [y/N]: ").strip().lower()
            if response != 'y':
                sys.exit(1)

        # Choose model based on VRAM (local model names, not cloud API names)
        if hw.has_nvidia_gpu and hw.nvidia_vram_gb:
            if hw.nvidia_vram_gb >= 8:
                model = "large-v3"
            elif hw.nvidia_vram_gb >= 5:
                model = "medium"
            elif hw.nvidia_vram_gb >= 3:
                model = "small"
            else:
                model = "base"
        else:
            model = "large-v3"
        config["whisper"]["local_model"] = model
        config["whisper"]["device"] = "cuda"
        print(f"  ℹ️  Using {model} model with CUDA.")
        print("  ℹ️  Model will download automatically on first run (~3GB for large-v3)")

    if whisper_provider == "mlx":
        # Check if mlx-whisper is installed
        try:
            import mlx_whisper
            print("  ✅ mlx-whisper is installed")
        except ImportError:
            print("\n  ⚠️  mlx-whisper is not installed!")
            print("  Run: pip install mlx-whisper")
            print("\n  After installing, run 'subgen init' again.")
            response = input("\n  Continue anyway? [y/N]: ").strip().lower()
            if response != 'y':
                sys.exit(1)

        config["whisper"]["local_model"] = "large-v3"
        print("  ℹ️  Using large-v3 model with MLX.")
        print("  ℹ️  Model will download automatically on first run (~3GB)")

    # Step 2: LLM provider
    print("\n" + "-" * 50)
    print_provider_options(LLM_PROVIDERS, "🌍 Translation (LLM)")

    llm_keys = list(LLM_PROVIDERS.keys())
    llm_choice = get_choice("Select translation service", len(llm_keys))
    llm_provider = llm_keys[llm_choice - 1]
    llm_info = LLM_PROVIDERS[llm_provider]

    config["llm"]["provider"] = llm_provider
    print(f"\n  ✅ Selected: {llm_info['name']}")

    if llm_info.get("requires_oauth"):
        oauth_type = llm_info["requires_oauth"]
        if oauth_type == "copilot":
            from .auth.store import load_credentials
            creds = load_credentials()
            if creds.get("copilot", {}).get("access_token"):
                print("  ✅ GitHub Copilot already authorized")
            else:
                success = setup_copilot_oauth()
                if not success:
                    print("  Falling back to manual setup. Run 'subgen auth login copilot' later.")
        elif oauth_type == "chatgpt":
            from .auth.store import load_credentials
            creds = load_credentials()
            if creds.get("chatgpt", {}).get("access_token"):
                print("  ✅ ChatGPT already authorized")
            else:
                success = setup_chatgpt_oauth()
                if not success:
                    print("  Falling back to manual setup. Run 'subgen auth login chatgpt' later.")
    elif llm_info.get("requires_key"):
        key = get_api_key(llm_info)
        config["llm"]["api_key"] = key

    if llm_provider == "ollama":
        config["llm"]["ollama_host"] = "http://localhost:11434"
        config["llm"]["ollama_model"] = "qwen2.5:14b"
        print("  ℹ️  Make sure Ollama is running. Edit config.yaml to change model.")
    elif llm_provider == "openai":
        config["llm"]["model"] = "gpt-4o-mini"
    elif llm_provider == "deepseek":
        config["llm"]["model"] = "deepseek-chat"
    elif llm_provider == "claude":
        config["llm"]["model"] = "claude-3-haiku-20240307"
    elif llm_provider == "chatgpt":
        config["llm"]["model"] = "gpt-5.1-codex-mini"  # Codex API requires gpt-5.x-codex models
    elif llm_provider == "copilot":
        config["llm"]["model"] = "gpt-4o-mini"

    # Step 3: FFmpeg check
    print("\n" + "-" * 50)
    print("\n🔧 Step 3: FFmpeg\n")

    import shutil
    from .components import ComponentManager
    cm_ffmpeg = ComponentManager()
    ffmpeg_path = cm_ffmpeg.find_ffmpeg()
    if ffmpeg_path:
        print(f"  ✅ FFmpeg found: {ffmpeg_path}")
    else:
        print("  ✗ FFmpeg not found")
        try:
            dl_ff = input("  📥 Download FFmpeg automatically? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            dl_ff = "y"
        if dl_ff != "n":
            try:
                cm_ffmpeg.install("ffmpeg")
                print("  ✅ FFmpeg installed")
            except Exception as e:
                print(f"  ⚠️  FFmpeg install failed: {e}")
                print("  You can install later: subgen install ffmpeg")

    # Step 4: Defaults
    print("\n" + "-" * 50)
    print("\n🎯 Step 4: Default Output Settings\n")
    print("  Common options: zh (中文), en (English), ja (日本語), ko (한국어)")

    try:
        lang = input("  Target language [zh]: ").strip() or "zh"
        config["output"]["target_language"] = lang
    except (EOFError, KeyboardInterrupt):
        config["output"]["target_language"] = "zh"

    try:
        bi = input("  Enable bilingual subtitles? [y/N]: ").strip().lower()
        config["output"]["bilingual"] = bi == "y"
    except (EOFError, KeyboardInterrupt):
        pass

    try:
        fmt = input("  Subtitle format (srt/ass/vtt) [srt]: ").strip().lower() or "srt"
        if fmt in ("srt", "ass", "vtt"):
            config["output"]["format"] = fmt
    except (EOFError, KeyboardInterrupt):
        pass

    if config["output"].get("format") == "ass":
        try:
            preset = input("  Style preset (default/netflix/fansub/minimal) [default]: ").strip().lower() or "default"
            if preset in ("default", "netflix", "fansub", "minimal"):
                config.setdefault("styles", {})["preset"] = preset
        except (EOFError, KeyboardInterrupt):
            pass

    # Summary
    print("\n" + "=" * 50)
    print("  ✅ Setup Complete!")
    print("=" * 50)
    print(f"\n  Whisper: {WHISPER_PROVIDERS[whisper_provider]['name']}")
    print(f"  LLM:     {LLM_PROVIDERS[llm_provider]['name']}")
    print(f"  Target:  {config['output']['target_language']}")
    print("\n  Config saved to: config.yaml")
    print("\n  Try it out:")
    run_cmd = "subgen run" if is_bundled() else "python subgen.py run"
    print(f"    {run_cmd} your-video.mp4\n")

    return config


def check_config_exists(config_path: Path = None) -> bool:
    """Check if config file exists."""
    if config_path:
        return config_path.exists()

    # Check common locations
    locations = [
        Path("config.yaml"),
        Path("config.yml"),
        Path.home() / ".subgen" / "config.yaml",
    ]

    return any(p.exists() for p in locations)


def should_run_wizard(config_path: Path = None) -> bool:
    """Determine if setup wizard should run."""
    # If no config exists, run wizard
    if not check_config_exists(config_path):
        return True

    return False
