# Any Given Stat

NFL analytics site. Python/DuckDB pipeline turns nflverse play-by-play into static JSON + slim
parquet; a static SvelteKit site renders it. No backend.

## Layout

- `pipeline/` (uv project, package `ags`)
  - `src/ags/db.py`: **canonical views** (`plays`, `scoped_plays`, `drives`, `games`, `team_games`). Every metric builds on these.
  - `src/ags/datasets.py`: one function per published dataset; `STABILITY_METRICS` list.
  - `src/ags/build.py`: writes `web/static/data/*.json`, `pbp/pbp_<season>.parquet`, `meta.json`.
  - `tests/`: synthetic-pbp fixture in `conftest.py` (`make_pbp`, `run()` helper); `test_presets.py` runs explorer presets against real data (skipped if not built).
- `web/` (SvelteKit 2, Svelte 5 runes, adapter-static, `ssr = false`, prerendered shells)
  - `src/lib/types.ts` mirrors the JSON shapes; keep it in sync with `datasets.py`.
  - `src/lib/components/`: `Plot.svelte` (Observable Plot wrapper), `DataTable.svelte` (sort, percentile shading, CSV), `Controls.svelte` (season + garbage-time toggle).
  - `src/lib/presets.ts`: SQL explorer presets (template literals; `test_presets.py` parses them with a regex, so keep the `title: '...'` / `sql: \`...\`` shape).
  - `src/lib/duck.ts`: DuckDB-WASM, self-hosted engine; the parquet extension is fetched from extensions.duckdb.org at runtime.
- `data/raw/`: downloaded nflverse parquet (gitignored). `web/static/data/`: generated (gitignored).

## Commands

```bash
cd pipeline && uv run ags build [--seasons 2016-2026] [--no-refresh] [--no-explorer]
cd pipeline && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd web && npm run dev | npm test | npm run check | npm run lint | npm run format
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
- **Stability**: split-half = odd vs even weeks, complete seasons only; reliability = 2r/(1+r); n for 50% signal = n_half·(1−r)/r.

## Conventions

- Add a metric: SQL in `datasets.py` → test with hand-computed answer in `tests/` → field in `types.ts` → column/chart in the page. Consider adding it to `STABILITY_METRICS` too.
- Charts: dataviz conventions. Colors come from CSS tokens in `app.css` (`--series-1/2`, `--neutral-mark`, `--good/--bad` washes), never raw hex in pages; one y-axis; a legend whenever there are 2+ series; text in text tokens, never series colors.
- Formatters in `src/lib/format.ts` (real minus sign, no negative zero). `DataTable` `fmt` takes the value only.
- Small samples are a feature, not a bug: in-progress seasons show `SampleWarning`; don't hide uncertainty.
- SvelteKit is pinned to 2.x on purpose (3.0 shipped 2026-10-01). Don't bump majors casually.
