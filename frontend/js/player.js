(function () {
  let youtubeApiPromise = null;

  function ensureYouTubeApi() {
    if (window.YT && window.YT.Player) {
      return Promise.resolve(window.YT);
    }

    if (youtubeApiPromise) {
      return youtubeApiPromise;
    }

    youtubeApiPromise = new Promise((resolve) => {
      const existingScript = document.querySelector(
        'script[data-subtrad-youtube-api="true"]'
      );

      if (!existingScript) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        script.async = true;
        script.dataset.subtradYoutubeApi = "true";
        document.head.appendChild(script);
      }

      const previousReady = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = function onYouTubeIframeAPIReady() {
        if (typeof previousReady === "function") {
          previousReady();
        }
        resolve(window.YT);
      };
    });

    return youtubeApiPromise;
  }

  function createEstimatedPlayer(iframe) {
    const playCallbacks = [];
    const pauseCallbacks = [];
    let running = false;
    let elapsedSeconds = 0;
    let startedAt = 0;

    function getCurrentTime() {
      if (!running) {
        return elapsedSeconds;
      }

      return elapsedSeconds + (Date.now() - startedAt) / 1000;
    }

    function setPlaying(nextState) {
      if (nextState === running) {
        return;
      }

      if (nextState) {
        startedAt = Date.now();
        running = true;
        playCallbacks.forEach((callback) => callback());
        return;
      }

      elapsedSeconds = getCurrentTime();
      running = false;
      pauseCallbacks.forEach((callback) => callback());
    }

    iframe.addEventListener("load", function () {
      setPlaying(true);
    });

    return {
      getCurrentTime,
      onPlay(callback) {
        playCallbacks.push(callback);
      },
      onPause(callback) {
        pauseCallbacks.push(callback);
      },
      destroy() {
        setPlaying(false);
        iframe.remove();
      },
    };
  }

  async function initYouTubePlayer(videoId, containerElement) {
    const YT = await ensureYouTubeApi();
    const target = document.createElement("div");
    const playerId = "subtrad-youtube-player";
    target.id = playerId;
    containerElement.replaceChildren(target);

    return await new Promise((resolve) => {
      const playCallbacks = [];
      const pauseCallbacks = [];
      const player = new YT.Player(playerId, {
        videoId,
        playerVars: {
          playsinline: 1,
          rel: 0,
        },
        events: {
          onStateChange(event) {
            if (event.data === YT.PlayerState.PLAYING) {
              playCallbacks.forEach((callback) => callback());
            }
            if (
              event.data === YT.PlayerState.PAUSED ||
              event.data === YT.PlayerState.ENDED
            ) {
              pauseCallbacks.forEach((callback) => callback());
            }
          },
          onReady() {
            resolve({
              getCurrentTime() {
                return Number(player.getCurrentTime() || 0);
              },
              onPlay(callback) {
                playCallbacks.push(callback);
              },
              onPause(callback) {
                pauseCallbacks.push(callback);
              },
              destroy() {
                player.destroy();
              },
            });
          },
        },
      });
    });
  }

  function createIframe(src, title, containerElement) {
    const iframe = document.createElement("iframe");
    iframe.src = src;
    iframe.title = title;
    iframe.allow =
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.allowFullscreen = true;
    iframe.loading = "lazy";
    containerElement.replaceChildren(iframe);
    return iframe;
  }

  async function initPlayer(platform, videoId, containerElement) {
    if (platform === "youtube") {
      return initYouTubePlayer(videoId, containerElement);
    }

    if (platform === "instagram") {
      const iframe = createIframe(
        "https://www.instagram.com/p/" + encodeURIComponent(videoId) + "/embed/",
        "Instagram player",
        containerElement
      );
      return createEstimatedPlayer(iframe);
    }

    if (platform === "tiktok") {
      const iframe = createIframe(
        "https://www.tiktok.com/embed/v2/" + encodeURIComponent(videoId),
        "TikTok player",
        containerElement
      );
      return createEstimatedPlayer(iframe);
    }

    throw new Error("Unsupported platform");
  }

  window.SubTradPlayer = {
    initPlayer,
  };
})();
