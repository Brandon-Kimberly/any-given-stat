<script lang="ts" module>
	// Sortable table. Columns with `better` get a diverging wash by percentile within the
	// visible rows (blue = good end, red = bad end, none in the middle). Clicking a column sorts
	// best-first, so "#" always reads as a rank.
	export interface Column<R> {
		key: keyof R & string;
		label: string;
		fmt?: (v: any) => string;
		title?: string;
		better?: 'high' | 'low';
		sticky?: boolean;
		/** Render the value (a team code) as a colored team badge. */
		team?: boolean;
	}
</script>

<script lang="ts" generics="T extends Record<string, any>">
	import { goto } from '$app/navigation';
	import { favorite } from '$lib/favorite.svelte';
	import TeamBadge from './TeamBadge.svelte';

	let {
		rows,
		columns,
		sortKey: initialSort,
		sortDesc: initialDesc = true,
		search,
		href,
		onrowclick,
		highlight,
		showIndex = true,
		filename = 'any-given-stat',
		maxHeight = '70vh'
	}: {
		rows: T[];
		columns: Column<T>[];
		sortKey: keyof T & string;
		sortDesc?: boolean;
		search?: keyof T & string;
		/** Makes the first (sticky) cell a link; the whole row is clickable with a mouse. An
		 * empty string leaves that row unlinked. */
		href?: (row: T) => string;
		/** Row action without a URL (e.g. toggling a highlight); keyboard users get a button. */
		onrowclick?: (row: T) => void;
		highlight?: (row: T) => boolean;
		showIndex?: boolean;
		filename?: string;
		maxHeight?: string;
	} = $props();

	// svelte-ignore state_referenced_locally
	let sortKey = $state(initialSort);
	// svelte-ignore state_referenced_locally
	let sortDesc = $state(initialDesc);
	let query = $state('');
	// Render a first screenful quickly; long tables reveal the rest on request.
	const STEP = 75;
	let limit = $state(STEP);

	const teamKeys = $derived(columns.filter((c) => c.team).map((c) => c.key));
	const isFav = (row: T) => !!favorite.team && teamKeys.some((k) => row[k] === favorite.team);

	const visible = $derived.by(() => {
		const q = query.trim().toLowerCase();
		const filtered =
			search && q ? rows.filter((r) => String(r[search]).toLowerCase().includes(q)) : rows;
		return [...filtered].sort((a, b) => {
			const av = a[sortKey];
			const bv = b[sortKey];
			if (av == null && bv == null) return 0;
			if (av == null) return 1;
			if (bv == null) return -1;
			const c = av < bv ? -1 : av > bv ? 1 : 0;
			return sortDesc ? -c : c;
		});
	});

	// Percentile (0..1) per value for each shaded column; tied values share their average rank.
	const pctiles = $derived.by(() => {
		const out = new Map<string, Map<number, number>>();
		for (const c of columns) {
			if (!c.better) continue;
			const vals = visible
				.map((r) => r[c.key])
				.filter((v: unknown): v is number => typeof v === 'number') as number[];
			const sorted = [...vals].sort((a, b) => a - b);
			const first = new Map<number, number>();
			const last = new Map<number, number>();
			sorted.forEach((v, i) => {
				if (!first.has(v)) first.set(v, i);
				last.set(v, i);
			});
			const m = new Map<number, number>();
			const denom = Math.max(1, sorted.length - 1);
			for (const [v, i] of first)
				m.set(v, sorted.length > 1 ? (i + last.get(v)!) / 2 / denom : 0.5);
			out.set(c.key, m);
		}
		return out;
	});

	function shade(c: Column<T>, v: unknown): string {
		if (!c.better || typeof v !== 'number') return '';
		let p = pctiles.get(c.key)?.get(v);
		if (p == null) return '';
		if (c.better === 'low') p = 1 - p;
		const d = (p - 0.5) * 2; // -1 (worst) .. +1 (best)
		if (Math.abs(d) < 0.2) return '';
		const alpha = Math.min(1, (Math.abs(d) - 0.2) / 0.8);
		const color = d > 0 ? 'var(--good-wash)' : 'var(--bad-wash)';
		return `background: color-mix(in srgb, ${color} ${Math.round(alpha * 100)}%, transparent)`;
	}

	function sortBy(c: Column<T>) {
		if (c.key === sortKey) sortDesc = !sortDesc;
		else {
			sortKey = c.key;
			// Best first: ascending for "lower is better", descending otherwise.
			sortDesc = c.better !== 'low';
		}
	}

	function csv() {
		const esc = (v: unknown) => {
			const s = v == null ? '' : String(v);
			return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
		};
		const lines = [columns.map((c) => esc(c.label)).join(',')].concat(
			visible.map((r) => columns.map((c) => esc(r[c.key])).join(','))
		);
		const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
		const a = Object.assign(document.createElement('a'), {
			href: url,
			download: `${filename}.csv`
		});
		document.body.append(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	/** A row's own season (season-by-season tables), so team links open that season. */
	const rowSeason = (row: T): number | undefined => {
		const s = (row as Record<string, unknown>).season;
		return typeof s === 'number' ? s : undefined;
	};

	function rowClick(e: MouseEvent, row: T) {
		if ((e.target as HTMLElement).closest('a, button')) return; // the cell control handles it
		const url = href?.(row);
		if (url) goto(url);
		else onrowclick?.(row);
	}
</script>

<div class="toolbar table-tools">
	{#if search}
		<input type="search" placeholder="Filter…" bind:value={query} aria-label="Filter rows" />
	{/if}
	<span class="muted count">{visible.length} rows</span>
	<button class="ghost small" onclick={csv} title="Download these rows as CSV">
		<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" /></svg>
		CSV
	</button>
</div>
<div class="scroll" style="max-height: {maxHeight}">
	<table>
		<thead>
			<tr>
				{#if showIndex}<th class="rank" scope="col">#</th>{/if}
				{#each columns as c (c.key)}
					<th
						scope="col"
						class:sticky={c.sticky}
						class:num={!c.sticky && !c.team}
						title={c.title}
						aria-sort={sortKey === c.key ? (sortDesc ? 'descending' : 'ascending') : 'none'}
					>
						<button class="th" class:sorted={sortKey === c.key} onclick={() => sortBy(c)}>
							{c.label}<span class="arrow" aria-hidden="true"
								>{sortKey === c.key ? (sortDesc ? '↓' : '↑') : '↕'}</span
							>
						</button>
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each visible.slice(0, limit) as row, i (i)}
				<tr
					class:clickable={!!(href?.(row) || onrowclick)}
					class:hl={highlight?.(row)}
					class:fav={isFav(row)}
					onclick={(e) => rowClick(e, row)}
				>
					{#if showIndex}<td class="rank"
							>{#if i < 3}<span class="medal m{i + 1}">{i + 1}</span>{:else}{i + 1}{/if}</td
						>{/if}
					{#each columns as c, ci (c.key)}
						{@const text = c.fmt ? c.fmt(row[c.key]) : (row[c.key] ?? '–')}
						<td
							class:sticky={c.sticky}
							class:num={!c.sticky && !c.team}
							style={shade(c, row[c.key])}
						>
							{#if ci === 0 && href?.(row)}
								<a class="cell-link" href={href(row)}
									>{#if c.team}<TeamBadge team={row[c.key]} />{:else}{text}{/if}</a
								>
							{:else if ci === 0 && onrowclick}
								<button
									class="cell-btn"
									aria-pressed={highlight ? highlight(row) : undefined}
									onclick={() => onrowclick(row)}
									>{#if c.team}<TeamBadge team={row[c.key]} />{:else}{text}{/if}</button
								>
							{:else if c.team && row[c.key]}
								<TeamBadge team={row[c.key]} link season={rowSeason(row)} />
							{:else}
								{text}
							{/if}
						</td>
					{/each}
				</tr>
			{:else}
				<tr><td class="empty" colspan={columns.length + 1}>No rows match.</td></tr>
			{/each}
		</tbody>
	</table>
</div>
{#if visible.length > limit}
	<button class="more" onclick={() => (limit = Infinity)}>
		Show all {visible.length} rows
	</button>
{/if}

<style>
	.table-tools {
		margin-bottom: 0.6rem;
	}
	.count {
		font-size: 0.8rem;
		margin-left: auto;
	}
	.small {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.82rem;
		color: var(--text-secondary);
	}
	.small svg {
		width: 15px;
		height: 15px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.scroll {
		overflow: auto;
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	table {
		border-collapse: separate;
		border-spacing: 0;
		width: 100%;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
	}
	th,
	td {
		padding: 0.38rem 0.65rem;
		white-space: nowrap;
		border-bottom: 1px solid var(--grid);
	}
	thead th {
		position: sticky;
		top: 0;
		background: var(--surface-2);
		z-index: 2;
		font-weight: 700;
		font-size: 0.7rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--text-secondary);
		text-align: left;
		box-shadow: inset 0 -1px 0 var(--border-strong);
	}
	.th {
		all: unset;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.th:hover,
	.th.sorted {
		color: var(--text-primary);
	}
	.arrow {
		font-size: 0.8em;
		opacity: 0.35;
	}
	.th.sorted .arrow {
		opacity: 1;
		color: var(--accent-ink);
		text-shadow: 0 0 10px color-mix(in srgb, var(--accent) 60%, transparent);
	}
	.th:focus-visible {
		outline: 2px solid var(--accent);
		border-radius: 3px;
	}
	th.num,
	td.num {
		text-align: right;
	}
	th.num .th {
		flex-direction: row-reverse;
	}
	.rank {
		color: var(--text-muted);
		text-align: right;
		width: 2.5rem;
	}
	td.sticky,
	th.sticky {
		position: sticky;
		left: 0;
		text-align: left;
		background: var(--surface);
		z-index: 1;
		font-weight: 600;
	}
	thead th.sticky {
		background: var(--surface-2);
		z-index: 3;
	}
	tbody tr {
		transition: background-color 0.12s;
	}
	tbody tr:hover td {
		background-color: color-mix(in srgb, var(--accent) 7%, var(--surface));
	}
	/* The hovered row gets a brand-gradient edge on its first cell. */
	tbody tr:hover td:first-child {
		background-image: var(--brand-gradient);
		background-size: 3px 100%;
		background-repeat: no-repeat;
	}
	/* Top three rows: gold, silver, bronze rank discs. */
	.medal {
		display: inline-grid;
		place-items: center;
		width: 1.45rem;
		height: 1.45rem;
		border-radius: 50%;
		font-size: 0.72rem;
		font-weight: 800;
		color: #1b1405;
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.55),
			0 2px 6px -2px rgba(0, 0, 0, 0.35);
	}
	.m1 {
		background: linear-gradient(145deg, #ffe08a, #e0a91b);
	}
	.m2 {
		background: linear-gradient(145deg, #f1f3f6, #b7bec9);
	}
	.m3 {
		background: linear-gradient(145deg, #f3c7a0, #c27c45);
	}
	tbody tr:last-child td {
		border-bottom: 0;
	}
	tr.clickable {
		cursor: pointer;
	}
	tr.hl td {
		box-shadow: inset 0 -2px 0 var(--accent);
	}
	tr.fav td:first-child {
		box-shadow: inset 3px 0 0 var(--fav);
	}
	.cell-link {
		color: inherit;
		text-decoration: none;
	}
	.cell-link:hover {
		color: var(--accent-ink);
		text-decoration: underline;
	}
	.cell-btn {
		all: unset;
		cursor: pointer;
	}
	.cell-btn:focus-visible {
		outline: 2px solid var(--accent);
		border-radius: 3px;
	}
	.more {
		display: block;
		margin: 0.6rem auto 0;
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--accent-ink);
	}
	.empty {
		text-align: center;
		color: var(--text-muted);
		padding: 1.5rem;
	}
</style>
