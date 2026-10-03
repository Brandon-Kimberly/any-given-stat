// Renders static/og.png (then bump OG_IMAGE_VERSION in src/lib/seo.ts), the 1200×630 card Discord, Slack, iMessage, X and others show when
// someone shares a link to the site. Re-run after changing the design:
//
//   PW_PATH=/path/to/node_modules/playwright node scripts/og-card.mjs
//
// (Playwright isn't a dependency of the site; point PW_PATH at any install.) The win-probability
// trace comes from static/data/highlight.json when a build has produced it, else a built-in game.
// Text is sized for the ~400 px wide previews chat apps actually show.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW_PATH ?? 'playwright');

const font = (pkg, file) =>
	'file://' + path.join(root, 'node_modules/@fontsource-variable', pkg, 'files', file);
const mark = fs.readFileSync(path.join(root, 'static/favicon.svg'), 'utf8');

// [elapsed seconds, home win probability]
let wp = [
	[0, 0.55],
	[600, 0.48],
	[1200, 0.38],
	[1800, 0.42],
	[2100, 0.3],
	[2500, 0.36],
	[2900, 0.52],
	[3100, 0.47],
	[3300, 0.66],
	[3420, 0.3],
	[3480, 0.58],
	[3560, 0.82],
	[3600, 1]
];
try {
	wp = JSON.parse(fs.readFileSync(path.join(root, 'static/data/highlight.json'), 'utf8')).wp;
} catch {
	/* built-in trace */
}

// The trace as a smooth curve in a 760×300 box (same smoothing as the home hero).
const W = 760;
const H = 300;
const end = Math.max(3600, wp.at(-1)[0]);
const pts = wp.map(([t, p], i) => {
	const win = wp.slice(Math.max(0, i - 1), i + 2).map((q) => q[1]);
	const v = i === 0 || i === wp.length - 1 ? p : win.reduce((a, b) => a + b, 0) / win.length;
	return [(t / end) * W, 20 + (1 - v) * (H - 40)];
});
let d = `M${pts[0][0]} ${pts[0][1]}`;
for (let i = 0; i < pts.length - 1; i++) {
	const [p0, p1, p2, p3] = [pts[i - 1] ?? pts[i], pts[i], pts[i + 1], pts[i + 2] ?? pts[i + 1]];
	d += `C${p1[0] + (p2[0] - p0[0]) / 6} ${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6} ${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]} ${p2[1]}`;
}
const last = pts.at(-1);
const mid = 20 + 0.5 * (H - 40);

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: Archivo; src: url(${font('archivo', 'archivo-latin-wdth-normal.woff2')}) format('woff2'); font-weight: 100 900; font-stretch: 62% 125%; }
@font-face { font-family: Inter; src: url(${font('inter', 'inter-latin-wght-normal.woff2')}) format('woff2'); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; }
body { width: 1200px; height: 630px; overflow: hidden; font-family: Inter, sans-serif; color: #fff;
  background:
    radial-gradient(60% 80% at 82% 22%, rgba(125, 211, 252, 0.2), transparent 60%),
    radial-gradient(55% 70% at 0% 100%, rgba(167, 139, 250, 0.18), transparent 60%),
    linear-gradient(150deg, #0b1830 0%, #0d1f3d 45%, #12305c 100%); position: relative; }
.lines { position: absolute; inset: 0; background: repeating-linear-gradient(90deg, transparent 0 119px, rgba(255,255,255,0.045) 119px 120px);
  -webkit-mask-image: linear-gradient(to bottom, transparent, #000 25%, #000 75%, transparent); }
.trace { position: absolute; right: 76px; top: 140px; width: ${W}px; height: ${H}px; overflow: visible;
  -webkit-mask-image: linear-gradient(to right, transparent 0%, #000 45%); }
.copy { position: absolute; left: 72px; top: 60px; bottom: 56px; width: 980px; display: flex; flex-direction: column; }
.brand { display: flex; align-items: center; gap: 20px; }
.brand svg { width: 76px; height: 76px; border-radius: 18px; box-shadow: 0 12px 30px -10px rgba(0,0,0,.6); }
.name { font-family: Archivo; font-weight: 800; font-stretch: 110%; font-size: 40px; letter-spacing: -0.01em; }
.name b { color: #7dd3fc; font-weight: 800; }
h1 { margin-top: 64px; white-space: nowrap; font-family: Archivo; font-weight: 800; font-stretch: 112%;
  font-size: 72px; line-height: 0.98; letter-spacing: -0.03em; text-shadow: 0 4px 40px rgba(0,0,0,.35); }
h1 span { background: linear-gradient(95deg, #fff 0%, #a5f3fc 75%); -webkit-background-clip: text; color: transparent; }
.sub { margin-top: 22px; width: 680px; font-size: 30px; line-height: 1.32; color: rgba(255,255,255,0.86); }
.chips { margin-top: auto; display: flex; gap: 12px; }
.chip { padding: 9px 18px; border-radius: 999px; font-size: 22px; font-weight: 600; color: #e0f2fe;
  background: rgba(255,255,255,0.08); border: 1.5px solid rgba(255,255,255,0.18); }
.free { position: absolute; right: 72px; bottom: 62px; font-size: 22px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: #a5f3fc; }
</style></head><body>
<div class="lines"></div>
<svg class="trace" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="s" x1="0" x2="1"><stop offset="0" stop-color="#7dd3fc" stop-opacity=".35"/><stop offset=".6" stop-color="#a5f3fc"/><stop offset="1" stop-color="#fff"/></linearGradient>
    <linearGradient id="f" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#67e8f9" stop-opacity=".28"/><stop offset=".5" stop-color="#67e8f9" stop-opacity=".02"/><stop offset=".5" stop-color="#c4b5fd" stop-opacity=".02"/><stop offset="1" stop-color="#c4b5fd" stop-opacity=".26"/></linearGradient>
    <filter id="g"><feGaussianBlur stdDeviation="7"/></filter>
  </defs>
  <line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="rgba(255,255,255,.25)" stroke-dasharray="4 7" stroke-width="1.5"/>
  <path d="${d}L${last[0]} ${mid}L0 ${mid}Z" fill="url(#f)"/>
  <path d="${d}" fill="none" stroke="#67e8f9" stroke-width="12" opacity=".22" filter="url(#g)"/>
  <path d="${d}" fill="none" stroke="url(#s)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="${last[0]}" cy="${last[1]}" r="14" fill="#67e8f9" opacity=".3"/>
  <circle cx="${last[0]}" cy="${last[1]}" r="7" fill="#fff"/>
</svg>
<div class="copy">
<div class="brand">${mark}<div class="name">Any Given <b>Stat</b></div></div>
<h1>Know which numbers<br><span>matter.</span></h1>
<p class="sub">NFL power ratings, win probability for every game since 2016, playoff odds and forecasts graded against Vegas.</p>
<div class="chips"><span class="chip">Power ratings</span><span class="chip">Playoff odds</span><span class="chip">Fantasy</span></div>
</div>
<div class="free">Free · No ads</div>
</body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
// A file page, so the file:// fonts load (about:blank may not read them).
const tmp = path.join(root, 'scripts/.og-card.html');
fs.writeFileSync(tmp, html);
await page.goto('file://' + tmp, { waitUntil: 'load' });
fs.rmSync(tmp);
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: path.join(root, 'static/og.png') });
await browser.close();
console.log('wrote static/og.png');
