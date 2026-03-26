from __future__ import annotations

LANGUAGE_NAMES = {
    "fr": "French",
    "es": "Spanish",
    "en": "English",
    "ja": "Japanese",
}

SYSTEM_PROMPT = (
    "You are a professional subtitle translator. Translate naturally, not literally. "
    "Preserve meaning, tone, and cultural context."
)


def get_translation_prompt(
    target_lang: str,
    segments: list[dict[str, object]],
) -> str:
    language_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    numbered_segments = "\n".join(
        f"{index}|{segment['text']}" for index, segment in enumerate(segments, start=1)
    )

    return (
        f"System: {SYSTEM_PROMPT}\n"
        f"User: Translate these subtitle segments into {language_name}.\n"
        "Preserve numbering and return the response in the same `number|text` format.\n"
        f"{numbered_segments}"
    )


def parse_translation_response(
    response_text: str,
    original_segments: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not original_segments:
        return []

    lines = [line.strip() for line in response_text.splitlines() if line.strip()]
    if len(lines) != len(original_segments):
        return list(original_segments)

    translated_segments: list[dict[str, object]] = []
    for original_segment, line in zip(original_segments, lines, strict=True):
        _, separator, translated_text = line.partition("|")
        if not separator or not translated_text.strip():
            return list(original_segments)

        translated_segments.append(
            {
                "start": original_segment["start"],
                "end": original_segment["end"],
                "text": translated_text.strip(),
            }
        )

    return translated_segments
