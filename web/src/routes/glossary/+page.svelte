<script lang="ts">
	import { base } from '$app/paths';
	import PageToc from '$lib/components/PageToc.svelte';

	// Other pages deep-link to /glossary/#<id>. Keep ids stable; `aliases` are extra anchors
	// (readable slugs like #epa-per-play) that land on the same term.
	interface Term {
		id: string;
		term: string;
		def: string;
		see?: [string, string];
		aliases?: string[];
	}
	const groups: { id: string; name: string; short: string; terms: Term[] }[] = [
		{
			id: 'core',
			short: 'Core',
			name: 'Core concepts',
			terms: [
				{
					id: 'ep',
					term: 'Expected points (EP)',
					def: 'The average net points of the next score from a given down, distance and field position. 1st and 10 at your own 25 is worth about +1.1; at the opponent’s 25 about +4.2. From the nflfastR model.',
					see: ['/learn/#ep', 'See the curve'],
					aliases: ['expected-points']
				},
				{
					id: 'epa',
					term: 'EPA (expected points added)',
					def: 'EP after a play minus EP before it. It credits a 4-yard gain on 3rd and 3 and penalizes a 4-yard gain on 3rd and 10, which yards can’t do. Summed over a drive, EPA roughly equals the points scored. EPA per play averages it over plays (runs and dropbacks, no special teams).',
					aliases: ['epa-per-play', 'expected-points-added']
				},
				{
					id: 'success',
					term: 'Success rate',
					def: 'Share of plays with positive EPA. Less sensitive than EPA to a few huge plays, so it measures consistency.',
					aliases: ['success-rate']
				},
				{
					id: 'wp',
					term: 'Win probability (WP)',
					def: 'The chance the team with the ball wins, from the score, time, field position, timeouts and the pre-game Vegas line (nflfastR model). WPA is the change in WP on a play.',
					see: ['/learn/#wp', 'See the map'],
					aliases: ['win-probability', 'wpa']
				},
				{
					id: 'garbage',
					term: 'Garbage time',
					def: 'Plays where the offense’s win probability is below 10% or above 90%. Excluding them stops a fourth-quarter blowout from padding (or sinking) a team’s numbers. Pages with a “No garbage time / All plays” toggle use this filter.',
					aliases: ['garbage-time']
				},
				{
					id: 'explosive',
					term: 'Explosive play',
					def: 'A pass of 20+ yards or a run of 10+ yards.',
					aliases: ['explosive-play']
				},
				{
					id: 'dropback',
					term: 'Dropback',
					def: 'A pass play from the quarterback’s side: attempts, sacks and scrambles all count. Per-dropback stats charge sacks to the passing game.'
				},
				{
					id: 'designed-run',
					term: 'Designed run',
					def: 'A called running play. QB scrambles are dropbacks, not runs, so rushing stats on this site leave them out.'
				},
				{
					id: 'red-zone',
					term: 'Red zone trip / red zone TD rate',
					def: 'A drive that reaches the opponent’s 20-yard line. Red zone TD rate is the share of those trips that end in a touchdown; it is one of the noisiest team stats.',
					aliases: ['red-zone-td-rate']
				},
				{
					id: 'drive-points',
					term: 'Points per drive',
					def: 'Points scored per offensive drive, counting a touchdown as 7 and a field goal as 3.'
				}
			]
		},
		{
			id: 'players',
			short: 'Players',
			name: 'Quarterbacks, receivers and rushers',
			terms: [
				{
					id: 'epa-db',
					term: 'EPA per dropback',
					def: 'EPA credited to the QB on every dropback: completions, incompletions, sacks and scrambles. If a receiver fumbles, the QB keeps the value of the catch.',
					aliases: ['epa-per-dropback', 'qb-epa']
				},
				{
					id: 'cpoe',
					term: 'CPOE',
					def: 'Completion percentage over expected. The nflfastR completion model sets an expected completion rate from air yards, target location, down, distance and more; CPOE is actual minus expected, in percentage points.',
					aliases: ['completion-percentage-over-expected']
				},
				{
					id: 'adot',
					term: 'aDOT',
					def: 'Average depth of target: mean air yards on pass attempts.',
					aliases: ['average-depth-of-target']
				},
				{
					id: 'wopr',
					term: 'Target share / air yards share / WOPR',
					def: 'A receiver’s share of the team’s targets and of its total air yards. WOPR = 1.5 × target share + 0.7 × air yards share (Josh Hermsmeyer).',
					aliases: ['target-share', 'air-yards-share']
				},
				{
					id: 'catch-oe',
					term: 'Catch rate over expected',
					def: 'A receiver’s catch rate minus the nflfastR completion probability of his targets, in percentage points. Positive means he caught more of his targets than their difficulty predicts.'
				},
				{
					id: 'stuff',
					term: 'Stuff rate',
					def: 'Share of designed runs that gain zero yards or lose yards. Lower is better for the runner.',
					aliases: ['stuff-rate']
				},
				{
					id: 'yacoe',
					term: 'YAC over expected',
					def: 'Yards after catch minus the nflfastR xYAC model’s expectation for that catch.',
					aliases: ['yac-over-expected', 'xyac']
				},
				{
					id: 'ci',
					term: '95% confidence interval',
					def: 'The range that likely holds a QB’s true EPA/dropback: mean ± 1.96 × SD / √n. EPA has fat tails (rare huge plays), so treat it as a rough guide.'
				},
				{
					id: 'percentile',
					term: 'Percentile (player profiles)',
					def: 'Share of qualified players at the position that season who were worse. Qualified = at least 40% of the season leader’s volume (dropbacks, targets or carries), so it works mid-season too.'
				}
			]
		},
		{
			id: 'teams',
			short: 'Teams & models',
			name: 'Teams and models',
			terms: [
				{
					id: 'proe',
					term: 'PROE',
					def: 'Pass rate over expected. nflfastR’s xpass model gives the probability a team passes given down, distance, score, time and field position. PROE = actual pass rate − expected. Positive means pass-happy.',
					aliases: ['pass-rate-over-expected']
				},
				{
					id: 'adjusted',
					term: 'Opponent-adjusted EPA',
					def: 'Each team-game’s EPA/play is modeled as league average + offense rating + opposing defense rating + home field, fit by ridge regression, which pulls extreme ratings toward average. The team ratings are what’s left after accounting for who they played and where.'
				},
				{
					id: 'power',
					term: 'Power rating',
					def: 'The predictive version of the adjusted rating: recent games count more (a game 16 weeks old counts half), and last season’s games carry it early in the year. Expressed in points vs an average team on a neutral field. It has two parts: the EPA rating above and a points rating.',
					see: ['/ratings/', 'Power ratings'],
					aliases: ['power-rating', 'ratings']
				},
				{
					id: 'points-rating',
					term: 'Points rating',
					def: 'A team rating built from final margins instead of EPA. Noisier, but it captures special teams and the full value of turnovers. The forecast uses both.'
				},
				{
					id: 'forecast',
					term: 'Site forecast (model margin)',
					def: 'The predicted margin for a game: the gap in EPA and points ratings plus home field, the starting-QB adjustment and an injury adjustment. Chosen for accuracy on past seasons and frozen before it was tested.',
					see: ['/predictions/', 'Predictions']
				},
				{
					id: 'blend',
					term: 'Best estimate (blend)',
					def: 'The Vegas line moved part of the way toward the model (line + k × (model − line)), with the share k fit on past seasons. Markets are hard to beat, so the blend stays close to the line.',
					aliases: ['best-estimate', 'market-blend']
				},
				{
					id: 'qb-adj',
					term: 'QB adjustment',
					def: 'For each game, the listed starter’s EPA per dropback (pulled toward a below-average baseline) compared with the QBs behind the team’s rating, times 35 dropbacks and a fitted weight. Catches injuries, rest and returns.'
				},
				{
					id: 'pythag',
					term: 'Pythagorean wins',
					def: 'Expected win % = PF^2.37 / (PF^2.37 + PA^2.37), times games played. Point differential predicts future records better than record does.',
					see: ['/luck/', 'Luck'],
					aliases: ['pythagorean-wins', 'pythagorean']
				},
				{
					id: 'one-score',
					term: 'One-score game',
					def: 'Decided by 8 points or fewer. Records in these games are mostly noise and regress hard.',
					aliases: ['one-score-game']
				},
				{
					id: 'fourth',
					term: 'Fourth-down decision model',
					def: 'For each distance and field-position bucket, the average EPA teams actually got from going for it, punting and kicking (competitive games only). The best is the recommendation; “EPA left on the field” sums how much worse each real decision was. Biased toward going for it, since teams go more when they expect to convert.',
					see: ['/fourth/', 'Fourth downs'],
					aliases: ['fourth-down', 'epa-left-on-the-field']
				},
				{
					id: 'clear-go',
					term: 'Clear-go spot',
					def: 'A 4th down where going for it beat the best kicking option by 0.3+ EPA.'
				},
				{
					id: 'excitement',
					term: 'Excitement index',
					def: 'Total win-probability movement over a game (the sum of every play’s absolute WP change). The median game since 2016 scores about 3.7; the top 10% score 5.8 or more.',
					see: ['/games/', 'Games'],
					aliases: ['excitement-index']
				},
				{
					id: 'playoff-odds',
					term: 'Playoff odds',
					def: 'The share of 10,000 simulated rest-of-seasons in which a team makes the playoffs (or wins its division, earns a bye, wins the Super Bowl). Each unplayed game is drawn around the site’s forecast, and each simulation also draws how wrong each team’s rating might be.',
					see: ['/odds/', 'Playoff odds']
				}
			]
		},
		{
			id: 'stats',
			short: 'Betting & stats',
			name: 'Betting and statistics',
			terms: [
				{
					id: 'ats',
					term: 'Against the spread (ATS)',
					def: 'Results measured against the point spread: a team covers if it beats the spread. For the model, it means betting its side of the Vegas line. At standard −110 odds you must win 52.4% to break even.',
					aliases: ['against-the-spread']
				},
				{
					id: 'spread',
					term: 'Point spread',
					def: 'The Vegas line: how many points the favorite is expected to win by. It is the market’s forecast of the margin, and the bar any model has to clear.',
					aliases: ['vegas-line', 'point-spread']
				},
				{
					id: 'closing-line',
					term: 'Closing line',
					def: 'The Vegas spread at kickoff, the sharpest public forecast. Backtests are scored against it.',
					aliases: ['clv']
				},
				{
					id: 'calibration',
					term: 'Calibration',
					def: 'Whether predicted probabilities mean what they say: of all games given a 70% win probability, about 70% should be won.'
				},
				{
					id: 'average-miss',
					term: 'Average miss / RMSE',
					def: 'Average miss is the mean number of points a predicted margin is off by. RMSE (root-mean-square error) is similar but weighs big misses more. Lower is better for both.',
					aliases: ['rmse', 'mae']
				},
				{
					id: 'brier',
					term: 'Brier score',
					def: 'Average squared error of probability forecasts: 0 is perfect, lower is better. Skill compares it with a naive guess, such as giving every team the league-wide rate.',
					aliases: ['brier-score', 'skill']
				},
				{
					id: 'log-loss',
					term: 'Log loss',
					def: 'Another score for win probabilities that punishes confident wrong calls hard. Lower is better.'
				},
				{
					id: 'p-value',
					term: 'p-value',
					def: 'The chance of a result at least this good if there were no real edge. Small (under 0.05) suggests something real; it is not proof.'
				},
				{
					id: 'funnel',
					term: 'Funnel',
					def: 'The shaded range where 95% of results would land by chance alone. It narrows as samples grow, so a dot outside it is unusual for its sample size.',
					aliases: ['funnel-plot']
				},
				{
					id: 'split-half',
					term: 'Split-half r / season reliability',
					def: 'Split-half r is the correlation of a stat between odd and even weeks of the same season. Spearman-Brown, 2r / (1 + r), turns it into full-season reliability: the share of the variation between teams that is real.',
					see: ['/stability/', 'Signal vs noise'],
					aliases: ['reliability', 'split-half-reliability', 'stability']
				},
				{
					id: 'half-signal',
					term: 'n for 50% signal',
					def: 'The sample size at which a stat is half skill, half noise: n_half × (1 − r) / r, where n_half is the sample in each half-season. Below it, regress hard toward the league average.'
				},
				{
					id: 'yoy',
					term: 'Year-over-year r',
					def: 'Correlation of a stat between one season and the next. It also includes real change (roster turnover, coaching), so it is a lower bound on how stable the underlying skill is.',
					aliases: ['year-over-year']
				},
				{
					id: 'holdout',
					term: 'Fit / validate / test',
					def: 'How the prediction model is kept honest: coefficients are fit on 2017–2021, choices are made on 2022–2023, and 2024–2025 is scored once at the end. Later experiments reuse 2024–2025 and label it a reused test. A model judged on the data it was tuned on always looks better than it is.'
				},
				{
					id: 'live-test',
					term: 'Reused test / live test',
					def: 'A reused test is seasons an earlier experiment already looked at, so it is not clean. A live test is games played after a model choice was frozen (committed publicly), the only fully clean evidence.'
				}
			]
		}
	];

	let q = $state('');
	const shown = $derived(
		groups
			.map((g) => ({
				...g,
				terms: g.terms.filter((t) =>
					`${t.term} ${t.def}`.toLowerCase().includes(q.trim().toLowerCase())
				)
			}))
			.filter((g) => g.terms.length)
	);
</script>

<svelte:head><title>Glossary · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Learn</div>
	<h1>Glossary</h1>
	<p class="lede">
		What the numbers mean and where they come from. All play data is from
		<a href="https://github.com/nflverse/nflverse-data">nflverse</a>; regular season and scrimmage
		plays only (no kneels, spikes, special teams or plays wiped out by penalty) unless noted.
	</p>
</section>

<input
	class="filter"
	type="search"
	placeholder="Filter terms…"
	bind:value={q}
	aria-label="Filter glossary"
/>

<PageToc items={shown.map((g) => ({ id: g.id, label: g.short }))} />

{#each shown as g (g.name)}
	<section class="card" id={g.id}>
		<h2>{g.name}</h2>
		<dl>
			{#each g.terms as t (t.id)}
				<div class="term" id={t.id}>
					<dt>
						{#each t.aliases ?? [] as a (a)}<span class="alias" id={a}></span>{/each}<a
							class="anchor"
							href="#{t.id}"
							aria-label="Link to {t.term}">#</a
						>{t.term}
					</dt>
					<dd>
						{t.def}
						{#if t.see}<a href="{base}{t.see[0]}">{t.see[1]} →</a>{/if}
					</dd>
				</div>
			{/each}
		</dl>
	</section>
{:else}
	<p class="muted">No terms match “{q}”.</p>
{/each}

<style>
	.filter {
		max-width: 360px;
		width: 100%;
	}
	.filter {
		margin-bottom: 0.75rem;
	}
	/* One column of readable measure on phones; a two-column term grid on wide screens. */
	dl {
		margin: 0.75rem 0 0;
		display: grid;
		gap: 1rem 2.5rem;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 440px), 1fr));
		align-items: start;
	}
	.term {
		position: relative;
		scroll-margin-top: 130px;
	}
	/* Extra anchors for a term (readable slugs); invisible, at the top of the term. */
	.alias {
		position: absolute;
		top: 0;
		scroll-margin-top: 130px;
	}
	.term:target,
	.term:has(.alias:target) {
		background: var(--accent-soft);
		border-radius: 8px;
		margin: -0.4rem;
		padding: 0.4rem;
	}
	dt {
		font-weight: 700;
		position: relative;
	}
	.anchor {
		position: absolute;
		left: -1.5rem;
		min-width: 24px;
		text-align: center;
		opacity: 0;
		text-decoration: none;
		color: var(--text-muted);
	}
	.term:hover .anchor,
	.anchor:focus {
		opacity: 1;
	}
	dd {
		margin: 0.15rem 0 0;
		color: var(--text-secondary);
	}
</style>
