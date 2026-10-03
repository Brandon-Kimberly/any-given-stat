# Any Given Stat

NFL analytics site. Python/DuckDB pipeline turns nflverse play-by-play into static JSON + slim
parquet; a static SvelteKit site renders it. No backend.

## Layout

- `pipeline/` (uv project, package `ags`)
  - `src/ags/db.py`: **canonical views** (`plays`, `scoped_plays`, `drives`, `games`, `team_games`). Every metric builds on these.
  - `src/ags/datasets.py`: one function per published dataset; `STABILITY_METRICS` list; `SPLITS` for team situational splits.
  - `src/ags/ratings.py`: ridge-regression team ratings (numpy), walk-forward spread model, backtest vs Vegas. Needs the `schedule` view (nflverse `games.csv`, team codes mapped via `db.TEAM_ALIASES`).
  - `src/ags/teams.py` (names, divisions, theme-safe colors → `teams_meta.json`, plus `logo` when `fetch.fetch_logos` got nflverse's squared logo tile into `data/raw/logos`; the build copies them to `/data/logos/`), `players.py` (directory + `full_name`/`position` merged into player datasets), `fourth.py` (empirical 4th-down model), `games.py` (per-season `games/games_<season>.json`: WP series, top plays, box).
  - `db.py` also has `scrimmage_plays` (the `plays` filters without the REG-only restriction, for playoff box scores).
  - `src/ags/qb.py`: walk-forward starting-QB adjustment (listed starter vs the QBs behind the team's rating).
  - `src/ags/market.py`: the pre-registered beat-the-line experiment (`VARIANTS`, `THRESHOLDS`, selection rule) → `lab.json`.
  - `src/ags/lab2.py`: round 2 vs the closing line (`VARIANTS`, `FROZEN` choice committed 2026-10-02; 2024–2025 reported as a *reused* test; games after the freeze are the sealed live test) → `lab2.json`. Features from `context.py` (injuries = role × presence by position group from injury reports + snap counts; rest/bye; time zones; weather as margin compressors; late-season stakes from `sim.py`) and `forecast.py` (Open-Meteo kickoff forecasts for live games; backtests use recorded weather). Never edit `FROZEN` or `VARIANTS` to chase results; a new idea is round 3 with its own freeze.
  - `src/ags/strength.py`: walk-forward margin-of-victory (points) ridge ratings, the second team rating next to EPA.
  - `src/ags/lab3.py`: round 3 = the site's forecast, chosen for accuracy (validation RMSE), `FROZEN` 2026-10-02: EPA + points ratings + QB + injuries. `apply_to_predictions` writes its margins/WPs into `predictions.json`; `sim_inputs` gives the simulator its game model and next-week overrides (market blend `line + k·(model − line)`, k fit on FIT) → `lab3.json`.
  - `src/ags/sim.py` (v2): Monte Carlo playoff odds (10,000 sims per week state) with the round-3 rating terms, correlated per-team strength uncertainty (`TAU_PRESEASON`→`TAU_LATE`, tuned on FIT by Brier; per-game noise shrunk so single games stay calibrated), NFL-style tiebreakers, and a per-state cache in `data/cache/odds` keyed by every input (bump `SIM_VERSION` when logic changes) → `playoff_odds/<season>.json` + `index.json`. v1's Brier scores are kept in `src/ags/reference/sim_v1_brier.json`.
  - `src/ags/playbyplay.py`: per-game plays (compact arrays, `PLAYS_COLUMNS`, flag letters) and drives → `games/<season>/<game_id>.json` (plus `box` from statlines).
  - `src/ags/statlines.py`: one pass over pbp credits every play to its players → per-player-game stat lines (keys = Sleeper scoring names, documented in `web/src/lib/fantasy/statline.ts`), team-defense `DEF` lines and team box stats. Feeds the game box scores and `fantasy/<season>.json` (box-only fields dropped); `fantasy_ids.json` maps Sleeper/ESPN ids → gsis (dynastyprocess `db_playerids.csv` + nflverse `espn_id`). Validated against nflverse weekly player stats (PPR reproduces exactly on 99.7% of 2024 player-games). Change the stat keys only together with `statline.ts`.
  - `src/ags/records.py` (`records.json`; regular-season OT excluded from WP lists) and `people.py` (`coaches.json`, `referees.json`).
  - `ratings`, `team_splits`, `team_weeks`, `qb_games` are also written per season (`<name>/<season>.json`); pages load those, not the combined files.
  - `src/ags/build.py`: writes `web/static/data/*.json` (atomically), `pbp/pbp_<season>.parquet`, `meta.json`. Past seasons' per-game files are skipped when `games/<season>/.done` matches `playbyplay.VERSION`.
  - `src/ags/serve.py` (`ags up`: build if missing or older than `config.DATA_VERSION` (stamped in `meta.json`; bump it when the site needs new datasets), serve `web/build` with `/data` live from `web/static/data`, open the browser; `npm install` first whenever `package*.json` is newer than `node_modules/.package-lock.json`, e.g. after a pull adds a dependency) and `sync.py` (Sync button API: HEAD change check against `data/raw/sync_manifest.json`, rebuild in a subprocess, auto-sync off/interval/game days in `data/sync_settings.json`). Repo-root `start.cmd` / `start.sh` wrap `ags up`.
  - `tests/`: synthetic-pbp fixture in `conftest.py` (`make_pbp`, `run()` helper); `test_presets.py` runs explorer presets against real data (skipped if not built).
- `web/` (SvelteKit 2, Svelte 5 runes, adapter-static, `ssr = false`, prerendered shells)
  - `src/lib/types.ts` mirrors the JSON shapes; keep it in sync with `datasets.py`.
  - `src/lib/components/`: `Plot.svelte` (Observable Plot wrapper: labels any `className: 'declutter'` text mark, exposes the chart as one labeled image), `DataTable.svelte` (sort best-first, percentile shading, `href` row links, `team: true` badge columns, CSV), `Controls.svelte` (season + garbage-time toggle), `TeamBadge`, `CommandPalette` (⌘K), `Skeleton`, `LoadError`.
  - Data loading: `resource('name')` (`src/lib/resource.svelte.ts`) gives `{value, error}` as `$state.raw` (never deep proxies for datasets); `seasonResource(dir, () => season)` loads `<dir>/<season>.json` reactively. Each route's `+page.ts` calls `prefetch(...)` / `prefetchSeason(url, ...)` so downloads start on hover/navigation. Game files via `loadSeasonGames` / `loadGamePlays` (`src/lib/games.ts`).
  - Fantasy (`src/lib/fantasy/`): `scoring.ts` (Sleeper keys + ESPN statIds → points, `breakdown`, `unsupported`, presets; compiled per scoring, memoize with `scoringKey`), `sleeper.ts`/`espn.ts` connectors (ESPN goes through `serve.py`'s `/api/espn/league` proxy: no CORS, so only under `ags up`), `league.svelte.ts` store (`fantasy`: league, preset, my team, ownership; localStorage `ags-fantasy-*`), `analysis.ts` (season totals, starter weeks, value over replacement with flex allocation, points allowed by position), `data.svelte.ts` loaders. UI: `/fantasy/` page, `LeagueConnect`, `BoxScore` (game page; fantasy table + owner marks), `PlayerFantasy`, `TeamFantasy`, `FantasyRecords` (lazy-loads every season).
  - More components: `GameFlow` (drive chart + play feed, hover syncs the WP chart), `RecordList`, `Ticker`, `FavoriteCard`, `CountUp` (tile numbers), `Shortcuts` (g+letter, `[ ]`, t, c, ?), `Toast`. `Plot.svelte` renders lazily near the viewport, wipes in on first render only, and has a PNG export (`src/lib/exportChart.ts`).
  - `favorite` (`src/lib/favorite.svelte.ts`, localStorage): gold `--fav` ring on badges and table rows. `odds.ts`: calibration / Brier skill for playoff odds. `recent.ts`: recently opened teams/players/pages (the ⌘K palette's empty state). `PageToc` (sticky "On this page" jumps on predictions and odds; sections need ids, `app.css` gives them `scroll-margin-top`), `BackToTop`, footer site map from `nav.ts`.
  - Visual system: fonts are self-hosted variable Inter + Archivo (`font-stretch` = Archivo's width axis for headlines). `app.css` tokens: `--brand-a/b/c` + `--brand-gradient` (decoration only, never behind text), `--ambient-*` page glows, `--card-sheen`, `--shadow-glow`. `src/lib/motion.ts` (started in the layout): card spotlight (`--mx/--my` → `.card` gradient border/fill) and sliding `.seg` pills (`.seg::before` from `--pill-*`). Route changes use View Transitions (`onNavigate` in the layout; same-path changes stay instant); `toggleTheme(e)` reveals the new theme in a circle. Cards rise in via scroll-driven animations (transform only, so axe/contrast never sees faded text). `confetti()` (`src/lib/confetti.ts`) on picking a favorite team. `TeamLogo` (logo tile, badge fallback) and `Avatar` (headshot from `players.json` `headshot`, initials fallback); `heroColors(team)`/`nightShade()` darken team colors until white text passes. Toasts take a tone (`toast.show(text, ms, 'ok' | 'info' | 'error')`). Everything decorative stops under `prefers-reduced-motion`; the home hero's loops pause off-screen.
  - Shared state: `prefs` (season/scope, synced to `?season=&scope=`), `theme` (re-renders theme-dependent charts), `teamMeta` with `teamColor`/`teamName` (`src/lib/teams.svelte.ts`). Site map in `src/lib/nav.ts`.
  - `src/lib/presets.ts`: SQL explorer presets (template literals; `test_presets.py` parses them with a regex, so keep the `title: '...'` / `sql: \`...\`` shape).
  - `src/lib/duck.ts`: DuckDB-WASM, self-hosted engine; the parquet extension is fetched from extensions.duckdb.org at runtime.
- `data/raw/`: downloaded nflverse parquet, incl. `injuries_<season>` and `snap_counts_<season>` (gitignored). `web/static/data/`: generated (gitignored).

## Commands

```bash
uv run --project pipeline ags up [--port 4173] [--no-open]   # or .\start.cmd / ./start.sh: everything, one command
cd pipeline && uv run ags build [--seasons 2016-2026] [--no-refresh] [--no-explorer]
cd pipeline && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd web && npm run dev | npm run serve | npm test | npm run check | npm run lint | npm run format   # serve = production build + preview (much faster than dev)
cd web && BASE_PATH=/any-given-stat npm run build   # what CI deploys; preview needs the same BASE_PATH
```

## Stat definitions (change only together with `db.py`)

- **Play** = regular season, `play_type in ('pass','run')`, `epa` not null, `posteam` not null. Excludes kneels, spikes, special teams, `no_play` penalties.
- **Dropback** = `pass = 1` (includes sacks and scrambles). **Designed run** = `rush = 1` (scrambles excluded).
- **No garbage time** = offense `wp` in [0.10, 0.90]. Datasets with a `scope` column carry both `all` and `no_garbage`.
- **Explosive** = pass ≥ 20 yards or run ≥ 10 yards.
- **QB EPA** uses `qb_epa`; CI = mean ± 1.96·sd/√n.
- **Drive points** approximated as TD = 7, FG = 3. **Red zone trip** = drive reaching `yardline_100 <= 20`.
- **Pythagorean** exponent 2.37; one-score = margin ≤ 8.
- **Ratings**: per team-game offense row, `epa/play = mu + off[team] + def[opp] + h*home`, weighted by plays, ridge on team terms. Predictive ratings use only games before the week predicted (current + previous season, 16-week half-life). Splits live in `ratings.py`: fit on `FIT_SEASONS` (2017–2021), choose on `VALIDATE_SEASONS` (2022–2023), report `TEST_SEASONS` (2024–2025). Never tune or choose on test; adding a variant to `market.VARIANTS` after seeing test results invalidates the test, so say so on the page if it happens. Vegas `spread_line` > 0 = home favored.
- **Stability**: split-half = odd vs even weeks, complete seasons only; reliability = 2r/(1+r); n for 50% signal = n_half·(1−r)/r.

## Conventions

- Add a metric: SQL in `datasets.py` → test with hand-computed answer in `tests/` → field in `types.ts` → column/chart in the page. Consider adding it to `STABILITY_METRICS` too.
- Charts: dataviz conventions. Colors come from CSS tokens in `app.css` (`--series-1/2`, `--neutral-mark`, `--good/--bad` washes), never raw hex in pages; one y-axis; a legend whenever there are 2+ series; text in text tokens, never series colors.
- Formatters in `src/lib/format.ts` (real minus sign, no negative zero; `wlt` for records with ties). `DataTable` `fmt` takes the value only.
- Team colors (`teamColor`) are fine for marks with a text label or tooltip (identity is never color-alone); multi-series comparisons use the validated `--series-1..4` palette instead. Two-team views use `matchupColors(away, home)`, which falls back to the series pair when the team colors clash.
- Responsiveness: re-renders on filter changes must stay instant (no entry animations on re-render, no view-transition waits). Large tables render 75 rows until "Show all".
- Layout stability: CLS ≤ 0.1 on every page (main reserves the viewport; on-screen charts render before first paint). Reserve space for anything that fills in after data loads.
- Plot radii: a function `r` is a data channel that Plot rescales to tiny dots; give the plot `r: { type: 'identity' }` when the function returns pixels. Markers ≥ 8 px (r ≥ 4).
- "Through week N" (`meta.seasons[].last_week`) is the last fully played week; a lone Thursday game doesn't count.
- Claims of skill get a null model: funnels for rates (`funnelBand`), base-rate Brier for forecasts.
- Every page: `page-head` with an eyebrow, a `Skeleton` while loading, `LoadError` on failure, `SampleWarning` for in-progress seasons. Check new pages with axe (zero WCAG A/AA violations is the bar) at 1280px light and 390px dark.
- Small samples are a feature, not a bug: in-progress seasons show `SampleWarning`; don't hide uncertainty.
- SvelteKit is pinned to 2.x on purpose (3.0 shipped 2026-10-01). Don't bump majors casually.
