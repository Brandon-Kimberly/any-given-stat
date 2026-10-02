// Chart → PNG. Plot charts style themselves with CSS variables, which a standalone SVG image
// can't resolve, so every element's computed paint and type are inlined into a clone first.
// Swatch legends are HTML, so they are redrawn on the canvas from their colors and labels.

const PROPS = [
	'fill',
	'fill-opacity',
	'stroke',
	'stroke-width',
	'stroke-opacity',
	'stroke-dasharray',
	'stroke-linecap',
	'stroke-linejoin',
	'opacity',
	'font-family',
	'font-size',
	'font-weight',
	'font-style',
	'font-variant-numeric',
	'letter-spacing',
	'text-anchor',
	'dominant-baseline',
	'paint-order',
	'display',
	'visibility'
];

function inlined(svg: SVGSVGElement): { url: string; w: number; h: number } {
	const box = svg.getBoundingClientRect();
	const clone = svg.cloneNode(true) as SVGSVGElement;
	const src = [svg, ...svg.querySelectorAll('*')];
	const dst = [clone, ...clone.querySelectorAll('*')];
	src.forEach((el, i) => {
		const cs = getComputedStyle(el);
		const style = PROPS.map((p) => `${p}:${cs.getPropertyValue(p)}`).join(';');
		(dst[i] as SVGElement).setAttribute('style', style);
	});
	clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
	clone.setAttribute('width', String(box.width));
	clone.setAttribute('height', String(box.height));
	const xml = new XMLSerializer().serializeToString(clone);
	return {
		url: URL.createObjectURL(new Blob([xml], { type: 'image/svg+xml;charset=utf-8' })),
		w: box.width,
		h: box.height
	};
}

function image(url: string): Promise<HTMLImageElement> {
	return new Promise((resolve, reject) => {
		const img = new Image();
		img.onload = () => resolve(img);
		img.onerror = () => reject(new Error('Could not rasterize chart'));
		img.src = url;
	});
}

interface Swatch {
	color: string;
	label: string;
}

function swatches(root: HTMLElement): Swatch[] {
	return [...root.querySelectorAll<HTMLElement>('[class*="-swatch"]:not([class*="-swatches"])')]
		.filter((s) => s.querySelector('svg'))
		.map((s) => {
			const mark = s.querySelector('svg')!.querySelector('rect, circle, path, line');
			const cs = mark ? getComputedStyle(mark) : null;
			const fill = cs?.fill && cs.fill !== 'none' ? cs.fill : (cs?.stroke ?? '#888');
			return { color: fill, label: s.textContent?.trim() ?? '' };
		});
}

/** Render the chart(s) in `root` to a PNG blob with a title, legend and source line. */
export async function chartPng(root: HTMLElement, title: string): Promise<Blob> {
	const svgs = [...root.querySelectorAll<SVGSVGElement>('svg')].filter(
		(s) => !s.closest('[class*="-swatch"]') && !s.parentElement?.closest('svg')
	);
	if (!svgs.length) throw new Error('Nothing to export');
	const css = getComputedStyle(root);
	const bg = css.getPropertyValue('--surface').trim() || '#fff';
	const ink = css.getPropertyValue('--text-primary').trim() || '#111';
	const muted = css.getPropertyValue('--text-muted').trim() || '#666';
	const font = 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif';

	const parts = await Promise.all(
		svgs.map(async (s) => {
			const { url, w, h } = inlined(s);
			try {
				return { img: await image(url), w, h };
			} finally {
				URL.revokeObjectURL(url);
			}
		})
	);
	const legend = swatches(root);

	const pad = 24;
	const width = Math.max(...parts.map((p) => p.w)) + pad * 2;
	const titleH = 34;
	const legendH = legend.length ? 26 : 0;
	const footH = 30;
	const height = pad + titleH + legendH + parts.reduce((a, p) => a + p.h + 8, 0) + footH;
	const scale = Math.min(2, Math.max(1, devicePixelRatio || 1)) * 1.5;

	const canvas = document.createElement('canvas');
	canvas.width = Math.round(width * scale);
	canvas.height = Math.round(height * scale);
	const ctx = canvas.getContext('2d')!;
	ctx.scale(scale, scale);
	ctx.fillStyle = bg;
	ctx.fillRect(0, 0, width, height);

	ctx.fillStyle = ink;
	ctx.font = `700 17px ${font}`;
	ctx.textBaseline = 'top';
	ctx.fillText(title, pad, pad);
	let y = pad + titleH;

	if (legend.length) {
		let x = pad;
		ctx.font = `500 12px ${font}`;
		for (const s of legend) {
			ctx.fillStyle = s.color;
			ctx.fillRect(x, y + 1, 11, 11);
			ctx.fillStyle = ink;
			ctx.fillText(s.label, x + 16, y);
			x += 16 + ctx.measureText(s.label).width + 18;
		}
		y += legendH;
	}
	for (const p of parts) {
		ctx.drawImage(p.img, pad, y, p.w, p.h);
		y += p.h + 8;
	}
	ctx.fillStyle = muted;
	ctx.font = `500 11px ${font}`;
	ctx.fillText('Any Given Stat · data: nflverse', pad, height - footH + 6);

	return new Promise((resolve, reject) =>
		canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('PNG encode failed'))), 'image/png')
	);
}

export function download(blob: Blob, filename: string): void {
	const url = URL.createObjectURL(blob);
	const a = Object.assign(document.createElement('a'), { href: url, download: filename });
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function slug(s: string): string {
	return (
		s
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-|-$/g, '')
			.slice(0, 60) || 'chart'
	);
}
