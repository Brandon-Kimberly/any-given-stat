const n = (v: number | null | undefined): v is number => v != null && Number.isFinite(v);

export const dash = '–';

/** Signed fixed-point with a real minus sign; values that round to zero get no sign. */
function signedFixed(v: number, digits: number): string {
	const s = v.toFixed(digits);
	if (Number(s) === 0) return (0).toFixed(digits);
	return v > 0 ? `+${s}` : s.replace('-', '−');
}

/** EPA-style values: signed, 3 decimals (e.g. +0.142). */
export function epa(v: number | null | undefined, digits = 3): string {
	return n(v) ? signedFixed(v, digits) : dash;
}

/** Rates stored as 0–1 shown as percentages. */
export function pct(v: number | null | undefined, digits = 1): string {
	return n(v) ? `${(v * 100).toFixed(digits)}%` : dash;
}

/** Signed percentage points for "over expected" rates (0.031 -> +3.1). */
export function pp(v: number | null | undefined, digits = 1): string {
	return n(v) ? signedFixed(v * 100, digits) : dash;
}

const numFormats = new Map<number, Intl.NumberFormat>();
function numFormat(digits: number): Intl.NumberFormat {
	let f = numFormats.get(digits);
	if (!f) {
		f = new Intl.NumberFormat('en-US', {
			maximumFractionDigits: digits,
			minimumFractionDigits: digits
		});
		numFormats.set(digits, f);
	}
	return f;
}

export function num(v: number | null | undefined, digits = 0): string {
	return n(v) ? numFormat(digits).format(v) : dash;
}

export function signed(v: number | null | undefined, digits = 1): string {
	return n(v) ? signedFixed(v, digits) : dash;
}

export function corr(v: number | null | undefined): string {
	return n(v) ? v.toFixed(2).replace('-', '−') : dash;
}

/** A point spread as "KC −3.5" (favorite, negative number) or "PK" for a pick'em. */
export function spread(homeMargin: number | null | undefined, home: string, away: string): string {
	if (!n(homeMargin)) return dash;
	if (Math.abs(homeMargin) < 0.05) return 'PK';
	const fav = homeMargin > 0 ? home : away;
	return `${fav} −${Math.abs(homeMargin).toFixed(1)}`;
}

/** "9–7–1" from half-win-for-tie totals (a .5 means one tie; two ties in a season is ~never). */
export function wlt(wins: number | null | undefined, games: number | null | undefined): string {
	if (!n(wins) || !n(games)) return dash;
	const w = Math.floor(wins);
	const t = wins % 1 ? 1 : 0;
	return `${w}–${games - w - t}${t ? `–${t}` : ''}`;
}
