// Loading fantasy data for pages: a season's stat lines, the platform id map, and the
// current scoring + lineup from the league store.

import { loadPath } from '$lib/data';
import { DEFAULT_LINEUP, scored, type Lineup, type SeasonResult } from './analysis';
import { fantasy } from './league.svelte';
import type { FantasyIds, FantasySeason } from './statline';

export const loadFantasySeason = (season: number) => loadPath<FantasySeason>(`fantasy/${season}`);

/** `fantasy/<season>.json`, reloading when `season()` changes. */
export function fantasySeason(season: () => number | null | undefined) {
	let value = $state.raw<FantasySeason | undefined>(undefined);
	let error = $state.raw<string | null>(null);
	$effect(() => {
		const s = season();
		if (!s) return;
		loadFantasySeason(s)
			.then((v) => {
				if (season() === s) {
					value = v;
					error = null;
				}
			})
			.catch((e) => {
				if (season() === s) error = e instanceof Error ? e.message : String(e);
			});
	});
	return {
		get value() {
			return value;
		},
		get error() {
			return error;
		}
	};
}

/** Platform player ids -> gsis ids, loaded only once a league is connected. */
export function fantasyIds() {
	let value = $state.raw<FantasyIds | null>(null);
	$effect(() => {
		if (!fantasy.league) return;
		loadPath<FantasyIds>('fantasy_ids')
			.then((v) => (value = v))
			.catch(() => {});
	});
	return {
		get value() {
			return value;
		}
	};
}

/** The connected league's lineup, or a typical 12-team one. */
export function currentLineup(): Lineup {
	const l = fantasy.league;
	return l ? { teams: l.teams, starters: l.starters } : DEFAULT_LINEUP;
}

/** A season scored with the current scoring and lineup (memoized per scoring). */
export function scoredSeason(fs: FantasySeason | undefined): SeasonResult | null {
	return fs ? scored(fs, fantasy.scoring, currentLineup()) : null;
}

/** "PPR", "Half PPR", or the league's name. */
export function scoringLabel(): string {
	return fantasy.league ? fantasy.league.name : fantasy.scoring.label;
}
