// E2E test: YouTube Shorts with ASR-only captions should display translated subtitles
// Target video: https://youtube.com/shorts/tk-w1zHHIZM (ASR captions, no manual subs)

const { test, expect } = require("@playwright/test");

const BASE_URL = "https://subtrad.bunnichrist.fr";

const SHORTS_VIDEOS = [
  { url: "https://youtube.com/shorts/tk-w1zHHIZM", label: "Shorts ASR #1" },
  { url: "https://www.youtube.com/shorts/xowmZ9xLYXE", label: "Shorts ASR #2" },
];

for (const video of SHORTS_VIDEOS) {
  test(`${video.label}: ASR captions → translated subtitles appear`, async ({
    page,
  }) => {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });

    // Accept cookies if banner is present
    const cookieBtn = page.locator("button", { hasText: /accept|accepter/i });
    if (await cookieBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await cookieBtn.click();
    }

    await page.fill("#video-url", video.url);
    await page.selectOption("#target-lang", "fr");
    await page.click("#submit-button");

    const formError = page.locator("#form-error");
    const premiumNotice = page.locator("#premium-notice");

    // Wait for player section (translation complete) — up to 60s
    const playerSection = page.locator("#player-section");
    await expect(playerSection).toBeVisible({ timeout: 60000 });

    // No error shown
    await expect(formError).toBeHidden();
    await expect(premiumNotice).toBeHidden();

    // Subtitle track present
    const subtitleContainer = page.locator("#subtitle-overlay, .subtitle-line, track[kind='subtitles']");
    await expect(subtitleContainer.first()).toBeAttached({ timeout: 5000 });

    // Detected language populated
    const detectedLang = page.locator("#detected-language");
    await expect(detectedLang).not.toHaveText("-", { timeout: 5000 });
  });
}
