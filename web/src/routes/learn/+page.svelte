<script lang="ts">
	import { base } from '$app/paths';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { epa, num, pct } from '$lib/format';
	import { gridX, gridY, isNarrow, Plot, plotStyle, signedTick } from '$lib/plot';
	import { resource } from '$lib/resource.svelte';
	import { theme } from '$lib/theme.svelte';
	import type { Concepts, FourthBucket } from '$lib/types';

	const res = resource('concepts');
	const fourthRes = resource('fourth_downs');
	const c = $derived(res.value);

	const DOWNS = ['1st down', '2nd down', '3rd down', '4th down'];
	const SLOTS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'];
	const downLabel = (d: number) => DOWNS[d - 1];

	// Expected points at a spot: yards from own goal line (0..100).
	function epAt(down: number, fromOwn: number): number | null {
		const yl = 100 - fromOwn;
		return c?.ep_curve.find((r) => r.down === down && r.yardline_100 === yl)?.ep ?? null;
	}
	let spot = $state(25);
	const spotLabel = $derived(
		spot === 50 ? 'midfield' : spot < 50 ? `your own ${spot}` : `the opponent's ${100 - spot}`
	);

	function epChart(width: number) {
		const data = c!.ep_curve.map((r) => ({
			...r,
			own: 100 - r.yardline_100,
			label: downLabel(r.down)
		}));
		const narrow = isNarrow(width);
		const ends = [1, 2, 3, 4]
			.map((d) => data.filter((r) => r.down === d).sort((a, b) => b.own - a.own)[0])
			.filter(Boolean);
		return Plot.plot({
			width,
			height: narrow ? 300 : 380,
			style: plotStyle,
			marginRight: narrow ? 10 : 70,
			x: {
				domain: [0, 100],
				label: 'Field position →',
				ticks: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
				tickFormat: (v: number) =>
					v === 0 ? 'Own goal' : v === 100 ? 'TD' : v <= 50 ? `${v}` : `${100 - v}`
			},
			y: { label: '↑ Expected points for the offense', tickFormat: signedTick, domain: [-2.5, 7] },
			color: { domain: DOWNS, range: SLOTS, legend: true },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.ruleX([50], { stroke: 'var(--grid)' }),
				Plot.ruleX([spot], { stroke: 'var(--accent)', strokeDasharray: '4,3' }),
				Plot.line(data, { x: 'own', y: 'ep', stroke: 'label', strokeWidth: 2, curve: 'basis' }),
				Plot.text(narrow ? [] : ends, {
					x: 'own',
					y: 'ep',
					text: 'label',
					dx: 6,
					textAnchor: 'start',
					fill: 'var(--text-secondary)',
					fontSize: 11
				}),
				Plot.tip(
					data,
					Plot.pointer({
						lineWidth: 40,
						x: 'own',
						y: 'ep',
						title: (d: (typeof data)[number]) =>
							`${d.label} at ${d.own <= 50 ? 'own' : 'opp'} ${d.own <= 50 ? d.own : 100 - d.own}\nExpected points ${epa(d.ep, 2)} (${num(d.n)} plays)`
					})
				)
			]
		});
	}

	// Win probability heatmap: score margin x time left.
	let wpScore = $state(7);
	let wpMinutes = $state(5);
	const wpCell = $derived(
		c?.wp_grid.find(
			(r) =>
				r.score_diff === Math.floor(wpScore / 3) * 3 &&
				r.minutes_left === Math.floor(wpMinutes / 5) * 5
		)
	);
	const wpLookup = (score: number, minutes: number) =>
		c?.wp_grid.find((r) => r.score_diff === Math.floor(score / 3) * 3 && r.minutes_left === minutes)
			?.wp ?? null;

	function wpChart(width: number) {
		const mid = theme.dark ? '#383835' : '#f0efec';
		const narrow = isNarrow(width);
		return Plot.plot({
			width,
			height: narrow ? 320 : 400,
			style: plotStyle,
			marginLeft: 52,
			x: {
				label: 'Minutes left in the game →',
				reverse: true,
				ticks: [55, 45, 35, 25, 15, 5],
				tickFormat: (m: number) => `${m + 5}`
			},
			y: {
				label: '↑ Offense score margin',
				domain: [...new Set(c!.wp_grid.map((r) => r.score_diff))].sort((a, b) => b - a),
				tickFormat: (v: number) => (v > 0 ? `+${v}` : `${v}`)
			},
			color: {
				type: 'linear',
				domain: [0, 0.5, 1],
				range: [theme.dark ? '#e66767' : '#e34948', mid, theme.dark ? '#3987e5' : '#2a78d6'],
				legend: true,
				label: 'Offense win probability',
				tickFormat: '.0%'
			},
			marks: [
				Plot.cell(c!.wp_grid, {
					x: 'minutes_left',
					y: 'score_diff',
					fill: 'wp',
					inset: 0.5
				}),
				Plot.tip(
					c!.wp_grid,
					Plot.pointer({
						lineWidth: 40,
						x: 'minutes_left',
						y: 'score_diff',
						title: (d: Concepts['wp_grid'][number]) =>
							`Margin ${d.score_diff >= 0 ? '+' : ''}${d.score_diff} to ${d.score_diff + 2}, ${d.minutes_left}–${d.minutes_left + 5} min left\nWins ${pct(d.wp, 0)} of the time (${num(d.n)} plays)`
					})
				)
			]
		});
	}

	// Pass vs run by situation.
	const sitLabel = (r: Concepts['situations'][number]) => {
		const n = ['1st', '2nd', '3rd'][r.down - 1];
		return `${n} & ${r.distance}`;
	};
	function sitChart(width: number) {
		const rows = [...c!.situations].sort((a, b) => a.down - b.down || a.ord - b.ord);
		const long = rows.flatMap((r) => [
			{ s: sitLabel(r), v: r.pass_epa, kind: 'Pass', rate: r.pass_rate },
			{ s: sitLabel(r), v: r.run_epa, kind: 'Run', rate: r.pass_rate }
		]);
		return Plot.plot({
			width,
			height: rows.length * 26 + 60,
			style: plotStyle,
			marginLeft: 76,
			x: { label: 'EPA per play →', tickFormat: '+.2f', grid: true },
			y: { domain: rows.map(sitLabel), label: null },
			color: {
				domain: ['Pass', 'Run'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				Plot.ruleX([0], { stroke: 'var(--axis)' }),
				Plot.ruleY(rows, {
					y: sitLabel,
					x1: (r: Concepts['situations'][number]) => Math.min(r.pass_epa ?? 0, r.run_epa ?? 0),
					x2: (r: Concepts['situations'][number]) => Math.max(r.pass_epa ?? 0, r.run_epa ?? 0),
					stroke: 'var(--grid)',
					strokeWidth: 3
				}),
				Plot.dot(long, {
					x: 'v',
					y: 's',
					fill: 'kind',
					r: 5.5,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.tip(
					long,
					Plot.pointer({
						lineWidth: 40,
						x: 'v',
						y: 's',
						title: (d: (typeof long)[number]) =>
							`${d.s}: ${d.kind} ${epa(d.v)} EPA/play\nTeams pass ${pct(d.rate, 0)} of the time here`
					})
				)
			]
		});
	}
	const passWins = $derived(
		c ? c.situations.filter((r) => (r.pass_epa ?? -9) > (r.run_epa ?? -9)).length : 0
	);

	function histChart(width: number) {
		const data = c!.epa_hist.map((h) => ({ ...h, mid: h.bin + 0.125 }));
		return Plot.plot({
			width,
			height: 300,
			style: plotStyle,
			x: { label: 'EPA on the play →', domain: [-4, 4.25], ticks: [-4, -3, -2, -1, 0, 1, 2, 3, 4] },
			y: { label: '↑ Share of plays', tickFormat: '.0%' },
			color: {
				domain: ['Pass', 'Run'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridY(),
				Plot.ruleX([0], { stroke: 'var(--axis)' }),
				Plot.areaY(data, { x: 'mid', y: 'share', fill: 'kind', fillOpacity: 0.12, curve: 'step' }),
				Plot.line(data, { x: 'mid', y: 'share', stroke: 'kind', strokeWidth: 2, curve: 'step' }),
				Plot.tip(
					data,
					Plot.pointer({
						lineWidth: 40,
						x: 'mid',
						y: 'share',
						title: (d: (typeof data)[number]) =>
							`${d.kind}: ${pct(d.share, 1)} of plays between ${d.bin} and ${d.bin + 0.25} EPA`
					})
				)
			]
		});
	}
	const tail = $derived.by(() => {
		if (!c) return null;
		const share = (k: string, f: (b: number) => boolean) =>
			c.epa_hist.filter((h) => h.kind === k && f(h.bin)).reduce((a, h) => a + h.share, 0);
		return {
			passBig: share('Pass', (b) => b >= 2),
			runBig: share('Run', (b) => b >= 2),
			passBad: share('Pass', (b) => b < -2),
			runBad: share('Run', (b) => b < -2)
		};
	});

	function convChart(width: number) {
		return Plot.plot({
			width,
			height: 260,
			style: plotStyle,
			x: { label: 'Yards to go on 4th down', ticks: c!.fourth.conversion.map((r) => r.ydstogo) },
			y: { label: '↑ Converted', domain: [0, 1], tickFormat: '.0%' },
			marks: [
				gridY(),
				Plot.barY(c!.fourth.conversion, {
					x: 'ydstogo',
					y: 'rate',
					fill: 'var(--series-1)',
					rx: 4,
					insetLeft: 4,
					insetRight: 4
				}),
				Plot.text(c!.fourth.conversion, {
					x: 'ydstogo',
					y: 'rate',
					text: (r: { rate: number }) => pct(r.rate, 0),
					dy: -8,
					fill: 'var(--text-secondary)',
					fontSize: 10.5
				}),
				Plot.tip(
					c!.fourth.conversion,
					Plot.pointerX({
						lineWidth: 40,
						x: 'ydstogo',
						y: 'rate',
						title: (r: { ydstogo: number; rate: number; attempts: number }) =>
							`4th & ${r.ydstogo}: ${pct(r.rate)} converted (${num(r.attempts)} tries)`
					})
				)
			]
		});
	}
	function fgChart(width: number) {
		return Plot.plot({
			width,
			height: 260,
			style: plotStyle,
			r: { type: 'identity' }, // radii below are pixels; Plot would rescale them
			x: { label: 'Kick distance (yards) →' },
			y: { label: '↑ Made', domain: [0, 1], tickFormat: '.0%' },
			marks: [
				gridY(),
				Plot.line(c!.fourth.field_goals, {
					x: 'distance',
					y: 'made_rate',
					stroke: 'var(--series-2)',
					strokeWidth: 2,
					curve: 'monotone-x'
				}),
				Plot.dot(c!.fourth.field_goals, {
					x: 'distance',
					y: 'made_rate',
					r: (d: { attempts: number }) => Math.max(2, Math.sqrt(d.attempts) / 3),
					fill: 'var(--series-2)',
					fillOpacity: 0.5
				}),
				Plot.tip(
					c!.fourth.field_goals,
					Plot.pointerX({
						lineWidth: 40,
						x: 'distance',
						y: 'made_rate',
						title: (d: { distance: number; made_rate: number; attempts: number }) =>
							`${d.distance} yards: ${pct(d.made_rate)} made (${num(d.attempts)} kicks)`
					})
				)
			]
		});
	}

	const DECISION = { go: 'Go for it', punt: 'Punt', fg: 'Field goal' } as const;
	const SHORT = { go: 'GO', punt: 'P', fg: 'FG' } as const;
	const clear = (d: FourthBucket) => d.margin == null || d.margin >= 0.3;
	function decisionChart(width: number) {
		const b = fourthRes.value!.buckets.filter((x) => x.best);
		const narrow = isNarrow(width);
		const fields = [...new Map(b.map((x) => [x.field_ord, x.field])).entries()]
			.sort((a, z) => a[0] - z[0])
			.map(([, f]) => f);
		const dists = [...new Map(b.map((x) => [x.dist_ord, x.distance])).entries()]
			.sort((a, z) => a[0] - z[0])
			.map(([, d]) => d);
		return Plot.plot({
			width,
			height: dists.length * 46 + 80,
			style: plotStyle,
			marginLeft: 56,
			marginBottom: narrow ? 60 : 40,
			x: {
				domain: fields,
				label: 'Field position (offense moving right) →',
				tickRotate: narrow ? -40 : 0
			},
			y: { domain: dists, label: '↑ Yards to go' },
			color: {
				domain: Object.values(DECISION),
				range: ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'],
				legend: true
			},
			marks: [
				Plot.cell(b, {
					x: 'field',
					y: 'distance',
					fill: (d: FourthBucket) => DECISION[d.best!],
					fillOpacity: (d: FourthBucket) =>
						d.margin == null ? 0.35 : Math.min(1, 0.35 + d.margin),
					inset: 1.5,
					rx: 4
				}),
				Plot.text(b, {
					x: 'field',
					y: 'distance',
					text: (d: FourthBucket) =>
						narrow ? d.best!.toUpperCase().slice(0, 2) : DECISION[d.best!],
					fill: '#fff',
					fontWeight: 700,
					fontSize: narrow ? 9 : 10.5
				}),
				Plot.tip(
					b,
					Plot.pointer({
						lineWidth: 44,
						x: 'field',
						y: 'distance',
						title: (d: FourthBucket) =>
							`4th & ${d.distance}, ${d.field}\nGo ${epa(d.go_epa)} (${num(d.go_n)}) · Punt ${epa(d.punt_epa)} (${num(d.punt_n)}) · FG ${epa(d.fg_epa)} (${num(d.fg_n)})\nBest: ${DECISION[d.best!]}${d.margin != null ? ` by ${num(d.margin, 2)} EPA` : ''}`
					})
				)
			]
		});
	}
</script>

<svelte:head><title>How football works, in numbers · Any Given Stat</title></svelte:head>

<section class="hero">
	<div class="eyebrow" style="color: rgba(255,255,255,0.75)">Learn</div>
	<h1>How football works, in numbers</h1>
	<p class="lede">
		Five ideas that explain most of modern football analytics, each measured from every play
		{c ? `${c.seasons[0]}–${c.seasons[1]}` : 'since 2016'}. Understand these and you understand why
		coaches go for it more, pass more, and why some teams' records lie.
	</p>
	<nav class="toc" aria-label="Lessons">
		<a href="#ep">1 · Expected points</a>
		<a href="#wp">2 · Win probability</a>
		<a href="#passrun">3 · Pass vs run</a>
		<a href="#tails">4 · Big plays</a>
		<a href="#fourth">5 · Fourth down</a>
	</nav>
</section>

{#if res.error}
	<LoadError message={res.error} />
{:else if !c}
	<Skeleton height={380} />
{:else}
	<section class="card lesson" id="ep">
		<div class="num-badge">1</div>
		<h2>Every spot on the field is worth points</h2>
		<p>
			Before the snap, a team's situation already has a value: the average number of points the next
			score will be worth to them. That's <strong>expected points (EP)</strong>. A play's
			<strong>EPA</strong> (expected points added) is simply EP after the play minus EP before. That's
			why EPA beats yards: 4 yards on 3rd and 3 is a big win; 4 yards on 3rd and 10 is a loss.
		</p>
		<div class="try">
			<label class="field">
				Ball on
				<input type="range" min="1" max="99" bind:value={spot} aria-label="Field position" />
				<b>{spotLabel}</b>
			</label>
			<div class="readout">
				{#each [1, 2, 3, 4] as d (d)}
					{@const v = epAt(d, spot)}
					<div><span class="k">{DOWNS[d - 1]}</span><b>{v == null ? '–' : epa(v, 2)}</b></div>
				{/each}
			</div>
		</div>
		<PlotFigure label="Expected points by field position and down" render={epChart} />
		<p class="takeaway">
			<strong>Takeaway:</strong> 1st and 10 at your own 25 is worth about {epa(epAt(1, 25), 1)} points;
			at midfield {epa(epAt(1, 50), 1)}; at the opponent's 25 {epa(epAt(1, 75), 1)}. Pinned at your
			own goal line it's negative: the other team is more likely to score next. Each down you burn
			costs roughly a point, which is why 3rd down matters so much.
		</p>
	</section>

	<section class="card lesson" id="wp">
		<div class="num-badge">2</div>
		<h2>Win probability: score and clock together</h2>
		<p>
			How often does the team with the ball go on to win, given the score and the time left? Read
			across a row to watch the same lead get safer as the clock runs out. This is the backbone of
			every live win-probability chart, including the <a href="{base}/games/">game charts</a> on this
			site.
		</p>
		<div class="try">
			<label class="field"
				>Lead <input type="range" min="-21" max="21" bind:value={wpScore} /><b
					>{wpScore > 0 ? `up ${wpScore}` : wpScore < 0 ? `down ${-wpScore}` : 'tied'}</b
				></label
			>
			<label class="field"
				>Time left <input type="range" min="0" max="59" bind:value={wpMinutes} /><b
					>{wpMinutes} min</b
				></label
			>
			<div class="readout one">
				<span class="k">Teams in this spot won</span><b>{wpCell ? pct(wpCell.wp, 0) : '–'}</b>
			</div>
		</div>
		<PlotFigure label="Win probability by score margin and time left" render={wpChart} />
		<p class="takeaway">
			<strong>Takeaway:</strong> a one-score lead early is close to a coin flip with a small edge; the
			same lead with five minutes left is worth far more. Comebacks feel common because you remember them,
			but the map shows how rare they are.
		</p>
	</section>

	<section class="card lesson" id="passrun">
		<div class="num-badge">3</div>
		<h2>Why everyone passes more now</h2>
		<p>
			EPA per play for passes (including sacks and scrambles) and designed runs, by down and
			distance, with garbage time excluded.
		</p>
		<PlotFigure label="Pass vs run EPA by down and distance" render={sitChart} />
		<p class="takeaway">
			<strong>Takeaway:</strong> passing produced more EPA per play in {passWins} of {c.situations
				.length} situations. Running holds up mainly in short yardage, where it's efficient and safe.
			Teams still run often on early downs, which is why “pass rate over expected” is a coaching-aggressiveness
			stat.
		</p>
	</section>

	<section class="card lesson" id="tails">
		<div class="num-badge">4</div>
		<h2>Passing is a high-variance bet that pays</h2>
		<p>
			The distribution of EPA on individual plays. Most plays are small; the tails decide games.
		</p>
		<PlotFigure label="Distribution of EPA per play, pass vs run" render={histChart} />
		{#if tail}
			<p class="takeaway">
				<strong>Takeaway:</strong>
				{pct(tail.passBig, 1)} of passes gain 2+ EPA versus {pct(tail.runBig, 1)} of runs, but
				{pct(tail.passBad, 1)} of passes lose 2+ EPA (sacks, interceptions) versus {pct(
					tail.runBad,
					1
				)} of runs. Passing has fatter tails on both ends and a higher average. That's why a quarterback
				who avoids the bad tail (sacks, picks) is so valuable.
			</p>
		{/if}
	</section>

	<section class="card lesson" id="fourth">
		<div class="num-badge">5</div>
		<h2>Fourth down: the math coaches used to ignore</h2>
		<p>
			Going for it is a bet: the chance of converting times what you gain, against what you give up
			by punting or kicking. Here are the two inputs, then the empirical answer.
		</p>
		<div class="grid-2">
			<div>
				<h3>How often 4th downs convert</h3>
				<PlotFigure label="4th down conversion rate by yards to go" render={convChart} />
			</div>
			<div>
				<h3>Field goal range</h3>
				<PlotFigure label="Field goal make rate by distance" render={fgChart} />
			</div>
		</div>
		{#if fourthRes.value}
			<h3 style="margin-top: 1rem">What actually paid off</h3>
			<p class="muted small">
				For each distance and field position, the decision with the highest average EPA over
				{fourthRes.value.meta.reference_seasons?.join('–')}. Solid = a clear edge (0.3+ EPA, or the
				only option with data); outlined with “?” = a close call.
				{fourthRes.value.meta.caveat}
			</p>
			<PlotFigure
				label="Best 4th down decision by distance and field position"
				render={decisionChart}
			/>
			<p class="takeaway">
				<strong>Takeaway:</strong> on 4th and 1 or 2, going for it beats punting almost everywhere
				past your own 20. See which teams follow the math on
				<a href="{base}/fourth/">Fourth downs</a>.
			</p>
		{/if}
	</section>

	<section class="card lesson">
		<h2>Next: which numbers to trust</h2>
		<p>
			These ideas tell you what matters. <a href="{base}/stability/">Signal vs noise</a> tells you
			which stats are stable enough to believe, and <a href="{base}/glossary/">the glossary</a>
			defines every metric on the site.
		</p>
	</section>
{/if}

<style>
	.toc {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 1rem;
	}
	.toc a {
		padding: 0.3rem 0.7rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		border: 1px solid rgba(255, 255, 255, 0.22);
		text-decoration: none;
		font-size: 0.85rem;
		font-weight: 600;
	}
	.toc a:hover {
		background: rgba(255, 255, 255, 0.22);
	}
	.lesson {
		position: relative;
		padding-left: clamp(1.15rem, 0.8rem + 3vw, 4rem);
	}
	.lesson > p {
		max-width: 78ch;
	}
	.num-badge {
		position: absolute;
		left: 1.1rem;
		top: 1.05rem;
		width: 30px;
		height: 30px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: var(--accent-fill);
		color: #fff;
		font: 800 0.95rem var(--display);
	}
	@media (max-width: 700px) {
		.num-badge {
			position: static;
			margin-bottom: 0.5rem;
		}
	}
	.try {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.5rem;
		align-items: center;
		padding: 0.75rem 0.9rem;
		margin: 0.25rem 0 1rem;
		background: var(--surface-2);
		border-radius: 12px;
	}
	.try input[type='range'] {
		width: min(220px, 50vw);
		accent-color: var(--accent);
	}
	.readout {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		font-variant-numeric: tabular-nums;
	}
	.readout > div {
		display: grid;
	}
	.readout.one {
		align-items: baseline;
		gap: 0.5rem;
	}
	.readout b {
		font: 800 1.25rem var(--display);
	}
	.k {
		font-size: 0.75rem;
		color: var(--text-muted);
	}
	.takeaway {
		margin: 0.9rem 0 0;
		padding: 0.75rem 0.9rem;
		border-left: 3px solid var(--accent);
		background: var(--accent-soft);
		border-radius: 0 10px 10px 0;
		font-size: 0.93rem;
	}
	.small {
		font-size: 0.82rem;
	}
</style>
