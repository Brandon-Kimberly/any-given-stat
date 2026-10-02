import { load } from './data';
import { theme } from './theme.svelte';
import type { TeamMeta } from './types';

/** Team identity (names, divisions, colors). Empty until loaded; every helper falls back. */
export const teamMeta = $state<{ byTeam: Record<string, TeamMeta> }>({ byTeam: {} });

let started = false;
export function loadTeamMeta(): void {
	if (started) return;
	started = true;
	load('teams_meta')
		.then((rows) => {
			teamMeta.byTeam = Object.fromEntries(rows.map((r) => [r.team, r]));
		})
		.catch(() => {
			/* optional dataset: badges fall back to neutral */
		});
}

/** Team color that stays visible on the current theme's chart surface. */
export function teamColor(team: string): string {
	const m = teamMeta.byTeam[team];
	if (!m) return 'var(--neutral-mark)';
	return theme.dark ? m.color_dark : m.color_light;
}

export function teamName(team: string): string {
	return teamMeta.byTeam[team]?.name ?? team;
}

export function teamNick(team: string): string {
	return teamMeta.byTeam[team]?.nick ?? team;
}
