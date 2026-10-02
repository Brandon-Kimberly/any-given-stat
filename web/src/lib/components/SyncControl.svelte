<script lang="ts">
	// Header control for the local sync server (`uv run ags up`). Renders nothing on the static
	// site, where /api/status doesn't exist.
	import { agoShort, inShort, INTERVALS, sync, type AutoMode } from '$lib/sync.svelte';
	import { onMount, tick } from 'svelte';

	let { generatedAt }: { generatedAt?: string } = $props();

	let open = $state(false);
	let now = $state(Date.now());
	let root = $state<HTMLDivElement>();
	let btn = $state<HTMLButtonElement>();
	let panel = $state<HTMLDivElement>();

	onMount(() => {
		sync.start();
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	const status = $derived(sync.status);
	const running = $derived(sync.running);
	const failed = $derived(status?.state === 'error');
	const dataTime = $derived(generatedAt ?? status?.last_success_at ?? null);
	const label = $derived(
		running ? 'Syncing…' : failed ? 'Sync failed' : `Updated ${agoShort(dataTime, now)}`
	);
	const lastLine = $derived(status?.log_tail.at(-1) ?? '');
	const mode = $derived(status?.settings.auto ?? 'off');
	const interval = $derived(status?.settings.interval_minutes ?? 15);
	const modes: { value: AutoMode; label: string }[] = [
		{ value: 'off', label: 'Off' },
		{ value: 'interval', label: 'Interval' },
		{ value: 'gameday', label: 'Game days' }
	];
	const every = (m: number) => (m < 60 ? `${m} min` : `${m / 60} h`);

	async function toggle() {
		open = !open;
		if (open) {
			now = Date.now();
			void sync.poll();
			await tick();
			panel?.focus();
		}
	}
	function close(restoreFocus = true) {
		open = false;
		if (restoreFocus) btn?.focus();
	}
	function onKey(e: KeyboardEvent) {
		if (open && e.key === 'Escape') {
			// Return focus to the button only if it was inside the panel (or nowhere).
			const inside =
				root?.contains(document.activeElement) || document.activeElement === document.body;
			close(inside);
		}
	}
	function onWindowClick(e: MouseEvent) {
		if (open && root && !root.contains(e.target as Node)) close(false);
	}
</script>

<svelte:window onclick={onWindowClick} onkeydown={onKey} />

{#if sync.available}
	<div class="sync" bind:this={root}>
		<button
			bind:this={btn}
			class="sync-btn"
			class:failed
			aria-expanded={open}
			aria-controls="sync-panel"
			title="Data sync: {label}"
			onclick={toggle}
		>
			<span class="icon" aria-hidden="true">
				<svg viewBox="0 0 24 24" class:spinning={running}
					><path d="M20 12a8 8 0 0 1-14.3 4.9M4 12a8 8 0 0 1 14.3-4.9" /><path
						d="M18.5 3v4.2h-4.2M5.5 21v-4.2h4.2"
					/></svg
				>
				{#if !running}<span class="sdot" class:bad={failed}></span>{/if}
			</span>
			<span class="sr-only">Data sync:</span>
			<span class="label">{label}</span>
		</button>

		{#if open}
			<div
				bind:this={panel}
				id="sync-panel"
				class="sync-panel"
				role="dialog"
				aria-labelledby="sync-title"
				tabindex="-1"
			>
				<div class="panel-head">
					<h2 id="sync-title">Data sync</h2>
					<button class="close ghost" onclick={() => close()} aria-label="Close data sync">
						<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
					</button>
				</div>
				<p class="meta muted">
					Data built {agoShort(generatedAt, now)}{status?.last_success_at
						? ` · last checked ${agoShort(status.last_success_at, now)}`
						: ''}
				</p>

				<div class="progress" aria-live="polite">
					{#if running}
						<p class="stage"><span class="spinner" aria-hidden="true"></span>{status?.stage}</p>
					{:else if status?.last_result === 'error'}
						<p class="result bad">{status.message || 'Sync failed'}</p>
					{:else if status?.last_result === 'up_to_date'}
						<p class="result">
							Already up to date (checked {agoShort(status.finished_at, now)}).
						</p>
					{:else if status?.last_result === 'updated'}
						<p class="result">{status.message} ({agoShort(status.finished_at, now)}).</p>
					{/if}
				</div>
				{#if running && lastLine}<p class="log" title={lastLine}>{lastLine}</p>{/if}

				<!-- aria-disabled (not disabled) so focus stays on the button while it runs. -->
				<button
					class="primary sync-now"
					aria-disabled={running || sync.pending}
					onclick={() => !running && !sync.pending && sync.syncNow()}
					>{running ? 'Syncing…' : 'Sync now'}</button
				>

				<div class="auto">
					<div class="auto-head">
						<span class="auto-label" id="auto-label">Auto-sync</span>
						<div class="seg" role="group" aria-labelledby="auto-label">
							{#each modes as m (m.value)}
								<button
									aria-pressed={mode === m.value}
									disabled={sync.pending}
									onclick={() => sync.saveSettings({ auto: m.value })}>{m.label}</button
								>
							{/each}
						</div>
					</div>
					{#if mode !== 'off'}
						<label class="every">
							Every
							<select
								value={interval}
								disabled={sync.pending}
								onchange={(e) =>
									sync.saveSettings({ interval_minutes: Number(e.currentTarget.value) })}
							>
								{#each INTERVALS as m (m)}
									<option value={m}>{every(m)}</option>
								{/each}
							</select>
							{mode === 'gameday' ? 'during games' : ''}
						</label>
					{/if}
					<p class="hint muted">
						{#if mode === 'off'}
							Syncs only when you press Sync now.
						{:else if mode === 'interval'}
							Checks for new data every {every(interval)} while this server runs.
						{:else}
							Every {every(interval)} during NFL game windows (Thu and Mon nights, Sundays, Saturdays
							from Dec 10, Thanksgiving, Christmas; US Eastern), every 6 h otherwise.
						{/if}
						{#if status?.next_auto_at && !running}
							Next check {inShort(status.next_auto_at, now)}.{/if}
					</p>
					<p class="hint muted">
						nflverse posts play-by-play about nightly and scores sooner, so frequent syncs pick up
						new data only when it's published. A check with nothing new takes seconds.
					</p>
				</div>
			</div>
		{/if}
	</div>
{/if}

<style>
	.sync {
		position: relative;
	}
	.sync-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		height: 36px;
		min-height: 36px;
		padding: 0 0.65rem 0 0.5rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: transparent;
		color: var(--text-secondary);
		font-size: 0.84rem;
		white-space: nowrap;
	}
	.sync-btn:hover,
	.sync-btn[aria-expanded='true'] {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.icon {
		position: relative;
		display: grid;
		place-items: center;
		width: 18px;
		height: 18px;
	}
	svg {
		width: 18px;
		height: 18px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.spinning {
		animation: spin 1s linear infinite;
	}
	.sdot {
		position: absolute;
		right: -3px;
		bottom: -2px;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--series-3);
		box-shadow: 0 0 0 2px var(--surface);
	}
	.sdot.bad {
		background: var(--bad);
	}
	.sync-panel {
		position: absolute;
		top: calc(100% + 8px);
		right: 0;
		z-index: 80;
		width: 340px;
		padding: 0.9rem 1rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border-strong);
		border-radius: var(--radius);
		box-shadow: var(--shadow-md);
		display: grid;
		gap: 0.6rem;
		color: var(--text-primary);
		white-space: normal;
		outline: none;
		animation: drop 0.16s var(--ease);
	}
	.sync-panel:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.panel-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: -0.3rem;
	}
	h2 {
		font-size: 1rem;
		margin: 0;
	}
	.close {
		display: grid;
		place-items: center;
		width: 32px;
		height: 32px;
		min-height: 32px;
		padding: 0;
		color: var(--text-secondary);
	}
	.meta,
	.hint {
		margin: 0;
		font-size: 0.8rem;
	}
	.progress p {
		margin: 0;
		font-size: 0.88rem;
	}
	.progress:empty {
		display: none;
	}
	.stage {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-weight: 600;
	}
	.result.bad {
		color: var(--bad-ink);
		font-weight: 600;
	}
	.spinner {
		flex: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		border: 2px solid var(--border-strong);
		border-top-color: var(--accent);
		animation: spin 0.8s linear infinite;
	}
	.log {
		margin: -0.3rem 0 0;
		font: 0.75rem var(--mono);
		color: var(--text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.sync-now {
		justify-self: start;
	}
	.sync-now[aria-disabled='true'] {
		cursor: progress;
	}
	.auto {
		display: grid;
		gap: 0.5rem;
		padding-top: 0.7rem;
		border-top: 1px solid var(--border);
	}
	.auto-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.4rem;
	}
	.auto-label {
		font-weight: 600;
		font-size: 0.88rem;
	}
	.every {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.85rem;
		color: var(--text-secondary);
	}
	/* The text label only fits next to the full nav on wide screens; below that the button is
	   an icon whose label stays in the accessible name (and the tooltip). */
	@media (max-width: 1319px) {
		.sync-btn {
			width: 36px;
			padding: 0;
			justify-content: center;
			border-color: transparent;
		}
		.label {
			position: absolute;
			width: 1px;
			height: 1px;
			overflow: hidden;
			clip: rect(0, 0, 0, 0);
			white-space: nowrap;
		}
	}
	@media (max-width: 960px) {
		.sync {
			position: static;
		}
		.sync-panel {
			position: absolute;
			top: calc(100% + 6px);
			left: 16px;
			right: 16px;
			width: auto;
			max-height: calc(100vh - 80px);
			overflow-y: auto;
		}
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	@keyframes drop {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.spinning,
		.spinner {
			animation-duration: 3s;
		}
	}
</style>
