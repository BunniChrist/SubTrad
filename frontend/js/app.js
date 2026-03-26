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
    const resetButton = $("reset-button");

    let activePlayer = null;

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
      window.AdManager.destroyAll();
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
      window.AdManager.hideInterstitial();
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
      window.AdManager.hideInterstitial();
      premiumNotice.classList.remove("hidden");
      form.classList.remove("hidden");
    }

    function startPreroll() {
      return new Promise(function (resolve) {
        window.AdManager.showPreroll(resolve);
      });
    }

    function bindPlayerAds(player) {
      player.onPause(function () {
        window.AdManager.showPauseAd();
      });

      player.onPlay(function () {
        window.AdManager.hidePauseAd();
      });
    }

    async function handleSuccessfulTranslation(responseData) {
      setLoading(false);
      window.AdManager.hideInterstitial();
      clearError();
      renderMetadata(responseData);
      playerSection.classList.remove("hidden");
      await startPreroll();
      activePlayer = await window.SubTradPlayer.initPlayer(
        responseData.platform,
        responseData.video_id,
        playerContainer
      );
      bindPlayerAds(activePlayer);
      window.AdManager.initBanners();
      window.AdManager.hidePauseAd();
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

      window.AdManager.showInterstitial();
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
        window.AdManager.hideInterstitial();

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

    resetPlayerState();
  });
})();
