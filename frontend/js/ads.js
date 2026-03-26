(function () {
  let prerollTimer = 0;

  function getElement(id) {
    return document.getElementById(id);
  }

  function setHidden(element, hidden) {
    if (!element) {
      return;
    }

    element.classList.toggle("hidden", hidden);
    element.classList.toggle("is-visible", !hidden);
  }

  function clearPrerollTimer() {
    if (!prerollTimer) {
      return;
    }

    clearInterval(prerollTimer);
    prerollTimer = 0;
  }

  const AdManager = {
    showInterstitial() {
      setHidden(getElement("ad-interstitial"), false);
    },

    hideInterstitial() {
      setHidden(getElement("ad-interstitial"), true);
    },

    showPreroll(onComplete) {
      const preroll = getElement("ad-preroll");
      const countdown = getElement("preroll-countdown");
      let remaining = 5;

      clearPrerollTimer();
      if (countdown) {
        countdown.textContent = String(remaining);
      }
      setHidden(preroll, false);

      prerollTimer = setInterval(function () {
        remaining -= 1;

        if (countdown) {
          countdown.textContent = String(Math.max(remaining, 0));
        }

        if (remaining > 0) {
          return;
        }

        clearPrerollTimer();
        setHidden(preroll, true);
        if (typeof onComplete === "function") {
          onComplete();
        }
      }, 1000);
    },

    showPauseAd() {
      setHidden(getElement("ad-pause-overlay"), false);
    },

    hidePauseAd() {
      setHidden(getElement("ad-pause-overlay"), true);
    },

    initBanners() {
      ["ad-banner-left", "ad-banner-right", "ad-banner-bottom"].forEach(function (id) {
        setHidden(getElement(id), false);
      });
    },

    destroyAll() {
      clearPrerollTimer();
      const countdown = getElement("preroll-countdown");

      if (countdown) {
        countdown.textContent = "5";
      }

      [
        "ad-interstitial",
        "ad-preroll",
        "ad-banner-left",
        "ad-banner-right",
        "ad-banner-bottom",
        "ad-pause-overlay",
      ].forEach(function (id) {
        setHidden(getElement(id), true);
      });
    },
  };

  // To activate Google AdSense:
  // 1. Replace placeholder divs with <ins class="adsbygoogle" ...> elements.
  // 2. Add the AdSense script to index.html with your ca-pub client id.
  // 3. Call (adsbygoogle = window.adsbygoogle || []).push({}) after each slot render.

  window.AdManager = AdManager;
})();
