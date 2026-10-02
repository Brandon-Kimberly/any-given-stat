<script lang="ts">
	import { prefs, savePrefs } from '$lib/prefs.svelte';
	import type { SeasonStatus } from '$lib/types';

	let { seasons, showScope = true }: { seasons: SeasonStatus[]; showScope?: boolean } = $props();
</script>

<div class="toolbar">
	<label class="field">
		Season
		<select bind:value={prefs.season} onchange={savePrefs}>
			{#each [...seasons].reverse() as s (s.season)}
				<option value={s.season}
					>{s.season}{s.complete ? '' : ` (through wk ${s.last_week})`}</option
				>
			{/each}
		</select>
	</label>
	{#if showScope}
		<div class="seg" role="group" aria-label="Play filter">
			<button
				aria-pressed={prefs.scope === 'no_garbage'}
				title="Exclude plays where the offense's win probability is under 10% or over 90%"
				onclick={() => ((prefs.scope = 'no_garbage'), savePrefs())}>No garbage time</button
			>
			<button
				aria-pressed={prefs.scope === 'all'}
				onclick={() => ((prefs.scope = 'all'), savePrefs())}>All plays</button
			>
		</div>
	{/if}
</div>
