"""Setup wizard for SubGen first-run configuration."""

import sys
from pathlib import Path
from typing import Optional

from .auth.copilot import copilot_login, CopilotAuthError
from .hardware import detect_hardware, recommend_whisper_config, print_hardware_summary, get_install_instructions


# Provider definitions
WHISPER_PROVIDERS = {
    "groq": {
        "name": "Groq",
        "description": "Free tier, very fast",
        "requires_key": True,
        "key_name": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys",
    },
    "mlx": {
        "name": "MLX (Apple Silicon)",
        "description": "Free, optimized for M1/M2/M3 Mac",
        "requires_key": False,
        "mac_only": True
    },
    "openai": {
        "name": "OpenAI",
        "description": "$0.006/min, most stable",
        "requires_key": True,
        "key_name": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys"
    },
    "local": {
        "name": "Local (faster-whisper)",
        "description": "Free, requires NVIDIA GPU with 4GB+ VRAM",
        "requires_key": False
    }
}

LLM_PROVIDERS = {
    "copilot": {
        "name": "GitHub Copilot",
        "description": "Use your GitHub subscription, OAuth login",
        "requires_key": False,
        "requires_oauth": True,
        "recommended": True
    },
    "openai": {
        "name": "OpenAI",
        "description": "gpt-4o-mini ~$0.15/M tokens",
        "requires_key": True,
        "key_name": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys"
    },
    "deepseek": {
        "name": "DeepSeek",
        "description": "Very cheap, good for Chinese",
        "requires_key": True,
        "key_name": "DEEPSEEK_API_KEY",
        "key_url": "https://platform.deepseek.com/"
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
    if install_cmd:
        print(f"📦 To use local processing, install:")
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
    # Mark recommended provider
    for key in WHISPER_PROVIDERS:
        WHISPER_PROVIDERS[key]["recommended"] = (key == rec_provider)
    
    print_provider_options(WHISPER_PROVIDERS, "📢 Speech Recognition (Whisper)")
    
    # Show auto-detected recommendation
    print(f"  💡 Auto-detected recommendation: {rec_provider}")
    if rec_provider == "local" and hw.nvidia_vram_gb:
        print(f"     (GPU: {hw.nvidia_gpu_name}, {hw.nvidia_vram_gb:.0f}GB VRAM → {rec_model})")
    elif rec_provider == "mlx":
        print(f"     (Apple Silicon detected)")
    print()

    whisper_keys = list(WHISPER_PROVIDERS.keys())
    whisper_choice = get_choice("Select speech recognition", len(whisper_keys))
    whisper_provider = whisper_keys[whisper_choice - 1]
    whisper_info = WHISPER_PROVIDERS[whisper_provider]

    config["whisper"]["provider"] = whisper_provider
    print(f"\n  ✅ Selected: {whisper_info['name']}")

    if whisper_info.get("requires_key"):
        key = get_api_key(whisper_info)
        config["whisper"][f"{whisper_provider}_key"] = key

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
        
        # Use auto-detected model if available
        if hw.has_nvidia_gpu and hw.nvidia_vram_gb:
            model = rec_model
        else:
            model = "large-v3"
        config["whisper"]["local_model"] = model
        config["whisper"]["device"] = "cuda"
        print(f"  ℹ️  Using {model} model with CUDA.")
        print(f"  ℹ️  Model will download automatically on first run (~3GB for large-v3)")
    
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
        print(f"  ℹ️  Using large-v3 model with MLX.")
        print(f"  ℹ️  Model will download automatically on first run (~3GB)")

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
        if llm_provider == "copilot":
            success = setup_copilot_oauth()
            if not success:
                print("  Falling back to manual setup. You can run 'subgen auth login copilot' later.")
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

    # Step 3: Target language
    print("\n" + "-" * 50)
    print("\n🎯 Default Target Language:\n")
    print("  Common options: zh (中文), en (English), ja (日本語), ko (한국어)")

    try:
        lang = input("  Enter target language [zh]: ").strip() or "zh"
        config["output"]["target_language"] = lang
    except (EOFError, KeyboardInterrupt):
        config["output"]["target_language"] = "zh"

    # Summary
    print("\n" + "=" * 50)
    print("  ✅ Setup Complete!")
    print("=" * 50)
    print(f"\n  Whisper: {WHISPER_PROVIDERS[whisper_provider]['name']}")
    print(f"  LLM:     {LLM_PROVIDERS[llm_provider]['name']}")
    print(f"  Target:  {config['output']['target_language']}")
    print("\n  Config saved to: config.yaml")
    print("\n  Try it out:")
    print("    python subgen.py your-video.mp4\n")

    return config


def check_config_exists(config_path: Path = None) -> bool:
    """Check if config file exists."""
    if config_path:
        return config_path.exists()

    # Check common locations
    locations = [
        Path("config.yaml"),
        Path("config.yml"),
    ]

    return any(p.exists() for p in locations)


def should_run_wizard(config_path: Path = None) -> bool:
    """Determine if setup wizard should run."""
    # If no config exists, run wizard
    if not check_config_exists(config_path):
        return True

    return False
