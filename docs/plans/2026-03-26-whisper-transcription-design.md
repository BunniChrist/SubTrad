# Whisper Transcription Design

**Context:** Phase 1 already validates URLs, extracts video IDs, checks duration, fetches existing subtitles, and exposes `/api/translate`.

**Recommended approach:** keep the translate endpoint synchronous for Phase 2 and add a fallback pipeline only when existing subtitles are missing. The fallback path is `extract_audio(url, video_id) -> transcribe_audio(audio_path, api_key) -> cleanup_audio(audio_path)` with explicit error handling and response metadata.

**Alternatives considered:**
1. **Synchronous fallback in the request path** — simplest integration, smallest diff, fits current API shape. Recommended for Phase 2.
2. **Background job + polling** — better for long media, but adds job state, storage, and client changes not required yet.
3. **Direct transcription inside the router without services** — fewer files, but poor testability and harder mocking.

**Data flow:** the router keeps Phase 1 behavior for existing captions. If subtitles are absent, it downloads temporary audio to `/tmp/subtrad/<video_id>.<ext>`, sends that file to Whisper with `response_format="verbose_json"` and segment timestamps, then returns timestamped subtitles plus `source="whisper_transcription"` and `needs_transcription=true`.

**Error handling:** extraction and transcription failures return a clear `502` API error. Audio cleanup runs in `finally` so temporary files are removed on both success and failure.

**Testing strategy:** unit tests mock `yt-dlp` and `OpenAI` client calls; one integration extractor test uses a short real YouTube URL; one integration transcription test uses a tracked fixture audio file and a real OpenAI key loaded from `SUBTRAD_OPENAI_API_KEY`.
