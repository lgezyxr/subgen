"""Component manager for downloading and managing SubGen components."""

import hashlib
import json
import os
import platform
import shutil
import struct
import tarfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Component:
    """Component definition from registry."""
    id: str
    name: str
    type: str  # engine | model | tool
    version: str
    description: str
    size_bytes: int
    urls: Dict[str, str]
    sha256: Dict[str, str]
    install_path: str
    executable: str = ""
    requires: List[str] = field(default_factory=list)


@dataclass
class InstalledComponent:
    """Installed component record."""
    id: str
    version: str
    path: Path
    installed_at: str
    size_bytes: int


# Built-in registry fallback
BUILTIN_REGISTRY: Dict[str, Any] = {
    "version": "1",
    "updated": "2026-02-26T00:00:00Z",
    "components": {
        "whisper-cpp-cuda": {
            "name": "whisper.cpp (CUDA)",
            "type": "engine",
            "version": "1.7.3",
            "description": "Local speech recognition with NVIDIA GPU acceleration",
            "urls": {
                "linux-x64": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cuda-linux-x64.tar.gz",
                "windows": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cuda-windows-x64.zip",
            },
            "sha256": {"linux-x64": "", "windows": ""},
            "size_bytes": 15728640,
            "install_path": "bin/whisper-cpp",
            "executable": "whisper-cpp",
        },
        "whisper-cpp-cpu": {
            "name": "whisper.cpp (CPU)",
            "type": "engine",
            "version": "1.7.3",
            "description": "Local speech recognition (CPU only)",
            "urls": {
                "linux-x64": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cpu-linux-x64.tar.gz",
                "windows": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cpu-windows-x64.zip",
                "macos-x64": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cpu-macos-x64.tar.gz",
                "macos-arm64": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-cpu-macos-arm64.tar.gz",
            },
            "sha256": {"linux-x64": "", "windows": "", "macos-x64": "", "macos-arm64": ""},
            "size_bytes": 5242880,
            "install_path": "bin/whisper-cpp",
            "executable": "whisper-cpp",
        },
        "whisper-cpp-metal": {
            "name": "whisper.cpp (Metal)",
            "type": "engine",
            "version": "1.7.3",
            "description": "Local speech recognition with Apple Metal acceleration",
            "urls": {
                "macos-arm64": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-metal-macos-arm64.tar.gz",
                "macos-x64": "https://github.com/lgezyxr/subgen/releases/download/components-v1/whisper-cpp-metal-macos-x64.tar.gz",
            },
            "sha256": {"macos-arm64": "", "macos-x64": ""},
            "size_bytes": 8388608,
            "install_path": "bin/whisper-cpp",
            "executable": "whisper-cpp",
        },
        "model-whisper-tiny": {
            "name": "Whisper Tiny",
            "type": "model",
            "version": "1.0",
            "description": "Smallest model, 75MB, fast but lower quality",
            "urls": {"*": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"},
            "sha256": {"*": ""},
            "size_bytes": 78643200,
            "install_path": "models/whisper/ggml-tiny.bin",
        },
        "model-whisper-base": {
            "name": "Whisper Base",
            "type": "model",
            "version": "1.0",
            "description": "Base model, 142MB, balanced for quick tasks",
            "urls": {"*": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"},
            "sha256": {"*": ""},
            "size_bytes": 148897792,
            "install_path": "models/whisper/ggml-base.bin",
        },
        "model-whisper-small": {
            "name": "Whisper Small",
            "type": "model",
            "version": "1.0",
            "description": "Small model, 466MB, good quality",
            "urls": {"*": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"},
            "sha256": {"*": ""},
            "size_bytes": 488636416,
            "install_path": "models/whisper/ggml-small.bin",
        },
        "model-whisper-medium": {
            "name": "Whisper Medium",
            "type": "model",
            "version": "1.0",
            "description": "Medium model, 1.5GB, great quality",
            "urls": {"*": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"},
            "sha256": {"*": ""},
            "size_bytes": 1610612736,
            "install_path": "models/whisper/ggml-medium.bin",
        },
        "model-whisper-large-v3": {
            "name": "Whisper Large V3",
            "type": "model",
            "version": "1.0",
            "description": "Best quality, 3.1GB, requires ≥8GB VRAM",
            "urls": {"*": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin"},
            "sha256": {"*": ""},
            "size_bytes": 3326234624,
            "install_path": "models/whisper/ggml-large-v3.bin",
        },
        "ffmpeg": {
            "name": "FFmpeg",
            "type": "tool",
            "version": "7.1",
            "description": "Audio/video processing (required for video input)",
            "urls": {
                "linux-x64": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
                "windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
                "macos-arm64": "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
                "macos-x64": "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
            },
            "sha256": {"linux-x64": "", "windows": "", "macos-arm64": "", "macos-x64": ""},
            "size_bytes": 83886080,
            "install_path": "bin",
            "executable": "ffmpeg",
        },
    },
}

CACHE_MAX_AGE_SECONDS = 24 * 3600  # 24 hours


def _safe_extractall_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    """Safely extract all members of a zip archive, preventing zip-slip attacks.

    Validates that every extracted file resolves to a path within the
    destination directory. Rejects any entry that would escape via '..'
    traversal or absolute paths.

    Args:
        zf: An open ZipFile object.
        dest: Target directory for extraction.

    Raises:
        ValueError: If any archive member would extract outside dest.
    """
    dest_resolved = dest.resolve()
    for member_name in zf.namelist():
        member_path = (dest / member_name).resolve()
        # Ensure the resolved path is within or equal to the destination
        if not (member_path == dest_resolved or str(member_path).startswith(str(dest_resolved) + os.sep)):
            raise ValueError(
                f"Zip archive contains path traversal entry: {member_name!r}. "
                f"Extraction aborted for security."
            )
    zf.extractall(dest)


def _safe_extractall_tar(tf: tarfile.TarFile, dest: Path) -> None:
    """Safely extract all members of a tar archive, preventing tar-slip attacks.

    Validates that every extracted file resolves to a path within the
    destination directory. Rejects any entry that would escape via '..'
    traversal, absolute paths, or symlink tricks.

    Args:
        tf: An open TarFile object.
        dest: Target directory for extraction.

    Raises:
        ValueError: If any archive member would extract outside dest.
    """
    dest_resolved = dest.resolve()
    for member in tf.getmembers():
        member_path = (dest / member.name).resolve()
        # Ensure the resolved path is within or equal to the destination
        if not (member_path == dest_resolved or str(member_path).startswith(str(dest_resolved) + os.sep)):
            raise ValueError(
                f"Tar archive contains path traversal entry: {member.name!r}. "
                f"Extraction aborted for security."
            )
        # Also reject absolute paths and symlinks pointing outside
        if member.issym() or member.islnk():
            link_target = (dest / member.linkname).resolve()
            if not (link_target == dest_resolved or str(link_target).startswith(str(dest_resolved) + os.sep)):
                raise ValueError(
                    f"Tar archive contains symlink escaping target directory: "
                    f"{member.name!r} -> {member.linkname!r}. "
                    f"Extraction aborted for security."
                )
    tf.extractall(dest)


class ComponentManager:
    """Manage downloading, installing, updating, and removing components."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """Initialize component manager.

        Args:
            base_dir: Base directory for components. Defaults to ~/.subgen/
        """
        self.base_dir = base_dir or Path.home() / ".subgen"
        self.bin_dir = self.base_dir / "bin"
        self.models_dir = self.base_dir / "models" / "whisper"
        self.installed_path = self.base_dir / "installed.json"
        self.registry_path = self.base_dir / "components.json"

        # Create directories
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.platform = self._detect_platform()
        self.registry = self._refresh_registry()

    def _detect_platform(self) -> str:
        """Detect current platform.

        Returns:
            One of: windows, linux-x64, linux-arm64, linux-armv7l,
                    macos-x64, macos-arm64

        Raises:
            RuntimeError: If the architecture is not supported.
        """
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "windows":
            return "windows"
        elif system == "darwin":
            if machine == "arm64":
                return "macos-arm64"
            return "macos-x64"
        else:
            # Linux — detect architecture
            arch_map = {
                "x86_64": "linux-x64",
                "amd64": "linux-x64",
                "aarch64": "linux-arm64",
                "arm64": "linux-arm64",
                "armv7l": "linux-armv7l",
            }
            linux_platform = arch_map.get(machine)
            if linux_platform is None:
                raise RuntimeError(
                    f"Unsupported architecture: {machine} on {system}. "
                    f"Supported Linux architectures: x86_64, aarch64, armv7l"
                )
            return linux_platform

    def _refresh_registry(self) -> Dict[str, Any]:
        """Load component registry from local cache or builtin fallback.

        Returns:
            Registry dictionary with component definitions.
        """
        # Try local cache first
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r") as f:
                    cached = json.load(f)
                # Check if cache is fresh (24h)
                cached_at = cached.get("_cached_at", 0)
                if time.time() - cached_at < CACHE_MAX_AGE_SECONDS:
                    return cached
            except (json.JSONDecodeError, IOError):
                pass

        # Use builtin fallback
        registry = BUILTIN_REGISTRY.copy()
        registry["_cached_at"] = time.time()

        # Save to local cache
        try:
            with open(self.registry_path, "w") as f:
                json.dump(registry, f, indent=2)
        except IOError:
            pass

        return registry

    def _load_installed(self) -> Dict[str, Any]:
        """Load installed components state."""
        if self.installed_path.exists():
            try:
                with open(self.installed_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"components": {}}

    def _save_installed(self, data: Dict[str, Any]) -> None:
        """Save installed components state atomically."""
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.installed_path.parent),
            prefix=".installed_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, str(self.installed_path))
        except BaseException:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def list_available(self) -> List[Component]:
        """List all available components for current platform."""
        components = []
        for cid, info in self.registry.get("components", {}).items():
            urls = info.get("urls", {})
            # Check if available for current platform
            if self.platform in urls or "*" in urls:
                components.append(Component(
                    id=cid,
                    name=info["name"],
                    type=info["type"],
                    version=info["version"],
                    description=info["description"],
                    size_bytes=info["size_bytes"],
                    urls=urls,
                    sha256=info.get("sha256", {}),
                    install_path=info["install_path"],
                    executable=info.get("executable", ""),
                ))
        return components

    def list_installed(self) -> List[InstalledComponent]:
        """List all installed components."""
        data = self._load_installed()
        result = []
        for cid, info in data.get("components", {}).items():
            result.append(InstalledComponent(
                id=cid,
                version=info["version"],
                path=Path(info["path"]),
                installed_at=info["installed_at"],
                size_bytes=info["size_bytes"],
            ))
        return result

    def is_installed(self, component_id: str) -> bool:
        """Check if a component is installed."""
        data = self._load_installed()
        if component_id not in data.get("components", {}):
            return False
        # Verify file still exists
        path = Path(data["components"][component_id]["path"])
        return path.exists()

    def get_path(self, component_id: str) -> Optional[Path]:
        """Get path to an installed component."""
        data = self._load_installed()
        info = data.get("components", {}).get(component_id)
        if info:
            p = Path(info["path"])
            if p.exists():
                return p
        return None

    def needs_update(self, component_id: str) -> bool:
        """Check if a component has an available update."""
        data = self._load_installed()
        installed = data.get("components", {}).get(component_id)
        if not installed:
            return False
        registry_info = self.registry.get("components", {}).get(component_id)
        if not registry_info:
            return False
        return installed["version"] != registry_info["version"]

    def install(self, component_id: str,
                on_progress: Optional[Callable[[int, int], None]] = None) -> Path:
        """Download and install a component.

        Args:
            component_id: Component identifier.
            on_progress: Progress callback(downloaded_bytes, total_bytes).

        Returns:
            Path to installed component.

        Raises:
            ValueError: If component not found or not available for platform.
            RuntimeError: If download or verification fails.
        """
        comp_info = self.registry.get("components", {}).get(component_id)
        if not comp_info:
            raise ValueError(f"Unknown component: {component_id}")

        urls = comp_info.get("urls", {})
        url = urls.get(self.platform) or urls.get("*")
        if not url:
            raise ValueError(f"Component {component_id} not available for {self.platform}")

        sha256_map = comp_info.get("sha256", {})
        expected_sha = sha256_map.get(self.platform) or sha256_map.get("*", "")

        install_path_rel = comp_info["install_path"]
        install_path = self.base_dir / install_path_rel

        # Determine if this is a direct file or needs extraction
        is_archive = url.endswith((".zip", ".tar.gz", ".tar.xz", ".tgz"))

        if is_archive:
            # Download to unique temp file then extract — avoids collisions
            # when multiple concurrent downloads are in progress.
            import tempfile
            tmp_fd, tmp_file_str = tempfile.mkstemp(
                prefix="subgen_download_", dir=str(self.base_dir)
            )
            os.close(tmp_fd)
            tmp_file = Path(tmp_file_str)
            try:
                self._download(url, tmp_file, on_progress=on_progress, sha256=expected_sha)
                # Extract safely (validate paths to prevent zip-slip)
                install_path.mkdir(parents=True, exist_ok=True)
                if url.endswith(".zip"):
                    with zipfile.ZipFile(tmp_file) as zf:
                        _safe_extractall_zip(zf, install_path)
                elif url.endswith((".tar.gz", ".tgz")):
                    with tarfile.open(tmp_file, "r:gz") as tf:
                        _safe_extractall_tar(tf, install_path)
                elif url.endswith(".tar.xz"):
                    with tarfile.open(tmp_file, "r:xz") as tf:
                        _safe_extractall_tar(tf, install_path)

                # Make executables executable
                executable = comp_info.get("executable", "")
                if executable:
                    for p in install_path.rglob(executable + "*"):
                        p.chmod(p.stat().st_mode | 0o755)
            finally:
                tmp_file.unlink(missing_ok=True)

            result_path = install_path
        else:
            # Direct file download (e.g., model files)
            install_path.parent.mkdir(parents=True, exist_ok=True)
            self._download(url, install_path, on_progress=on_progress, sha256=expected_sha)
            result_path = install_path

        # Record installation
        data = self._load_installed()
        actual_size = self._get_size(result_path)
        data["components"][component_id] = {
            "version": comp_info["version"],
            "path": str(result_path),
            "installed_at": datetime.now().isoformat(),
            "size_bytes": actual_size,
        }
        self._save_installed(data)

        return result_path

    def install_model(self, model_name: str,
                      on_progress: Optional[Callable[[int, int], None]] = None) -> Path:
        """Install a Whisper model by short name.

        Args:
            model_name: One of tiny, base, small, medium, large-v3.
            on_progress: Progress callback.

        Returns:
            Path to installed model file.
        """
        component_id = f"model-whisper-{model_name}"
        return self.install(component_id, on_progress=on_progress)

    def uninstall(self, component_id: str) -> bool:
        """Remove an installed component.

        Returns:
            True if component was uninstalled, False if not found.
        """
        data = self._load_installed()
        info = data.get("components", {}).get(component_id)
        if not info:
            return False

        path = Path(info["path"])
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

        del data["components"][component_id]
        self._save_installed(data)
        return True

    def find_ffmpeg(self) -> Optional[Path]:
        """Find ffmpeg binary.

        Search order: 1) ~/.subgen/bin/ 2) system PATH.

        Returns:
            Path to ffmpeg or None.
        """
        # Check managed installation
        suffix = ".exe" if self.platform == "windows" else ""
        local = self.bin_dir / f"ffmpeg{suffix}"
        if local.exists():
            return local

        # Search in extracted dirs
        for p in self.bin_dir.rglob(f"ffmpeg{suffix}"):
            if p.is_file():
                return p

        # Check PATH
        which = shutil.which("ffmpeg")
        if which:
            return Path(which)

        return None

    def find_whisper_engine(self) -> Optional[Path]:
        """Find whisper-cpp binary.

        Returns:
            Path to whisper-cpp executable or None.
        """
        suffix = ".exe" if self.platform == "windows" else ""
        whisper_dir = self.bin_dir / "whisper-cpp"

        if whisper_dir.exists():
            # Search for the binary (may be in a subdirectory after extraction)
            for name in [f"whisper-cpp{suffix}", f"main{suffix}", f"whisper{suffix}"]:
                for p in whisper_dir.rglob(name):
                    if p.is_file():
                        return p

        # Direct check
        direct = self.bin_dir / f"whisper-cpp{suffix}"
        if direct.exists():
            return direct

        return None

    def find_whisper_model(self, model_name: str) -> Optional[Path]:
        """Find a downloaded Whisper model.

        Args:
            model_name: Model name (tiny, base, small, medium, large-v3).

        Returns:
            Path to model file or None.
        """
        model_path = self.models_dir / f"ggml-{model_name}.bin"
        if model_path.exists():
            return model_path
        return None

    def _download(self, url: str, dest: Path,
                  on_progress: Optional[Callable[[int, int], None]] = None,
                  sha256: str = "") -> Path:
        """Download a file with progress and SHA256 verification.

        Args:
            url: Download URL.
            dest: Destination path.
            on_progress: Callback(downloaded_bytes, total_bytes).
            sha256: Expected SHA256 hash. If empty, raises an error
                    indicating integrity verification is not available.

        Returns:
            Path to downloaded file.

        Raises:
            RuntimeError: If hash is empty (integrity cannot be verified)
                          or if hash does not match.
        """
        # SECURITY: Reject downloads with empty/missing SHA256 hash.
        # All components in the registry MUST have valid SHA256 hashes
        # to prevent MITM substitution of arbitrary binaries.
        if not sha256:
            raise RuntimeError(
                f"Integrity verification not available for this component — "
                f"please verify manually or update the registry with a valid "
                f"SHA256 hash. URL: {url}"
            )

        import httpx

        dest.parent.mkdir(parents=True, exist_ok=True)

        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            hasher = hashlib.sha256()

            with open(dest, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    hasher.update(chunk)
                    if on_progress:
                        on_progress(downloaded, total)

        # Verify checksum
        actual = hasher.hexdigest()
        if actual != sha256:
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"SHA256 mismatch for {url}:\n"
                f"  expected: {sha256}\n"
                f"  got:      {actual}"
            )

        return dest

    def disk_usage(self) -> Dict[str, int]:
        """Get disk usage for each installed component.

        Returns:
            Dict mapping component_id to bytes used.
        """
        data = self._load_installed()
        result = {}
        for cid, info in data.get("components", {}).items():
            path = Path(info["path"])
            result[cid] = self._get_size(path) if path.exists() else 0
        return result

    @staticmethod
    def _get_size(path: Path) -> int:
        """Get total size of a file or directory."""
        if path.is_file():
            return path.stat().st_size
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total
