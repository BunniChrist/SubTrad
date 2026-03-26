(function () {
  function $(id) {
    return document.getElementById(id);
  }

  const languageNames = {
    en: "English",
    es: "Spanish",
    fr: "French",
    ja: "Japanese",
  };

  document.addEventListener("DOMContentLoaded", function () {
    const form = $("translate-form");
    const urlInput = $("video-url");
    const languageSelect = $("target-lang");
    const errorElement = $("form-error");
    const loadingSection = $("loading-section");
    const premiumNotice = $("premium-notice");
    const playerSection = $("player-section");
    const metadata = $("player-metadata");
    const detectedLanguage = $("detected-language");
    const translationStatus = $("translation-status");
    const playerContainer = $("player-container");
    const subtitleOverlay = $("subtitle-overlay");
    const prerollOverlay = $("preroll-overlay");
    const prerollCountdown = $("preroll-countdown");
    const resetButton = $("reset-button");
    const adElements = document.querySelectorAll(".ad-slot, .ad-interstitial");

    let activePlayer = null;
    let prerollTimer = 0;

    function adsAllowed() {
      return window.subtradAdsAllowed === true;
    }

    function syncAdsVisibility() {
      adElements.forEach(function (element) {
        element.classList.toggle("hidden", !adsAllowed());
      });
    }

    function clearError() {
      errorElement.textContent = "";
      errorElement.classList.add("hidden");
    }

    function showError(message) {
      errorElement.textContent = message;
      errorElement.classList.remove("hidden");
    }

    function setLoading(isLoading) {
      loadingSection.classList.toggle("hidden", !isLoading);
      form.classList.toggle("hidden", isLoading);
      if (isLoading) {
        premiumNotice.classList.add("hidden");
      }
    }

    function resetPlayerState() {
      if (prerollTimer) {
        clearInterval(prerollTimer);
        prerollTimer = 0;
      }

      prerollOverlay.classList.add("hidden");
      window.SubTradSubtitles.destroySubtitles(subtitleOverlay);

      if (activePlayer) {
        activePlayer.destroy();
        activePlayer = null;
      }

      playerContainer.innerHTML =
        '<div class="player-placeholder">Player ready when subtitles are generated.</div>';
      metadata.classList.add("hidden");
      playerSection.classList.add("hidden");
    }

    function resetUi() {
      clearError();
      setLoading(false);
      premiumNotice.classList.add("hidden");
      form.classList.remove("hidden");
      resetPlayerState();
      urlInput.focus();
    }

    function renderMetadata(responseData) {
      const languageCode = responseData.detected_language || "";
      detectedLanguage.textContent =
        languageNames[languageCode] || languageCode || "Unknown";
      translationStatus.textContent = responseData.translation_status;
      metadata.classList.remove("hidden");
    }

    function showPremiumNotice() {
      setLoading(false);
      premiumNotice.classList.remove("hidden");
      form.classList.remove("hidden");
    }

    function startPreroll() {
      if (!adsAllowed()) {
        prerollOverlay.classList.add("hidden");
        return Promise.resolve();
      }

      return new Promise(function (resolve) {
        let remaining = 5;
        prerollCountdown.textContent = String(remaining);
        prerollOverlay.classList.remove("hidden");

        prerollTimer = window.setInterval(function () {
          remaining -= 1;
          prerollCountdown.textContent = String(Math.max(remaining, 0));

          if (remaining <= 0) {
            clearInterval(prerollTimer);
            prerollTimer = 0;
            prerollOverlay.classList.add("hidden");
            resolve();
          }
        }, 1000);
      });
    }

    async function handleSuccessfulTranslation(responseData) {
      setLoading(false);
      clearError();
      renderMetadata(responseData);
      playerSection.classList.remove("hidden");
      await startPreroll();
      activePlayer = await window.SubTradPlayer.initPlayer(
        responseData.platform,
        responseData.video_id,
        playerContainer
      );
      window.SubTradSubtitles.initSubtitles(
        responseData.subtitles || [],
        activePlayer,
        subtitleOverlay
      );
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearError();
      premiumNotice.classList.add("hidden");
      resetPlayerState();

      const url = urlInput.value.trim();
      const targetLang = languageSelect.value;

      if (!url) {
        showError("Please paste a video URL.");
        return;
      }

      if (!targetLang) {
        showError("Please choose a language.");
        return;
      }

      setLoading(true);

      try {
        const responseData = await window.SubTradApi.translateVideo(url, targetLang);

        if (responseData.duration_seconds > 720 || responseData.redirect === "premium") {
          showPremiumNotice();
          return;
        }

        await handleSuccessfulTranslation(responseData);
      } catch (error) {
        setLoading(false);

        if (error && error.status === 403) {
          showPremiumNotice();
          return;
        }

        showError(error.message || "Something went wrong.");
        form.classList.remove("hidden");
      }
    });

    resetButton.addEventListener("click", function () {
      resetUi();
    });

    document.addEventListener("subtrad:cookie-consent-changed", function () {
      syncAdsVisibility();
    });

    syncAdsVisibility();
    resetPlayerState();
  });
})();
