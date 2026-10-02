<script lang="ts">
	// Round 2 of trying to beat the closing line: injuries, travel, weather, stakes, market
	// biases. Frozen choice, a reused test, a sealed live test, and per-game factor breakdowns.
	import { base } from '$app/paths';
	import { num, pct, signed, spread } from '$lib/format';
	import { Plot, plotStyle, gridX } from '$lib/plot';
	import type { BetScore, Lab2, Lab2Game, Lab2Upcoming } from '$lib/types';
	import CountUp from './CountUp.svelte';
	import DataTable, { type Column } from './DataTable.svelte';
	import PlotFigure from './Plot.svelte';
	import TeamBadge from './TeamBadge.svelte';

	let { lab }: { lab: Lab2 } = $props();

	const p = $derived(lab.protocol);
	const th = $derived(lab.chosen.threshold);
	const record = (s: BetScore) => `${s.wins}–${s.bets - s.wins}`;
	const verdict = (s: BetScore) =>
		!s.bets
			? 'no bets yet'
			: (s.win_rate ?? 0) > p.breakeven && (s.p_value ?? 1) < 0.05
				? `${pct(s.win_rate)}, p = ${num(s.p_value, 2)}: beating the line`
				: `${pct(s.win_rate)}, p = ${num(s.p_value, 2)}: no evidence of an edge`;

	/** "DAL +3.0" / "HOU −3.0": the line from one team's side. */
	function teamLine(g: Lab2Game, team: string): string {
		if (g.vegas == null) return team;
		const v = team === g.home ? -g.vegas : g.vegas;
		if (Math.abs(v) < 0.05) return `${team} PK`;
		return `${team} ${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`;
	}

	const games = $derived(
		[...lab.upcoming].sort(
			(a, b) => Math.abs(b.model - (b.vegas ?? b.model)) - Math.abs(a.model - (a.vegas ?? a.model))
		)
	);
	const scale = $derived(
		Math.max(3, ...lab.upcoming.flatMap((g) => g.factors.map((f) => Math.abs(f.points))))
	);
	const injuryFresh = $derived(
		p.teams_with_final_statuses != null && p.teams_with_final_statuses >= p.teams_playing * 0.8
	);
	const injuryLine = (list: Lab2Upcoming['injuries']['home']) =>
		list
			.slice(0, 4)
			.map((x) => `${x.name} (${x.pos}, ${x.status.toLowerCase()})`)
			.join(', ');

	// Does the line already price each factor? Effect beyond team ratings vs beyond the line.
	const checks = $derived(lab.market_check.filter((c) => c.vs_ratings_se < 3 && c.vs_line_se < 3));
	function checkChart(width: number) {
		const rows = checks.flatMap((c) => [
			{ label: c.label, what: 'Beyond team ratings', b: c.vs_ratings, se: c.vs_ratings_se },
			{ label: c.label, what: 'Beyond the closing line', b: c.vs_line, se: c.vs_line_se }
		]);
		return Plot.plot({
			width,
			height: checks.length * 34 + 60,
			style: plotStyle,
			marginLeft: width < 520 ? 112 : 210,
			x: { label: 'Home margin, points per unit →', grid: false },
			y: { label: null, domain: checks.map((c) => c.label), axis: null },
			color: {
				domain: ['Beyond team ratings', 'Beyond the closing line'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridX(),
				Plot.axisY({ tickSize: 0, label: null, lineWidth: width < 520 ? 9 : 30 }),
				Plot.ruleX([0], { stroke: 'var(--axis)' }),
				...(['Beyond team ratings', 'Beyond the closing line'] as const).flatMap((what, k) => {
					const sub = rows.filter((r) => r.what === what);
					const dy = k ? 5 : -5;
					return [
						Plot.ruleY(sub, {
							y: 'label',
							x1: (d: (typeof rows)[number]) => d.b - 1.96 * d.se,
							x2: (d: (typeof rows)[number]) => d.b + 1.96 * d.se,
							stroke: 'what',
							strokeWidth: 2,
							dy
						}),
						Plot.dot(sub, { y: 'label', x: 'b', fill: 'what', r: 4.5, dy })
					];
				}),
				Plot.tip(
					rows,
					Plot.pointer({
						y: 'label',
						x: 'b',
						title: (d: (typeof rows)[number]) =>
							`${d.label}\n${d.what}: ${signed(d.b, 2)} ± ${num(1.96 * d.se, 2)} pts per unit`
					})
				)
			]
		});
	}

	type SelRow = Lab2['selection'][number] & { chosen: boolean };
	const selRows = $derived<SelRow[]>(
		lab.selection.map((r) => ({
			...r,
			chosen: r.variant === lab.chosen.variant && r.threshold === lab.chosen.threshold
		}))
	);
	const selCols: Column<SelRow>[] = [
		{ key: 'variant', label: 'Variant', sticky: true },
		{
			key: 'threshold',
			label: 'Gap ≥',
			fmt: (v) => (v ? `${v} pts` : 'every game'),
			title: 'Bet only when the model and the line disagree by this much'
		},
		{
			key: 'fit_win_rate',
			label: 'Fit ATS',
			fmt: (v) => pct(v),
			title: 'Win rate against the spread on the fitting seasons'
		},
		{ key: 'val_bets', label: 'Val bets', fmt: num },
		{ key: 'val_win_rate', label: 'Val ATS', fmt: (v) => pct(v), better: 'high' },
		{
			key: 'val_p_value',
			label: 'p',
			fmt: (v) => num(v, 2),
			title: 'Chance of this validation win rate with no real edge'
		},
		{ key: 'val_mae', label: 'Val miss', fmt: (v) => num(v, 2), better: 'low' },
		{ key: 'val_vegas_mae', label: 'Vegas miss', fmt: (v) => num(v, 2) }
	];

	type LedgerRow = Lab2Game & {
		matchup: string;
		line: string;
		model_line: string;
		outcome: string;
	};
	const ledger = $derived<LedgerRow[]>(
		lab.live.games
			.filter((g) => g.bet)
			.map((g) => ({
				...g,
				matchup: `${g.away} @ ${g.home}`,
				line: spread(g.vegas, g.home, g.away),
				model_line: spread(g.model, g.home, g.away),
				outcome: g.won == null ? 'Push' : g.won ? 'Won' : 'Lost'
			}))
	);
	const ledgerCols: Column<LedgerRow>[] = [
		{ key: 'matchup', label: 'Game', sticky: true },
		{ key: 'week', label: 'Wk' },
		{ key: 'line', label: 'Vegas' },
		{ key: 'model_line', label: 'Model' },
		{ key: 'bet', label: 'Bet', team: true },
		{ key: 'outcome', label: 'Result' },
		{ key: 'sealed', label: 'After freeze', fmt: (v) => (v ? 'Yes' : 'No') }
	];
</script>

<section class="card" id="round2">
	<div class="eyebrow">Round 2</div>
	<h2>Everything the line was supposed to know</h2>
	<p class="sub">
		Round 1 concluded that the line knows things the model doesn't: injuries, weather, motivation.
		Round 2 adds them, plus the betting market's known biases, under the same rules: {Object.keys(
			lab.variants
		).length} variants fit on {p.fit_seasons.join('–')}, one chosen on {p.validate_seasons.join(
			'–'
		)}. The choice was
		<a href="https://github.com/Brandon-Kimberly/any-given-stat/commit/97932fd">committed</a>
		on {p.freeze_date}, before any round-2 test or live result existed. (The week table at the top
		of the page shows the round-3 forecast; round 2's lines are below.)
	</p>
	<div class="tiles">
		<div class="card tile">
			<div class="label">Frozen choice</div>
			<div class="value small-value">{lab.chosen.variant}</div>
			<div class="note">bet only when it disagrees with the line by {th}+ points</div>
		</div>
		<div class="card tile">
			<div class="label">Live test, {p.live_season} (after the freeze)</div>
			<div class="value">
				<CountUp text={lab.live.sealed.bets ? record(lab.live.sealed) : '0–0'} />
			</div>
			<div class="note">games after {p.freeze_date}: {verdict(lab.live.sealed)}</div>
		</div>
		<div class="card tile">
			<div class="label">Reused test, {p.test_seasons.join('–')}</div>
			<div class="value"><CountUp text={record(lab.test)} /></div>
			<div class="note">{verdict(lab.test)}. Not clean: round 1 had already looked here.</div>
		</div>
		<div class="card tile">
			<div class="label">{p.live_season} before the freeze</div>
			<div class="value"><CountUp text={record(lab.live.pre_freeze)} /></div>
			<div class="note">unseen when frozen, but already played</div>
		</div>
	</div>
	{#if !lab.selection_agrees}
		<div class="callout" role="note">
			Re-running the selection on today's data picks a different option (data revisions). The frozen
			choice is still the one being scored.
		</div>
	{/if}
</section>

{#if games.length}
	<section class="card">
		<div class="card-head">
			<h2>Week {games[0].week}, factor by factor</h2>
		</div>
		<p class="sub">
			What moves each line, in points toward the home team (right) or the visitor (left). Biggest
			disagreements with Vegas first; a ★ marks a bet under the frozen rule.
		</p>
		{#if !injuryFresh}
			<div class="callout info" role="note">
				Final injury statuses are in for {p.teams_with_final_statuses ?? 0} of {p.teams_playing} teams.
				Teams file them Friday (Wednesday for Thursday games). Until then, injuries count as 0 here, and
				lines will move when the site rebuilds.
			</div>
		{/if}
		<div class="games">
			{#each games as g (g.game_id)}
				<article class="game" class:bet={!!g.bet}>
					<header>
						<a href="{base}/game/?id={g.game_id}" class="mu">
							<TeamBadge team={g.away} /> <span class="muted">@</span>
							<TeamBadge team={g.home} />
						</a>
						{#if g.bet}<span class="star" title="Bet under the frozen rule"
								>★ {teamLine(g, g.bet)}</span
							>{/if}
					</header>
					<div class="lines">
						<span><span class="k">Model</span> <b>{spread(g.model, g.home, g.away)}</b></span>
						<span><span class="k">Vegas</span> <b>{spread(g.vegas, g.home, g.away)}</b></span>
					</div>
					<ul class="factors">
						{#each g.factors as f (f.feature)}
							<li>
								<span class="fl">{f.label}</span>
								<span class="track" aria-hidden="true">
									<span
										class="fb"
										class:pos={f.points > 0}
										style:width="{(Math.abs(f.points) / scale) * 50}%"
										style:left={f.points >= 0
											? '50%'
											: `${50 - (Math.abs(f.points) / scale) * 50}%`}
									></span>
								</span>
								<span class="fv"
									>{Math.abs(f.points) < 0.05
										? '0'
										: `${f.points > 0 ? g.home : g.away} +${Math.abs(f.points).toFixed(1)}`}</span
								>
							</li>
						{/each}
					</ul>
					{#if g.injuries.home.length || g.injuries.away.length}
						<p class="inj">
							{#if g.injuries.away.length}<b>{g.away}:</b> {injuryLine(g.injuries.away)}<br />{/if}
							{#if g.injuries.home.length}<b>{g.home}:</b> {injuryLine(g.injuries.home)}{/if}
						</p>
					{/if}
					<p class="wx muted">
						{#if g.weather.roof === 'dome' || g.weather.roof === 'closed'}Indoors{:else if g.weather.source === 'forecast'}Forecast
							{num(g.weather.temp)}°F, wind {num(g.weather.wind)} mph{:else}Outdoors, no forecast
							available{/if}
					</p>
				</article>
			{/each}
		</div>
	</section>
{/if}

<div class="grid-2">
	<section class="card">
		<h2>What does the line already price?</h2>
		<p class="sub">
			“Beyond team ratings”: how much each factor moves the final margin after ratings and the QB.
			“Beyond the closing line”: how much it still moves it after the line. Near 0 on the second
			means the line already prices it. Bars are 95% intervals; units are per starter-equivalent
			out, per day, per zone and so on.
		</p>
		<PlotFigure
			label="Factor effects beyond ratings and beyond the closing line"
			render={checkChart}
		/>
		<p class="muted small">
			All {p.fit_seasons[0]}–{p.test_seasons[1]} games, after the fact. With {lab.market_check
				.length}
			factors checked, expect about {Math.round(lab.market_check.length * 0.05)} to look significant (2+
			standard errors from zero) by chance alone.
		</p>
	</section>
	<section class="card">
		<h2>Live coefficients</h2>
		<p class="sub">
			The frozen variant refit on every completed season before {p.live_season} (a fixed rule, no choices).
			“Per unit” is one unit's effect (± 95% range). “Typical” is how many points it moves a usual game
			(one standard deviation).
		</p>
		<table class="coef">
			<thead><tr><th>Input</th><th>Per unit</th><th>Typical</th></tr></thead>
			<tbody>
				{#each lab.coefficients as c (c.feature)}
					<tr>
						<td>{c.label}</td>
						<td class="num"
							>{signed(c.beta, 2)} <span class="muted">± {num(1.96 * c.se, 2)}</span></td
						>
						<td class="num">{num(c.typical_points, 1)} pts</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="muted small">
			Injuries: players listed Out or Doubtful count fully; Questionable players count a quarter.
			Each is weighted by his usual snap share (over his last {p.role_games} games) and by how much of
			the team's recent play he was on the field for. That way a long absence the ratings already reflect
			isn't counted twice.
		</p>
	</section>
</div>

<section class="card">
	<h2>All {selRows.length} options on validation</h2>
	<p class="sub">
		The highlighted row was chosen: best validation win rate with {p.min_validate_bets}+ bets. Note
		how the flexible “Market + everything” model wins in fit and loses on validation: that's
		overfitting.
	</p>
	<DataTable
		rows={selRows}
		columns={selCols}
		sortKey="val_win_rate"
		highlight={(r) => r.chosen}
		filename="round2-selection"
	/>
</section>

{#if ledger.length}
	<section class="card">
		<h2>Every {p.live_season} bet</h2>
		<p class="sub">The running record. Bets after the freeze are the only clean evidence.</p>
		<DataTable
			rows={ledger}
			columns={ledgerCols}
			sortKey="week"
			showIndex={false}
			filename="round2-ledger"
			href={(r) => `${base}/game/?id=${r.game_id}`}
		/>
	</section>
{/if}

<style>
	.small-value {
		font-size: 1.05rem !important;
		line-height: 1.25;
	}
	.games {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
		gap: 0.75rem;
	}
	.game {
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 0.75rem 0.85rem;
		display: grid;
		gap: 0.45rem;
		align-content: start;
	}
	.game.bet {
		border-color: color-mix(in srgb, var(--fav) 60%, transparent);
		box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--fav) 40%, transparent);
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}
	.mu {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		text-decoration: none;
		color: inherit;
	}
	.star {
		font-size: 0.8rem;
		font-weight: 800;
		white-space: nowrap;
	}
	.lines {
		display: flex;
		gap: 1rem;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
	}
	.k {
		color: var(--text-muted);
		font-size: 0.78rem;
	}
	.factors {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.2rem;
	}
	.factors li {
		display: grid;
		grid-template-columns: 7.5rem 1fr 4.6rem;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.76rem;
	}
	.fl {
		color: var(--text-secondary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.track {
		position: relative;
		height: 10px;
		background:
			linear-gradient(var(--axis), var(--axis)) 50% / 1px 100% no-repeat,
			var(--surface-2);
		border-radius: 3px;
	}
	.fb {
		position: absolute;
		top: 1px;
		bottom: 1px;
		border-radius: 2px;
		background: var(--series-2);
		transition:
			width 0.3s var(--ease),
			left 0.3s var(--ease);
	}
	.fb.pos {
		background: var(--series-1);
	}
	.fv {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.inj {
		margin: 0;
		font-size: 0.76rem;
		color: var(--text-secondary);
	}
	.wx {
		margin: 0;
		font-size: 0.74rem;
	}
	.coef {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	.coef th {
		text-align: left;
		font-size: 0.75rem;
		color: var(--text-secondary);
		border-bottom: 1px solid var(--border);
		padding: 0 0.3rem 0.35rem;
	}
	.coef td {
		padding: 0.35rem 0.3rem;
		border-bottom: 1px solid var(--grid);
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.small {
		font-size: 0.78rem;
	}
</style>
