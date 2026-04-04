from backend.transcript_cleanup import cleanup_transcript


def test_cleanup_transcript_filters_music_and_repeated_noise() -> None:
    cleaned = cleanup_transcript(
        [
            {"start": 0.0, "end": 0.8, "text": "[Music]"},
            {"start": 0.8, "end": 1.6, "text": "Hello there"},
            {"start": 1.6, "end": 2.4, "text": "Hello there"},
        ]
    )

    assert cleaned == [{"start": 0.8, "end": 1.6, "text": "Hello there"}]


def test_cleanup_transcript_merges_mid_sentence_segments() -> None:
    cleaned = cleanup_transcript(
        [
            {"start": 0.0, "end": 1.0, "text": "This is"},
            {"start": 1.0, "end": 2.0, "text": "a sentence."},
            {"start": 2.0, "end": 3.0, "text": "New thought."},
        ]
    )

    assert cleaned == [
        {"start": 0.0, "end": 2.0, "text": "This is a sentence."},
        {"start": 2.0, "end": 3.0, "text": "New thought."},
    ]


def test_cleanup_transcript_drops_meaningless_short_segments() -> None:
    cleaned = cleanup_transcript(
        [
            {"start": 0.0, "end": 0.2, "text": "Mm"},
            {"start": 0.2, "end": 1.2, "text": "Actual speech"},
        ]
    )

    assert cleaned == [{"start": 0.2, "end": 1.2, "text": "Actual speech"}]
