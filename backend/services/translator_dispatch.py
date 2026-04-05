from __future__ import annotations

try:
    from backend.config import get_settings
    from backend.services.translator import (
        detect_source_language,
        translate_subtitles,
        translate_subtitles_with_metadata,
    )
    from backend.services.translator_codex import (
        detect_source_language_codex,
        translate_subtitles_codex,
        translate_subtitles_with_metadata_codex,
    )
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from config import get_settings
    from services.translator import (
        detect_source_language,
        translate_subtitles,
        translate_subtitles_with_metadata,
    )
    from services.translator_codex import (
        detect_source_language_codex,
        translate_subtitles_codex,
        translate_subtitles_with_metadata_codex,
    )


def detect_source_language_dispatch(
    segments: list[dict[str, float | str]],
    api_key: str,
    backend: str | None = None,
) -> str | None:
    selected_backend = _select_backend(backend)
    if selected_backend == "codex":
        return detect_source_language_codex(segments)
    return detect_source_language(segments, api_key)


def translate_subtitles_dispatch(
    segments: list[dict[str, float | str]],
    target_lang: str,
    api_key: str,
    source_lang: str | None = None,
    backend: str | None = None,
) -> list[dict[str, float | str]]:
    selected_backend = _select_backend(backend)
    if selected_backend == "codex":
        return translate_subtitles_codex(
            segments,
            target_lang,
            source_lang=source_lang,
        )
    return translate_subtitles(
        segments,
        target_lang,
        api_key,
        source_lang=source_lang,
    )


def translate_subtitles_with_metadata_dispatch(
    segments: list[dict[str, float | str]],
    target_lang: str,
    api_key: str,
    source_lang: str | None = None,
    backend: str | None = None,
):
    selected_backend = _select_backend(backend)
    if selected_backend == "codex":
        return translate_subtitles_with_metadata_codex(
            segments,
            target_lang,
            source_lang=source_lang,
        )
    return translate_subtitles_with_metadata(
        segments,
        target_lang,
        api_key,
        source_lang=source_lang,
    )


def _select_backend(backend: str | None) -> str:
    if backend is not None:
        return backend
    return get_settings().translation_backend
