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

/** Standard normal CDF (Abramowitz–Stegun 7.1.26, |error| < 1.5e-7). */
export function normCdf(z: number): number {
	const t = 1 / (1 + (0.3275911 * Math.abs(z)) / Math.SQRT2);
	const poly =
		t *
		(0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
	const erf = 1 - poly * Math.exp(-(z * z) / 2);
	return z >= 0 ? (1 + erf) / 2 : (1 - erf) / 2;
}

/** Percentile (0..100) of `x` within `pool`: share below plus half the ties. */
export function percentileOf(x: number, pool: number[]): number {
	if (!pool.length) return 50;
	let below = 0;
	let ties = 0;
	for (const v of pool) {
		if (v < x) below++;
		else if (v === x) ties++;
	}
	return (100 * (below + ties / 2)) / pool.length;
}

/** 95% band for an observed rate around `p` at sample sizes `ns` (binomial, normal approx). */
export function funnelBand(p: number, ns: number[]): { n: number; lo: number; hi: number }[] {
	return ns.map((n) => {
		const half = 1.96 * Math.sqrt((p * (1 - p)) / n);
		return { n, lo: p - half, hi: p + half };
	});
}
