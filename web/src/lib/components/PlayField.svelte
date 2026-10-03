<script lang="ts">
	// A mini field for one play, oriented like the drive chart (away's end zone on the left):
	// the line of scrimmage, the line to gain and where the ball went, in the color of the
	// team moving it. Decorative: the play's text gives the same facts.
	import type { Play } from '$lib/playText';

	let {
		play: p,
		home,
		away,
		colors
	}: {
		play: Play;
		home: string;
		away: string;
		colors: { home: string; away: string };
	} = $props();

	// 0–100 yards plus 10-yard end zones, as % of the bar.
	const x = (team: string, yl: number) => ((team === away ? yl : 100 - yl) + 10) / 1.2;
	const opp = $derived(p.team === home ? away : home);
	const colorOf = (t: string) => (t === home ? colors.home : colors.away);

	const geom = $derived.by(() => {
		if (p.yl == null || p.kind === 'end') return null;
		const kind = p.kind ?? '';
		const los = x(p.team, p.yl);
		let end: number | null = null;
		let style: 'gain' | 'kick' | 'flag' = 'gain';
		let color = colorOf(p.team);
		if (kind.startsWith('fg_')) {
			end = x(p.team, 100);
			style = 'kick';
		} else if (kind.startsWith('xp_') || kind.startsWith('2pt_')) {
			end = null;
		} else if (kind === 'kickoff' || kind === 'onside') {
			if (p.ylEnd != null) end = x(p.team, p.ylEnd);
			style = 'kick';
			color = colorOf(opp);
		} else if (kind.startsWith('punt')) {
			if (p.ylEnd != null) end = x(p.team, p.ylEnd);
			style = 'kick';
		} else if (kind === 'penalty') {
			if (p.ylEnd != null) end = x(p.team, p.ylEnd);
			style = 'flag';
			color = 'var(--neutral-mark)';
		} else {
			const to = p.ylEnd ?? (p.yds != null ? Math.max(0, Math.min(100, p.yl + p.yds)) : null);
			if (to != null) end = x(p.team, to);
		}
		const gain = p.down && p.togo != null && p.yl + p.togo < 100 ? x(p.team, p.yl + p.togo) : null;
		return {
			los,
			gain,
			end,
			left: end == null ? los : Math.min(los, end),
			width: end == null ? 0 : Math.abs(end - los),
			style,
			color
		};
	});
</script>

<span class="pf" aria-hidden="true">
	<span class="ez l" style:background={colors.away}></span>
	<span class="ez r" style:background={colors.home}></span>
	{#if geom}
		{#if geom.gain != null}<span class="gain" style:left="{geom.gain}%"></span>{/if}
		<span class="los" style:left="{geom.los}%"></span>
		{#if geom.end != null}
			{#if geom.width > 0.4}
				<span
					class="trail {geom.style}"
					style:left="{geom.left}%"
					style:width="{geom.width}%"
					style:--c={geom.color}
				></span>
			{/if}
			<span class="ball" style:left="{geom.end}%" style:--c={geom.color}></span>
		{/if}
	{/if}
</span>

<style>
	.pf {
		position: relative;
		display: block;
		width: 100%;
		height: 14px;
		border-radius: 3px;
		overflow: hidden;
		background:
			repeating-linear-gradient(
				90deg,
				transparent 0 calc(8.333% - 1px),
				var(--border) calc(8.333% - 1px) 8.333%
			),
			var(--surface-2);
	}
	.ez {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 8.333%;
		opacity: 0.45;
	}
	.ez.l {
		left: 0;
	}
	.ez.r {
		right: 0;
	}
	.los,
	.gain {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		margin-left: -1px;
	}
	.los {
		background: var(--text-muted);
	}
	.gain {
		background: var(--warning);
	}
	.trail {
		position: absolute;
		top: 5px;
		height: 4px;
		border-radius: 2px;
		background: var(--c);
	}
	.trail.kick {
		top: 6px;
		height: 2px;
		background: repeating-linear-gradient(90deg, var(--c) 0 4px, transparent 4px 7px);
	}
	.trail.flag {
		background: var(--neutral-mark);
	}
	.ball {
		position: absolute;
		top: 3px;
		width: 8px;
		height: 8px;
		margin-left: -4px;
		border-radius: 50%;
		background: var(--c);
		box-shadow: 0 0 0 1.5px var(--surface);
	}
</style>
