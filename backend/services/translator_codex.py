from __future__ import annotations

import subprocess

try:
    from backend.config import get_settings
    from backend.services.translation_prompts import (
        SYSTEM_PROMPT,
        get_translation_prompt,
        parse_translation_response,
    )
    from backend.services.translator import TranslationResult
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from config import get_settings
    from services.translation_prompts import (
        SYSTEM_PROMPT,
        get_translation_prompt,
        parse_translation_response,
    )
    from services.translator import TranslationResult


def detect_source_language_codex(
    segments: list[dict[str, float | str]],
) -> str | None:
    if not segments:
        return None

    sample_segments = segments[:3]
    numbered_segments = "\n".join(
        f"{index}|{segment['text']}" for index, segment in enumerate(sample_segments, start=1)
    )
    prompt = (
        "What language is this subtitle sample? Reply with the ISO 639-1 code only.\n"
        f"{numbered_segments}"
    )

    output = _run_codex(prompt)
    if output is None:
        return None

    detected = output.strip().lower()
    if len(detected) == 2 and detected.isalpha():
        return detected
    return None


def translate_subtitles_codex(
    segments: list[dict[str, float | str]],
    target_lang: str,
    source_lang: str | None = None,
) -> list[dict[str, float | str]]:
    return translate_subtitles_with_metadata_codex(
        segments,
        target_lang,
        source_lang=source_lang,
    ).segments


def translate_subtitles_with_metadata_codex(
    segments: list[dict[str, float | str]],
    target_lang: str,
    source_lang: str | None = None,
) -> TranslationResult:
    if not segments:
        return TranslationResult(
            segments=[],
            detected_language=source_lang,
            translation_status="translated",
        )

    detected_source = source_lang or detect_source_language_codex(segments)
    if detected_source == target_lang:
        return TranslationResult(
            segments=list(segments),
            detected_language=detected_source,
            translation_status="skipped_same_lang",
        )

    translated_segments: list[dict[str, float | str]] = []
    had_failure = False

    for start_index in range(0, len(segments), 20):
        batch = segments[start_index : start_index + 20]
        previous_text = _get_context_text(segments, start_index - 1)
        next_text = _get_context_text(segments, start_index + len(batch))
        prompt = _build_batch_prompt(
            target_lang=target_lang,
            batch=batch,
            previous_text=previous_text,
            next_text=next_text,
        )
        output = _run_codex(prompt)

        if output is None:
            translated_batch = list(batch)
            had_failure = True
        else:
            translated_batch = parse_translation_response(output, batch)
            if translated_batch == list(batch):
                had_failure = True

        translated_segments.extend(translated_batch)

    return TranslationResult(
        segments=translated_segments,
        detected_language=detected_source,
        translation_status="failed_fallback_original" if had_failure else "translated",
    )


def _run_codex(prompt: str) -> str | None:
    model = get_settings().codex_model

    try:
        completed = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check", "-m", model, "-"],
            capture_output=True,
            text=True,
            input=prompt,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None

    return _parse_codex_output(str(completed.stdout or ""))


def _parse_codex_output(raw: str) -> str | None:
    """Extract the response text from codex exec stdout.

    Codex exec output varies between versions but always contains:
        codex
        <response>
        [<response repeated>]
        tokens used
        <N>
        [<response repeated>]

    Strategy: extract text between 'codex' and 'tokens used', then
    de-duplicate by checking if the block is a repeated concatenation.
    """
    lines = raw.splitlines()
    start = None
    end = None
    for i, line in enumerate(lines):
        if line.strip() == "codex" and start is None:
            start = i + 1
        elif line.strip() == "tokens used":
            end = i
            break

    if start is not None and end is not None and start < end:
        content_lines = lines[start:end]
    elif start is not None:
        # 'tokens used' not found — take everything after 'codex'
        content_lines = lines[start:]
    else:
        return raw.strip() or None

    # De-duplicate: if content is even-length and first half == second half
    n = len(content_lines)
    if n >= 2 and n % 2 == 0:
        half = n // 2
        if content_lines[:half] == content_lines[half:]:
            content_lines = content_lines[:half]

    return "\n".join(content_lines).strip() or None


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


def _get_context_text(
    segments: list[dict[str, float | str]],
    index: int,
) -> str | None:
    if index < 0 or index >= len(segments):
        return None

    text = segments[index].get("text")
    return str(text) if text is not None else None
