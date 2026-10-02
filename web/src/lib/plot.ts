import * as Plot from '@observablehq/plot';

/** Shared Plot defaults so every chart reads as one system. */
export const plotStyle = {
	fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
	fontSize: '12px',
	color: 'var(--text-muted)',
	background: 'transparent',
	overflow: 'visible'
} as const;

export const gridX = () => Plot.gridX({ stroke: 'var(--grid)', strokeOpacity: 1 });
export const gridY = () => Plot.gridY({ stroke: 'var(--grid)', strokeOpacity: 1 });

/** True on phone-width charts: drop end labels, thin ticks, shrink margins. */
export const isNarrow = (width: number) => width < 520;

/** At most one tick per `minPx` pixels, taken evenly from `values` (keeps first and last). */
export function thinTicks<T>(values: T[], width: number, minPx = 44): T[] {
	const max = Math.max(2, Math.floor(width / minPx));
	if (values.length <= max) return values;
	const step = Math.ceil((values.length - 1) / (max - 1));
	return values.filter((_, i) => i % step === 0 || i === values.length - 1);
}

/** Hide labels in `.declutter` text marks that overlap an earlier label. */
export function declutter(root: HTMLElement): void {
	const kept: DOMRect[] = [];
	const pad = 1.5;
	for (const t of root.querySelectorAll<SVGTextElement>('g.declutter text')) {
		const r = t.getBoundingClientRect();
		if (!r.width) continue;
		const hit = kept.some(
			(k) =>
				r.left < k.right + pad &&
				r.right > k.left - pad &&
				r.top < k.bottom + pad &&
				r.bottom > k.top - pad
		);
		if (hit) t.style.display = 'none';
		else kept.push(r);
	}
}

export { Plot };
