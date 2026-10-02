<script lang="ts">
	import PlotFigure from '$lib/components/Plot.svelte';
	import { load } from '$lib/data';
	import { run, usePbp, type QueryResult } from '$lib/duck';
	import { gridX, gridY, Plot, plotStyle } from '$lib/plot';
	import { presets } from '$lib/presets';
	import type { Meta } from '$lib/types';

	let meta = $state<Meta>();
	let picked = $state<number[]>([]);
	let sql = $state(presets[0].sql);
	let result = $state<QueryResult | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let engine = $state<'idle' | 'loading' | 'ready'>('idle');

	load('meta').then((m) => {
		meta = m;
		const complete = m.seasons.filter((s) => s.complete).map((s) => s.season);
		picked = [complete.at(-1) ?? m.seasons.at(-1)!.season];
	});

	const files = $derived(
		meta?.explorer_files.filter((f) => picked.includes(f.season)).map((f) => f.file) ?? []
	);
	const mb = $derived(
		(meta?.explorer_files
			.filter((f) => picked.includes(f.season))
			.reduce((a, f) => a + f.bytes, 0) ?? 0) / 1e6
	);

	async function execute() {
		if (!files.length) {
			error = 'Pick at least one season.';
			return;
		}
		busy = true;
		error = null;
		try {
			if (engine === 'idle') engine = 'loading';
			await usePbp(files);
			engine = 'ready';
			result = await run(sql);
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
			result = null;
			if (engine === 'loading') engine = 'idle';
		} finally {
			busy = false;
		}
	}

	function onkeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
			e.preventDefault();
			execute();
		}
	}

	function toggle(season: number) {
		picked = picked.includes(season)
			? picked.filter((s) => s !== season)
			: [...picked, season].sort();
	}

	function csv() {
		if (!result) return;
		const esc = (v: unknown) => {
			const s = v == null ? '' : String(v);
			return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
		};
		const names = result.columns.map((c) => c.name);
		const text = [names.map(esc).join(',')]
			.concat(result.rows.map((r) => names.map((n) => esc(r[n])).join(',')))
			.join('\n');
		const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
		Object.assign(document.createElement('a'), { href: url, download: 'query.csv' }).click();
		URL.revokeObjectURL(url);
	}

	// Auto-chart: first text column as labels + a chosen numeric column -> bar chart;
	// no text column but 2+ numeric columns -> scatter of the first two.
	const labelCol = $derived(result?.columns.find((c) => !c.numeric)?.name);
	const numericCols = $derived(result?.columns.filter((c) => c.numeric).map((c) => c.name) ?? []);
	let measure = $state<string | null>(null);
	const yCol = $derived(measure && numericCols.includes(measure) ? measure : numericCols.at(-1));
	const chartable = $derived(
		!!result &&
			result.rows.length > 1 &&
			result.rows.length <= 60 &&
			numericCols.length > 0 &&
			(!!labelCol || numericCols.length > 1)
	);

	function chart(width: number) {
		const rows = result!.rows;
		if (labelCol) {
			const y = yCol!;
			return Plot.plot({
				width,
				height: Math.max(200, rows.length * 22 + 50),
				style: plotStyle,
				marginLeft: Math.min(220, width * 0.35),
				x: { label: `${y} →`, grid: false },
				y: { label: null, domain: rows.map((r) => String(r[labelCol])) },
				marks: [
					gridX(),
					Plot.ruleX([0], { stroke: 'var(--axis)' }),
					Plot.barX(rows, {
						y: (r) => String(r[labelCol]),
						x: y,
						fill: 'var(--series-1)',
						rx: 4,
						insetTop: 3,
						insetBottom: 3
					}),
					Plot.tip(
						rows,
						Plot.pointerY({
							lineWidth: 40,
							y: (r) => String(r[labelCol]),
							x: y,
							title: (r) => `${r[labelCol]}: ${r[y]}`
						})
					)
				]
			});
		}
		const [x, y] = numericCols;
		return Plot.plot({
			width,
			height: 360,
			style: plotStyle,
			x: { label: `${x} →` },
			y: { label: `↑ ${y}` },
			marks: [
				gridX(),
				gridY(),
				Plot.dot(rows, { x, y, r: 4, fill: 'var(--series-1)', fillOpacity: 0.7 }),
				Plot.tip(rows, Plot.pointer({ lineWidth: 40, x, y }))
			]
		});
	}

	const shown = $derived(result?.rows.slice(0, 1000) ?? []);
	const fmt = (v: unknown) =>
		v == null
			? '–'
			: typeof v === 'number'
				? Number.isInteger(v)
					? v.toLocaleString()
					: v.toFixed(3)
				: String(v);
</script>

<svelte:head><title>SQL explorer · Any Given Stat</title></svelte:head>

<section>
	<h1>SQL explorer</h1>
	<p class="lede">
		Ask anything. Every play since 2016 runs through DuckDB in your browser; nothing touches a
		server. Query the <code>pbp</code> view (one row per play, nflfastR columns). Start from a
		preset or write your own. Press <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> to run.
	</p>
</section>

<div class="layout">
	<aside class="card presets">
		<h2>Questions to ask</h2>
		<ul>
			{#each presets as p (p.title)}
				<li>
					<button
						class:active={sql === p.sql}
						onclick={() => ((sql = p.sql), (measure = null), execute())}
					>
						<strong>{p.title}</strong>
						<span>{p.question}</span>
					</button>
				</li>
			{/each}
		</ul>
	</aside>

	<div class="stack main">
		<div class="card">
			{#if meta}
				<div class="seasons" role="group" aria-label="Seasons to query">
					{#each meta.explorer_files as f (f.season)}
						<button aria-pressed={picked.includes(f.season)} onclick={() => toggle(f.season)}
							>{f.season}</button
						>
					{/each}
					<span class="muted small">{mb.toFixed(1)} MB</span>
				</div>
			{/if}
			<textarea bind:value={sql} {onkeydown} spellcheck="false" rows="12" aria-label="SQL query"
			></textarea>
			<div class="toolbar">
				<button class="primary" onclick={execute} disabled={busy}
					>{busy ? 'Running…' : 'Run query'}</button
				>
				{#if engine === 'loading'}<span class="muted small"
						>Starting DuckDB (one-time engine download)…</span
					>{/if}
				{#if result}
					<span class="muted small"
						>{result.rows.length.toLocaleString()} rows · {result.ms.toFixed(0)} ms</span
					>
					<button onclick={csv}>Download CSV</button>
				{/if}
			</div>
			{#if error}<pre class="error">{error}</pre>{/if}
		</div>

		{#if result && chartable}
			<div class="card">
				<div class="toolbar" style="margin-bottom: 0.5rem">
					<h2 style="margin: 0">Quick chart</h2>
					{#if labelCol && numericCols.length > 1}
						<label class="field">
							Value
							<select
								value={yCol}
								onchange={(e) => (measure = (e.currentTarget as HTMLSelectElement).value)}
							>
								{#each numericCols as c (c)}<option value={c}>{c}</option>{/each}
							</select>
						</label>
					{/if}
				</div>
				<PlotFigure label="Chart of query result" render={chart} />
			</div>
		{/if}

		{#if result}
			<div class="card">
				<div class="scroll">
					<table>
						<thead>
							<tr
								>{#each result.columns as c (c.name)}<th class:num={c.numeric}>{c.name}</th
									>{/each}</tr
							>
						</thead>
						<tbody>
							{#each shown as row, i (i)}
								<tr
									>{#each result.columns as c (c.name)}<td
											class:num={c.numeric}
											class:wrap={c.name === 'desc'}>{fmt(row[c.name])}</td
										>{/each}</tr
								>
							{/each}
						</tbody>
					</table>
				</div>
				{#if result.rows.length > shown.length}<p class="muted small">
						Showing the first 1,000 rows. Download CSV for all.
					</p>{/if}
			</div>
		{/if}
	</div>
</div>

<style>
	.layout {
		display: grid;
		grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
		gap: 1rem;
		align-items: start;
	}
	@media (max-width: 860px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}
	.presets ul {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		display: grid;
		gap: 0.25rem;
	}
	.presets button {
		all: unset;
		box-sizing: border-box;
		display: grid;
		width: 100%;
		padding: 0.45rem 0.6rem;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.85rem;
	}
	.presets button span {
		color: var(--text-secondary);
		font-size: 0.8rem;
	}
	.presets button:hover,
	.presets button.active {
		background: var(--surface-2);
	}
	.presets button:focus-visible {
		outline: 2px solid var(--accent);
	}
	.seasons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		align-items: center;
		margin-bottom: 0.6rem;
	}
	.seasons button {
		padding: 0.15rem 0.5rem;
		font-size: 0.8rem;
	}
	.seasons button[aria-pressed='true'] {
		background: var(--accent-fill);
		border-color: var(--accent-fill);
		color: #fff;
	}
	textarea {
		width: 100%;
		font: 13px/1.5 var(--mono);
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 0.6rem;
		margin-bottom: 0.6rem;
		resize: vertical;
		tab-size: 2;
	}
	.small {
		font-size: 0.8rem;
	}
	.error {
		color: var(--bad);
		white-space: pre-wrap;
		font-size: 0.8rem;
		margin: 0.6rem 0 0;
	}
	.scroll {
		overflow: auto;
		max-height: 60vh;
	}
	table {
		border-collapse: collapse;
		width: 100%;
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
	}
	th,
	td {
		padding: 0.25rem 0.5rem;
		border-bottom: 1px solid var(--grid);
		white-space: nowrap;
		text-align: left;
	}
	th {
		position: sticky;
		top: 0;
		background: var(--surface-2);
		font-weight: 600;
		color: var(--text-secondary);
	}
	.num {
		text-align: right;
	}
	td.wrap {
		white-space: normal;
		min-width: 320px;
	}
	kbd {
		font: 0.8em var(--mono);
		border: 1px solid var(--border);
		border-radius: 4px;
		padding: 0 0.3em;
	}
</style>
