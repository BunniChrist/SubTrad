from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from yt_dlp import YoutubeDL

try:
    from backend.api_errors import ApiError
    from backend.config import get_settings
    from backend.export_formats import to_md, to_txt, to_vtt
    from backend.models import TranslateRequest, TranslateResponse
    from backend.services.audio_extractor import cleanup_audio, extract_audio
    from backend.services.cache import SubtitleCache
    from backend.services.duration_checker import check_duration
    from backend.services.request_counter import RequestCounter
    from backend.services.subtitle_fetcher import fetch_existing_subtitles
    from backend.services.transcriber import transcribe_audio_with_metadata
    from backend.services.translator import translate_subtitles_with_metadata
    from backend.services.url_validator import detect_platform, validate_url
    from backend.services.video_id import extract_video_id
    from backend.services.warp_rotator import is_youtube_block, rotate_warp_ip
    from backend.services.youtube_api import (
        fetch_captions_with_source as fetch_captions_via_api,
        get_video_info,
    )
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from api_errors import ApiError
    from config import get_settings
    from export_formats import to_md, to_txt, to_vtt
    from models import TranslateRequest, TranslateResponse
    from services.audio_extractor import cleanup_audio, extract_audio
    from services.cache import SubtitleCache
    from services.duration_checker import check_duration
    from services.request_counter import RequestCounter
    from services.subtitle_fetcher import fetch_existing_subtitles
    from services.transcriber import transcribe_audio_with_metadata
    from services.translator import translate_subtitles_with_metadata
    from services.url_validator import detect_platform, validate_url
    from services.video_id import extract_video_id
    from services.warp_rotator import is_youtube_block, rotate_warp_ip
    from services.youtube_api import (
        fetch_captions_with_source as fetch_captions_via_api,
        get_video_info,
    )


router = APIRouter(prefix="/api", tags=["translate"])
YOUTUBE_COOKIE_FILE = Path("/root/yt_cookies.txt")
logger = logging.getLogger(__name__)


def fetch_video_duration_seconds(url: str, proxy: str = "") -> int:
    options = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignore_no_formats_error": True,
    }
    if YOUTUBE_COOKIE_FILE.exists():
        options["cookiefile"] = str(YOUTUBE_COOKIE_FILE)
    if proxy:
        options["proxy"] = proxy

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    return int(info.get("duration") or 0)


def build_translate_response(
    *,
    platform: str,
    video_id: str,
    subtitles: list[dict[str, object]],
    duration_seconds: int,
    needs_transcription: bool,
    source: str,
    target_lang: str,
    detected_language: str | None,
    translation_status: str,
    exports: dict[str, str] | None = None,
) -> TranslateResponse:
    return TranslateResponse(
        platform=platform,
        video_id=video_id,
        subtitles=subtitles,
        duration_seconds=duration_seconds,
        needs_transcription=needs_transcription,
        source=source,
        target_lang=target_lang,
        detected_language=detected_language,
        translation_status=translation_status,
        exports=exports,
    )


def _build_transcript_exports(
    *,
    segments: list[dict[str, float | str]],
    platform: str,
    video_id: str,
    language: str | None,
) -> dict[str, str]:
    metadata = {
        "title": f"{platform}-{video_id}",
        "platform": platform,
        "video_id": video_id,
        "language": language or "",
        "date": date.today().isoformat(),
    }
    return {
        "vtt": to_vtt(segments),
        "txt": to_txt(segments),
        "md": to_md(segments, metadata=metadata),
    }


def _platform_error(detail: str, error_code: str, status_code: int = 422) -> JSONResponse:
    raise ApiError(status_code=status_code, content={"detail": detail, "error_code": error_code})


def _response_error(status_code: int, detail: str, error: str) -> None:
    raise ApiError(status_code=status_code, content={"detail": detail, "error": error})


def _call_ytdlp_with_retry(operation, *, settings):
    try:
        return operation()
    except Exception as exc:
        if not is_youtube_block(exc):
            raise
        rotation_url = settings.warp_rotation_url
        if rotation_url:
            rotate_warp_ip(rotation_url)
        return operation()


def _extract_segments(payload: object) -> list[dict[str, float | str]]:
    if isinstance(payload, dict):
        segments = payload.get("segments")
    else:
        segments = getattr(payload, "segments", None)
    if not isinstance(segments, list):
        return []
    return [segment for segment in segments if isinstance(segment, dict)]


def _extract_language(payload: object) -> str | None:
    if isinstance(payload, dict):
        language = payload.get("language")
    else:
        language = getattr(payload, "language", None)
    return str(language) if language is not None else None


def _translation_value(payload: object, key: str, default: object = None) -> object:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _translation_segments(payload: object) -> list[dict[str, object]]:
    segments = _translation_value(payload, "segments", [])
    if not isinstance(segments, list):
        return []
    return [segment for segment in segments if isinstance(segment, dict)]


def _translation_detected_language(payload: object) -> str | None:
    value = _translation_value(payload, "detected_language")
    return str(value) if value is not None else None


def _translation_status(payload: object) -> str:
    value = _translation_value(payload, "translation_status", "translated")
    return str(value)


def _timing_value(payload: object, key: str) -> float:
    if not isinstance(payload, dict):
        return 0.0
    timings = payload.get("timings")
    if not isinstance(timings, dict):
        return 0.0
    value = timings.get(key, 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _run_whisper_fallback(
    *,
    audio_source_url: str,
    platform: str,
    video_id: str,
    target_lang: str,
    duration_seconds: int,
    settings,
    cache: SubtitleCache,
    counter: RequestCounter,
) -> TranslateResponse:
    audio_path = ""
    total_started_at = time.perf_counter()
    download_started_at = total_started_at

    try:
        audio_path = extract_audio(
            audio_source_url,
            video_id,
            proxy=settings.warp_proxy_url or settings.proxy_url,
        )
        download_elapsed = time.perf_counter() - download_started_at
        transcription_result = transcribe_audio_with_metadata(audio_path)
    finally:
        if audio_path:
            cleanup_audio(audio_path)

    transcription_segments = _extract_segments(transcription_result)
    if not transcription_segments:
        _platform_error(
            "No speech detected in this video.",
            "no_speech_detected",
        )

    preprocess_elapsed = _timing_value(transcription_result, "preprocess_seconds")
    transcription_elapsed = _timing_value(transcription_result, "transcription_seconds")
    total_elapsed = time.perf_counter() - total_started_at
    logger.info(
        "Whisper fallback timings platform=%s video_id=%s download_seconds=%.3f preprocess_seconds=%.3f transcription_seconds=%.3f total_seconds=%.3f",
        platform,
        video_id,
        download_elapsed,
        preprocess_elapsed,
        transcription_elapsed,
        total_elapsed,
    )

    translation_result = translate_subtitles_with_metadata(
        transcription_segments,
        target_lang,
        settings.openai_api_key,
        source_lang=_extract_language(transcription_result),
    )

    response = build_translate_response(
        platform=platform,
        video_id=video_id,
        subtitles=_translation_segments(translation_result),
        duration_seconds=duration_seconds,
        needs_transcription=True,
        source="whisper_transcription",
        target_lang=target_lang,
        detected_language=_translation_detected_language(translation_result),
        translation_status=_translation_status(translation_result),
        exports=_build_transcript_exports(
            segments=transcription_segments,
            platform=platform,
            video_id=video_id,
            language=_extract_language(transcription_result),
        ),
    )
    counter.increment(video_id, target_lang)
    if counter.should_cache(video_id, target_lang):
        cache.store(video_id, target_lang, response.model_dump())
    return response


@router.post("/translate", response_model=TranslateResponse)
def translate_video(request: TranslateRequest) -> TranslateResponse:
    settings = get_settings()

    if not validate_url(request.url):
        raise HTTPException(status_code=400, detail="Unsupported video URL")

    if request.target_lang not in settings.supported_languages:
        raise HTTPException(status_code=400, detail="Unsupported target language")

    platform = detect_platform(request.url)
    if platform is None:
        raise HTTPException(status_code=400, detail="Unsupported video URL")

    video_id = extract_video_id(request.url, platform)
    cache = SubtitleCache(settings.cache_db_path)
    counter = RequestCounter(settings.cache_db_path, threshold=settings.cache_threshold)

    cached = cache.retrieve(video_id, request.target_lang)
    if cached is not None:
        cached["translation_status"] = "cached"
        return TranslateResponse(**cached)

    # --- YouTube: use YouTube Data API v3 ---
    if platform == "youtube":
        return _handle_youtube(
            video_id=video_id,
            target_lang=request.target_lang,
            settings=settings,
            cache=cache,
            counter=counter,
        )

    # --- TikTok / Instagram: keep existing yt-dlp flow ---
    return _handle_ytdlp(
        url=request.url,
        platform=platform,
        video_id=video_id,
        target_lang=request.target_lang,
        settings=settings,
        cache=cache,
        counter=counter,
    )


def _handle_youtube(
    *,
    video_id: str,
    target_lang: str,
    settings,
    cache: SubtitleCache,
    counter: RequestCounter,
) -> TranslateResponse:
    """Handle YouTube videos via YouTube Data API v3."""
    try:
        info = get_video_info(video_id, settings.youtube_api_key)
    except Exception as exc:
        _response_error(502, "Video metadata lookup failed", str(exc))

    if info is None:
        _response_error(502, "Video metadata lookup failed", "Video not found")

    duration_value = info.get("duration_seconds") if isinstance(info, dict) else getattr(info, "duration_seconds", None)
    if not isinstance(duration_value, int):
        _response_error(502, "Video metadata lookup failed", "Missing video duration")
    duration_seconds = duration_value
    duration_result = check_duration(duration_seconds)

    if not duration_result.allowed:
        raise ApiError(
            status_code=403,
            content={
                "detail": "Video exceeds maximum duration",
                "redirect": duration_result.redirect,
                "duration_seconds": duration_result.duration_seconds,
            },
        )

    subtitles_result = fetch_captions_via_api(
        video_id,
        target_lang,
        settings.youtube_api_key,
        proxy=settings.warp_proxy_url or settings.proxy_url,
        cookie_file=str(YOUTUBE_COOKIE_FILE) if YOUTUBE_COOKIE_FILE.exists() else None,
    )
    subtitle_source = "existing_captions"
    if isinstance(subtitles_result, tuple):
        subtitles, subtitle_source = subtitles_result
    else:
        subtitles = subtitles_result

    if subtitles is None:
        try:
            return _run_whisper_fallback(
                audio_source_url=f"https://www.youtube.com/watch?v={video_id}",
                platform="youtube",
                video_id=video_id,
                target_lang=target_lang,
                duration_seconds=duration_result.duration_seconds,
                settings=settings,
                cache=cache,
                counter=counter,
            )
        except ApiError:
            raise
        except ValueError:
            _platform_error("Audio transcription failed.", "audio_transcription_failed")
        except Exception:
            logger.exception("Unexpected Whisper fallback failure for youtube video_id=%s", video_id)
            raise ApiError(
                status_code=500,
                content={
                    "detail": "Transcription pipeline failed.",
                    "error_code": "internal_error",
                },
            )

    translation_result = translate_subtitles_with_metadata(
        subtitles,
        target_lang,
        settings.openai_api_key,
    )

    response = build_translate_response(
        platform="youtube",
        video_id=video_id,
        subtitles=_translation_segments(translation_result),
        duration_seconds=duration_result.duration_seconds,
        needs_transcription=False,
        source=subtitle_source,
        target_lang=target_lang,
        detected_language=_translation_detected_language(translation_result),
        translation_status=_translation_status(translation_result),
    )
    counter.increment(video_id, target_lang)
    if counter.should_cache(video_id, target_lang):
        cache.store(video_id, target_lang, response.model_dump())
    return response


def _handle_ytdlp(
    *,
    url: str,
    platform: str,
    video_id: str,
    target_lang: str,
    settings,
    cache: SubtitleCache,
    counter: RequestCounter,
) -> TranslateResponse:
    """Handle TikTok/Instagram videos via yt-dlp (existing flow)."""
    try:
        duration_seconds = _call_ytdlp_with_retry(
            lambda: fetch_video_duration_seconds(url, proxy=settings.warp_proxy_url or settings.proxy_url),
            settings=settings,
        )
    except Exception:
        _platform_error(
            "Could not access this video. It may be private or unavailable.",
            "platform_access_failed",
        )
    duration_result = check_duration(duration_seconds)

    if not duration_result.allowed:
        raise ApiError(
            status_code=403,
            content={
                "detail": "Video exceeds maximum duration",
                "redirect": duration_result.redirect,
                "duration_seconds": duration_result.duration_seconds,
            },
        )

    try:
        subtitles = _call_ytdlp_with_retry(
            lambda: fetch_existing_subtitles(url, proxy=settings.warp_proxy_url or settings.proxy_url),
            settings=settings,
        )
    except Exception:
        _platform_error(
            "Could not access this video. It may be private or unavailable.",
            "platform_access_failed",
        )
    if subtitles is not None:
        translation_result = translate_subtitles_with_metadata(
            subtitles,
            target_lang,
            settings.openai_api_key,
        )
        response = build_translate_response(
            platform=platform,
            video_id=video_id,
            subtitles=_translation_segments(translation_result),
            duration_seconds=duration_result.duration_seconds,
            needs_transcription=False,
            source="existing_captions",
            target_lang=target_lang,
            detected_language=_translation_detected_language(translation_result),
            translation_status=_translation_status(translation_result),
        )
        counter.increment(video_id, target_lang)
        if counter.should_cache(video_id, target_lang):
            cache.store(video_id, target_lang, response.model_dump())
        return response

    try:
        return _run_whisper_fallback(
            audio_source_url=url,
            platform=platform,
            video_id=video_id,
            target_lang=target_lang,
            duration_seconds=duration_result.duration_seconds,
            settings=settings,
            cache=cache,
            counter=counter,
        )
    except ApiError:
        raise
    except ValueError:
        _platform_error(
            "Audio transcription failed.",
            "audio_transcription_failed",
        )
    except Exception:
        logger.exception(
            "Unexpected Whisper fallback failure for platform=%s video_id=%s",
            platform,
            video_id,
        )
        raise ApiError(
            status_code=500,
            content={
                "detail": "Transcription pipeline failed.",
                "error_code": "internal_error",
            },
        )
