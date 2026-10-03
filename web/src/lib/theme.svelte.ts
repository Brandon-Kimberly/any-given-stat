import { tick } from 'svelte';

/** Resolved color theme, reactive so charts using theme-dependent colors re-render. */
export const theme = $state({ dark: false });

function resolve(): boolean {
	const t = document.documentElement.dataset.theme;
	if (t === 'dark') return true;
	if (t === 'light') return false;
	return matchMedia('(prefers-color-scheme: dark)').matches;
}

export function initTheme(): void {
	theme.dark = resolve();
	matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
		theme.dark = resolve();
	});
}

function applyToggle(): void {
	const root = document.documentElement;
	root.dataset.theme = resolve() ? 'light' : 'dark';
	try {
		localStorage.setItem('ags-theme', root.dataset.theme);
	} catch {
		/* ignore */
	}
	theme.dark = resolve();
}

/** Flip light/dark. With an origin (the toggle button's click), the new theme is revealed in
 * a circle growing from that point (View Transitions); otherwise colors crossfade. */
export function toggleTheme(e?: MouseEvent | { clientX: number; clientY: number }): void {
	const root = document.documentElement;
	const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
	if (reduced) return applyToggle();
	if (!document.startViewTransition) {
		root.classList.add('theming');
		setTimeout(() => root.classList.remove('theming'), 300);
		return applyToggle();
	}
	const x = e && 'clientX' in e && e.clientX ? e.clientX : innerWidth - 40;
	const y = e && 'clientY' in e && e.clientY ? e.clientY : 30;
	const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
	// One snapshot of the whole page (named page groups would animate on their own).
	root.classList.add('theme-vt');
	const t = document.startViewTransition(async () => {
		applyToggle();
		await tick(); // theme-dependent charts re-render before the new snapshot
	});
	t.ready
		.then(() =>
			root.animate(
				{ clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
				{
					duration: 600,
					easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)',
					pseudoElement: '::view-transition-new(root)'
				}
			)
		)
		.catch(() => {});
	t.finished.finally(() => root.classList.remove('theme-vt'));
}
