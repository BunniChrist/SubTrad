from playwright.sync_api import Page, expect


YOUTUBE_URL = "https://youtube.com/shorts/tk-w1zHHIZM"
UNSUPPORTED_URL = "https://www.example.com/video"


def dismiss_cookie_banner(page: Page) -> None:
    accept_button = page.get_by_role("button", name="Accepter")
    if accept_button.is_visible(timeout=3_000):
        accept_button.click()


def open_homepage(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    dismiss_cookie_banner(page)


def submit_video(page: Page, url: str, target_lang: str = "fr") -> None:
    page.locator("#video-url").fill(url)
    page.locator("#target-lang").select_option(target_lang)
    page.locator("#submit-button").click()


def test_homepage_loads_correctly(page: Page, base_url: str) -> None:
    open_homepage(page, base_url)

    expect(page).to_have_title("SubTrad")
    expect(page.locator("#video-url")).to_be_visible()
    expect(page.locator("#target-lang")).to_be_visible()
    expect(page.locator("#submit-button")).to_be_visible()


def test_invalid_url_shows_error(page: Page, base_url: str) -> None:
    open_homepage(page, base_url)

    submit_video(page, "not a url")

    expect(page.locator("#form-error")).to_be_visible()


def test_unsupported_platform_shows_error(page: Page, base_url: str) -> None:
    open_homepage(page, base_url)

    submit_video(page, UNSUPPORTED_URL)

    expect(page.locator("#form-error")).to_have_text("Unsupported video URL")


def test_valid_youtube_url_shows_processing_then_result(page: Page, base_url: str) -> None:
    open_homepage(page, base_url)

    submit_video(page, YOUTUBE_URL)

    expect(page.locator("#loading-section")).to_be_visible()
    page.wait_for_function(
        """
        () => {
            const player = document.querySelector("#player-section");
            const premiumNotice = document.querySelector("#premium-notice");
            const playerVisible = player && !player.classList.contains("hidden");
            const premiumVisible = premiumNotice && !premiumNotice.classList.contains("hidden");
            return playerVisible || premiumVisible || window.location.pathname === "/premium.html";
        }
        """,
        timeout=60_000,
    )

    if page.url.endswith("/premium.html"):
        expect(page).to_have_url(f"{base_url}/premium.html")
        return

    player_section = page.locator("#player-section")
    if player_section.is_visible():
        expect(player_section).to_be_visible()
        expect(page.locator("#subtitle-overlay")).to_be_attached()
        return

    expect(page.locator("#premium-notice")).to_be_visible()


def test_navigation_pages_load(page: Page, base_url: str) -> None:
    legal_response = page.goto(f"{base_url}/legal.html", wait_until="domcontentloaded")
    assert legal_response is not None
    assert legal_response.ok
    expect(page.locator("h1")).to_have_text("Politique de confidentialité et mentions légales")

    suggestions_response = page.goto(
        f"{base_url}/suggestions.html",
        wait_until="domcontentloaded",
    )
    assert suggestions_response is not None
    assert suggestions_response.ok
    expect(page.locator("h1")).to_have_text("Help us improve SubTrad.")
