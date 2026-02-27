"""Tests for security fixes: TOCTOU, zip-slip, SHA256 verification, FFmpeg injection."""

import io
import os
import struct
import tarfile
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.components import (
    ComponentManager,
    _safe_extractall_zip,
    _safe_extractall_tar,
)
from src.subtitle import _escape_ffmpeg_filter_path


# ---------------------------------------------------------------------------
# CRIT-1: tempfile.mktemp() TOCTOU race → replaced with mkdtemp
# ---------------------------------------------------------------------------

class TestTempfileSecure:
    """Verify that transcribe_cpp no longer uses insecure tempfile.mktemp()."""

    def test_no_mktemp_usage(self):
        """Source code must not contain tempfile.mktemp calls."""
        src_path = Path(__file__).parent.parent / "src" / "transcribe_cpp.py"
        source = src_path.read_text()
        # Should use mkdtemp, not mktemp
        assert "mktemp(" not in source, (
            "tempfile.mktemp() is insecure (TOCTOU race). "
            "Use tempfile.mkdtemp() instead."
        )
        assert "mkdtemp(" in source, (
            "Expected tempfile.mkdtemp() to be used for secure temp directory creation."
        )

    def test_mkdtemp_creates_directory(self):
        """mkdtemp should create an actual directory (basic sanity)."""
        tmp_dir = tempfile.mkdtemp(prefix="subgen_test_")
        try:
            assert os.path.isdir(tmp_dir)
        finally:
            os.rmdir(tmp_dir)


# ---------------------------------------------------------------------------
# CRIT-2: Zip Slip / Tar Slip in extractall()
# ---------------------------------------------------------------------------

class TestZipSlipPrevention:
    """Verify that malicious zip archives with path traversal are rejected."""

    def test_safe_zip_normal(self, tmp_path):
        """Normal zip archive should extract successfully."""
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("readme.txt", "hello")
            zf.writestr("subdir/file.txt", "world")
        zip_buf.seek(0)

        dest = tmp_path / "output"
        dest.mkdir()
        with zipfile.ZipFile(zip_buf) as zf:
            _safe_extractall_zip(zf, dest)

        assert (dest / "readme.txt").read_text() == "hello"
        assert (dest / "subdir" / "file.txt").read_text() == "world"

    def test_zip_slip_dotdot_rejected(self, tmp_path):
        """Zip entry with '../' path traversal must be rejected."""
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("../../etc/passwd", "malicious content")
        zip_buf.seek(0)

        dest = tmp_path / "output"
        dest.mkdir()
        with zipfile.ZipFile(zip_buf) as zf:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_extractall_zip(zf, dest)

    def test_zip_slip_absolute_path_rejected(self, tmp_path):
        """Zip entry with absolute path must be rejected."""
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("/tmp/evil.txt", "malicious content")
        zip_buf.seek(0)

        dest = tmp_path / "output"
        dest.mkdir()
        with zipfile.ZipFile(zip_buf) as zf:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_extractall_zip(zf, dest)


class TestTarSlipPrevention:
    """Verify that malicious tar archives with path traversal are rejected."""

    def test_safe_tar_normal(self, tmp_path):
        """Normal tar archive should extract successfully."""
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w:gz") as tf:
            data = b"hello"
            info = tarfile.TarInfo(name="readme.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        tar_buf.seek(0)

        dest = tmp_path / "output"
        dest.mkdir()
        with tarfile.open(fileobj=tar_buf, mode="r:gz") as tf:
            _safe_extractall_tar(tf, dest)

        assert (dest / "readme.txt").read_bytes() == b"hello"

    def test_tar_slip_dotdot_rejected(self, tmp_path):
        """Tar entry with '../' path traversal must be rejected."""
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w:gz") as tf:
            data = b"malicious"
            info = tarfile.TarInfo(name="../../etc/passwd")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        tar_buf.seek(0)

        dest = tmp_path / "output"
        dest.mkdir()
        with tarfile.open(fileobj=tar_buf, mode="r:gz") as tf:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_extractall_tar(tf, dest)

    def test_tar_slip_absolute_path_rejected(self, tmp_path):
        """Tar entry with absolute path must be rejected."""
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w:gz") as tf:
            data = b"malicious"
            info = tarfile.TarInfo(name="/tmp/evil.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        tar_buf.seek(0)

        dest = tmp_path / "output"
        dest.mkdir()
        with tarfile.open(fileobj=tar_buf, mode="r:gz") as tf:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_extractall_tar(tf, dest)

    def test_tar_slip_symlink_escape_rejected(self, tmp_path):
        """Tar entry with symlink pointing outside dest must be rejected."""
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name="evil_link")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../../etc/passwd"
            tf.addfile(info)
        tar_buf.seek(0)

        dest = tmp_path / "output"
        dest.mkdir()
        with tarfile.open(fileobj=tar_buf, mode="r:gz") as tf:
            with pytest.raises(ValueError, match="symlink escaping"):
                _safe_extractall_tar(tf, dest)


# ---------------------------------------------------------------------------
# CRIT-3: SHA256 hashes are all empty strings — must reject empty hashes
# ---------------------------------------------------------------------------

class TestSHA256EmptyHashRejection:
    """Verify that _download raises an error when SHA256 hash is empty."""

    def test_empty_hash_raises_error(self, tmp_path):
        """Downloading with empty SHA256 must raise RuntimeError."""
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        dest = tmp_path / "download_dest"
        with pytest.raises(RuntimeError, match="Integrity verification not available"):
            cm._download("https://example.com/file.bin", dest, sha256="")

    def test_no_hash_raises_error(self, tmp_path):
        """Downloading with no SHA256 (default empty string) must raise RuntimeError."""
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        dest = tmp_path / "download_dest"
        with pytest.raises(RuntimeError, match="Integrity verification not available"):
            cm._download("https://example.com/file.bin", dest)

    def test_valid_hash_accepted(self, tmp_path):
        """Downloading with a valid SHA256 should proceed (mocked network)."""
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        dest = tmp_path / "download_dest"

        fake_content = b"test file content"
        import hashlib
        expected_hash = hashlib.sha256(fake_content).hexdigest()

        # Mock httpx.stream to return fake content
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-length": str(len(fake_content))}
        mock_response.iter_bytes = MagicMock(return_value=[fake_content])

        # Create a mock httpx module with stream function
        mock_httpx = MagicMock()
        mock_httpx.stream = MagicMock(return_value=mock_response)

        import sys
        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            result = cm._download("https://example.com/file.bin", dest, sha256=expected_hash)
            assert result == dest
            assert dest.read_bytes() == fake_content

    def test_wrong_hash_raises_mismatch(self, tmp_path):
        """Downloading with wrong SHA256 must raise RuntimeError with mismatch."""
        cm = ComponentManager(base_dir=tmp_path / "subgen")
        dest = tmp_path / "download_dest"

        fake_content = b"test file content"
        wrong_hash = "a" * 64

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-length": str(len(fake_content))}
        mock_response.iter_bytes = MagicMock(return_value=[fake_content])

        # Create a mock httpx module with stream function
        mock_httpx = MagicMock()
        mock_httpx.stream = MagicMock(return_value=mock_response)

        import sys
        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            with pytest.raises(RuntimeError, match="SHA256 mismatch"):
                cm._download("https://example.com/file.bin", dest, sha256=wrong_hash)


# ---------------------------------------------------------------------------
# CRIT-4: FFmpeg filter-path escaping — missing ;,=@ characters
# ---------------------------------------------------------------------------

class TestFFmpegPathEscapingComplete:
    """Verify that all FFmpeg filter special characters are properly escaped."""

    def test_semicolon_escaped(self):
        """Semicolon (filter separator) must be escaped."""
        assert _escape_ffmpeg_filter_path("path;injection") == r"path\;injection"

    def test_comma_escaped(self):
        """Comma (option separator) must be escaped."""
        assert _escape_ffmpeg_filter_path("file,name.srt") == r"file\,name.srt"

    def test_equals_escaped(self):
        """Equals sign (key=value separator) must be escaped."""
        assert _escape_ffmpeg_filter_path("key=value.srt") == r"key\=value.srt"

    def test_at_sign_escaped(self):
        """At sign (link label) must be escaped."""
        assert _escape_ffmpeg_filter_path("user@host.srt") == r"user\@host.srt"

    def test_all_special_chars_escaped(self):
        """All FFmpeg special characters should be escaped in a combined test."""
        # Input has every special character
        path = "C:\\dir\\f'i:l;e,n=a@m[e].srt"
        result = _escape_ffmpeg_filter_path(path)
        # Backslash → forward slash, then each special char escaped
        assert result == r"C\:/dir/f\'i\:l\;e\,n\=a\@m\[e\].srt"

    def test_existing_escape_backslash(self):
        """Backslashes should be converted to forward slashes."""
        assert _escape_ffmpeg_filter_path("C:\\Users\\test") == r"C\:/Users/test"

    def test_existing_escape_colon(self):
        """Colons should be escaped."""
        assert _escape_ffmpeg_filter_path("C:/file") == r"C\:/file"

    def test_existing_escape_single_quote(self):
        """Single quotes should be escaped."""
        assert _escape_ffmpeg_filter_path("it's") == r"it\'s"

    def test_existing_escape_brackets(self):
        """Brackets should be escaped."""
        assert _escape_ffmpeg_filter_path("file[1]") == r"file\[1\]"

    def test_unix_path_clean(self):
        """Unix paths without special chars should remain unchanged."""
        result = _escape_ffmpeg_filter_path("/home/user/video.srt")
        assert result == "/home/user/video.srt"

    def test_filter_injection_prevention(self):
        """A crafted filename trying to inject a filter should be neutralized."""
        # Attacker tries: subtitle.srt';[evil]filter=inject
        malicious = "subtitle.srt';[evil]filter=inject"
        result = _escape_ffmpeg_filter_path(malicious)
        # Every special char should be escaped, preventing injection
        assert result == r"subtitle.srt\'\;\[evil\]filter\=inject"
