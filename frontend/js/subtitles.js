(function () {
  let animationFrameId = 0;
  let currentText = "";

  function toSeconds(value) {
    if (typeof value === "number") {
      return value;
    }

    const normalized = String(value).replace(",", ".");
    if (!normalized.includes(":")) {
      return Number(normalized);
    }

    const parts = normalized.split(":").map(Number);
    if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }

    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }

    return Number(normalized) || 0;
  }

  function destroySubtitles(overlayElement) {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = 0;
    }

    currentText = "";
    if (overlayElement) {
      overlayElement.textContent = "";
      overlayElement.classList.remove("visible");
    }
  }

  function initSubtitles(subtitles, playerInterface, overlayElement) {
    destroySubtitles(overlayElement);

    const preparedSubtitles = subtitles.map(function (segment) {
      return {
        start: toSeconds(segment.start),
        end: toSeconds(segment.end),
        text: segment.text,
      };
    });

    function tick() {
      const currentTime = playerInterface.getCurrentTime();
      const activeSubtitle = preparedSubtitles.find(function (segment) {
        return currentTime >= segment.start && currentTime <= segment.end;
      });
      const nextText = activeSubtitle ? activeSubtitle.text : "";

      if (nextText !== currentText) {
        currentText = nextText;
        overlayElement.textContent = nextText;
        overlayElement.classList.toggle("visible", nextText.length > 0);
      }

      animationFrameId = requestAnimationFrame(tick);
    }

    animationFrameId = requestAnimationFrame(tick);
  }

  window.SubTradSubtitles = {
    destroySubtitles,
    initSubtitles,
  };
})();
