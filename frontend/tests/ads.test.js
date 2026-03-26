const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  add(...names) {
    names.forEach((name) => this.values.add(name));
  }

  remove(...names) {
    names.forEach((name) => this.values.delete(name));
  }

  contains(name) {
    return this.values.has(name);
  }

  toggle(name, force) {
    if (force === undefined) {
      if (this.values.has(name)) {
        this.values.delete(name);
        return false;
      }

      this.values.add(name);
      return true;
    }

    if (force) {
      this.values.add(name);
      return true;
    }

    this.values.delete(name);
    return false;
  }
}

class FakeElement {
  constructor(id) {
    this.id = id;
    this.classList = new FakeClassList();
    this.textContent = "";
  }
}

function createEnvironment() {
  const ids = [
    "ad-interstitial",
    "ad-preroll",
    "preroll-countdown",
    "ad-banner-left",
    "ad-banner-right",
    "ad-banner-bottom",
    "ad-pause-overlay",
  ];
  const elements = new Map(ids.map((id) => [id, new FakeElement(id)]));
  const timers = new Map();
  let timerId = 1;

  const document = {
    readyState: "complete",
    addEventListener() {},
    getElementById(id) {
      return elements.get(id) || null;
    },
  };

  const sandbox = {
    window: {},
    document,
    console,
    setInterval(callback) {
      const currentId = timerId++;
      timers.set(currentId, callback);
      return currentId;
    },
    clearInterval(id) {
      timers.delete(id);
    },
  };

  sandbox.window = sandbox;

  return {
    elements,
    sandbox,
    tick(count = 1) {
      for (let index = 0; index < count; index += 1) {
        Array.from(timers.values()).forEach((callback) => callback());
      }
    },
  };
}

function loadAdManager(environment) {
  const adsPath = path.resolve(__dirname, "..", "js", "ads.js");
  const source = fs.readFileSync(adsPath, "utf8");
  vm.runInNewContext(source, environment.sandbox, { filename: adsPath });
  return environment.sandbox.window.AdManager;
}

test("showInterstitial and hideInterstitial toggle the loading ad", () => {
  const environment = createEnvironment();
  const adManager = loadAdManager(environment);

  adManager.showInterstitial();
  assert.equal(
    environment.elements.get("ad-interstitial").classList.contains("hidden"),
    false
  );

  adManager.hideInterstitial();
  assert.equal(
    environment.elements.get("ad-interstitial").classList.contains("hidden"),
    true
  );
});

test("showPreroll counts down and calls onComplete", () => {
  const environment = createEnvironment();
  const adManager = loadAdManager(environment);
  let completed = 0;

  adManager.showPreroll(() => {
    completed += 1;
  });

  assert.equal(
    environment.elements.get("ad-preroll").classList.contains("hidden"),
    false
  );
  assert.equal(environment.elements.get("preroll-countdown").textContent, "5");

  environment.tick(5);

  assert.equal(completed, 1);
  assert.equal(
    environment.elements.get("ad-preroll").classList.contains("hidden"),
    true
  );
  assert.equal(environment.elements.get("preroll-countdown").textContent, "0");
});

test("pause overlay toggles with play state", () => {
  const environment = createEnvironment();
  const adManager = loadAdManager(environment);

  adManager.showPauseAd();
  assert.equal(
    environment.elements.get("ad-pause-overlay").classList.contains("hidden"),
    false
  );

  adManager.hidePauseAd();
  assert.equal(
    environment.elements.get("ad-pause-overlay").classList.contains("hidden"),
    true
  );
});

test("initBanners reveals desktop and mobile banner placeholders", () => {
  const environment = createEnvironment();
  const adManager = loadAdManager(environment);

  adManager.initBanners();

  assert.equal(
    environment.elements.get("ad-banner-left").classList.contains("hidden"),
    false
  );
  assert.equal(
    environment.elements.get("ad-banner-right").classList.contains("hidden"),
    false
  );
  assert.equal(
    environment.elements.get("ad-banner-bottom").classList.contains("hidden"),
    false
  );
});

test("destroyAll clears every ad surface and timer state", () => {
  const environment = createEnvironment();
  const adManager = loadAdManager(environment);

  adManager.showInterstitial();
  adManager.showPauseAd();
  adManager.initBanners();
  adManager.showPreroll(() => {});
  adManager.destroyAll();

  [
    "ad-interstitial",
    "ad-preroll",
    "ad-banner-left",
    "ad-banner-right",
    "ad-banner-bottom",
    "ad-pause-overlay",
  ].forEach((id) => {
    assert.equal(environment.elements.get(id).classList.contains("hidden"), true);
  });
  assert.equal(environment.elements.get("preroll-countdown").textContent, "5");
});
