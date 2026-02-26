"""SubGen core engine — orchestrates transcription, translation, proofreading, and export.

This module contains no terminal/UI output. All progress is reported via callbacks.
"""

import shutil
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

from .config import load_config
from .audio import extract_audio, cleanup_temp_files, check_ffmpeg
from .transcribe import transcribe_audio, Segment, Word
from .translate import translate_segments, translate_segments_sentence_aware, proofread_translations
from .subtitle import generate_subtitle, embed_subtitle, load_srt
from .cache import load_cache, save_cache
from .project import SubtitleProject, ProjectMetadata, ProjectState
from .styles import StyleProfile, PRESETS, load_style
from .logger import debug as log_debug

ProgressCallback = Callable[[str, int, int], None]
"""callback(stage, current, total) — stage is one of
'extracting', 'transcribing', 'translating', 'proofreading', 'exporting'."""


def _segments_to_cache_dicts(segments: List[Segment]) -> List[Dict[str, Any]]:
    """Convert Segment objects to serializable dicts for cache."""
    result = []
    for seg in segments:
        d: Dict[str, Any] = {
            'start': seg.start,
            'end': seg.end,
            'text': seg.text,
            'no_speech_prob': getattr(seg, 'no_speech_prob', 0.0),
            'avg_logprob': getattr(seg, 'avg_logprob', 0.0),
        }
        if seg.translated:
            d['translated'] = seg.translated
        if seg.translated_raw:
            d['translated_raw'] = seg.translated_raw
        if hasattr(seg, 'words') and seg.words:
            d['words'] = [{'text': w.text, 'start': w.start, 'end': w.end} for w in seg.words]
        result.append(d)
    return result


def _cache_dicts_to_segments(data: List[Dict[str, Any]]) -> List[Segment]:
    """Convert cached dicts back to Segment objects."""
    segments = []
    for seg_data in data:
        seg = Segment(
            start=seg_data['start'],
            end=seg_data['end'],
            text=seg_data['text'],
            translated=seg_data.get('translated', ''),
            translated_raw=seg_data.get('translated_raw', ''),
            no_speech_prob=seg_data.get('no_speech_prob', 0.0),
            avg_logprob=seg_data.get('avg_logprob', 0.0),
        )
        if 'words' in seg_data and seg_data['words']:
            seg.words = [Word(text=w['text'], start=w['start'], end=w['end']) for w in seg_data['words']]
        segments.append(seg)
    return segments


class SubGenEngine:
    """Core engine for subtitle generation.

    Orchestrates: audio extraction → transcription → translation → proofreading.
    Returns SubtitleProject objects. Does **no** terminal I/O.
    """

    def __init__(self, config: Dict[str, Any], on_progress: Optional[ProgressCallback] = None):
        """Initialize engine.

        Args:
            config: Loaded and merged configuration dictionary.
            on_progress: Optional progress callback(stage, current, total).
        """
        self.config = config
        self.on_progress = on_progress or (lambda *_: None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_path: Path, **options: Any) -> SubtitleProject:
        """Full pipeline: video → transcribe → translate → (proofread) → SubtitleProject.

        Args:
            input_path: Path to video/audio file.
            **options:
                source_lang, target_lang, no_translate (bool),
                sentence_aware (bool), proofread (bool), bilingual (bool),
                force_transcribe (bool), proofread_only (bool).

        Returns:
            SubtitleProject with segments populated.
        """
        input_path = Path(input_path)
        cfg = self.config

        no_translate = options.get('no_translate', False)
        sentence_aware = options.get('sentence_aware', False)
        do_proofread = options.get('proofread', False)
        proofread_only = options.get('proofread_only', False)
        force_transcribe = options.get('force_transcribe', False)

        final_source_lang = cfg['output'].get('source_language', 'auto')
        final_target_lang = cfg['output'].get('target_language', 'zh')

        # --- Proofread-only path ---
        if proofread_only:
            return self._run_proofread_only(input_path, cfg, final_source_lang, final_target_lang)

        # --- Obtain segments (cache / embedded / transcribe) ---
        segments, source_from = self._obtain_segments(input_path, cfg, final_source_lang, final_target_lang, force_transcribe)

        if not segments:
            # Return empty project
            return self._build_project([], cfg, input_path, final_source_lang, final_target_lang)

        # --- Translation ---
        if no_translate:
            for seg in segments:
                seg.translated = seg.text
        else:
            total = len(segments)
            self.on_progress('translating', 0, total)

            if sentence_aware:
                segments = translate_segments_sentence_aware(
                    segments, cfg, translate_fn=None,
                    progress_callback=lambda n: self.on_progress('translating', n, total),
                )
            else:
                segments = translate_segments(
                    segments, cfg,
                    progress_callback=lambda n: self.on_progress('translating', n, total),
                )

            # Update cache with translations
            try:
                self._save_cache(input_path, segments, cfg)
            except Exception:
                pass

            # --- Proofreading ---
            if do_proofread:
                self.on_progress('proofreading', 0, len(segments))
                segments = proofread_translations(
                    segments, cfg,
                    progress_callback=lambda n: self.on_progress('proofreading', n, len(segments)),
                )

        return self._build_project(segments, cfg, input_path, final_source_lang, final_target_lang)

    def transcribe(self, input_path: Path, **options: Any) -> SubtitleProject:
        """Transcribe only (no translation).

        Args:
            input_path: Path to video/audio file.
            **options: force_transcribe (bool).

        Returns:
            SubtitleProject with transcribed segments.
        """
        return self.run(input_path, no_translate=True, **options)

    def translate(self, project: SubtitleProject, **options: Any) -> SubtitleProject:
        """Translate an existing project's segments.

        Args:
            project: SubtitleProject with transcribed segments.
            **options: sentence_aware (bool).

        Returns:
            Same project with translations populated.
        """
        cfg = self.config
        segments = project.segments
        sentence_aware = options.get('sentence_aware', False)
        total = len(segments)
        self.on_progress('translating', 0, total)

        if sentence_aware:
            segments = translate_segments_sentence_aware(
                segments, cfg, translate_fn=None,
                progress_callback=lambda n: self.on_progress('translating', n, total),
            )
        else:
            segments = translate_segments(
                segments, cfg,
                progress_callback=lambda n: self.on_progress('translating', n, total),
            )

        project.segments = segments
        project.state.is_translated = True
        return project

    def proofread(self, project: SubtitleProject) -> SubtitleProject:
        """Proofread an existing project's translations.

        Args:
            project: SubtitleProject with translated segments.

        Returns:
            Same project with proofread translations.
        """
        cfg = self.config
        segments = project.segments
        total = len(segments)
        self.on_progress('proofreading', 0, total)

        segments = proofread_translations(
            segments, cfg,
            progress_callback=lambda n: self.on_progress('proofreading', n, total),
        )

        project.segments = segments
        project.state.is_proofread = True
        return project

    def export(
        self,
        project: SubtitleProject,
        output_path: Path,
        format: str = 'srt',
        style: Optional[StyleProfile] = None,
    ) -> Path:
        """Export subtitle file from project.

        Args:
            project: SubtitleProject with segments.
            output_path: Destination file path.
            format: 'srt' or 'ass'.
            style: Optional style override; falls back to project.style.

        Returns:
            The output_path written.
        """
        self.on_progress('exporting', 0, 1)

        effective_style = style or project.style
        # Build a minimal config for generate_subtitle
        export_cfg = dict(self.config)
        export_cfg.setdefault('output', {})
        export_cfg['output']['format'] = format

        generate_subtitle(project.segments, Path(output_path), export_cfg, style=effective_style)
        self.on_progress('exporting', 1, 1)
        return Path(output_path)

    def export_video(
        self,
        project: SubtitleProject,
        video_path: Path,
        output_path: Path,
        embed_mode: str = 'soft',
    ) -> Path:
        """Export video with subtitles.

        Args:
            project: SubtitleProject with segments.
            video_path: Original video file.
            output_path: Destination video file.
            embed_mode: 'soft' (mux) or 'hard' (burn-in).

        Returns:
            The output_path.
        """
        self.on_progress('exporting', 0, 1)
        # We need a temporary subtitle file for ffmpeg
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.srt', delete=False, mode='w') as tmp:
            tmp_path = Path(tmp.name)

        try:
            self.export(project, tmp_path, format='srt')
            if embed_mode == 'hard':
                embed_subtitle(video_path, tmp_path, output_path, self.config)
            else:
                # Soft embed via ffmpeg mux
                import subprocess
                cmd = [
                    'ffmpeg', '-i', str(video_path), '-i', str(tmp_path),
                    '-c', 'copy', '-c:s', 'srt', '-y', '-loglevel', 'error',
                    str(output_path),
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
        finally:
            tmp_path.unlink(missing_ok=True)

        self.on_progress('exporting', 1, 1)
        return Path(output_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _obtain_segments(
        self, input_path: Path, cfg: Dict[str, Any],
        final_source_lang: str, final_target_lang: str,
        force_transcribe: bool,
    ) -> tuple:
        """Get segments from cache, embedded subs, or fresh transcription.

        Returns:
            (segments, source) where source is 'cache' | 'embedded' | 'transcribed'.
        """
        # Try cache first
        if not force_transcribe:
            cached = load_cache(input_path)
            if cached and cached.get('segments'):
                segments = _cache_dicts_to_segments(cached['segments'])
                if not cfg.get('_source_lang_from_cli') and cached.get('source_lang'):
                    cfg['whisper']['source_language'] = cached['source_lang']
                    cfg['output']['source_language'] = cached['source_lang']
                return segments, 'cache'

        # Try embedded subtitles
        if not force_transcribe:
            result = self._try_embedded(input_path, cfg, final_source_lang, final_target_lang)
            if result is not None:
                return result, 'embedded'

        # Fresh transcription
        self.on_progress('extracting', 0, 1)
        audio_path = extract_audio(input_path, cfg)
        self.on_progress('extracting', 1, 1)

        self.on_progress('transcribing', 0, 1)
        segments = transcribe_audio(audio_path, cfg)
        self.on_progress('transcribing', 1, 1)

        if not segments:
            return [], 'transcribed'

        # Save to cache
        try:
            self._save_cache(input_path, segments, cfg)
        except Exception as e:
            log_debug("engine: cache save failed: %s", e)

        return segments, 'transcribed'

    def _try_embedded(
        self, input_path: Path, cfg: Dict[str, Any],
        source_lang: str, target_lang: str,
    ) -> Optional[List[Segment]]:
        """Try to use embedded subtitles. Returns segments or None."""
        from .embedded import check_embedded_subtitles, extract_subtitle_track

        embed_check = check_embedded_subtitles(input_path, source_lang, target_lang)

        if embed_check['action'] == 'use_target':
            track = embed_check['track']
            extracted = input_path.parent / f"{input_path.stem}_{target_lang}_extracted.srt"
            result = extract_subtitle_track(input_path, track, extracted)
            if result:
                segs = load_srt(extracted)
                segments = [
                    Segment(start=s.start, end=s.end, text=s.text, translated=s.text)
                    for s in segs
                ]
                extracted.unlink(missing_ok=True)
                return segments
        elif embed_check['action'] == 'use_source':
            track = embed_check['track']
            extracted = input_path.parent / f"{input_path.stem}_embedded_source.srt"
            result = extract_subtitle_track(input_path, track, extracted)
            if result:
                segs = load_srt(extracted)
                segments = [
                    Segment(start=s.start, end=s.end, text=s.text)
                    for s in segs
                ]
                extracted.unlink(missing_ok=True)
                if track.language:
                    cfg['output']['source_language'] = track.language
                # Cache embedded
                try:
                    self._save_cache(input_path, segments, cfg, provider='embedded', model='embedded')
                except Exception:
                    pass
                return segments
        return None

    def _run_proofread_only(
        self, input_path: Path, cfg: Dict[str, Any],
        source_lang: str, target_lang: str,
    ) -> SubtitleProject:
        """Handle proofread-only mode."""
        segments = None

        # Try cache with translations
        cached = load_cache(input_path)
        if cached and cached.get('segments'):
            has_translations = any(seg.get('translated') for seg in cached['segments'])
            if has_translations:
                segments = _cache_dicts_to_segments(cached['segments'])

        # Try .srt file
        if not segments:
            existing_srt = input_path.parent / f"{input_path.stem}_{target_lang}.srt"
            if not existing_srt.exists():
                existing_srt = input_path.with_suffix('.srt')
            if existing_srt.exists():
                segments = load_srt(existing_srt)
            else:
                raise FileNotFoundError("No cache or subtitle file found for proofreading")

        total = len(segments)
        self.on_progress('proofreading', 0, total)
        segments = proofread_translations(
            segments, cfg,
            progress_callback=lambda n: self.on_progress('proofreading', n, total),
        )

        return self._build_project(segments, cfg, input_path, source_lang, target_lang, is_proofread=True)

    def _save_cache(
        self, input_path: Path, segments: List[Segment],
        cfg: Dict[str, Any], provider: Optional[str] = None, model: Optional[str] = None,
    ) -> None:
        """Save segments to cache."""
        save_cache(
            video_path=input_path,
            segments=_segments_to_cache_dicts(segments),
            word_segments=None,
            whisper_provider=provider or cfg['whisper'].get('provider', 'local'),
            whisper_model=model or cfg['whisper'].get('local_model', 'large-v3'),
            source_lang=cfg['whisper'].get('source_language', 'auto'),
        )

    def _build_project(
        self, segments: List[Segment], cfg: Dict[str, Any],
        input_path: Path, source_lang: str, target_lang: str,
        is_proofread: bool = False,
    ) -> SubtitleProject:
        """Build a SubtitleProject from segments and config."""
        style = load_style(cfg)
        metadata = ProjectMetadata(
            video_path=str(input_path),
            source_lang=source_lang,
            target_lang=target_lang,
            whisper_provider=cfg['whisper'].get('provider', 'local'),
            llm_provider=cfg.get('translation', {}).get('provider', ''),
            llm_model=cfg.get('translation', {}).get('model', ''),
        )
        has_translation = any(getattr(s, 'translated', '') for s in segments)
        state = ProjectState(
            is_transcribed=len(segments) > 0,
            is_translated=has_translation,
            is_proofread=is_proofread,
        )
        return SubtitleProject(segments=segments, style=style, metadata=metadata, state=state)
