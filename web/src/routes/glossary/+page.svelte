<script lang="ts">
	const terms: [string, string][] = [
		[
			'EPA (expected points added)',
			"Every down, distance and field position is worth some number of expected points: 1st & 10 at your own 25 is worth about +0.5, 1st & goal at the 1 about +5.5. A play's EPA is the change in expected points it caused. It credits a 4-yard gain on 3rd & 3 and penalizes a 4-yard gain on 3rd & 10, which yards can't do. From the nflfastR model."
		],
		[
			'Success rate',
			'Share of plays with positive EPA. Less sensitive than EPA to a few huge plays, so it measures consistency.'
		],
		[
			'EPA per dropback',
			'QB EPA (credits the QB with yards at the catch point when a receiver fumbles) on all dropbacks: completions, incompletions, sacks and scrambles.'
		],
		[
			'CPOE',
			'Completion percentage over expected. The nflfastR completion model sets an expected completion rate from air yards, target location, down, distance and more. CPOE is actual minus expected, in percentage points.'
		],
		[
			'PROE',
			"Pass rate over expected. nflfastR's xpass model gives the probability a team passes given down, distance, score, time and field position. PROE = actual pass rate − expected. Positive means pass-happy."
		],
		['aDOT', 'Average depth of target: mean air yards on pass attempts.'],
		[
			'Target share / air yards share / WOPR',
			"A receiver's share of the team's targets and of its total air yards. WOPR = 1.5 × target share + 0.7 × air yards share (Josh Hermsmeyer)."
		],
		[
			'YAC over expected',
			"Yards after catch minus the nflfastR xYAC model's expectation for that catch."
		],
		['Explosive play', 'A pass of 20+ yards or a run of 10+ yards.'],
		[
			'Garbage time',
			"Plays where the offense's win probability is below 10% or above 90%. Excluding them stops a 4th-quarter blowout from padding (or sinking) a team's numbers. The toggle on each page controls this."
		],
		[
			'Pythagorean wins',
			'Expected win % = PF^2.37 / (PF^2.37 + PA^2.37), times games played. Point differential predicts future records better than record does.'
		],
		[
			'One-score game',
			'Decided by 8 points or fewer. Records in these games are mostly noise and regress hard.'
		],
		[
			'Split-half reliability',
			'Correlation of a stat between odd and even weeks of the same season. Spearman-Brown, 2r / (1 + r), turns it into full-season reliability: the share of the variation between teams that is real skill.'
		],
		[
			'95% confidence interval',
			'Shown for QB EPA/dropback as mean ± 1.96 × SD / √n. EPA is fat-tailed, so treat it as a rough guide, not a guarantee.'
		]
	];
</script>

<svelte:head><title>Glossary · Any Given Stat</title></svelte:head>

<section>
	<h1>Glossary</h1>
	<p class="lede">
		What the numbers mean and where they come from. All play data is from <a
			href="https://github.com/nflverse/nflverse-data">nflverse</a
		>. Regular season only, scrimmage plays only (no kneels, spikes, special teams or plays wiped
		out by penalty).
	</p>
</section>

<div class="card">
	<dl>
		{#each terms as [term, def] (term)}
			<dt>{term}</dt>
			<dd>{def}</dd>
		{/each}
	</dl>
</div>

<style>
	dl {
		margin: 0;
		max-width: 80ch;
	}
	dt {
		font-weight: 600;
		margin-top: 0.9rem;
	}
	dt:first-child {
		margin-top: 0;
	}
	dd {
		margin: 0.15rem 0 0;
		color: var(--text-secondary);
	}
</style>
