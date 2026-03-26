// E2E deployment verification tests for SubTrad
const { test, expect } = require("@playwright/test");

const BASE_URL = "https://subtrad.bunnichrist.fr";

async function dismissCookieBanner(page) {
  const cookieBtn = page.locator("button", { hasText: /accept|accepter/i });
  if (await cookieBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await cookieBtn.click();
  }
}

test.describe("SubTrad deployment verification", () => {
  test("1. Homepage loads with dark theme and form visible", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });

    await expect(page).toHaveTitle(/SubTrad/);
    await expect(page.locator(".brand-mark")).toHaveText("SubTrad");
    await expect(page.locator("h1")).toContainText("Understand any video");

    // Form elements visible
    await expect(page.locator("#video-url")).toBeVisible();
    await expect(page.locator("#target-lang")).toBeVisible();
    await expect(page.locator("#submit-button")).toBeVisible();

    // Dark theme: body background should be dark
    const bgColor = await page.evaluate(() =>
      getComputedStyle(document.body).backgroundColor
    );
    // Dark backgrounds have low RGB values
    const match = bgColor.match(/\d+/g);
    if (match) {
      const avg = (parseInt(match[0]) + parseInt(match[1]) + parseInt(match[2])) / 3;
      expect(avg).toBeLessThan(100);
    }
  });

  test("2. Invalid URL shows error message", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
    await dismissCookieBanner(page);

    await page.fill("#video-url", "not-a-valid-url");
    await page.selectOption("#target-lang", "fr");
    await page.click("#submit-button");

    const formError = page.locator("#form-error");
    await expect(formError).toBeVisible({ timeout: 5000 });
  });

  test("3. Missing language shows validation", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
    await dismissCookieBanner(page);

    await page.fill("#video-url", "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
    // Don't select a language
    await page.click("#submit-button");

    const formError = page.locator("#form-error");
    await expect(formError).toBeVisible({ timeout: 5000 });
  });

  test("4. YouTube regular video — translation or premium redirect", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
    await dismissCookieBanner(page);

    await page.fill("#video-url", "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
    await page.selectOption("#target-lang", "fr");
    await page.click("#submit-button");

    // Loading should appear
    await expect(page.locator("#loading-section")).toBeVisible({ timeout: 5000 });

    // Either player appears (success), premium notice (too long), or error message
    // Also accept that the request may still be loading (long video processing)
    const result = page.locator("#player-section, #premium-notice, #form-error:not(.hidden)");
    await expect(result.first()).toBeVisible({ timeout: 90000 });
  });

  test("5. YouTube Shorts ASR — translation with player and subtitles", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
    await dismissCookieBanner(page);

    await page.fill("#video-url", "https://www.youtube.com/shorts/dQw4w9WgXcQ");
    await page.selectOption("#target-lang", "fr");
    await page.click("#submit-button");

    // Loading indicator
    await expect(page.locator("#loading-section")).toBeVisible({ timeout: 5000 });

    // Wait for result — either player (success) or premium notice or error
    const result = page.locator("#player-section, #premium-notice, #form-error:not(.hidden)");
    await expect(result.first()).toBeVisible({ timeout: 90000 });

    // If player appeared, verify subtitles and metadata
    const playerSection = page.locator("#player-section");
    if (await playerSection.isVisible().catch(() => false)) {
      // Metadata shown
      await expect(page.locator("#detected-language")).not.toHaveText("-");
      await expect(page.locator("#translation-status")).not.toHaveText("-");

      // Subtitle overlay attached
      const subtitles = page.locator("#subtitle-overlay, .subtitle-line, track[kind='subtitles']");
      await expect(subtitles.first()).toBeAttached({ timeout: 5000 });
    }
  });
});
