# Any Given Stat

NFL analytics built on every play since 2016: opponent-adjusted power ratings, win-probability
charts for every game, predictions honestly scored against Vegas, fourth-down decision grades, an
interactive primer on how football works in numbers, and a page that measures which stats are signal
and which are noise.

**Live site:** https://brandon-kimberly.github.io/any-given-stat/ (rebuilt daily during the season)

![Home dashboard](docs/home.png)

## What's in it

| Page | Question it answers |
|---|---|
| **Home** | What matters this week: model vs Vegas lines, power top 10, risers and fallers, regression candidates, QB leaders. |
| **Games / game page** | Every game's win probability, a drive chart, the full play-by-play (filter by scoring, turnovers, explosives, 4th downs; hover a play to mark it on the WP chart), an efficiency box score and excitement index. Upcoming games get a matchup preview. |
| **How football works** | Expected points by field position and down, win probability by score and clock, pass vs run, the EPA distribution, and fourth-down math, each with interactive controls and data-driven takeaways. |
| **Fourth downs** | An empirical decision model (what going, punting and kicking actually produced), league aggressiveness over time, and team grades by EPA left on the field. |
| **Player pages** | League percentile profile, career arc with intervals, game logs. Search any player with ⌘K / Ctrl+K. |
| **Team tiers** | Who is actually good? Offense vs defense EPA/play, raw or opponent-adjusted, with equal-net-EPA tier lines. |
| **Power ratings** | Opponent-adjusted, recency-weighted team ratings in points, week by week. |
| **Playoff odds** | 10,000 simulated seasons at every week: replay the race, division odds over time, title odds, and a calibration check of past odds. |
| **Compare** | Any two teams or players from any seasons, on percentiles within their own season, with a neutral-field projection for teams. |
| **Record book** | Best and worst team, unit and player seasons by efficiency; biggest upsets, most exciting games, comebacks, biggest plays. |
| **Coaches / Referees** | 4th-down aggressiveness, records and ATS; penalty volume and home lean, each against a 95% chance funnel. |
| **Predictions** | Model spreads for the coming week vs the Vegas line, plus a walk-forward backtest and calibration check. |
| **Teams / team page** | Every efficiency stat by team; per team: auto-generated identity (strengths and weaknesses by league rank), division standings, situational splits, strength of schedule, power-rating path, linked game log. |
| **Quarterbacks** | EPA per dropback vs CPOE, plus 95% intervals that show when two QBs can't be told apart yet. |
| **Receivers / Rushers** | Usage (target share, air yards share, WOPR) and efficiency over expectation (xYAC, catch rate). |
| **Luck** | Record vs Pythagorean expectation, one-score games, fumble recovery, and how much luck reverses next season. |
| **Signal vs noise** | Split-half and year-over-year reliability for 20 stats, and the sample size where each becomes half signal. |
| **SQL explorer** | DuckDB compiled to WebAssembly, querying play-by-play parquet in the browser. Ten preset questions. |

## Findings the site makes easy to defend

Measured on 2016–2025 regular seasons, garbage time excluded (see *Signal vs noise*):

- **Offense is real, defense is shakier.** Offensive EPA/play has a split-half r of 0.50 (full-season
  reliability 0.67). Defense is 0.27 (0.43).
- **Passing beats rushing at predicting itself.** Team pass EPA r = 0.41, rush EPA r = 0.30. Individual
  rusher EPA/carry carries over year to year at only r = 0.06.
- **Some favorite talking points are close to random:** red zone TD rate (r = 0.09), offensive turnover
  rate (0.09), QB interception rate (0.05), fumble recovery rate (−0.02).
- **Public data doesn't beat the closing line, even with QB injuries modeled.** A walk-forward
  ridge model with a starting-QB adjustment missed final margins by 10.00 points on held-out
  2024–2025 (Vegas: 9.67). In a pre-registered attempt (6 variants × 4 bet thresholds, chosen on
  2022–2023), the winning strategy went 87–83 (51.2%) on the sealed test seasons: p = 0.65 against
  the 52.4% break-even. Models given the line as an input put ~95% weight on it and add nothing.
- **Luck reverses.** Teams that beat their Pythagorean record by 2+ wins averaged about 3 fewer wins the
  next season.
- **Injuries matter, and the line mostly knows it.** Each full-time starter out (beyond the QB) is
  worth about −0.9 points against team ratings; beyond the closing line the effect shrinks to
  −0.5 ± 0.2, and a pre-registered round 2 adding injuries, travel, weather and late-season stakes
  went 68–65 (51.1%) on 2024–2025, below the 52.4% break-even. Its choice was frozen in a commit
  before any result was computed; every game after 2026-10-02 is a sealed, live test on the site.
- **Preseason playoff odds are nearly worthless.** Scored against 2017–2025 outcomes, simulated odds
  before week 1 improve on "every team has the league-average chance" by only 6% (Brier skill); by
  week 8 it's 45%.
- **Nobody reliably beats the spread.** 3 of 55 head coaches with 34+ games fall outside a 95%
  coin-flip funnel for cover rate, about what chance alone produces.

![Signal vs noise](docs/stability.png)

## Built to be read

<p>
<img src="docs/game.png" alt="Game page: win probability chart" width="49%">
<img src="docs/learn.png" alt="How football works: expected points" width="49%">
</p>

- **One design system:** Inter and Archivo type, light and dark themes chosen separately (not inverted),
  team colors picked per theme to stay visible, colored team badges, consistent chart grammar
  (single axis, legends for 2+ series, decluttered labels, tooltips everywhere).
- **Accessible:** keyboard navigation (skip link, table rows as links, search palette), WCAG 2 AA
  verified with axe-core on every page in both themes, motion off under `prefers-reduced-motion`.
- **Fast and shareable:** fully static; datasets prefetch on link hover and load one season at a time;
  charts render only when scrolled near; season and filters live in the URL, so any view can be shared
  as a link (press <kbd>c</kbd> to copy it).
- **Built for power users:** keyboard shortcuts (<kbd>?</kbd> lists them; <kbd>g</kbd> then a letter jumps
  to a page, <kbd>[</kbd> <kbd>]</kbd> step seasons), a favorite team highlighted everywhere, PNG export
  on every chart, CSV on every table.

## How it works

```
nflverse play-by-play (parquet, ~20 MB/season) + schedules with closing lines (games.csv)
        │  pipeline/ — Python + DuckDB
        ▼
canonical filtered views (db.py) ──► datasets.py ──► web/static/data/*.json
                                                └──► web/static/data/pbp/pbp_<season>.parquet (slim)
        │  web/ — SvelteKit (static) + Observable Plot + DuckDB-WASM
        ▼
static site on GitHub Pages, rebuilt by a scheduled GitHub Action
```

- **No server.** All aggregation happens at build time in DuckDB SQL. The site is static files, and
  ad-hoc queries run in the visitor's browser.
- **One definition of a play.** Every dataset builds on the views in `pipeline/src/ags/db.py`
  (scrimmage plays, the garbage-time filter, drives, games), so numbers agree across pages.
- **No look-ahead, no peeking.** Ratings for week *w* use only games before week *w*. Coefficients
  are fit on 2017–2021, model choices made on 2022–2023, and 2024–2025 is scored once
  (`pipeline/src/ags/market.py`).
- **Tested math.** Metric logic is unit-tested against hand-computed answers on synthetic play-by-play
  (`pipeline/tests`), and every SQL explorer preset is executed against real data in CI.

## Run it locally

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
cd pipeline && uv sync && uv run ags build   # downloads 2016–current (~200 MB, cached in data/raw)
cd ../web && npm install && npm run serve    # production build + preview: http://localhost:4173
```

`npm run dev` (http://localhost:5173) hot-reloads while editing but is noticeably slower to click
around; use `npm run serve` to see the real thing.

On Windows PowerShell 5.1 (which doesn't support `&&`), run the steps one per line:

```powershell
cd pipeline
uv sync
uv run ags build
cd ..\web
npm install
npm run serve
```

`uv run ags build --seasons 2024-2025` builds a subset. Tests: `uv run pytest` (pipeline) and
`npm test && npm run check` (web).

## Data and credits

Play-by-play, EPA, win probability, CPOE, xYAC and xpass come from
[nflverse](https://github.com/nflverse/nflverse-data) and the
[nflfastR](https://www.nflfastr.com/) models. This project is not affiliated with the NFL.
