# Whisper Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Optimize the Whisper fallback pipeline for Instagram, TikTok, and YouTube with audio preprocessing, transcript cleanup, export consistency, and timing visibility.

**Architecture:** Keep the current route flow in `backend/routers/translate.py`, but split the Whisper fallback into explicit stages: extract audio, preprocess/cache normalized WAV, transcribe with optional language detection, clean transcript segments, then build exports from cleaned source segments. Add two focused service modules for preprocessing and cleanup so tests can cover the pipeline without coupling everything to `faster-whisper`.

**Tech Stack:** FastAPI, pytest, faster-whisper, ffmpeg via subprocess, yt-dlp

---

### Task 1: Add preprocessing primitives

**Files:**
- Create: `backend/audio_preprocess.py`
- Test: `backend/tests/test_audio_preprocess.py`

**Step 1: Write the failing test**

```python
def test_build_preprocessed_audio_path_uses_stable_cache_name(tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")

    path = build_preprocessed_audio_path(source)

    assert path.name == "clip.preprocessed.wav"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_audio_preprocess.py::test_build_preprocessed_audio_path_uses_stable_cache_name -v`
Expected: FAIL with missing module or function

**Step 3: Write minimal implementation**

```python
def build_preprocessed_audio_path(source: Path) -> Path:
    return source.with_suffix(".preprocessed.wav")
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_audio_preprocess.py::test_build_preprocessed_audio_path_uses_stable_cache_name -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/audio_preprocess.py backend/tests/test_audio_preprocess.py
git commit -m "feat: add audio preprocess path helper"
```

### Task 2: Add ffmpeg preprocessing command generation and cache reuse

**Files:**
- Modify: `backend/audio_preprocess.py`
- Test: `backend/tests/test_audio_preprocess.py`

**Step 1: Write the failing tests**

```python
def test_preprocess_audio_runs_ffmpeg_with_expected_filters(monkeypatch, tmp_path) -> None:
    ...

def test_preprocess_audio_reuses_existing_cached_wav(monkeypatch, tmp_path) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_audio_preprocess.py -v`
Expected: FAIL because `preprocess_audio` does not exist

**Step 3: Write minimal implementation**

Implement `preprocess_audio(audio_path: str) -> str` that:
- converts to mono 16kHz WAV
- applies normalization and silence trimming filters
- skips ffmpeg when the cached `.preprocessed.wav` already exists and is non-empty
- raises a clear `RuntimeError` when ffmpeg fails

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_audio_preprocess.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/audio_preprocess.py backend/tests/test_audio_preprocess.py
git commit -m "feat: add cached ffmpeg audio preprocessing"
```

### Task 3: Add transcript cleanup rules

**Files:**
- Create: `backend/transcript_cleanup.py`
- Test: `backend/tests/test_transcript_cleanup.py`

**Step 1: Write the failing tests**

```python
def test_cleanup_transcript_filters_music_and_repeated_noise() -> None:
    ...

def test_cleanup_transcript_merges_mid_sentence_segments() -> None:
    ...

def test_cleanup_transcript_drops_meaningless_short_segments() -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_transcript_cleanup.py -v`
Expected: FAIL with missing module or functions

**Step 3: Write minimal implementation**

Implement cleanup helpers that:
- strip whitespace
- remove `[Music]`/`[Applause]` style tags
- remove adjacent repeated text
- drop very short low-signal segments
- merge adjacent segments when the first fragment lacks terminal punctuation

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_transcript_cleanup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/transcript_cleanup.py backend/tests/test_transcript_cleanup.py
git commit -m "feat: add transcript cleanup pipeline"
```

### Task 4: Extend transcriber for preprocessing and language detection

**Files:**
- Modify: `backend/services/transcriber.py`
- Test: `backend/tests/test_transcriber.py`

**Step 1: Write the failing tests**

```python
def test_transcribe_audio_uses_preprocessed_audio(monkeypatch, tmp_path) -> None:
    ...

def test_transcribe_audio_detects_language_from_first_thirty_seconds_when_unspecified(monkeypatch, tmp_path) -> None:
    ...

def test_transcribe_audio_cleans_segments_before_returning(monkeypatch, tmp_path) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_transcriber.py -v`
Expected: FAIL because the new behavior is not implemented

**Step 3: Write minimal implementation**

Update `transcribe_audio_with_metadata` to:
- preprocess audio before transcription
- call `model.transcribe(..., language=source_lang)` when a source language is supplied
- otherwise detect from the first 30 seconds and transcribe using detected language
- clean returned segments with `transcript_cleanup`
- include the final language in the response payload

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_transcriber.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/transcriber.py backend/tests/test_transcriber.py backend/audio_preprocess.py backend/transcript_cleanup.py backend/tests/test_audio_preprocess.py backend/tests/test_transcript_cleanup.py
git commit -m "feat: improve whisper preprocessing and cleanup"
```

### Task 5: Add timing logs and cleanup semantics in route fallback paths

**Files:**
- Modify: `backend/routers/translate.py`
- Test: `backend/tests/test_translate_youtube_whisper.py`
- Test: `backend/tests/test_instagram_tiktok.py`

**Step 1: Write the failing tests**

```python
def test_youtube_whisper_fallback_returns_exports_from_cleaned_segments(monkeypatch) -> None:
    ...

def test_ytdlp_whisper_fallback_returns_exports_and_timing_logs(monkeypatch, caplog) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_translate_youtube_whisper.py backend/tests/test_instagram_tiktok.py -v`
Expected: FAIL because logs/new payload assumptions are not yet true

**Step 3: Write minimal implementation**

Refactor the fallback path in `backend/routers/translate.py` to:
- log download, preprocess, transcription, and total pipeline durations
- build exports from cleaned transcript segments for YouTube, Instagram, and TikTok
- preserve the non-Whisper YouTube caption-fetch path unchanged
- continue returning `no_speech_detected` for empty cleaned segments

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_translate_youtube_whisper.py backend/tests/test_instagram_tiktok.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/routers/translate.py backend/tests/test_translate_youtube_whisper.py backend/tests/test_instagram_tiktok.py
git commit -m "feat: add whisper fallback timing and cleaned exports"
```

### Task 6: Cover export integration and edge cases

**Files:**
- Modify: `backend/tests/test_export_formats.py`
- Add or modify: `backend/tests/test_translate_endpoint.py`

**Step 1: Write the failing tests**

```python
def test_export_formats_preserve_special_characters_and_emoji() -> None:
    ...

def test_translate_endpoint_returns_exports_for_youtube_whisper_fallback() -> None:
    ...

def test_translate_endpoint_returns_no_speech_for_music_only_or_empty_audio() -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_export_formats.py backend/tests/test_translate_endpoint.py -v`
Expected: FAIL because the coverage is missing

**Step 3: Write minimal implementation**

Only add production changes if the new tests expose missing behavior. Prefer test-only updates if the route already satisfies the contract.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_export_formats.py backend/tests/test_translate_endpoint.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_export_formats.py backend/tests/test_translate_endpoint.py backend/routers/translate.py
git commit -m "test: cover whisper export edge cases"
```

### Task 7: Full verification

**Files:**
- Review: `backend/audio_preprocess.py`
- Review: `backend/transcript_cleanup.py`
- Review: `backend/services/transcriber.py`
- Review: `backend/routers/translate.py`
- Review: `backend/tests/`

**Step 1: Run the backend test suite**

Run: `python3 -m pytest backend/tests/ -v`
Expected: PASS with 0 failures

**Step 2: Run a manual smoke test**

Run the API against a 30s Instagram Reel and confirm:
- timing logs include download/preprocess/transcription/total
- response includes `exports.vtt`, `exports.txt`, and `exports.md`
- cleaned transcript content looks reasonable

**Step 3: Review git state**

Run: `git status --short`
Expected: clean working tree

**Step 4: Commit any final adjustments**

```bash
git add ...
git commit -m "feat: finalize whisper pipeline"
```
