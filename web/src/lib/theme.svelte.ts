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

export function toggleTheme(): void {
	const root = document.documentElement;
	root.dataset.theme = resolve() ? 'light' : 'dark';
	try {
		localStorage.setItem('ags-theme', root.dataset.theme);
	} catch {
		/* ignore */
	}
	theme.dark = resolve();
}
