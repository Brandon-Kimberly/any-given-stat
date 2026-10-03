<script lang="ts">
	// A team's full season from schedule/<season>.json: results that link to the game pages,
	// and for games still to come the kickoff, the line from this team's side and (for the
	// next games) the site's best-estimate win probability. Bye weeks get their own row.
	import { base } from '$app/paths';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { signed } from '$lib/format';
	import { kickoffLabel, played } from '$lib/standings';
	import type { GamePrediction, ScheduleGame } from '$lib/types';

	let {
		team,
		season,
		games,
		predictions = []
	}: {
		team: string;
		season: number;
		/** The season's schedule (undefined while it loads). */
		games: ScheduleGame[] | undefined;
		/** Upcoming games with best-estimate win probabilities (predictions upcoming + next_games). */
		predictions?: GamePrediction[];
	} = $props();

	const ROUND: Record<string, string> = { WC: 'WC', DIV: 'DIV', CON: 'CONF', SB: 'SB' };
	const ROUND_NAME: Record<string, string> = {
		WC: 'Wild Card',
		DIV: 'Divisional round',
		CON: 'Conference championship',
		SB: 'Super Bowl'
	};

	type Row =
		| { kind: 'bye'; week: number }
		| {
				kind: 'game';
				g: ScheduleGame;
				label: string;
				title: string;
				home: boolean;
				opp: string;
				done: boolean;
				/** This team's points minus the opponent's. */
				margin: number | null;
				score: string;
				/** Closing line from this team's side (negative = favored). */
				line: number | null;
				wp: number | null;
				next: boolean;
		  };

	const fmtDate = (d: string) =>
		new Date(`${d}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

	const rows = $derived.by<Row[]>(() => {
		const mine = (games ?? [])
			.filter((g) => g.home === team || g.away === team)
			.sort((a, b) => a.week - b.week || a.gameday.localeCompare(b.gameday));
		if (!mine.length) return [];
		const preds = new Map(predictions.map((p) => [p.game_id, p]));
		const firstOpen = mine.find((g) => !played(g));
		const reg = (games ?? []).filter((g) => g.game_type === 'REG');
		const lastRegWeek = Math.max(0, ...reg.map((g) => g.week));
		const out: Row[] = [];
		const weeksPlayed = new Set(mine.filter((g) => g.game_type === 'REG').map((g) => g.week));
		for (let w = 1; w <= lastRegWeek; w++) {
			if (!weeksPlayed.has(w)) out.push({ kind: 'bye', week: w });
		}
		for (const g of mine) {
			const home = g.home === team;
			const done = played(g);
			const pf = home ? g.home_score : g.away_score;
			const pa = home ? g.away_score : g.home_score;
			const margin = done ? pf! - pa! : null;
			const p = preds.get(g.game_id);
			const hwp = p ? (p.blend_wp ?? p.home_wp) : null;
			out.push({
				kind: 'game',
				g,
				label: ROUND[g.game_type] ?? String(g.week),
				title: ROUND_NAME[g.game_type] ?? `Week ${g.week}`,
				home,
				opp: home ? g.away : g.home,
				done,
				margin,
				score: done ? `${pf}–${pa}` : '',
				line: g.vegas == null ? null : home ? -g.vegas : g.vegas,
				wp: hwp == null ? null : home ? hwp : 1 - hwp,
				next: g === firstOpen
			});
		}
		const order = (r: Row) =>
			r.kind === 'bye' ? r.week : r.g.game_type === 'REG' ? r.g.week : 100 + r.g.week;
		return out.sort((a, b) => order(a) - order(b));
	});
	const hasWp = $derived(rows.some((r) => r.kind === 'game' && r.wp != null));
	const fmtLine = (v: number | null) =>
		v == null ? '–' : Math.abs(v) < 0.05 ? 'PK' : signed(v, 1);
	const outcome = (m: number) => (m > 0 ? 'W' : m < 0 ? 'L' : 'T');
</script>

<section class="card sched-card" id="schedule" aria-labelledby="schedule-title">
	<div class="card-head">
		<h2 id="schedule-title">Schedule</h2>
		<a href="{base}/games/?season={season}">All games →</a>
	</div>
	<p class="sub">
		Line: closing Vegas spread from {team}'s side (− = favored).{hasWp
			? ' Win %: best estimate, the model blended with the market.'
			: ''} Results link to the game pages.
	</p>
	{#if !games}
		<div class="placeholder" aria-hidden="true"></div>
	{:else if !rows.length}
		<p class="muted">No {season} schedule for {team}.</p>
	{:else}
		<table class="sched">
			<thead>
				<tr>
					<th scope="col"><abbr title="Week">Wk</abbr></th>
					<th scope="col">Date</th>
					<th scope="col">Opponent</th>
					<th scope="col" class="num">Line</th>
					<th scope="col" class="num">Result</th>
				</tr>
			</thead>
			<tbody>
				{#each rows as r (r.kind === 'bye' ? `bye-${r.week}` : r.g.game_id)}
					{#if r.kind === 'bye'}
						<tr class="bye">
							<td class="wk">{r.week}</td>
							<td colspan="4"><span class="chip">Bye week</span></td>
						</tr>
					{:else}
						<tr class:next={r.next} class:post={r.g.game_type !== 'REG'}>
							<td class="wk"><abbr title={r.title}>{r.label}</abbr></td>
							<td class="date">
								{fmtDate(r.g.gameday)}
								{#if !r.done}<span class="kick">{kickoffLabel(r.g.gameday, r.g.gametime)}</span
									>{/if}
							</td>
							<td class="opp">
								<span class="where" title={r.home ? 'Home' : r.g.neutral ? 'Neutral site' : 'Away'}
									>{r.home ? 'vs' : '@'}</span
								>
								<TeamBadge team={r.opp} name="nick" link {season} />
							</td>
							<td class="num line">{fmtLine(r.line)}</td>
							<td class="num res">
								{#if r.done && r.margin != null}
									<a
										class="result"
										href="{base}/game/?id={r.g.game_id}"
										aria-label="{r.margin > 0
											? 'Won'
											: r.margin < 0
												? 'Lost'
												: 'Tied'} {r.score}, game page"
									>
										<span
											class="wl"
											class:w={r.margin > 0}
											class:l={r.margin < 0}
											aria-hidden="true">{outcome(r.margin)}</span
										>
										<span class="tnum">{r.score}</span>
									</a>
								{:else if r.wp != null}
									<span class="wp" title="Best-estimate chance {team} wins"
										><b class="tnum">{Math.round(r.wp * 100)}%</b> win</span
									>
								{:else if r.next}
									<span class="chip">Next</span>
								{:else}
									<span class="muted">–</span>
								{/if}
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	{/if}
</section>

<style>
	.sched-card {
		min-width: 0;
	}
	.placeholder {
		height: 620px;
	}
	.sched {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.88rem;
	}
	.sched th {
		font-size: 0.72rem;
		font-weight: 600;
		color: var(--text-muted);
		text-align: left;
		padding: 0 0.35rem 0.3rem;
		border-bottom: 1px solid var(--border);
	}
	.sched abbr {
		text-decoration: none;
	}
	.sched td {
		padding: 0.32rem 0.35rem;
		border-bottom: 1px solid var(--grid);
		vertical-align: middle;
		height: 2.35rem;
	}
	.sched .num {
		text-align: right;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.wk {
		width: 2.4rem;
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
	.post .wk {
		font-size: 0.72rem;
	}
	.date {
		white-space: nowrap;
		line-height: 1.2;
	}
	.kick {
		display: block;
		font-size: 0.72rem;
		color: var(--text-muted);
	}
	.opp {
		white-space: nowrap;
	}
	.where {
		display: inline-block;
		width: 1.4rem;
		color: var(--text-muted);
		font-size: 0.8rem;
	}
	.line {
		color: var(--text-secondary);
	}
	.result {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 28px;
		color: inherit;
		text-decoration: none;
		font-weight: 600;
	}
	.result:hover .tnum {
		text-decoration: underline;
	}
	.wl {
		display: inline-grid;
		place-items: center;
		width: 1.35rem;
		height: 1.35rem;
		border-radius: 6px;
		font-size: 0.72rem;
		font-weight: 800;
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.wl.w {
		background: var(--good-wash);
	}
	.wl.l {
		background: var(--bad-wash);
	}
	.wp {
		color: var(--text-secondary);
		font-size: 0.82rem;
	}
	.wp b {
		color: var(--text-primary);
		font-size: 0.9rem;
	}
	tr.next td {
		background: var(--accent-soft);
	}
	tr.bye td {
		color: var(--text-muted);
	}
	@media (max-width: 560px) {
		.sched {
			font-size: 0.82rem;
		}
		.sched td,
		.sched th {
			padding-left: 0.2rem;
			padding-right: 0.2rem;
		}
		/* Badge only on phones; the nickname is in its tooltip and on the team page. */
		.opp :global(.name) {
			display: none;
		}
		.wk {
			width: 1.9rem;
		}
	}
</style>
