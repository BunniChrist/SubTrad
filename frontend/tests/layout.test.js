const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const stylesheetPath = path.resolve(__dirname, "..", "css", "style.css");
const stylesheet = fs.readFileSync(stylesheetPath, "utf8");

function getDesktopMediaBlock(source) {
  const marker = "@media (min-width: 1024px) {";
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, "desktop media query should exist");

  let depth = 0;
  let end = -1;
  for (let index = start; index < source.length; index += 1) {
    const character = source[index];
    if (character === "{") {
      depth += 1;
    } else if (character === "}") {
      depth -= 1;
      if (depth === 0) {
        end = index + 1;
        break;
      }
    }
  }

  assert.notEqual(end, -1, "desktop media query should close");
  return source.slice(start, end);
}

test("desktop grid assigns the app shell and banner columns explicitly", () => {
  const desktopBlock = getDesktopMediaBlock(stylesheet);

  assert.match(
    desktopBlock,
    /\.app-shell\s*\{[^}]*grid-column:\s*2\s*;/s,
    "app-shell should stay in the center column on desktop"
  );
  assert.match(
    desktopBlock,
    /\.ad-banner-left\s*\{[^}]*grid-column:\s*1\s*;/s,
    "left banner should stay in the first column on desktop"
  );
  assert.match(
    desktopBlock,
    /\.ad-banner-right\s*\{[^}]*grid-column:\s*3\s*;/s,
    "right banner should stay in the third column on desktop"
  );
});
