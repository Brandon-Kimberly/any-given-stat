<script lang="ts">
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import { load } from '$lib/data';
	import { epa, num, pct, pp } from '$lib/format';
	import { prefs } from '$lib/prefs.svelte';
	import type { Meta, TeamSeason } from '$lib/types';

	let meta = $state<Meta>();
	let teams = $state<TeamSeason[]>([]);
	load('meta').then((m) => (meta = m));
	load('teams').then((t) => (teams = t));

	type View = 'off' | 'def';
	let view = $state<View>('off');
	const rows = $derived(teams.filter((t) => t.season === prefs.season && t.scope === prefs.scope));
	const yds = (v: number | null) => num(v, 1);

	// Offense: higher is better except giveaways/sacks. Defense: the mirror image.
	function side(p: View): Column<TeamSeason>[] {
		const hi = p === 'off' ? 'high' : 'low';
		const lo = p === 'off' ? 'low' : 'high';
		const k = (s: string) => `${p}_${s}` as keyof TeamSeason & string;
		return [
			{ key: 'team', label: 'Team', sticky: true },
			{ key: k('epa_play'), label: 'EPA/play', fmt: epa, better: hi },
			{ key: k('pass_epa'), label: 'Pass EPA', fmt: epa, better: hi },
			{ key: k('rush_epa'), label: 'Rush EPA', fmt: epa, better: hi },
			{ key: k('success_rate'), label: 'Success', fmt: pct, better: hi },
			{ key: k('pass_success'), label: 'Pass SR', fmt: pct, better: hi },
			{ key: k('rush_success'), label: 'Rush SR', fmt: pct, better: hi },
			{
				key: k('explosive_rate'),
				label: 'Explosive',
				fmt: pct,
				better: hi,
				title: 'Passes of 20+ yards and runs of 10+'
			},
			{
				key: k('turnover_rate'),
				label: 'TO rate',
				fmt: (v) => pct(v, 2),
				better: lo,
				title: 'Interceptions + lost fumbles per play'
			},
			{ key: k('sack_rate'), label: 'Sack rate', fmt: pct, better: lo },
			{ key: k('third_down_rate'), label: '3rd down', fmt: pct, better: hi },
			{
				key: k('points_per_drive'),
				label: 'Pts/drive',
				fmt: (v) => num(v, 2),
				better: hi,
				title: 'TD = 7, FG = 3'
			},
			{
				key: k('rz_td_rate'),
				label: 'RZ TD%',
				fmt: pct,
				better: hi,
				title: 'Share of drives reaching the 20 that end in a TD'
			},
			{ key: k('pass_rate'), label: 'Pass rate', fmt: pct },
			{
				key: k('proe'),
				label: 'PROE',
				fmt: pp,
				title: 'Pass rate over expected (nflfastR xpass), percentage points'
			},
			{ key: k('early_down_pass_rate'), label: '1st/2nd pass%', fmt: pct },
			{ key: k('adot'), label: 'aDOT', fmt: yds, title: 'Average depth of target (air yards)' },
			{ key: k('plays'), label: 'Plays', fmt: num }
		];
	}
	const columns = $derived(side(view));
</script>

<svelte:head><title>Teams · Any Given Stat</title></svelte:head>

<section>
	<h1>Teams</h1>
	<p class="lede">
		Every team efficiency stat in one table. Color shows where a team ranks this season (blue = good
		end, red = bad end). On the defense view, “good” means allowing less. Pass rate and PROE aren't
		shaded because they describe style, not quality.
	</p>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} />
		<div class="seg" role="group" aria-label="Side of the ball">
			<button aria-pressed={view === 'off'} onclick={() => (view = 'off')}>Offense</button>
			<button aria-pressed={view === 'def'} onclick={() => (view = 'def')}>Defense</button>
		</div>
	</div>
	<SampleWarning status={meta.seasons.find((s) => s.season === prefs.season)} />
{/if}

<div class="card">
	{#key view}
		<DataTable
			{rows}
			{columns}
			sortKey={`${view}_epa_play`}
			sortDesc={view === 'off'}
			search="team"
			onrowclick={(r) => goto(`${base}/team/?t=${r.team}`)}
		/>
	{/key}
</div>
