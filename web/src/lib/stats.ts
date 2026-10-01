// Small, pure numeric helpers used by the pages. Covered by stats.test.ts.

export function mean(xs: number[]): number {
	return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN;
}

export function median(xs: number[]): number {
	if (!xs.length) return NaN;
	const s = [...xs].sort((a, b) => a - b);
	const m = s.length >> 1;
	return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function sd(xs: number[]): number {
	if (xs.length < 2) return NaN;
	const m = mean(xs);
	return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1));
}

/** Rank 1 = best. `higherIsBetter` false for defense EPA, sack rate, etc. Ties share a rank. */
export function ranks(xs: (number | null)[], higherIsBetter = true): (number | null)[] {
	const vals = xs.filter((x): x is number => x != null);
	return xs.map((x) =>
		x == null ? null : 1 + vals.filter((v) => (higherIsBetter ? v > x : v < x)).length
	);
}

/** Ordinary least squares y = a + b x. */
export function ols(xs: number[], ys: number[]): { a: number; b: number; r: number } {
	const mx = mean(xs);
	const my = mean(ys);
	let sxy = 0;
	let sxx = 0;
	let syy = 0;
	for (let i = 0; i < xs.length; i++) {
		sxy += (xs[i] - mx) * (ys[i] - my);
		sxx += (xs[i] - mx) ** 2;
		syy += (ys[i] - my) ** 2;
	}
	const b = sxy / sxx;
	return { a: my - b * mx, b, r: sxy / Math.sqrt(sxx * syy) };
}

/** Trailing moving average over a window (shorter at the start). */
export function rolling(xs: number[], window: number): number[] {
	return xs.map((_, i) => mean(xs.slice(Math.max(0, i - window + 1), i + 1)));
}
