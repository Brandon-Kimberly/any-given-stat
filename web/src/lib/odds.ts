// Track record of the playoff-odds simulation on completed seasons.
import type { PlayoffOdds } from './types';

export interface CalBin {
	lo: number;
	hi: number;
	n: number;
	predicted: number;
	actual: number;
}

/** Make-the-playoffs forecasts at `week` grouped into 10-point bins: mean forecast vs share
 * that actually made it. Only seasons with outcomes count. */
export function calibration(seasons: PlayoffOdds[], week: number): CalBin[] {
	const bins = Array.from({ length: 10 }, (_, i) => ({
		lo: i / 10,
		hi: (i + 1) / 10,
		n: 0,
		p: 0,
		a: 0
	}));
	for (const s of seasons) {
		if (!s.actual) continue;
		for (const r of s.rows) {
			if (r.week !== week || !s.actual[r.team]) continue;
			const b = bins[Math.min(9, Math.floor(r.p_playoffs * 10))];
			b.n++;
			b.p += r.p_playoffs;
			b.a += s.actual[r.team].made_playoffs ? 1 : 0;
		}
	}
	return bins
		.filter((b) => b.n > 0)
		.map((b) => ({ lo: b.lo, hi: b.hi, n: b.n, predicted: b.p / b.n, actual: b.a / b.n }));
}

export interface SkillPoint {
	week: number;
	brier: number;
	/** Brier score of always forecasting the base rate (share of teams that make it). */
	baseline: number;
	/** 1 - brier/baseline: 0 = no better than the base rate, 1 = perfect. */
	skill: number;
	n: number;
}

/** Brier score and skill vs the base rate at each week, pooled over completed seasons. */
export function skillByWeek(seasons: PlayoffOdds[]): SkillPoint[] {
	const by = new Map<number, { se: number; base: number; n: number }>();
	for (const s of seasons) {
		if (!s.actual) continue;
		const teams = Object.keys(s.actual);
		const rate = teams.filter((t) => s.actual![t].made_playoffs).length / teams.length;
		for (const r of s.rows) {
			const out = s.actual[r.team];
			if (!out) continue;
			const y = out.made_playoffs ? 1 : 0;
			const acc = by.get(r.week) ?? { se: 0, base: 0, n: 0 };
			acc.se += (r.p_playoffs - y) ** 2;
			acc.base += (rate - y) ** 2;
			acc.n++;
			by.set(r.week, acc);
		}
	}
	return [...by]
		.sort(([a], [b]) => a - b)
		.map(([week, { se, base, n }]) => ({
			week,
			brier: se / n,
			baseline: base / n,
			skill: 1 - se / base,
			n
		}));
}

/** "73%", "<1%", ">99%", "–" for zero, "✓" for certain. */
export function oddsPct(p: number): string {
	if (p >= 1) return '✓';
	if (p <= 0) return '–';
	if (p < 0.01) return '<1%';
	if (p > 0.99) return '>99%';
	return `${Math.round(p * 100)}%`;
}
