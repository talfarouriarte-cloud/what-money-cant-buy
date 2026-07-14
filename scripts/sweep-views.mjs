// scripts/sweep-views.mjs
// Behavioral jsdom sweep — DoD §2 of issue #50, generalized repro of the #43
// crash series. For each view it boots the real app offline (CDN bundles
// inlined) at #tab=<view>&lg=pl&sel=Liverpool, then drives an in-app league
// change and a change to the oldest season, asserting throughout: zero JS
// errors (console.error / uncaught / unhandledrejection) and #root populated.
// A layout change that reintroduces any of the series crashes fails here.
//
// This repo has no committed test infra (ADR-003), so install the runtime deps
// out-of-tree and point the script at them:
//
//   mkdir -p /tmp/fbm-sweep && cd /tmp/fbm-sweep && npm init -y >/dev/null
//   npm i jsdom react@18.2.0 react-dom@18.2.0 prop-types@15.8.1 recharts@2.12.7
//   FBM_DEPS=/tmp/fbm-sweep/node_modules \
//     node /path/to/repo/scripts/sweep-views.mjs /path/to/repo
//
// Exit 0 = all views green.
import fs from "fs";
import path from "path";
import { createRequire } from "module";

const REPO = process.argv[2] || process.cwd();
const DEPS = process.env.FBM_DEPS || path.join(REPO, "node_modules");
const req = createRequire(path.join(DEPS, "index.js"));
const { JSDOM, VirtualConsole } = req("jsdom");

const read = (p) => fs.readFileSync(path.join(REPO, p), "utf8");
const readDep = (rel) => fs.readFileSync(path.join(DEPS, rel), "utf8");

const umd = {
  react: readDep("react/umd/react.production.min.js"),
  reactDom: readDep("react-dom/umd/react-dom.production.min.js"),
  propTypes: readDep("prop-types/prop-types.min.js"),
  recharts: readDep("recharts/umd/Recharts.js"),
};

let html = read("index.html");
// Inline the four external bundles. Function replacers keep `$` sequences
// inside the minified code ($$typeof, $&, ...) literal.
html = html
  .replace(/<script src="https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/react\/[^"]+"><\/script>/, () => `<script>${umd.react}</script>`)
  .replace(/<script src="https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/react-dom\/[^"]+"><\/script>/, () => `<script>${umd.reactDom}</script>`)
  .replace(/<script src="https:\/\/cdn\.jsdelivr\.net\/npm\/prop-types[^"]+"><\/script>/, () => `<script>${umd.propTypes}</script>`)
  .replace(/<script src="https:\/\/cdn\.jsdelivr\.net\/npm\/recharts[^"]+"><\/script>/, () => `<script>${umd.recharts}</script>`);

const files = {};
for (const f of ["data.json", "i18n.json", "crests.json", "fixtures.json"]) {
  try { files[f] = read(f); } catch (e) {}
}
const localFor = (url) => {
  const u = String(url);
  for (const name of Object.keys(files)) if (u.endsWith(name)) return files[name];
  return null;
};

const VIEWS = ["home", "tracker", "matches", "predictions", "badrun", "h2h", "overperformance", "history", "calc", "data", "method"];
const D = JSON.parse(files["data.json"]);
const OLDEST_PL = Object.keys((D.seasons && D.seasons.pl) || {}).sort()[0];
const ALT_LEAGUE = Object.keys(D.seasons || {}).find((k) => k !== "pl") || "pl";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function boot(hash) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push("jsdomError: " + (e.detail || e.message || e)));
  vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));
  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    pretendToBeVisual: true,
    url: "https://footballbeyondmoney.uk/" + hash,
    virtualConsole: vc,
    beforeParse(window) {
      window.matchMedia = () => ({ matches: false, media: "", addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent() { return false; } });
      window.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
      window.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } };
      window.scrollTo = () => {};
      window.HTMLElement.prototype.scrollIntoView = () => {};
      window.fetch = (url) => {
        const body = localFor(url);
        if (body == null) return Promise.resolve({ ok: false, status: 404, json: () => Promise.reject(new Error("404")), text: () => Promise.resolve(""), clone() { return this; } });
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(JSON.parse(body)), text: () => Promise.resolve(body), clone() { return this; } });
      };
      window.onerror = (msg) => errors.push("window.onerror: " + msg);
      window.addEventListener("unhandledrejection", (e) => errors.push("unhandledrejection: " + (e.reason && e.reason.message || e.reason)));
    },
  });
  const win = dom.window;
  const root = win.document.getElementById("root");
  for (let i = 0; i < 200; i++) {
    if (win.document.querySelectorAll("header.head select").length >= 3) break;
    await sleep(50);
  }
  return { win, root, errors };
}
const setSelect = (win, el, value) => { el.value = value; el.dispatchEvent(new win.Event("change", { bubbles: true })); };

async function testView(view) {
  const out = { view, ok: true, notes: [] };
  const { win, root, errors } = await boot(`#tab=${view}&lg=pl&sel=Liverpool&lang=en`);
  if (root.childElementCount === 0) { out.ok = false; out.notes.push("boot: #root empty"); }
  const headerSelects = () => Array.from(win.document.querySelectorAll("header.head select"));
  let hs = headerSelects();
  if (hs.length >= 1 && ALT_LEAGUE !== "pl") {
    setSelect(win, hs[0], ALT_LEAGUE); await sleep(200);
    if (root.childElementCount === 0) { out.ok = false; out.notes.push("league-change: #root empty"); }
  } else out.notes.push("league select not found (n=" + hs.length + ")");
  hs = headerSelects();
  if (hs.length >= 1) { setSelect(win, hs[0], "pl"); await sleep(150); }
  hs = headerSelects();
  if (hs.length >= 3 && OLDEST_PL) {
    setSelect(win, hs[2], OLDEST_PL); await sleep(200);
    if (root.childElementCount === 0) { out.ok = false; out.notes.push("season-change: #root empty"); }
  } else out.notes.push("season select not found (n=" + hs.length + ")");
  if (errors.length) { out.ok = false; out.notes.push(...errors.map((e) => "JS: " + e)); }
  return out;
}

const results = [];
for (const v of VIEWS) {
  try { results.push(await testView(v)); }
  catch (e) { results.push({ view: v, ok: false, notes: ["harness threw: " + e.message] }); }
}
let failed = 0;
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.view}${r.notes.length ? "  — " + r.notes.join(" | ") : ""}`);
  if (!r.ok) failed++;
}
console.log(`\nSweep: ${results.length - failed}/${results.length} views passed  (altLeague=${ALT_LEAGUE}, oldestPL=${OLDEST_PL})`);
process.exit(failed ? 1 : 0);
