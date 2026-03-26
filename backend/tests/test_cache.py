from backend.services.cache import SubtitleCache


def build_response(text: str) -> dict[str, object]:
    return {
        "platform": "youtube",
        "video_id": "video-1",
        "subtitles": [{"start": 0.0, "end": 1.0, "text": text}],
        "duration_seconds": 120,
        "needs_transcription": True,
        "source": "whisper_transcription",
        "target_lang": "fr",
        "detected_language": "en",
        "translation_status": "translated",
    }


def test_store_and_retrieve_round_trip() -> None:
    cache = SubtitleCache(":memory:")
    response_data = build_response("Bonjour")

    cache.store("video-1", "fr", response_data)

    assert cache.retrieve("video-1", "fr") == response_data


def test_retrieve_returns_none_for_missing_entry() -> None:
    cache = SubtitleCache(":memory:")

    assert cache.retrieve("missing-video", "fr") is None


def test_exists_reflects_cache_presence() -> None:
    cache = SubtitleCache(":memory:")

    assert cache.exists("video-1", "fr") is False
    cache.store("video-1", "fr", build_response("Bonjour"))
    assert cache.exists("video-1", "fr") is True


def test_store_overwrites_existing_cache_entry() -> None:
    cache = SubtitleCache(":memory:")

    cache.store("video-1", "fr", build_response("Bonjour"))
    cache.store("video-1", "fr", build_response("Salut"))

    assert cache.retrieve("video-1", "fr") == build_response("Salut")


def test_subtitles_are_serialized_and_deserialized() -> None:
    cache = SubtitleCache(":memory:")
    response_data = {
        "platform": "youtube",
        "video_id": "video-1",
        "subtitles": [
            {"start": "00:00:01,000", "end": "00:00:02,000", "text": "Bonjour"},
            {"start": 2.0, "end": 3.5, "text": "Salut"},
        ],
        "duration_seconds": 120,
        "needs_transcription": False,
        "source": "existing_captions",
        "target_lang": "fr",
        "detected_language": "en",
        "translation_status": "translated",
    }

    cache.store("video-1", "fr", response_data)

    assert cache.retrieve("video-1", "fr") == response_data
