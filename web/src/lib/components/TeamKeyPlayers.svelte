<script lang="ts">
	// A team's key players for one season: its QBs (from the per-game QB log, so a QB traded
	// mid-season only counts his games for this team), top receivers by targets and top rushers
	// by carries, each with a headline stat. Names link to player pages where one exists.
	import { base } from '$app/paths';
	import Avatar from '$lib/components/Avatar.svelte';
	import { epa, num } from '$lib/format';
	import { hasPlayerPage } from '$lib/playerPages.svelte';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import type { QBGame } from '$lib/types';

	let { team, season }: { team: string; season: number } = $props();

	const qbGames = seasonResource<QBGame>('qb_games', () => season);
	const recRes = resource('receivers');
	const rushRes = resource('rushers');
	const playersRes = resource('players');
	const dir = $derived(new Map((playersRes.value ?? []).map((p) => [p.player_id, p])));

	type Entry = {
		id: string;
		name: string;
		pos: string;
		head: string;
		detail: string;
		title: string;
	};

	const qbs = $derived.by<Entry[]>(() => {
		const by = new Map<
			string,
			{ name: string; g: number; db: number; epa: number; yds: number; td: number; int: number }
		>();
		for (const g of qbGames.value ?? []) {
			if (g.team !== team || g.season !== season) continue;
			const c = by.get(g.player_id) ?? {
				name: g.name,
				g: 0,
				db: 0,
				epa: 0,
				yds: 0,
				td: 0,
				int: 0
			};
			c.g += 1;
			c.db += g.dropbacks;
			c.epa += g.epa_db * g.dropbacks;
			c.yds += g.pass_yards;
			c.td += g.tds;
			c.int += g.ints;
			by.set(g.player_id, c);
		}
		const total = [...by.values()].reduce((a, c) => a + c.db, 0);
		return [...by]
			.filter(([, c]) => c.db >= total * 0.15)
			.sort((a, b) => b[1].db - a[1].db)
			.slice(0, 2)
			.map(([id, c]) => ({
				id,
				name: dir.get(id)?.name ?? c.name,
				pos: 'QB',
				head: `${epa(c.epa / c.db, 2)} EPA/db`,
				detail: `${c.g} ${c.g === 1 ? 'game' : 'games'} · ${num(c.yds)} yds · ${c.td} TD · ${c.int} INT`,
				title: `${num(c.db)} dropbacks`
			}));
	});

	const receivers = $derived.by<Entry[]>(() =>
		(recRes.value ?? [])
			.filter((r) => r.season === season && r.team === team)
			.sort((a, b) => b.targets - a.targets)
			.slice(0, 3)
			.map((r) => ({
				id: r.player_id,
				name: dir.get(r.player_id)?.name ?? r.full_name ?? r.name,
				pos: r.position ?? dir.get(r.player_id)?.position ?? '',
				head: `${num(r.yards)} yds`,
				detail: `${num(r.targets)} tgt · ${num(r.receptions)} rec · ${num(r.tds)} TD`,
				title: `${epa(r.epa_target, 2)} EPA per target`
			}))
	);

	const rushers = $derived.by<Entry[]>(() =>
		(rushRes.value ?? [])
			.filter((r) => r.season === season && r.team === team)
			.sort((a, b) => b.carries - a.carries)
			.slice(0, 2)
			.map((r) => ({
				id: r.player_id,
				name: dir.get(r.player_id)?.name ?? r.full_name ?? r.name,
				pos: r.position ?? dir.get(r.player_id)?.position ?? '',
				head: `${num(r.yards)} yds`,
				detail: `${num(r.carries)} car · ${num(r.ypc, 1)} ypc · ${num(r.tds)} TD`,
				title: `${epa(r.epa_rush, 2)} EPA per carry`
			}))
	);

	const loaded = $derived(
		qbGames.value !== undefined && !!recRes.value && !!rushRes.value && !!playersRes.value
	);
	const groups = $derived([
		{ label: qbs.length > 1 ? 'Quarterbacks' : 'Quarterback', rows: qbs },
		{ label: 'Receivers', rows: receivers },
		{ label: 'Rushers', rows: rushers }
	]);
</script>

<section class="card kp" aria-labelledby="kp-title">
	<h2 id="kp-title">Key players</h2>
	<p class="sub">
		{season} regular season for {team}: QBs with at least 15% of the dropbacks, then the top
		receivers by targets and rushers by carries.
	</p>
	{#if !loaded}
		<div class="placeholder" aria-hidden="true"></div>
	{:else}
		<div class="groups">
			{#each groups as g (g.label)}
				<div>
					<h3>{g.label}</h3>
					{#if !g.rows.length}
						<p class="muted small">None yet.</p>
					{:else}
						<ul>
							{#each g.rows as p (p.id)}
								<li>
									<Avatar name={p.name} src={dir.get(p.id)?.headshot} {team} size={38} />
									<div class="who">
										<div class="nm">
											{#if hasPlayerPage(p.id)}<a href="{base}/player/?id={p.id}&season={season}"
													>{p.name}</a
												>{:else}<span>{p.name}</span>{/if}
											{#if p.pos}<span class="pos">{p.pos}</span>{/if}
										</div>
										<div class="detail muted">{p.detail}</div>
									</div>
									<b class="head tnum" title={p.title}>{p.head}</b>
								</li>
							{/each}
						</ul>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.placeholder {
		height: 430px;
	}
	.groups {
		display: grid;
		gap: 0.9rem;
	}
	h3 {
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--text-muted);
		margin: 0 0 0.35rem;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.45rem;
	}
	li {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 0.7rem;
		min-height: 42px;
	}
	.who {
		min-width: 0;
	}
	.nm {
		display: flex;
		align-items: baseline;
		gap: 0.45rem;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.nm a {
		display: inline-block;
		padding: 0.1rem 0;
	}
	.pos {
		font-size: 0.7rem;
		font-weight: 700;
		color: var(--text-muted);
	}
	.detail {
		font-size: 0.8rem;
	}
	.head {
		font: 800 1rem var(--display);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.small {
		font-size: 0.85rem;
		margin: 0;
	}
</style>
