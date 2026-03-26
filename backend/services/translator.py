from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

try:
    from backend.services.translation_prompts import (
        SYSTEM_PROMPT,
        get_translation_prompt,
        parse_translation_response,
    )
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from services.translation_prompts import (
        SYSTEM_PROMPT,
        get_translation_prompt,
        parse_translation_response,
    )


@dataclass
class TranslationResult:
    segments: list[dict[str, float | str]]
    detected_language: str | None
    translation_status: str


def detect_source_language(
    segments: list[dict[str, float | str]],
    api_key: str,
) -> str | None:
    if not segments:
        return None

    sample_segments = segments[:3]
    numbered_segments = "\n".join(
        f"{index}|{segment['text']}" for index, segment in enumerate(sample_segments, start=1)
    )

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Reply with the ISO 639-1 language code only.",
                },
                {
                    "role": "user",
                    "content": (
                        "What language is this subtitle sample? "
                        "Reply with the ISO 639-1 code only.\n"
                        f"{numbered_segments}"
                    ),
                },
            ],
        )
    except Exception:
        return None

    detected = _extract_message_content(response).strip().lower()
    if len(detected) == 2 and detected.isalpha():
        return detected
    return None


def translate_subtitles(
    segments: list[dict[str, float | str]],
    target_lang: str,
    api_key: str,
    source_lang: str | None = None,
) -> list[dict[str, float | str]]:
    return translate_subtitles_with_metadata(
        segments,
        target_lang,
        api_key,
        source_lang=source_lang,
    ).segments


def translate_subtitles_with_metadata(
    segments: list[dict[str, float | str]],
    target_lang: str,
    api_key: str,
    source_lang: str | None = None,
) -> TranslationResult:
    if not segments:
        return TranslationResult(
            segments=[],
            detected_language=source_lang,
            translation_status="translated",
        )

    detected_source = source_lang or detect_source_language(segments, api_key)
    if detected_source == target_lang:
        return TranslationResult(
            segments=list(segments),
            detected_language=detected_source,
            translation_status="skipped_same_lang",
        )

    client = OpenAI(api_key=api_key)
    translated_segments: list[dict[str, float | str]] = []
    had_failure = False

    for start_index in range(0, len(segments), 20):
        batch = segments[start_index : start_index + 20]
        previous_text = _get_context_text(segments, start_index - 1)
        next_text = _get_context_text(segments, start_index + len(batch))

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _build_batch_prompt(
                            target_lang=target_lang,
                            batch=batch,
                            previous_text=previous_text,
                            next_text=next_text,
                        ),
                    },
                ],
            )
            translated_batch = parse_translation_response(
                _extract_message_content(response),
                batch,
            )
        except Exception:
            translated_batch = list(batch)
            had_failure = True

        translated_segments.extend(translated_batch)

    return TranslationResult(
        segments=translated_segments,
        detected_language=detected_source,
        translation_status="failed_fallback_original" if had_failure else "translated",
    )


def _build_batch_prompt(
    target_lang: str,
    batch: list[dict[str, float | str]],
    previous_text: str | None,
    next_text: str | None,
) -> str:
    prompt = get_translation_prompt(target_lang, batch)
    context_lines = []
    if previous_text:
        context_lines.append(f"Previous segment context: {previous_text}")
    if next_text:
        context_lines.append(f"Next segment context: {next_text}")
    if not context_lines:
        return prompt

    return f"{prompt}\n" + "\n".join(context_lines)


def _extract_message_content(response: object) -> str:
    choices = getattr(response, "choices", [])
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    return str(getattr(message, "content", "") or "")


def _get_context_text(
    segments: list[dict[str, float | str]],
    index: int,
) -> str | None:
    if index < 0 or index >= len(segments):
        return None

    text = segments[index].get("text")
    return str(text) if text is not None else None
