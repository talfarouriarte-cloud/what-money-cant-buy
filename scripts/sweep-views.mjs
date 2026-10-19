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
// After the generic sweep, a Trajectories case (#119) boots
// #tab=trajectories&lg=l1&sel=Lyon&tm=diff&tj=20 and checks window.__FBM_TRAJ
// against data.json (J, jmax, one row per Lyon season, diff, capped); a second
// case deep-links a historical L1 team (absent from the latest season).
// Budget projection (#127): a PL team with bands (pts/diff, tj=L and tj=1) and
// L1/PSG at tj=38 (> 34 matchdays of the current season) check the projected
// row (proj) and window.__FBM_TRAJ.chart (projRows/bandRows).
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

const VIEWS = ["home", "tracker", "matches", "predictions", "badrun", "h2h", "overperformance", "trajectories", "history", "calc", "data", "method"];
const D = JSON.parse(files["data.json"]);
const OLDEST_PL = Object.keys((D.seasons && D.seasons.pl) || {}).sort()[0];
const ALT_LEAGUE = Object.keys(D.seasons || {}).find((k) => k !== "pl") || "pl";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const round1 = (v) => Math.round(v * 10) / 10;
// current season = latest season key across leagues (same derivation as the app)
const CUR = Object.values(D.seasons || {}).flatMap((s) => Object.keys(s)).sort().pop();

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
// Trajectories semantics (#119): Lyon / L1 / diff mode / J=20, read from window.__FBM_TRAJ.
async function testTrajectories() {
  const out = { view: "trajectories:l1-lyon-j20", ok: true, notes: [] };
  const fail = (m) => { out.ok = false; out.notes.push(m); };
  const { win, errors } = await boot("#tab=trajectories&lg=l1&sel=Lyon&tm=diff&tj=20&lang=en");
  for (let i = 0; i < 100 && !win.__FBM_TRAJ; i++) await sleep(50);
  const T = win.__FBM_TRAJ;
  if (!T) { fail("window.__FBM_TRAJ missing"); return out; }
  const L1 = (D.seasons && D.seasons.l1) || {};
  const sns = Object.keys(L1).filter((sn) => L1[sn].Lyon).sort();
  if (T.J !== 20) fail("J=" + T.J + " (expected 20)");
  if (T.mode !== "diff") fail("mode=" + T.mode + " (expected diff)");
  const jmax = Math.max(...sns.map((sn) => L1[sn].Lyon.a.length));
  if (T.jmax !== jmax) fail("jmax=" + T.jmax + " (expected " + jmax + ")");
  const got = T.rows.map((r) => r.sn).sort();
  if (got.join(",") !== sns.join(",")) fail("rows " + got.join(",") + " != seasons " + sns.join(","));
  for (const sn of sns) {
    const r = T.rows.find((x) => x.sn === sn);
    if (!r) continue;
    if (r.proj) {
      const B = D.bands.l1.Lyon, P = D.pre.l1.Lyon;
      if (sn !== CUR) fail(sn + ": proj on a non-current season");
      if (r.j !== 20) fail(sn + ": proj j=" + r.j + " (expected 20)");
      if (r.capped !== false) fail(sn + ": proj capped=" + r.capped);
      if (r.pts !== B.p50[19]) fail(sn + ": proj pts=" + r.pts + " (expected " + B.p50[19] + ")");
      if (r.exp !== P.p50[19]) fail(sn + ": proj exp=" + r.exp + " (expected " + P.p50[19] + ")");
      if (r.diff !== round1(r.pts - r.exp)) fail(sn + ": proj diff=" + r.diff);
      continue;
    }
    const { a, e } = L1[sn].Lyon;
    const j = Math.min(20, a.length);
    const diff = Math.round((a[j - 1] - e[j - 1]) * 10) / 10;
    if (r.j !== j) fail(sn + ": j=" + r.j + " (expected " + j + ")");
    if (r.diff !== diff) fail(sn + ": diff=" + r.diff + " (expected " + diff + ")");
    if (r.capped !== (a.length < 20)) fail(sn + ": capped=" + r.capped);
  }
  out.notes.push(sns.length + " seasons, jmax=" + T.jmax + ", capped=" + T.rows.filter((r) => r.capped).map((r) => r.sn).join(","));
  if (errors.length) { out.ok = false; out.notes.push(...errors.map((e) => "JS: " + e)); }
  return out;
}
try { results.push(await testTrajectories()); }
catch (e) { results.push({ view: "trajectories:l1-lyon-j20", ok: false, notes: ["harness threw: " + e.message] }); }
// Historical team deep link (#119 §2: candidates = every team of any season of lg):
// a team absent from the latest L1 season must survive the initial load.
async function testTrajectoriesHistorical() {
  const out = { view: "trajectories:l1-historical", ok: true, notes: [] };
  const L1 = (D.seasons && D.seasons.l1) || {};
  const last = L1[Object.keys(L1).sort().pop()] || {};
  const hist = Object.keys(L1).flatMap((sn) => Object.keys(L1[sn])).filter((t) => !last[t]).sort()[0];
  if (!hist) { out.notes.push("no historical L1 team in data.json, skipped"); return out; }
  const { win, errors } = await boot("#tab=trajectories&lg=l1&sel=" + encodeURIComponent(hist) + "&lang=en");
  for (let i = 0; i < 100 && !win.__FBM_TRAJ; i++) await sleep(50);
  await sleep(200);
  const T = win.__FBM_TRAJ;
  if (!T) { out.ok = false; out.notes.push("window.__FBM_TRAJ missing"); return out; }
  const n = Object.keys(L1).filter((sn) => L1[sn][hist]).length;
  if (T.team !== hist) { out.ok = false; out.notes.push("team=" + T.team + " (expected " + hist + ")"); }
  else if (T.rows.length !== n) { out.ok = false; out.notes.push("rows=" + T.rows.length + " (expected " + n + ")"); }
  out.notes.push(hist + ", " + T.rows.length + " seasons");
  if (errors.length) { out.ok = false; out.notes.push(...errors.map((e) => "JS: " + e)); }
  return out;
}
try { results.push(await testTrajectoriesHistorical()); }
catch (e) { results.push({ view: "trajectories:l1-historical", ok: false, notes: ["harness threw: " + e.message] }); }

// Budget projection (#127). Returns the current-season row and the chart observable.
async function bootTraj(lg, team, tm, tj) {
  const { win, errors } = await boot("#tab=trajectories&lg=" + lg + "&sel=" + encodeURIComponent(team) + "&tm=" + tm + "&tj=" + tj + "&lang=en");
  for (let i = 0; i < 100 && !(win.__FBM_TRAJ && win.__FBM_TRAJ.team === team); i++) await sleep(50);
  return { T: win.__FBM_TRAJ, errors };
}
function checkProjRow(fail, r, B, P, J) {
  const jp = Math.min(J, B.p50.length);
  if (!r) return fail("no current-season row");
  if (r.proj !== true) fail("proj=" + r.proj + " (expected true)");
  if (r.j !== jp) fail("j=" + r.j + " (expected " + jp + ")");
  if (r.capped !== (J > B.p50.length)) fail("capped=" + r.capped);
  if (r.pts !== B.p50[jp - 1]) fail("pts=" + r.pts + " (expected " + B.p50[jp - 1] + ")");
  if (r.exp !== P.p50[jp - 1]) fail("exp=" + r.exp + " (expected " + P.p50[jp - 1] + ")");
  if (r.diff !== round1(r.pts - r.exp)) fail("diff=" + r.diff + " (expected " + round1(r.pts - r.exp) + ")");
}
function checkChart(fail, T, B, np, pts) {
  const L = B.p50.length;
  const ep = pts ? L - Math.max(np - 1, 0) : 0, eb = pts ? L - np : 0;
  if (!T.chart) return fail("__FBM_TRAJ.chart missing");
  if (T.chart.projRows !== ep) fail(T.mode + ": projRows=" + T.chart.projRows + " (expected " + ep + ")");
  if (T.chart.bandRows !== eb) fail(T.mode + ": bandRows=" + T.chart.bandRows + " (expected " + eb + ")");
}
async function testTrajectoriesProjection() {
  const out = { view: "trajectories:pl-projection", ok: true, notes: [] };
  const fail = (m) => { out.ok = false; out.notes.push(m); };
  const PL = D.seasons.pl || {};
  const team = Object.keys((D.bands && D.bands.pl) || {}).filter((t) => PL[CUR] && PL[CUR][t] && D.pre.pl && D.pre.pl[t]).sort()[0];
  if (!team) { out.notes.push("no PL team with bands, skipped"); return out; }
  const B = D.bands.pl[team], P = D.pre.pl[team], L = B.p50.length;
  const a = PL[CUR][team].a || [], np = a.length;
  let { T, errors } = await bootTraj("pl", team, "pts", L);
  if (!T) { fail("window.__FBM_TRAJ missing"); return out; }
  const all = [...errors];
  if (L > np) checkProjRow(fail, T.rows.find((r) => r.sn === CUR), B, P, L);
  ({ T, errors } = await bootTraj("pl", team, "pts", 1));
  all.push(...errors);
  const r1 = T.rows.find((r) => r.sn === CUR);
  if (np >= 1) {
    if (!r1 || r1.proj !== false) fail("tj=1: proj=" + (r1 && r1.proj) + " (expected false)");
    else if (r1.pts !== a[0]) fail("tj=1: pts=" + r1.pts + " (expected " + a[0] + ")");
  }
  checkChart(fail, T, B, np, true);
  ({ T, errors } = await bootTraj("pl", team, "diff", L));
  all.push(...errors);
  checkChart(fail, T, B, np, false);
  out.notes.push(team + ", np=" + np + ", L=" + L);
  if (all.length) { out.ok = false; out.notes.push(...all.map((e) => "JS: " + e)); }
  return out;
}
try { results.push(await testTrajectoriesProjection()); }
catch (e) { results.push({ view: "trajectories:pl-projection", ok: false, notes: ["harness threw: " + e.message] }); }
// J beyond the current season's length (L1: 34 now, 38 in older seasons): projected final row, capped.
async function testTrajectoriesProjectionCapped() {
  const out = { view: "trajectories:l1-projection-j38", ok: true, notes: [] };
  const fail = (m) => { out.ok = false; out.notes.push(m); };
  const L1 = D.seasons.l1 || {};
  const ok = (t) => D.bands.l1 && D.bands.l1[t] && D.pre.l1 && D.pre.l1[t] && L1[CUR] && L1[CUR][t] &&
    Object.keys(L1).some((sn) => L1[sn][t] && (L1[sn][t].a || []).length === 38);
  const team = ok("PSG") ? "PSG" : Object.keys((D.bands && D.bands.l1) || {}).sort().find(ok);
  if (!team) { out.notes.push("no L1 team with bands and a 38-matchday season, skipped"); return out; }
  const B = D.bands.l1[team], P = D.pre.l1[team], np = (L1[CUR][team].a || []).length;
  const { T, errors } = await bootTraj("l1", team, "pts", 38);
  if (!T) { fail("window.__FBM_TRAJ missing"); return out; }
  if (T.J !== 38) fail("J=" + T.J + " (expected 38)");
  checkProjRow(fail, T.rows.find((r) => r.sn === CUR), B, P, 38);
  checkChart(fail, T, B, np, true);
  out.notes.push(team + ", np=" + np + ", L=" + B.p50.length);
  if (errors.length) { out.ok = false; out.notes.push(...errors.map((e) => "JS: " + e)); }
  return out;
}
try { results.push(await testTrajectoriesProjectionCapped()); }
catch (e) { results.push({ view: "trajectories:l1-projection-j38", ok: false, notes: ["harness threw: " + e.message] }); }

let failed = 0;
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.view}${r.notes.length ? "  — " + r.notes.join(" | ") : ""}`);
  if (!r.ok) failed++;
}
console.log(`\nSweep: ${results.length - failed}/${results.length} views passed  (altLeague=${ALT_LEAGUE}, oldestPL=${OLDEST_PL})`);
process.exit(failed ? 1 : 0);
