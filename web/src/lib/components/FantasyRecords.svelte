<script lang="ts">
	// All-time fantasy records under the current scoring. Every season's stat lines (~250 KB
	// each, gzipped) load only once this section scrolls near the screen.
	import { base } from '$app/paths';
	import RecordList, { type RecordItem } from '$lib/components/RecordList.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { scored, type SeasonResult } from '$lib/fantasy/analysis';
	import { currentLineup, loadFantasySeason, scoringLabel } from '$lib/fantasy/data.svelte';
	import { fantasy } from '$lib/fantasy/league.svelte';
	import type { FantasySeason } from '$lib/fantasy/statline';
	import { num, signed } from '$lib/format';
	import { teamName } from '$lib/teams.svelte';

	let { seasons }: { seasons: number[] } = $props();

	let el: HTMLElement;
	let files = $state.raw<FantasySeason[] | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		const want = seasons;
		const io = new IntersectionObserver(
			(entries) => {
				if (!entries.some((e) => e.isIntersecting)) return;
				io.disconnect();
				Promise.all(want.map((s) => loadFantasySeason(s).catch(() => null)))
					.then((all) => (files = all.filter((f): f is FantasySeason => !!f)))
					.catch((e) => (error = String(e)));
			},
			{ rootMargin: '600px 0px' }
		);
		io.observe(el);
		return () => io.disconnect();
	});

	const results = $derived<[FantasySeason, SeasonResult][]>(
		(files ?? []).map((f) => [f, scored(f, fantasy.scoring, currentLineup())])
	);
	const skill = (pos: string) => ['QB', 'RB', 'WR', 'TE'].includes(pos);

	type GameRow = { f: FantasySeason; gid: string; pid: string; team: string; pts: number };
	const games = $derived.by<GameRow[]>(() => {
		const out: GameRow[] = [];
		for (const [f, r] of results) {
			for (const [gid, pid, team] of f.lines) {
				const pts = r.byGame.get(gid)?.get(pid);
				if (pts != null && pts > 20) out.push({ f, gid, pid, team, pts });
			}
		}
		return out.sort((a, b) => b.pts - a.pts);
	});
	const gameLabel = (g: GameRow) => {
		const [week, type, home, away] = g.f.games[g.gid];
		const opp = g.team === home ? `vs ${away}` : `@ ${home}`;
		return `${g.f.season} ${type === 'REG' ? `week ${week}` : 'playoffs'} ${opp}`;
	};
	const toGameItem = (g: GameRow): RecordItem => {
		const [name, pos] = g.f.players[g.pid];
		return {
			key: `${g.gid}-${g.pid}`,
			href: `/game/?id=${g.gid}`,
			team: g.team,
			title: pos === 'DEF' ? `${teamName(g.pid)} D/ST` : `${name}, ${pos}`,
			sub: gameLabel(g),
			stat: `${num(g.pts, 1)} pts`
		};
	};
	const bestGames = $derived(
		games
			.filter((g) => g.f.players[g.pid][1] !== 'DEF')
			.slice(0, 30)
			.map(toGameItem)
	);
	const bestDst = $derived(
		games
			.filter((g) => g.f.players[g.pid][1] === 'DEF')
			.slice(0, 30)
			.map(toGameItem)
	);
	const seasonRows = $derived(
		results.flatMap(([f, r]) => r.players.map((p) => ({ season: f.season, p })))
	);
	const seasonItem = ({ season, p }: (typeof seasonRows)[number], stat: string): RecordItem => ({
		key: `${season}-${p.id}`,
		href: skill(p.pos) ? `/player/?id=${p.id}` : `/fantasy/?season=${season}`,
		team: p.team,
		title: p.pos === 'DEF' ? `${teamName(p.id)} D/ST` : `${p.name}, ${p.pos}`,
		sub: `${season} · ${num(p.ppg, 1)} per game over ${p.games} games`,
		stat
	});
	const bestSeasons = $derived(
		[...seasonRows]
			.sort((a, b) => b.p.points - a.p.points)
			.slice(0, 30)
			.map((x) => seasonItem(x, `${num(x.p.points, 1)} pts`))
	);
	const bestVor = $derived(
		[...seasonRows]
			.sort((a, b) => b.p.vor - a.p.vor)
			.slice(0, 30)
			.map((x) => seasonItem(x, signed(x.p.vor, 0)))
	);
</script>

<div bind:this={el}>
	{#if error}
		<p class="muted">Couldn't load fantasy data: {error}</p>
	{:else if !files}
		<Skeleton height={420} />
	{:else}
		<p class="muted small">
			Scored with <b>{scoringLabel()}</b> (change it on the <a href="{base}/fantasy/">Fantasy</a> page).
			Seasons are regular season only; single games include the playoffs.
		</p>
		<div class="grid-2">
			<RecordList
				title="Biggest fantasy games"
				blurb="Most points by one player in one game."
				items={bestGames}
			/>
			<RecordList
				title="Best fantasy seasons"
				blurb="Most regular-season points."
				items={bestSeasons}
			/>
			<RecordList
				title="Most valuable seasons"
				blurb="Points above a replacement-level player at the same position, for a league your size: the fairest way to compare a QB with a TE."
				items={bestVor}
			/>
			<RecordList
				title="Best defense games"
				blurb="Most points by a team defense and special teams in one game."
				items={bestDst}
			/>
		</div>
	{/if}
</div>

<style>
	.small {
		font-size: 0.85rem;
	}
</style>
