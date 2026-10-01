<script lang="ts" module>
	// Sortable table. Columns with `better` get a diverging wash by percentile
	// within the visible rows (blue = good end, red = bad end, none in the middle).
	export interface Column<R> {
		key: keyof R & string;
		label: string;
		fmt?: (v: any) => string;
		title?: string;
		better?: 'high' | 'low';
		sticky?: boolean;
	}
</script>

<script lang="ts" generics="T extends Record<string, any>">
	let {
		rows,
		columns,
		sortKey: initialSort,
		sortDesc: initialDesc = true,
		search,
		onrowclick,
		highlight
	}: {
		rows: T[];
		columns: Column<T>[];
		sortKey: keyof T & string;
		sortDesc?: boolean;
		search?: keyof T & string;
		onrowclick?: (row: T) => void;
		highlight?: (row: T) => boolean;
	} = $props();

	// svelte-ignore state_referenced_locally
	let sortKey = $state(initialSort);
	// svelte-ignore state_referenced_locally
	let sortDesc = $state(initialDesc);
	let query = $state('');

	const visible = $derived.by(() => {
		const q = query.trim().toLowerCase();
		const filtered =
			search && q ? rows.filter((r) => String(r[search]).toLowerCase().includes(q)) : rows;
		return [...filtered].sort((a, b) => {
			const av = a[sortKey];
			const bv = b[sortKey];
			if (av == null) return 1;
			if (bv == null) return -1;
			const c = av < bv ? -1 : av > bv ? 1 : 0;
			return sortDesc ? -c : c;
		});
	});

	// Percentile (0..1) per value for each shaded column.
	const pctiles = $derived.by(() => {
		const out = new Map<string, Map<number, number>>();
		for (const c of columns) {
			if (!c.better) continue;
			const vals = visible
				.map((r) => r[c.key])
				.filter((v: unknown): v is number => typeof v === 'number') as number[];
			const sorted = [...vals].sort((a, b) => a - b);
			const m = new Map<number, number>();
			sorted.forEach((v, i) => m.set(v, sorted.length > 1 ? i / (sorted.length - 1) : 0.5));
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

	function sortBy(key: keyof T & string) {
		if (key === sortKey) sortDesc = !sortDesc;
		else {
			sortKey = key;
			sortDesc = true;
		}
	}

	function csv() {
		const esc = (v: unknown) => {
			const s = v == null ? '' : String(v);
			return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
		};
		const lines = [columns.map((c) => esc(c.label)).join(',')].concat(
			visible.map((r) => columns.map((c) => esc(r[c.key])).join(','))
		);
		const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
		const a = Object.assign(document.createElement('a'), {
			href: url,
			download: 'any-given-stat.csv'
		});
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<div class="toolbar table-tools">
	{#if search}
		<input type="search" placeholder="Filter…" bind:value={query} aria-label="Filter rows" />
	{/if}
	<span class="muted count">{visible.length} rows</span>
	<button onclick={csv}>Download CSV</button>
</div>
<div class="scroll">
	<table>
		<thead>
			<tr>
				<th class="rank">#</th>
				{#each columns as c (c.key)}
					<th
						class:sticky={c.sticky}
						class:num={!c.sticky}
						title={c.title}
						aria-sort={sortKey === c.key ? (sortDesc ? 'descending' : 'ascending') : 'none'}
					>
						<button class="th" onclick={() => sortBy(c.key)}>
							{c.label}{sortKey === c.key ? (sortDesc ? ' ↓' : ' ↑') : ''}
						</button>
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each visible as row, i (i)}
				<tr
					class:clickable={!!onrowclick}
					class:hl={highlight?.(row)}
					onclick={() => onrowclick?.(row)}
				>
					<td class="rank">{i + 1}</td>
					{#each columns as c (c.key)}
						<td class:sticky={c.sticky} class:num={!c.sticky} style={shade(c, row[c.key])}>
							{c.fmt ? c.fmt(row[c.key]) : (row[c.key] ?? '–')}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.table-tools {
		margin-bottom: 0.5rem;
	}
	.count {
		font-size: 0.8rem;
		margin-left: auto;
	}
	.scroll {
		overflow: auto;
		max-height: 70vh;
		border: 1px solid var(--border);
		border-radius: 8px;
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
		padding: 0.3rem 0.6rem;
		white-space: nowrap;
		border-bottom: 1px solid var(--grid);
	}
	thead th {
		position: sticky;
		top: 0;
		background: var(--surface-2);
		z-index: 2;
		font-weight: 600;
		color: var(--text-secondary);
	}
	.th {
		all: unset;
		cursor: pointer;
	}
	.th:focus-visible {
		outline: 2px solid var(--accent);
	}
	.num {
		text-align: right;
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
		font-weight: 500;
	}
	thead th.sticky {
		background: var(--surface-2);
		z-index: 3;
	}
	tbody tr:hover td {
		background-color: var(--surface-2);
	}
	tr.clickable {
		cursor: pointer;
	}
	tr.hl td {
		box-shadow: inset 0 -2px 0 var(--accent);
	}
</style>
