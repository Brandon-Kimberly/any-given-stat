// Which week a page should treat as "now" for a season, so every page agrees.

import type { SeasonStatus } from './types';

/** The latest ratings week to show: in a season still in progress, the last fully played
 * week (`last_week`); a lone Thursday game of the next week doesn't count. */
export function ratingsWeek(weeks: Iterable<number>, status?: SeasonStatus | null): number {
	const sorted = [...new Set(weeks)].sort((a, b) => a - b);
	if (!sorted.length) return 0;
	if (!status || status.complete) return sorted.at(-1)!;
	return sorted.filter((w) => w <= status.last_week).at(-1) ?? sorted[0];
}
