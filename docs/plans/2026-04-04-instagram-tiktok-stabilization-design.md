# Instagram & TikTok Stabilization Design

## Scope

Stabilize the shared yt-dlp path used by Instagram and TikTok in `backend/routers/translate.py` without changing the YouTube pipeline. The work adds resilient access retry behavior, user-facing 422 errors for common failure modes, and transcript exports for downstream vectorization.

## Constraints

- Only the `_handle_ytdlp()` flow and directly related code should change.
- Tests must mock yt-dlp and OpenAI-facing behavior.
- Existing endpoint semantics for YouTube stay intact.
- No new dependencies.

## Approach

Keep `_handle_ytdlp()` as the orchestration point and add narrow helpers around it instead of extracting a new service. This keeps the branch low-risk and avoids broad architectural churn in a path that already integrates cache, duration checks, transcription, and translation.

For platform access and extraction failures, normalize exceptions into explicit JSON responses with stable `error_code` values. Retry is limited to one extra attempt after a WARP rotation when the first yt-dlp-related failure matches the existing block heuristics or an HTTP 429 pattern.

For Whisper output, generate `vtt`, `txt`, and `md` exports after transcription and include them in the API response and any cached payload created from that response. Export formatting stays in a dedicated utility module so it can be unit-tested independently from the endpoint.

## Testing Strategy

- Add a new parametric endpoint test file covering Instagram and TikTok.
- Add focused unit tests for `backend/export_formats.py`.
- Preserve existing tests in `backend/tests/test_translate_endpoint.py` and related files.

## Risks

- The existing response model currently does not expose `exports`; this needs a compatible schema extension.
- Cached payloads must accept the new field without breaking old responses.
- Markdown export should stay deterministic so snapshot-style assertions remain stable.
