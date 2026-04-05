# Codex Translator Backend Design

## Goal

Add an alternative subtitle translation backend that uses the local `codex exec` CLI instead of the OpenAI Python API, while preserving the existing OpenAI translator unchanged and keeping runtime switching to a single config value.

## Architecture

The existing OpenAI implementation in `backend/services/translator.py` remains the canonical OpenAI backend and is not modified. A new `backend/services/translator_codex.py` will mirror its public behavior, reuse `translation_prompts.py`, and execute prompts through `subprocess.run(["codex", "exec", "-m", model, prompt], ...)`.

A new `backend/services/translator_dispatch.py` will provide the stable entrypoints used by application code. It will read `translation_backend` from settings by default and route calls to either the unchanged OpenAI backend or the new Codex backend. This keeps caller changes small and preserves the option to switch back by changing environment only.

## Data Flow

For language detection, the dispatcher will call either `detect_source_language()` or `detect_source_language_codex()`. For translation, it will route to either backend-specific `translate_subtitles_with_metadata()` implementation. Both paths will return the same `TranslationResult` dataclass shape so the router layer can remain backend-agnostic.

The Codex backend will batch segments in groups of 20 exactly like the OpenAI backend, reuse `_build_batch_prompt`-equivalent behavior for previous/next context, and parse output with `parse_translation_response()`. On subprocess timeout, non-zero exit, or malformed output, it will fall back to the original batch and mark the overall status as `"failed_fallback_original"`.

## Error Handling

The Codex backend will treat subprocess failures the same way the OpenAI backend treats API failures: language detection returns `None`, translation falls back to the original segments for failed batches, and same-language detection skips translation entirely. Empty input still returns an empty successful result.

## Testing

TDD will cover the new behavior with dedicated tests for Codex subprocess invocation, timeout and non-zero exit fallback, empty input, same-language skip, and dispatcher routing. Existing OpenAI tests in `backend/tests/test_translator.py` must continue to pass unchanged to prove the original backend was preserved.
