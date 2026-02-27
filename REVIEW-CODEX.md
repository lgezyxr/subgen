## Critical Issues (must fix)

- `src/components.py:357-364` archive extraction uses `ZipFile.extractall` / `tarfile.extractall` without path sanitization, allowing path traversal from malicious archives (`../...`) to overwrite arbitrary files.

## High Severity (should fix)

- `src/engine.py:108-117,315-318,379,435-449` `run()` snapshots `final_source_lang` before `_obtain_segments()`, but `_obtain_segments()` may update `cfg['output']['source_language']` from cache/embedded tracks. The returned `SubtitleProject.metadata.source_lang` can be stale/incorrect.
- `src/transcribe_cpp.py:84-95` reads `stderr` to completion before reading `stdout`; with both streams piped this can deadlock if `stdout` fills OS pipe buffers while the process is still writing.
- `src/transcribe_cpp.py:55` uses `tempfile.mktemp`, which has a TOCTOU race and can collide with attacker/pre-existing paths on shared systems.
- `src/components.py:58,74,88,99,109,119,129,139,154,340-341,527-536` registry SHA256 fields are empty, so integrity verification is effectively disabled for all built-in component downloads; this opens a supply-chain tampering path.
- `src/components.py:202-203` platform detection hard-falls to `linux-x64` for all non-Windows/macOS systems, so Linux ARM and other architectures may download incompatible binaries.
- `src/wizard.py:200-203,361-401` setup writes translation choices under `config["llm"]`, but runtime code reads `config["translation"]` (e.g. `src/translate.py`, `src/engine.py`). Wizard selections can be silently ignored and fall back to defaults.
- `src/wizard.py:328-332` when `whisper_provider == "local"` and no NVIDIA GPU is detected, wizard still forces `device="cuda"` and `local_model="large-v3"`, causing likely runtime failure on CPU-only systems.
- `src/subtitle.py:107-110,329-335` bilingual SRT writer outputs `translated` first then `original`, but bilingual loader interprets first line as original and second as translated; round-tripping swaps language roles.
- `src/translate.py:1506-1510,1602-1664` proofreading for `openai`/`claude`/`deepseek` reads provider-specific keys (`openai_api_key`, `claude_api_key`, etc.), while translation config elsewhere uses shared keys (`translation.api_key`, `translation.model`). Common configs fail proofreading and silently fall back to uncorrected text.
- `src/translate.py:545-607` word-aligned parsing does not guarantee full source coverage; if parsed `end:` positions stop early or some lines fail parsing, trailing words are dropped instead of emitted in a final segment.

## Medium Severity (nice to fix)

- `src/engine.py:245-248` `export_cfg = dict(self.config)` is a shallow copy, so writing `export_cfg['output']['format']` mutates `self.config['output']`. Exporting once can unexpectedly change subsequent engine behavior.
- `src/engine.py:327-334` extracted audio is never cleaned up in this module despite importing `cleanup_temp_files`; repeated runs can leak temporary audio files and consume disk space.
- `src/transcribe_cpp.py:134-150,177-180` JSON/timestamp parsing trusts schema and format (`item["timestamps"]["from"]`, fixed `HH:MM:SS` split) without guards; malformed or version-shifted whisper.cpp output raises uncaught `KeyError`/`ValueError` and aborts the run.
- `src/components.py:351` uses a fixed temp filename (`~/.subgen/tmp_download`) for all installs; concurrent installs can clobber each other and produce partial/corrupted extractions.
- `src/components.py:246-250,382-390` installed-state writes are non-atomic and unlocked; concurrent `install/uninstall` calls can lose updates or leave `installed.json` corrupted.
- `src/config.py:70-82` loaded YAML is merged without schema/type validation; invalid values like `whisper: null` or wrong types are accepted and later crash in distant code paths (`.get` on non-dict), making failures harder to diagnose.
- `src/wizard.py:480-486` `check_config_exists()` treats `config.yml` as valid, but `load_config()` only searches `config.yaml`; wizard may skip initialization while runtime later fails to load config.
- `src/styles.py:165-170` `load_style()` assumes `config["styles"]` is a dict; malformed config (e.g., string/list) triggers `AttributeError` instead of a controlled validation error.
- `src/subtitle.py:306-317` `load_srt()` assumes classic `index` + `timestamp` layout (`lines[1]` must be time). Valid SRT variants without numeric index lines are silently skipped.
- `src/subtitle.py:202-212,235` FFmpeg `subtitles=` filter-path escaping does not handle all filter delimiters (notably commas), so hard-sub embedding can fail for valid file paths containing special characters.
- `src/project.py:136-140` project save writes JSON directly to final path without atomic temp-file swap; interruption/crash can leave a truncated/corrupted project file.
- `src/translate.py:294-295,494-495,1512-1513` progress callbacks send per-batch/group increments (`len(batch)`/`len(group)`) instead of cumulative processed count; upstream progress displays become inaccurate.
- `src/translate.py:878-880,923-924,967-968,1013-1014` several provider paths index `config['translation']` directly while other code uses guarded `.get(...)`; malformed or migrated configs can raise `KeyError` mid-run instead of producing a controlled configuration error.

## Low Severity (suggestions)

- `src/engine.py:116` `source_from` is returned from `_obtain_segments()` but never used, indicating dead state/debug info that can drift out of sync.
- `src/wizard.py:474-477` `config_path` is accepted by `run_setup_wizard()` but never used, which can mislead callers expecting non-default save behavior.
- `src/styles.py:16-24` `hex_to_ass_color()` checks only string length and not hex character validity, so malformed colors can pass through and generate invalid ASS color fields.
- `src/subtitle.py:147` `_generate_ass()` accepts `config` but never uses it, which is dead parameter surface and increases call-site confusion.
- `src/project.py:114,122-128` serialized `version` is written but never checked on load; incompatible future schema changes may fail in non-obvious ways instead of producing a clear migration/compatibility error.

## Summary

Reviewed files in required order:
`src/engine.py`, `src/transcribe_cpp.py`, `src/components.py`, `src/config.py`, `src/wizard.py`, `src/styles.py`, `src/subtitle.py`, `src/project.py`, `src/translate.py`.

Issue counts:
- Critical: 1
- High: 10
- Medium: 13
- Low: 5

Top risk areas:
- Supply-chain and filesystem safety in component installation (unchecked archive extraction and ineffective checksum enforcement).
- Configuration contract drift (`llm` vs `translation`, mixed key names) causing silent fallback behavior and disabled proofreading.
- Translation pipeline robustness issues (word-alignment coverage loss, subprocess/stream handling edge cases, inaccurate progress signaling).
