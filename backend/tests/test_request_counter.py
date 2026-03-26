from backend.services.request_counter import RequestCounter


def test_increment_starts_count_at_one() -> None:
    counter = RequestCounter(":memory:", threshold=100)

    assert counter.increment("video-1", "fr") == 1
    assert counter.get_count("video-1", "fr") == 1


def test_increment_accumulates_for_same_video_and_language() -> None:
    counter = RequestCounter(":memory:", threshold=100)

    counter.increment("video-1", "fr")
    count = counter.increment("video-1", "fr")

    assert count == 2
    assert counter.get_count("video-1", "fr") == 2


def test_should_cache_is_false_below_threshold() -> None:
    counter = RequestCounter(":memory:", threshold=100)

    for _ in range(99):
        counter.increment("video-1", "fr")

    assert counter.should_cache("video-1", "fr") is False


def test_should_cache_is_true_at_threshold() -> None:
    counter = RequestCounter(":memory:", threshold=100)

    for _ in range(100):
        counter.increment("video-1", "fr")

    assert counter.should_cache("video-1", "fr") is True


def test_should_cache_is_true_above_threshold() -> None:
    counter = RequestCounter(":memory:", threshold=100)

    for _ in range(101):
        counter.increment("video-1", "fr")

    assert counter.should_cache("video-1", "fr") is True


def test_counts_are_independent_per_video_and_language() -> None:
    counter = RequestCounter(":memory:", threshold=2)

    counter.increment("video-1", "fr")
    counter.increment("video-1", "es")
    counter.increment("video-2", "fr")
    counter.increment("video-2", "fr")

    assert counter.get_count("video-1", "fr") == 1
    assert counter.get_count("video-1", "es") == 1
    assert counter.get_count("video-2", "fr") == 2
    assert counter.should_cache("video-1", "fr") is False
    assert counter.should_cache("video-2", "fr") is True
