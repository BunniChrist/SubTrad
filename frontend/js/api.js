(function () {
  class ApiError extends Error {
    constructor(message, options) {
      super(message);
      this.name = "ApiError";
      this.status = options.status;
      this.code = options.code || null;
      this.payload = options.payload || null;
    }
  }

  async function translateVideo(url, targetLang) {
    let response;

    try {
      response = await fetch("/api/translate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url,
          target_lang: targetLang,
        }),
      });
    } catch (error) {
      throw new ApiError("Network error. Please try again.", {
        status: 0,
        code: "network_error",
      });
    }

    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      if (!response.ok) {
        throw new ApiError("Unexpected server response.", {
          status: response.status,
          code: "invalid_json",
        });
      }
    }

    if (!response.ok) {
      let message = "Something went wrong.";
      if (response.status >= 500) {
        message = "Server error. Please try again in a moment.";
      } else if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }

      throw new ApiError(message, {
        status: response.status,
        code: payload && payload.redirect ? payload.redirect : null,
        payload,
      });
    }

    return payload;
  }

  window.SubTradApi = {
    ApiError,
    translateVideo,
  };
})();
