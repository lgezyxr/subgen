# SubGen Security Review — Claude Code

**Date:** 2026-02-26
**Reviewer:** Claude (Anthropic)
**Scope:** Full codebase audit — `src/`, `tests/`, `subgen.py`
**Focus:** Security vulnerabilities, input validation, path traversal, command injection, credential handling, unsafe deserialization, cross-platform path issues

---

## Critical Issues (must fix)

### CRIT-1 — `tempfile.mktemp()` Race Condition / TOCTOU
**File:** `src/transcribe_cpp.py`, line 55

```python
output_base = tempfile.mktemp(prefix="subgen_whisper_")
```

`tempfile.mktemp()` is deprecated and unsafe. It returns a filename that does not yet exist, creating a classic TOCTOU race condition. Between the call returning and whisper.cpp creating the file, any local user can create a symlink at that path pointing to an arbitrary target (e.g. `~/.ssh/authorized_keys`), causing whisper to overwrite it with its output. `/tmp` is world-writable on Linux, making this directly exploitable.

**Fix:** Use `tempfile.mkdtemp()` to create a private directory, then place output files inside it. Or use `tempfile.NamedTemporaryFile(delete=False)`.

---

### CRIT-2 — Zip Slip / Tar Slip Path Traversal in Archive Extraction
**File:** `src/components.py`, lines 357–364

```python
with zipfile.ZipFile(tmp_file) as zf:
    zf.extractall(install_path)
...
with tarfile.open(tmp_file, "r:gz") as tf:
    tf.extractall(install_path)
...
with tarfile.open(tmp_file, "r:xz") as tf:
    tf.extractall(install_path)
```

All three archive extractions are vulnerable to path traversal. A malicious or compromised archive can contain entries with names like `../../../home/user/.bashrc` or absolute paths. `extractall()` without member filtering will write those files outside `install_path`, allowing arbitrary file write anywhere the current user can write.

This is especially dangerous because SHA256 hashes are all empty (see CRIT-3), so a MITM or compromised server can deliver a malicious archive with no detection.

**Fix:** Before extraction, iterate over members and verify each resolved path stays within `install_path`. Python 3.12+ supports a `filter='data'` parameter for `tarfile.extractall()`; for older versions manually check each member path.

---

### CRIT-3 — SHA256 Checksums All Empty — Zero Integrity Verification on Downloaded Executables
**File:** `src/components.py`, lines 58, 74, 82, 99, 109, 119, 129, 139, 154

```python
"sha256": {"linux-x64": "", "windows": ""},
"sha256": {"*": ""},
```

Every entry in `BUILTIN_REGISTRY` has empty SHA256 hashes. The `_download()` method skips verification when the hash is empty. This means downloaded binaries (whisper.cpp) and ML models are **never verified**. A MITM attacker (rogue Wi-Fi, compromised CDN, or compromised GitHub release) can substitute arbitrary executables that will be installed and executed without any warning.

**Fix:** Populate all `sha256` fields with the actual cryptographic hashes of released artifacts. Fail hard (not silently skip) if a downloaded file does not match.

---

### CRIT-4 — Incomplete FFmpeg Filter-Path Escaping Allows Filter Graph Injection
**File:** `src/subtitle.py`, lines 202–235

```python
def _escape_ffmpeg_filter_path(path: str) -> str:
    path = path.replace('\\', '/')
    for char in ["'", ":", "[", "]"]:
        path = path.replace(char, '\\' + char)
    return path

cmd = [..., '-vf', f"subtitles='{subtitle_path_escaped}'", ...]
result = subprocess.run(cmd, ...)
```

The escape function does not escape `;` (filter-graph separator), `,` (filter chain separator), `=` (key=value separator), or `@` (named instance). A subtitle file path containing any of these characters (all legal in Linux filenames) can inject additional FFmpeg filter-graph elements. Via filters like `movie=` or `lavfi`, this can lead to arbitrary file reads or in some FFmpeg build configurations to code execution. The path is also influenced by the input video filename (`video_path.stem`) supplied by the user.

**Fix:** Use a comprehensive escaping function covering all FFmpeg filter metacharacters, or pass subtitle paths via `-vf` options that do not embed the path in a string (e.g., use `-i` with a separate subtitle stream rather than the `subtitles=` filter).

---

## High Severity (should fix)

### HIGH-1 — OAuth Tokens Stored in Plaintext JSON
**File:** `src/auth/store.py`, lines 35–44; `src/auth/copilot.py`, lines 174–180; `src/auth/openai_codex.py`, line ~258

```python
def save_credentials(credentials: dict) -> None:
    path = get_credentials_path()
    with open(path, 'w') as f:
        json.dump(credentials, f, indent=2)
    path.chmod(0o600)
```

All OAuth tokens (GitHub OAuth tokens, Copilot session tokens, ChatGPT Plus access tokens, refresh tokens) are written as plaintext JSON to `~/.config/subgen/credentials.json`. The `chmod(0o600)` protects against other OS users but not against malware or compromised processes running as the same user, backup/cloud-sync utilities (Dropbox, iCloud, Time Machine), or swap/crash dumps.

**Fix:** Use the `keyring` library for OS-native secret storage (macOS Keychain, Windows Credential Manager, Linux Secret Service / libsecret). This is the cross-platform standard for credential storage in Python desktop apps.

---

### HIGH-2 — API Keys Written Plaintext to `config.yaml` Without Restrictive Permissions
**File:** `src/wizard.py`, lines 240–241, 385–386; `subgen.py`, lines 431–432

```python
config["whisper"][f"{whisper_provider}_key"] = key
config["llm"]["api_key"] = key
...
with open(output_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
```

API keys for OpenAI, Anthropic, DeepSeek, and Groq entered interactively during setup are written verbatim to `config.yaml` in the working directory with no restrictive permissions (unlike `credentials.json`). The file is likely to be accidentally committed to version control or may be world-readable depending on umask.

**Fix:** After writing `config.yaml`, call `Path(output_path).chmod(0o600)`. Consider not storing secrets in the config file at all — reference environment variables or the OS keychain instead.

---

### HIGH-3 — JWT Decoded Without Signature Verification
**File:** `src/auth/openai_codex.py`, lines 50–66

```python
def _decode_jwt(token: str) -> Optional[dict]:
    """Decode JWT payload without verification."""
    try:
        parts = token.split('.')
        ...
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
```

The `account_id` extracted from this unverified JWT is used directly in API request headers (`chatgpt-account-id`). If an attacker intercepts the OAuth token exchange (via MITM on `auth.openai.com`) and substitutes a crafted JWT, the extracted `account_id` becomes attacker-controlled, potentially routing API calls to a different account.

**Fix:** Use a proper JWT library (e.g., `PyJWT`, `python-jose`) to verify the token signature against the provider's public keys before trusting any claims.

---

### HIGH-4 — Ollama / OpenAI `base_url` Unvalidated — SSRF Risk
**File:** `src/translate.py`, lines ~770, ~1013–1032

```python
host = config['translation'].get('ollama_host', 'http://localhost:11434')
response = httpx.post(f"{host}/api/chat", ...)

base_url = config['translation'].get('base_url', None)
client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
```

`ollama_host` and `base_url` are read from `config.yaml` with no validation. A malicious or tampered config file can set these to attacker-controlled servers to exfiltrate all subtitle content being translated, or to internal network addresses for Server-Side Request Forgery (probing/attacking LAN services).

**Fix:** Validate these URLs against an allowlist of schemes (`http`, `https` only). Optionally restrict to `localhost` addresses for `ollama_host` unless the user explicitly opts into remote.

---

### HIGH-5 — User-Writable Registry Cache Can Redirect Install Paths
**File:** `src/components.py`, lines 381–390; lines 211–219

```python
data["components"][component_id] = {
    "version": comp_info["version"],
    "path": str(result_path),
    ...
}
```

`~/.subgen/components.json` is written and read back with no integrity protection. Any local process can modify it to change download URLs to attacker-controlled servers, set fake SHA256 hashes, or modify `install_path` values so that extracted archive contents are written anywhere. Combined with the missing Zip Slip protection (CRIT-2), a tampered registry can direct a malicious archive to overwrite arbitrary files.

**Fix:** Sign the registry cache with a static keypair (public key bundled in the app). At minimum, validate that all paths in the cache resolve to subdirectories of `self.base_dir`.

---

### HIGH-6 — Language Code Path Traversal Leaks Arbitrary Files into LLM Prompt
**File:** `src/translate.py`, lines 143–168

```python
candidates = [
    rules_dir / f'{lang_code}.md',
    rules_dir / f'{lang_code.split("-")[0]}.md',
    rules_dir / 'default.md',
]
for rule_file in candidates:
    if rule_file.exists():
        content = rule_file.read_text(encoding='utf-8')
```

`lang_code` flows in from `config['output']['target_language']`, which is set from the `--to` CLI argument with no sanitization. A value of `../../etc/passwd` constructs the path `<rules_dir>/../../etc/passwd`. If that file exists it is read and **injected directly into the LLM system prompt**, leaking its contents to a third-party API server.

**Fix:** Validate `lang_code` with a strict allowlist regex (e.g., `^[a-zA-Z]{2,3}(-[a-zA-Z]{2,4})?$`) before using it to construct file paths.

---

### HIGH-7 — OAuth Callback Hardcoded Port Allows Local Code Replay
**File:** `src/auth/openai_codex.py`, lines 211–244

```python
# Server binds to 127.0.0.1:1455 (hardcoded)
if server.auth_state != state:
    raise OpenAICodexAuthError("State mismatch. Possible CSRF attack.")
tokens = _exchange_code_for_token(server.auth_code, verifier)
```

The OAuth callback server binds to `127.0.0.1:1455` (hardcoded). The CSRF state check is present, but any local process sharing the user session can send a forged callback with a stolen authorization code if it can observe the state value (e.g., via `/proc` inspection or timing). There is also no mechanism to reject duplicate callbacks or clear `auth_code` after use.

**Fix:** Use a randomly selected available port (bind to port 0 and query the assigned port). Clear `auth_code` immediately after use. Add a one-shot flag to reject further callbacks after the first valid one.

---

## Medium Severity (nice to fix)

### MED-1 — Missing `--` Separator Before User-Controlled Paths in Subprocess Calls
**Files:** `src/audio.py` lines 52–68; `src/subtitle.py` lines 232–243; `src/engine.py` lines 284–289

```python
cmd = ['ffmpeg', '-i', str(video_path), ..., str(audio_path)]
result = subprocess.run(cmd, ...)
```

`subprocess.run` is used without `shell=True` (correct), but user-supplied filenames beginning with `-` or containing characters FFmpeg interprets as option flags can be misinterpreted. A file named `-vf subtitles=...` would be parsed as FFmpeg flags.

**Fix:** Insert `--` before user-supplied path arguments: `cmd = ['ffmpeg', '-i', '--', str(video_path), ...]`.

---

### MED-2 — Sensitive Auth Error Bodies Printed to stderr / Raised in Exceptions
**File:** `src/translate.py`, lines ~692, ~709; `src/auth/openai_codex.py`, line 137

```python
error_body = response.text[:1000]
debug("chatgpt: 403 error body: %s", error_body)
print(f"\n[ChatGPT 403 Error] {error_body[:200]}")
```

Error responses from authentication servers may contain partial tokens, session identifiers, or PII. These are printed to stderr and embedded in exception messages, potentially leaking to log files or monitoring systems.

**Fix:** Log only the HTTP status code and a generic error description for auth failures, not the raw response body.

---

### MED-3 — Config Path Not Canonicalized; Symlinks Followed Silently
**File:** `src/config.py`, line 71

The `config_path` from `--config` CLI flag is not resolved with `Path.resolve()` or `Path.absolute()` before use. A symlink at `./config.yaml` pointing to a location elsewhere is followed without notice, allowing configuration injection from unexpected locations.

**Fix:** Call `Path(config_path).resolve()` early and validate the resolved path is within an expected directory if appropriate.

---

### MED-4 — User-Controlled Temp Dir; Video Filename Stem Unsanitized in Path
**File:** `src/audio.py`, lines 42–45

```python
temp_dir = Path(config.get('advanced', {}).get('temp_dir', '/tmp/subgen'))
temp_dir.mkdir(parents=True, exist_ok=True)
audio_path = temp_dir / f"{video_path.stem}_audio.wav"
```

`temp_dir` comes from `config.yaml`. `video_path.stem` is derived from user-supplied input. A video named `"../evil"` would produce `temp_dir / "../evil_audio.wav"`, potentially writing outside the temp directory. On Windows, reserved device names (`CON`, `NUL`, `COM1`) in the stem cause unexpected failures or device handle access.

**Fix:** Sanitize `video_path.stem` to strip path-separator characters and reserved names. Use `Path(temp_dir / filename).resolve()` and assert it starts with `temp_dir.resolve()`.

---

### MED-5 — Registry Cache File Writable by User with No Integrity Check
**File:** `src/components.py`, lines 211–219

`~/.subgen/components.json` is written and cached for `CACHE_MAX_AGE_SECONDS` with no signature or HMAC. Any malware running as the current user can modify it to redirect downloads to attacker-controlled servers.

**Fix:** At minimum, use a read-only location for the bundled default registry and only cache user-added registries. For full protection, sign the registry with a key bundled in the package and verify on load.

---

### MED-6 — Hardcoded Third-Party OAuth Client IDs
**File:** `src/auth/copilot.py`, line 11; `src/auth/openai_codex.py`, lines 23–24

```python
CLIENT_ID = "Iv1.b507a08c87ecfe98"   # Copilot (VS Code extension client ID)
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"  # ChatGPT
```

The Copilot `CLIENT_ID` appears to be the one used by the official VS Code Copilot extension. Using it in third-party software may violate GitHub's Terms of Service and could be revoked at any time, breaking all users simultaneously without any warning. Hardcoded IDs also cannot be rotated without a code release.

**Fix:** Obtain a first-party OAuth Client ID by registering SubGen as its own GitHub OAuth App and ChatGPT plugin. Allow the client ID to be overridden via config/environment variable.

---

### MED-7 — No Timeout on `subprocess.run()` for FFmpeg Calls
**Files:** `src/audio.py` line 64; `src/subtitle.py` lines 242, 275

```python
result = subprocess.run(cmd, capture_output=True, text=True)  # No timeout
```

A crafted or malformed media file can cause FFmpeg to hang indefinitely (e.g., an MP4 with circular reference boxes). Without a `timeout=` parameter, the process stalls forever and cannot be interrupted short of SIGKILL. Note: `src/embedded.py` correctly sets timeouts on its FFmpeg calls.

**Fix:** Add `timeout=300` (or a user-configurable value) to all `subprocess.run()` calls invoking FFmpeg.

---

### MED-8 — `shutil.rmtree()` on Path from User-Writable JSON, No Bounds Check
**File:** `src/components.py`, lines 419–424

```python
path = Path(info["path"])
if path.exists():
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
```

The `path` value comes from `installed.json`, which is user-writable. A tampered entry with `"path": "/home/user"` would call `shutil.rmtree("/home/user")`, deleting the user's entire home directory.

**Fix:** Before calling `rmtree`, assert that `Path(path).resolve().is_relative_to(self.base_dir.resolve())`. Abort with an error if the check fails.

---

### MED-9 — No Timeout / Connection Limits on OAuth Local HTTP Server
**File:** `src/auth/openai_codex.py`, OAuth callback server implementation

The local HTTP server handling the OAuth callback has no connection-count limit, request-size limit, or per-connection timeout. A local attacker can hold the connection open, preventing the auth flow from completing (denial of service to the user), or send large request bodies causing unbounded memory allocation.

**Fix:** Set a socket timeout on the server, limit the number of requests handled, and add a maximum request size.

---

## Low Severity (suggestions)

### LOW-1 — TOCTOU Race Between File Write and `chmod(0o600)` on Credentials File
**File:** `src/auth/store.py`, lines 37–44

```python
with open(path, 'w') as f:
    json.dump(credentials, f, indent=2)
path.chmod(0o600)
```

The file is created with default umask permissions, written, then chmod'd. Between `open()` and `chmod()`, a local attacker can read the file.

**Fix:** Create the file with restricted permissions from the start:
```python
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    json.dump(credentials, f, indent=2)
```

---

### LOW-2 — `config.yaml` With API Keys Written Without Restrictive Permissions
**File:** `subgen.py`, lines 431–432

`config.yaml` is written with default umask permissions (typically 0o644, world-readable). Unlike `credentials.json`, no `chmod(0o600)` is applied after writing. API keys in this file are therefore potentially readable by all users on multi-user systems.

**Fix:** Add `Path(output_path).chmod(0o600)` after writing the config file.

---

### LOW-3 — `is_token_expired()` Falls Back to "Not Expired" with No Expiry Field
**File:** `src/auth/store.py`, lines 73–86

```python
expires_at = credential.get("expires_at")
if not expires_at:
    return False  # No expiry info, assume valid
```

A credential saved without `expires_at` (due to a bug or tampering) is assumed valid indefinitely, potentially using stale or revoked tokens without error.

**Fix:** Return `True` (expired/unknown) when no expiry info is present, forcing re-authentication.

---

### LOW-4 — Internal Filesystem Paths Exposed in Error Messages
**File:** `src/transcribe_cpp.py`, lines 107–112; `src/config.py` line 68; `src/cache.py` line 297

```python
raise RuntimeError(
    f"whisper.cpp did not produce JSON output.\n"
    f"Expected: {json_file}\n"
    ...
)
```

Full filesystem paths (including temp directory structure) are exposed in exception messages that may be logged or displayed to users. This leaks installation layout information.

**Fix:** Log full paths at DEBUG level only; show only filenames or generic descriptions in user-facing error messages.

---

### LOW-5 — No Certificate Pinning for Critical Auth Endpoints
**Files:** `src/auth/copilot.py`, `src/auth/openai_codex.py`, `src/translate.py`, `src/components.py`

All HTTPS requests use default certificate verification (correct), but there is no pinning for `auth.openai.com` or `github.com`. On corporate networks with SSL-inspection proxies, tokens exchanged with these endpoints can be intercepted without the user's knowledge.

**Note:** Certificate pinning in Python desktop apps is complex and maintenance-heavy. At minimum, consider documenting this limitation in user-facing security notes.

---

### LOW-6 — Bare `except Exception` Swallows Programming Errors
**File:** `src/auth/openai_codex.py`, line 65; multiple other locations

```python
except Exception:
    return None
```

Bare `except Exception` catches `MemoryError`, programming bugs, etc., masking them as a missing return value. Callers then silently proceed with `None` state.

**Fix:** Catch only the specific expected exceptions (`ValueError`, `KeyError`, `base64.binascii.Error`, `json.JSONDecodeError`). Let unexpected exceptions propagate.

---

### LOW-7 — Test Files Use Hardcoded `/tmp` Paths (Not Cross-Platform)
**File:** `tests/test_engine.py`, lines 99, 103

```python
project = engine._build_project(segments, cfg, Path("/tmp/test.mp4"), ...)
metadata = ProjectMetadata(video_path="/tmp/v.mp4", ...)
```

`/tmp` is Linux/macOS-specific. Tests will fail or behave unexpectedly on Windows. CI environments may also leave test artifacts in shared temp directories.

**Fix:** Use `tempfile.mkdtemp()` or `tmp_path` (pytest fixture) for temporary file paths in tests.

---

### LOW-8 — Proofread-Only SRT Path Follows Symlinks Without Validation
**File:** `src/engine.py`, lines 403–410

```python
existing_srt = input_path.parent / f"{input_path.stem}_{target_lang}.srt"
...
if existing_srt.exists():
    segments = load_srt(existing_srt)
```

The SRT path is constructed from the input video path without canonicalization. A symlink in the video directory pointing to a sensitive file would be followed and parsed.

**Fix:** Call `.resolve()` on the constructed path and validate it is within an expected directory.

---

## Summary

| ID | Severity | File | Line(s) | Issue |
|----|----------|------|---------|-------|
| CRIT-1 | **Critical** | `src/transcribe_cpp.py` | 55 | `tempfile.mktemp()` TOCTOU race — symlink attack on output file |
| CRIT-2 | **Critical** | `src/components.py` | 357–364 | Zip Slip / Tar Slip — path traversal via archive extraction |
| CRIT-3 | **Critical** | `src/components.py` | 58,74,82,99,109,119,129,139,154 | All SHA256 hashes empty — no integrity verification on downloaded executables |
| CRIT-4 | **Critical** | `src/subtitle.py` | 202–235 | Incomplete FFmpeg filter-path escaping — filter graph injection via filename |
| HIGH-1 | **High** | `src/auth/store.py` | 35–44 | OAuth tokens / refresh tokens stored in plaintext JSON |
| HIGH-2 | **High** | `src/wizard.py`, `subgen.py` | 240–241, 431–432 | API keys written plaintext to `config.yaml` without restrictive permissions |
| HIGH-3 | **High** | `src/auth/openai_codex.py` | 50–66 | JWT decoded without signature verification; `account_id` used in API calls |
| HIGH-4 | **High** | `src/translate.py` | ~770, ~1013 | Ollama/OpenAI `base_url` unvalidated — SSRF and data exfiltration risk |
| HIGH-5 | **High** | `src/components.py` | 211–219, 381–390 | User-writable registry cache can redirect downloads to attacker-controlled servers |
| HIGH-6 | **High** | `src/translate.py` | 143–168 | Language code path traversal — arbitrary file contents injected into LLM prompt |
| HIGH-7 | **High** | `src/auth/openai_codex.py` | 211–244 | OAuth callback on hardcoded port; no code-replay protection |
| MED-1 | **Medium** | `src/audio.py`, `subtitle.py`, `engine.py` | 52–68, 232–243, 284–289 | No `--` separator before user paths in subprocess calls |
| MED-2 | **Medium** | `src/translate.py`, `openai_codex.py` | ~692, 137 | Sensitive auth error bodies printed to stderr / raised in exceptions |
| MED-3 | **Medium** | `src/config.py` | 71 | Config path not canonicalized; symlinks followed silently |
| MED-4 | **Medium** | `src/audio.py` | 42–45 | User-controlled temp dir; video filename stem used unsanitized in path |
| MED-5 | **Medium** | `src/components.py` | 211–219 | Registry cache file has no integrity protection |
| MED-6 | **Medium** | `src/auth/copilot.py`, `openai_codex.py` | 11, 23–24 | Hardcoded third-party OAuth client IDs (ToS risk; unrevocable) |
| MED-7 | **Medium** | `src/audio.py`, `src/subtitle.py` | 64, 242, 275 | No timeout on `subprocess.run()` for FFmpeg calls — hang on crafted input |
| MED-8 | **Medium** | `src/components.py` | 419–424 | `shutil.rmtree()` on path from user-writable JSON — no bounds check |
| MED-9 | **Medium** | `src/auth/openai_codex.py` | OAuth server | No connection limits or timeout on local OAuth callback HTTP server |
| LOW-1 | **Low** | `src/auth/store.py` | 37–44 | TOCTOU race between credentials file write and `chmod(0o600)` |
| LOW-2 | **Low** | `subgen.py` | 431–432 | `config.yaml` with API keys written without restrictive permissions |
| LOW-3 | **Low** | `src/auth/store.py` | 73–86 | Missing `expires_at` assumes token is valid indefinitely |
| LOW-4 | **Low** | `src/transcribe_cpp.py`, `config.py`, `cache.py` | 107–112, 68, 297 | Internal filesystem paths exposed in user-facing error messages |
| LOW-5 | **Low** | Multiple auth/translate files | Various | No certificate pinning for critical OAuth endpoints |
| LOW-6 | **Low** | `src/auth/openai_codex.py` | 65 | Bare `except Exception` swallows programming errors |
| LOW-7 | **Low** | `tests/test_engine.py` | 99, 103 | Hardcoded `/tmp` in tests — not cross-platform; no cleanup |
| LOW-8 | **Low** | `src/engine.py` | 403–410 | Proofread-only SRT path follows symlinks without validation |

### Top Priorities

**Fix immediately (before any public release):**
1. **CRIT-1** — Replace `tempfile.mktemp()` with `tempfile.mkdtemp()`
2. **CRIT-2** — Add path-traversal filtering to all `extractall()` calls
3. **CRIT-3** — Populate all SHA256 hashes in `BUILTIN_REGISTRY`
4. **CRIT-4** — Fix or replace the FFmpeg filter-path escaping function
5. **MED-8** — Validate uninstall paths are under `self.base_dir` before `rmtree`

**Fix soon (next sprint):**
6. **HIGH-1** — Use `keyring` library for OS-native credential storage
7. **HIGH-2** — Set `0o600` on `config.yaml` after writing
8. **HIGH-4** — Validate Ollama/OpenAI `base_url` (scheme allowlist)
9. **HIGH-6** — Sanitize `lang_code` to `^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,4})?$` before path construction
10. **LOW-1** — Open credentials file with `os.open(..., 0o600)` to eliminate race

**Fix medium-term:**
11. **HIGH-3** — Verify JWT signatures with PyJWT / python-jose
12. **MED-1** — Add `--` separator before user-controlled paths in subprocess calls
13. **MED-5** — Sign or integrity-protect the component registry cache
14. **MED-7** — Add `timeout=300` to all FFmpeg subprocess calls
15. **MED-6** — Register SubGen as its own OAuth App; stop reusing VS Code Copilot client ID
