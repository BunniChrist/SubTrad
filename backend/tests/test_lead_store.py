from backend.services.lead_store import LeadStore


def test_save_lead_increments_count() -> None:
    store = LeadStore(":memory:")

    lead_id = store.save_lead("alice@example.com", "premium")

    assert lead_id == 1
    assert store.get_lead_count("premium") == 1


def test_duplicate_lead_returns_existing_id_without_creating_new_row() -> None:
    store = LeadStore(":memory:")

    first_id = store.save_lead("alice@example.com", "premium")
    duplicate_id = store.save_lead("alice@example.com", "premium")

    assert duplicate_id == first_id
    assert store.get_lead_count("premium") == 1


def test_counts_are_separated_by_lead_type() -> None:
    store = LeadStore(":memory:")

    store.save_lead("alice@example.com", "premium")
    store.save_lead("alice@example.com", "suggestion", "Add Italian subtitles")
    store.save_lead("bob@example.com", "suggestion", "Support Vimeo")

    assert store.get_lead_count("premium") == 1
    assert store.get_lead_count("suggestion") == 2


def test_message_is_optional() -> None:
    store = LeadStore(":memory:")

    store.save_lead("alice@example.com", "premium", None)

    assert store.get_lead_count("premium") == 1


def test_lead_exists_checks_email_and_type_together() -> None:
    store = LeadStore(":memory:")

    store.save_lead("alice@example.com", "premium")

    assert store.lead_exists("alice@example.com", "premium") is True
    assert store.lead_exists("alice@example.com", "suggestion") is False
