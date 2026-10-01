import * as Plot from '@observablehq/plot';

/** Shared Plot defaults so every chart reads as one system. */
export const plotStyle = {
	fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif',
	fontSize: '12px',
	color: 'var(--text-muted)',
	background: 'transparent',
	overflow: 'visible'
} as const;

export const gridX = () => Plot.gridX({ stroke: 'var(--grid)', strokeOpacity: 1 });
export const gridY = () => Plot.gridY({ stroke: 'var(--grid)', strokeOpacity: 1 });

export { Plot };
