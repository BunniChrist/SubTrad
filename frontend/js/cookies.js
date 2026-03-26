(function () {
  const STORAGE_KEY = "subtrad_cookie_consent";
  const EVENT_NAME = "subtrad:cookie-consent-changed";

  function getBanner() {
    return document.getElementById("cookie-banner");
  }

  function getManageLinks() {
    if (typeof document.querySelectorAll !== "function") {
      return [];
    }

    return document.querySelectorAll("[data-manage-cookies]");
  }

  function showBanner() {
    const banner = getBanner();

    if (banner) {
      banner.classList.remove("hidden");
    }
  }

  function hideBanner() {
    const banner = getBanner();

    if (banner) {
      banner.classList.add("hidden");
    }
  }

  function readDecision() {
    const value = window.localStorage.getItem(STORAGE_KEY);

    if (value === "accepted") {
      return true;
    }

    if (value === "rejected") {
      return false;
    }

    return null;
  }

  function applyDecision(decision) {
    if (decision === null) {
      window.subtradAdsAllowed = false;
      showBanner();
    } else {
      window.subtradAdsAllowed = decision;
      hideBanner();
    }

    if (typeof document.dispatchEvent === "function") {
      let event;

      if (typeof CustomEvent === "function") {
        event = new CustomEvent(EVENT_NAME, {
          detail: { allowed: window.subtradAdsAllowed, decided: decision !== null },
        });
      } else {
        event = { type: EVENT_NAME };
      }

      document.dispatchEvent(event);
    }
  }

  function bindActions() {
    const banner = getBanner();

    if (banner) {
      const acceptButton =
        typeof banner.querySelector === "function"
          ? banner.querySelector("[data-cookie-action='accept']")
          : null;
      const rejectButton =
        typeof banner.querySelector === "function"
          ? banner.querySelector("[data-cookie-action='reject']")
          : null;

      if (acceptButton && !acceptButton.dataset.cookieBound) {
        acceptButton.dataset.cookieBound = "true";
        acceptButton.addEventListener("click", function () {
          window.CookieConsent.accept();
        });
      }

      if (rejectButton && !rejectButton.dataset.cookieBound) {
        rejectButton.dataset.cookieBound = "true";
        rejectButton.addEventListener("click", function () {
          window.CookieConsent.reject();
        });
      }
    }

    getManageLinks().forEach(function (link) {
      if (link.dataset.cookieBound) {
        return;
      }

      link.dataset.cookieBound = "true";
      link.addEventListener("click", function (event) {
        event.preventDefault();
        window.CookieConsent.reset();
      });
    });
  }

  window.CookieConsent = {
    init() {
      bindActions();
      applyDecision(this.hasConsent());
    },

    accept() {
      window.localStorage.setItem(STORAGE_KEY, "accepted");
      applyDecision(true);
    },

    reject() {
      window.localStorage.setItem(STORAGE_KEY, "rejected");
      applyDecision(false);
    },

    hasConsent() {
      return readDecision();
    },

    reset() {
      window.localStorage.removeItem(STORAGE_KEY);
      applyDecision(null);
    },
  };

  document.addEventListener("DOMContentLoaded", function () {
    window.CookieConsent.init();
  });
})();
