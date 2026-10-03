<script lang="ts">
	// Connect a Sleeper or ESPN league (its scoring and rosters drive every fantasy number on
	// the site), or pick a standard scoring preset. Settings live in this browser only.
	import { currentSeason, fantasy } from '$lib/fantasy/league.svelte';
	import { PRESETS, unsupported, type PresetName } from '$lib/fantasy/scoring';
	import { toast } from '$lib/toast.svelte';
	import { hosted } from '$lib/hosted';

	let platform = $state<'sleeper' | 'espn'>('sleeper');
	let leagueId = $state('');
	let season = $state(currentSeason());
	let espnS2 = $state(fantasy.espnAuth?.espnS2 ?? '');
	let swid = $state(fantasy.espnAuth?.swid ?? '');

	const league = $derived(fantasy.league);
	const missing = $derived(league ? unsupported(league.scoring) : []);
	const lineup = $derived(
		league
			? Object.entries(league.starters)
					.filter(([slot]) => slot !== 'BN')
					.map(([slot, n]) => (n > 1 ? `${n} ${slot}` : slot))
					.join(' · ')
			: ''
	);
	const validId = $derived(/^\d{1,20}$/.test(leagueId.trim()));

	async function connect(e: SubmitEvent) {
		e.preventDefault();
		if (!validId) return;
		try {
			const l = await fantasy.connect(platform, leagueId.trim(), {
				season,
				espnS2: espnS2.trim() || undefined,
				swid: swid.trim() || undefined
			});
			toast.show(`Connected ${l.name}`, 2200, 'ok');
		} catch {
			/* fantasy.error shows it */
		}
	}
	async function refresh() {
		try {
			await fantasy.refresh();
			toast.show('League refreshed', 2200, 'ok');
		} catch {
			/* shown below */
		}
	}
	const presets: [PresetName, string][] = [
		['ppr', 'PPR'],
		['half', 'Half PPR'],
		['standard', 'Standard']
	];
</script>

<section class="card league" aria-labelledby="league-title">
	{#if league}
		<div class="head">
			<div>
				<div class="eyebrow">{league.platform === 'sleeper' ? 'Sleeper' : 'ESPN'} league</div>
				<h2 id="league-title">{league.name}</h2>
				<p class="muted small">
					{league.season} · {league.teams} teams · starts {lineup}
				</p>
			</div>
			<div class="actions">
				<button type="button" onclick={refresh} disabled={fantasy.loading}>
					{fantasy.loading ? 'Refreshing…' : 'Refresh'}
				</button>
				<button type="button" onclick={() => fantasy.disconnect()}>Disconnect</button>
			</div>
		</div>
		<label class="field mine">
			Your team
			<select
				value={fantasy.myTeam ?? ''}
				onchange={(e) => (fantasy.myTeam = e.currentTarget.value || null)}
			>
				<option value="">Pick your team…</option>
				{#each league.rosters as t (t.id)}
					<option value={t.id}
						>{t.name}{t.owner && t.owner !== t.name ? ` (${t.owner})` : ''}</option
					>
				{/each}
			</select>
		</label>
		<p class="muted small">
			Every fantasy number on the site now uses this league's scoring. Your players get a gold
			marker; other rostered players show their manager.
			{#if missing.length}
				<br /><span class="warn"
					>{missing.length} scoring rule{missing.length > 1 ? 's' : ''} can't be computed from play-by-play
					and {missing.length > 1 ? 'are' : 'is'} left out:
					<span class="keys">{missing.slice(0, 6).join(', ')}{missing.length > 6 ? '…' : ''}</span
					></span
				>
			{/if}
		</p>
	{:else}
		<div class="head">
			<div>
				<div class="eyebrow">Your league</div>
				<h2 id="league-title">Connect your {hosted ? 'Sleeper' : 'fantasy'} league</h2>
				<p class="muted small">
					Points across the site switch to your league's exact scoring, and your roster gets
					highlighted. Nothing leaves this browser except the request to your platform.
				</p>
			</div>
		</div>
		<form class="connect" onsubmit={connect}>
			{#if !hosted}
				<div class="seg" role="group" aria-label="Platform">
					<button
						type="button"
						aria-pressed={platform === 'sleeper'}
						onclick={() => (platform = 'sleeper')}>Sleeper</button
					>
					<button
						type="button"
						aria-pressed={platform === 'espn'}
						onclick={() => (platform = 'espn')}>ESPN</button
					>
				</div>
			{/if}
			<label class="field grow">
				League ID
				<input
					type="text"
					inputmode="numeric"
					autocomplete="off"
					placeholder={platform === 'sleeper' ? 'e.g. 1048313545995296768' : 'e.g. 336358'}
					bind:value={leagueId}
				/>
			</label>
			{#if platform === 'espn'}
				<label class="field">
					Season
					<select bind:value={season}>
						{#each [currentSeason(), currentSeason() - 1, currentSeason() - 2] as s (s)}
							<option value={s}>{s}</option>
						{/each}
					</select>
				</label>
			{/if}
			<button class="primary" type="submit" disabled={!validId || fantasy.loading}>
				{fantasy.loading ? 'Connecting…' : 'Connect'}
			</button>
		</form>
		<p class="muted small hint">
			{#if platform === 'sleeper'}
				Find it in the Sleeper app under League → Settings, or in the web address:
				sleeper.com/leagues/<b>ID</b>.
				{#if hosted}ESPN leagues connect in the free local app, since ESPN doesn't let other
					websites read league data.{/if}
			{:else}
				It's the <b>leagueId</b> in your league's web address on fantasy.espn.com. ESPN leagues load
				through the local app (<code>.\start.cmd</code> or <code>./start.sh</code>), since ESPN
				doesn't allow other websites to read it directly.
			{/if}
		</p>
		{#if platform === 'espn'}
			<details>
				<summary>Private league?</summary>
				<p class="muted small">
					ESPN needs two cookies from a browser where you're logged in to espn.com: open the
					developer tools → Application (Chrome) or Storage (Firefox) → Cookies → espn.com, and copy <b
						>espn_s2</b
					>
					and <b>SWID</b>. They're stored only in this browser and sent only to the local app.
				</p>
				<div class="cookies">
					<label class="field grow"
						>espn_s2 <input type="text" bind:value={espnS2} autocomplete="off" /></label
					>
					<label class="field grow"
						>SWID <input type="text" bind:value={swid} autocomplete="off" /></label
					>
				</div>
			</details>
		{/if}
		<div class="presets">
			<span class="muted small">No league? Score with</span>
			<div class="seg" role="group" aria-label="Scoring preset">
				{#each presets as [k, label] (k)}
					<button
						type="button"
						aria-pressed={fantasy.preset === k}
						onclick={() => (fantasy.preset = k)}
						title={`${PRESETS[k].label} scoring`}>{label}</button
					>
				{/each}
			</div>
		</div>
	{/if}
	{#if fantasy.error}
		<div class="callout" role="alert">{fantasy.error}</div>
	{/if}
</section>

<style>
	.league {
		display: grid;
		gap: 0.85rem;
	}
	.head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.75rem;
	}
	h2 {
		margin: 0.1rem 0 0.2rem;
	}
	.head p {
		margin: 0;
		max-width: 62ch;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
	}
	.actions button,
	.connect button.primary {
		min-height: 40px;
	}
	.actions button {
		padding: 0.45rem 0.9rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
		color: var(--text-primary);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.actions button:hover {
		border-color: var(--border-strong);
	}
	.connect {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0.75rem;
	}
	.grow {
		flex: 1 1 14rem;
		flex-direction: column;
		align-items: stretch;
		gap: 0.3rem;
	}
	.grow input {
		width: 100%;
	}
	.mine select {
		max-width: 22rem;
	}
	.hint,
	details p {
		margin: 0;
	}
	details summary {
		cursor: pointer;
		font-weight: 600;
		font-size: 0.88rem;
		min-height: 28px;
	}
	.cookies {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin-top: 0.5rem;
	}
	.presets {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--border);
	}
	.warn {
		color: var(--text-secondary);
	}
	.keys {
		font-family: var(--mono, ui-monospace, monospace);
		font-size: 0.78rem;
	}
	.small {
		font-size: 0.82rem;
	}
</style>
