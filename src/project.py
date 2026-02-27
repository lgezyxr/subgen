"""Subtitle project management."""

import json
import os
import tempfile
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .transcribe import Segment, Word
from .styles import StyleProfile

# Current project file format version
PROJECT_VERSION = "0.2"
# Versions compatible with the current loader
COMPATIBLE_VERSIONS = {"0.1", "0.2"}


@dataclass
class ProjectMetadata:
    """Project metadata."""

    video_path: str = ""
    source_lang: str = ""
    target_lang: str = ""
    whisper_provider: str = ""
    llm_provider: str = ""
    llm_model: str = ""
    created_at: str = ""
    modified_at: str = ""
    source_from: str = ""  # 'cache', 'embedded', or 'transcribed'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "video_path": self.video_path,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "whisper_provider": self.whisper_provider,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "source_from": self.source_from,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectMetadata":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProjectState:
    """Project processing state."""

    is_transcribed: bool = False
    is_translated: bool = False
    is_proofread: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "is_transcribed": self.is_transcribed,
            "is_translated": self.is_translated,
            "is_proofread": self.is_proofread,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectState":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _segment_to_dict(seg: Segment) -> Dict[str, Any]:
    """Serialize a Segment to dictionary."""
    d: Dict[str, Any] = {
        "start": seg.start,
        "end": seg.end,
        "text": seg.text,
    }
    if seg.translated:
        d["translated"] = seg.translated
    if seg.translated_raw:
        d["translated_raw"] = seg.translated_raw
    if seg.words:
        d["words"] = [{"text": w.text, "start": w.start, "end": w.end} for w in seg.words]
    if seg.no_speech_prob:
        d["no_speech_prob"] = seg.no_speech_prob
    if seg.avg_logprob:
        d["avg_logprob"] = seg.avg_logprob
    return d


def _segment_from_dict(data: Dict[str, Any]) -> Segment:
    """Deserialize a Segment from dictionary."""
    words = [Word(**w) for w in data.get("words", [])]
    return Segment(
        start=data["start"],
        end=data["end"],
        text=data.get("text", ""),
        translated=data.get("translated", ""),
        translated_raw=data.get("translated_raw", ""),
        words=words,
        no_speech_prob=data.get("no_speech_prob", 0.0),
        avg_logprob=data.get("avg_logprob", 0.0),
    )


@dataclass
class SubtitleProject:
    """A subtitle project with segments, style, metadata, and state."""

    segments: List[Segment] = field(default_factory=list)
    style: StyleProfile = field(default_factory=StyleProfile)
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    state: ProjectState = field(default_factory=ProjectState)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": PROJECT_VERSION,
            "segments": [_segment_to_dict(s) for s in self.segments],
            "style": self.style.to_dict(),
            "metadata": self.metadata.to_dict(),
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleProject":
        """Deserialize from dictionary.

        Warns if the project version is newer than what this loader supports.
        """
        file_version = data.get("version", "unknown")
        if file_version not in COMPATIBLE_VERSIONS:
            warnings.warn(
                f"Project file version '{file_version}' may be incompatible "
                f"with this version of SubGen (supports: {', '.join(sorted(COMPATIBLE_VERSIONS))}). "
                f"Some data may be lost or misinterpreted.",
                UserWarning,
                stacklevel=2,
            )
        segments = [_segment_from_dict(s) for s in data.get("segments", [])]
        style = StyleProfile.from_dict(data["style"]) if "style" in data else StyleProfile()
        metadata = ProjectMetadata.from_dict(data["metadata"]) if "metadata" in data else ProjectMetadata()
        state = ProjectState.from_dict(data["state"]) if "state" in data else ProjectState()
        return cls(segments=segments, style=style, metadata=metadata, state=state)

    def save(self, path: Path) -> None:
        """Save project to a .subgen JSON file atomically.

        Writes to a temp file first, then uses os.replace() to atomically
        move to the final path. This prevents data corruption from interrupted writes.

        Args:
            path: Output file path.
        """
        self.metadata.modified_at = datetime.now().isoformat()
        if not self.metadata.created_at:
            self.metadata.created_at = self.metadata.modified_at
        path.parent.mkdir(parents=True, exist_ok=True)

        content = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".subgen_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: Path) -> "SubtitleProject":
        """Load project from a .subgen JSON file.

        Args:
            path: Input file path.

        Returns:
            SubtitleProject instance.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
