"""Hardware detection for optimal Whisper provider selection."""

import platform
import subprocess
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class HardwareInfo:
    """Detected hardware information."""
    platform: str  # darwin, linux, windows
    arch: str  # arm64, x86_64
    is_apple_silicon: bool
    has_nvidia_gpu: bool
    nvidia_gpu_name: Optional[str]
    nvidia_vram_gb: Optional[float]
    has_cuda: bool
    cuda_version: Optional[str]


def detect_hardware() -> HardwareInfo:
    """Detect system hardware capabilities."""
    system = platform.system().lower()
    arch = platform.machine().lower()
    
    # Normalize platform names
    if system == "darwin":
        plat = "darwin"
    elif system == "windows":
        plat = "windows"
    else:
        plat = "linux"
    
    # Check Apple Silicon
    is_apple_silicon = (plat == "darwin" and arch == "arm64")
    
    # Check NVIDIA GPU
    has_nvidia = False
    gpu_name = None
    vram_gb = None
    has_cuda = False
    cuda_version = None
    
    if not is_apple_silicon:
        # Try nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = lines[0].split(',')
                    gpu_name = parts[0].strip()
                    if len(parts) > 1:
                        vram_mb = float(parts[1].strip())
                        vram_gb = vram_mb / 1024
                    has_nvidia = True
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        
        # Check CUDA via PyTorch
        try:
            import torch
            has_cuda = torch.cuda.is_available()
            if has_cuda:
                cuda_version = torch.version.cuda
                if not gpu_name:
                    gpu_name = torch.cuda.get_device_name(0)
                if not vram_gb:
                    vram_bytes = torch.cuda.get_device_properties(0).total_memory
                    vram_gb = vram_bytes / (1024 ** 3)
                has_nvidia = True
        except ImportError:
            pass
    
    return HardwareInfo(
        platform=plat,
        arch=arch,
        is_apple_silicon=is_apple_silicon,
        has_nvidia_gpu=has_nvidia,
        nvidia_gpu_name=gpu_name,
        nvidia_vram_gb=vram_gb,
        has_cuda=has_cuda,
        cuda_version=cuda_version
    )


def recommend_whisper_config(hw: HardwareInfo) -> Tuple[str, str, str]:
    """
    Recommend optimal Whisper configuration based on hardware.
    
    Returns:
        Tuple of (provider, device, model)
    """
    # Apple Silicon: MLX is best
    if hw.is_apple_silicon:
        return ("mlx", "cpu", "large-v3")
    
    # NVIDIA GPU with CUDA
    if hw.has_nvidia_gpu and hw.has_cuda:
        # Choose model based on VRAM
        if hw.nvidia_vram_gb:
            if hw.nvidia_vram_gb >= 8:
                model = "large-v3"
            elif hw.nvidia_vram_gb >= 5:
                model = "medium"
            elif hw.nvidia_vram_gb >= 3:
                model = "small"
            else:
                model = "base"
        else:
            model = "medium"  # Safe default
        
        return ("local", "cuda", model)
    
    # NVIDIA GPU but no CUDA installed
    if hw.has_nvidia_gpu and not hw.has_cuda:
        # Suggest installing CUDA, but default to cloud
        return ("groq", "cpu", "whisper-large-v3")
    
    # No GPU: recommend cloud API
    return ("groq", "cpu", "whisper-large-v3")


def get_install_instructions(hw: HardwareInfo) -> Optional[str]:
    """Get installation instructions for missing dependencies."""
    if hw.is_apple_silicon:
        try:
            import mlx_whisper
            return None
        except ImportError:
            return "pip install mlx-whisper"
    
    if hw.has_nvidia_gpu:
        if not hw.has_cuda:
            if hw.platform == "windows":
                return (
                    "# Install PyTorch with CUDA:\n"
                    "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118\n"
                    "pip install faster-whisper"
                )
            else:
                return (
                    "# Install PyTorch with CUDA:\n"
                    "pip install torch torchvision torchaudio\n"
                    "pip install faster-whisper"
                )
        else:
            try:
                import faster_whisper
                return None
            except ImportError:
                return "pip install faster-whisper"
    
    return None


def print_hardware_summary(hw: HardwareInfo) -> None:
    """Print a summary of detected hardware."""
    print(f"\n🔍 Hardware Detection")
    print(f"   Platform: {hw.platform} ({hw.arch})")
    
    if hw.is_apple_silicon:
        print(f"   Apple Silicon: ✅ Detected")
        print(f"   Recommended: MLX Whisper (fast, native)")
    elif hw.has_nvidia_gpu:
        print(f"   NVIDIA GPU: ✅ {hw.nvidia_gpu_name}")
        if hw.nvidia_vram_gb:
            print(f"   VRAM: {hw.nvidia_vram_gb:.1f} GB")
        if hw.has_cuda:
            print(f"   CUDA: ✅ {hw.cuda_version}")
            print(f"   Recommended: faster-whisper (local, fast)")
        else:
            print(f"   CUDA: ❌ Not installed")
            print(f"   Recommended: Install CUDA for local processing")
    else:
        print(f"   GPU: ❌ Not detected")
        print(f"   Recommended: Cloud API (Groq is free and fast)")
    
    print()
