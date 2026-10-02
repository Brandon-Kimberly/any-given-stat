import { load } from './data';
import { theme } from './theme.svelte';
import type { TeamMeta } from './types';

/** Team identity (names, divisions, colors). Empty until loaded; every helper falls back.
 * Raw state: read per mark in every chart, so no proxy on the hot path. */
let byTeam = $state.raw<Record<string, TeamMeta>>({});
export const teamMeta = {
	get byTeam() {
		return byTeam;
	}
};

let started = false;
export function loadTeamMeta(): void {
	if (started) return;
	started = true;
	load('teams_meta')
		.then((rows) => {
			byTeam = Object.fromEntries(rows.map((r) => [r.team, r]));
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

function rgb(hex: string): [number, number, number] | null {
	const m = /^#([0-9a-f]{6})$/i.exec(hex.trim());
	if (!m) return null;
	const n = parseInt(m[1], 16);
	return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** True when two colors are too close to tell apart side by side (weighted RGB distance). */
export function colorsClash(a: string, b: string): boolean {
	const x = rgb(a);
	const y = rgb(b);
	if (!x || !y) return true;
	const r = (x[0] + y[0]) / 2;
	const d = Math.sqrt(
		(2 + r / 256) * (x[0] - y[0]) ** 2 +
			4 * (x[1] - y[1]) ** 2 +
			(2 + (255 - r) / 256) * (x[2] - y[2]) ** 2
	);
	return d < 150;
}

/** Colors for a two-team view: team colors when distinct, else the validated series pair. */
export function matchupColors(away: string, home: string): { away: string; home: string } {
	const a = teamColor(away);
	const h = teamColor(home);
	return colorsClash(a, h)
		? { away: 'var(--series-2)', home: 'var(--series-1)' }
		: { away: a, home: h };
}
