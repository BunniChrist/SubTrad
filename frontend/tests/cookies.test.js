const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function createStorage() {
  const store = new Map();

  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
  };
}

function createBanner() {
  const classes = new Set(["hidden"]);

  return {
    classList: {
      add(name) {
        classes.add(name);
      },
      remove(name) {
        classes.delete(name);
      },
      contains(name) {
        return classes.has(name);
      },
      toggle(name, force) {
        if (force === undefined) {
          if (classes.has(name)) {
            classes.delete(name);
          } else {
            classes.add(name);
          }
          return;
        }

        if (force) {
          classes.add(name);
        } else {
          classes.delete(name);
        }
      },
    },
  };
}

function loadCookieConsent() {
  const scriptPath = path.join(__dirname, "..", "js", "cookies.js");
  const source = fs.readFileSync(scriptPath, "utf8");
  const banner = createBanner();
  const storage = createStorage();
  const document = {
    addEventListener() {},
    getElementById(id) {
      return id === "cookie-banner" ? banner : null;
    },
  };
  const window = {
    localStorage: storage,
    subtradAdsAllowed: undefined,
  };

  const context = vm.createContext({
    window,
    document,
    localStorage: storage,
    console,
  });

  vm.runInContext(source, context, { filename: "cookies.js" });

  return { CookieConsent: window.CookieConsent, banner, window, storage };
}

test("CookieConsent is undecided before initialization", function () {
  const { CookieConsent, window } = loadCookieConsent();

  assert.equal(CookieConsent.hasConsent(), null);
  assert.equal(window.subtradAdsAllowed, undefined);
});

test("CookieConsent.accept persists consent, hides banner, and enables ads", function () {
  const { CookieConsent, banner, window, storage } = loadCookieConsent();

  CookieConsent.init();
  CookieConsent.accept();

  assert.equal(storage.getItem("subtrad_cookie_consent"), "accepted");
  assert.equal(CookieConsent.hasConsent(), true);
  assert.equal(window.subtradAdsAllowed, true);
  assert.equal(banner.classList.contains("hidden"), true);
});

test("CookieConsent.reject persists refusal, hides banner, and disables ads", function () {
  const { CookieConsent, banner, window, storage } = loadCookieConsent();

  CookieConsent.init();
  CookieConsent.reject();

  assert.equal(storage.getItem("subtrad_cookie_consent"), "rejected");
  assert.equal(CookieConsent.hasConsent(), false);
  assert.equal(window.subtradAdsAllowed, false);
  assert.equal(banner.classList.contains("hidden"), true);
});

test("CookieConsent.reset clears state and shows the banner again", function () {
  const { CookieConsent, banner, window, storage } = loadCookieConsent();

  CookieConsent.init();
  CookieConsent.accept();
  CookieConsent.reset();

  assert.equal(storage.getItem("subtrad_cookie_consent"), null);
  assert.equal(CookieConsent.hasConsent(), null);
  assert.equal(window.subtradAdsAllowed, false);
  assert.equal(banner.classList.contains("hidden"), false);
});
