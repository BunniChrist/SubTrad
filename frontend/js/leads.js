(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function setFeedback(element, message, tone) {
    if (!element) {
      return;
    }

    element.textContent = message;
    element.classList.remove("hidden", "error", "success");

    if (tone === "error") {
      element.classList.add("error");
      return;
    }

    element.classList.add("success");
  }

  function updatePremiumCounter(totalSignups) {
    const countElement = $("premium-signup-count");
    const progressElement = $("premium-progress-bar");

    if (!countElement || !progressElement) {
      return;
    }

    const safeCount = Math.max(0, Number(totalSignups) || 0);
    const progress = Math.min((safeCount / 200) * 100, 100);

    countElement.textContent = String(safeCount);
    progressElement.style.width = progress + "%";
  }

  async function submitLead(payload) {
    let response;

    try {
      response = await fetch("/api/leads", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      throw new Error("Network error. Please try again.");
    }

    const responseBody = await response.json();

    if (!response.ok) {
      if (response.status === 422) {
        throw new Error("Please provide a valid email and form details.");
      }

      throw new Error("Server error. Please try again in a moment.");
    }

    return responseBody;
  }

  async function loadPremiumCount() {
    const countElement = $("premium-signup-count");
    if (!countElement) {
      return;
    }

    try {
      const response = await fetch("/api/leads/count?type=premium");
      if (!response.ok) {
        return;
      }

      const payload = await response.json();
      updatePremiumCounter(payload.count);
    } catch (error) {
      // Ignore count refresh failures and keep the page usable.
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("[data-lead-form]");
    if (!form) {
      return;
    }

    const feedback = $("lead-feedback");
    const submitButton = $("lead-submit");
    const type = form.dataset.leadType;

    loadPremiumCount();

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      const emailInput = $("lead-email");
      const messageInput = $("lead-message");
      const email = emailInput ? emailInput.value.trim() : "";
      const message = messageInput ? messageInput.value.trim() : "";

      if (!email) {
        setFeedback(feedback, "Please enter your email address.", "error");
        return;
      }

      if (type === "suggestion" && !message) {
        setFeedback(feedback, "Please share a suggestion before sending.", "error");
        return;
      }

      submitButton.disabled = true;
      setFeedback(feedback, "Submitting...", "success");

      try {
        const payload = {
          email: email,
          type: type,
        };

        if (message) {
          payload.message = message;
        }

        const responseBody = await submitLead(payload);
        updatePremiumCounter(responseBody.total_signups);

        if (responseBody.status === "already_registered") {
          setFeedback(
            feedback,
            type === "premium"
              ? "This email is already registered for Premium."
              : "This email already sent a suggestion.",
            "success"
          );
          return;
        }

        setFeedback(
          feedback,
          type === "premium"
            ? "Your spot is reserved. We'll contact you when Premium launches."
            : "Suggestion sent. Thanks for helping improve SubTrad.",
          "success"
        );
        form.reset();
      } catch (error) {
        setFeedback(
          feedback,
          error && error.message ? error.message : "Something went wrong.",
          "error"
        );
      } finally {
        submitButton.disabled = false;
      }
    });
  });
})();
