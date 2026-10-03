// One transient status message at a time (copied link, downloaded chart, shortcuts).

let message = $state<string | null>(null);
let tone = $state<'ok' | 'info' | 'error'>('info');
let timer: ReturnType<typeof setTimeout> | undefined;

export const toast = {
	get message() {
		return message;
	},
	/** ok = a check mark, error = a warning mark, info = neither. */
	get tone() {
		return tone;
	},
	show(text: string, ms = 2200, kind: 'ok' | 'info' | 'error' = 'info') {
		message = text;
		tone = kind;
		clearTimeout(timer);
		timer = setTimeout(() => (message = null), ms);
	}
};

export async function copyLink(href = location.href): Promise<void> {
	try {
		await navigator.clipboard.writeText(href);
		toast.show('Link copied', 2200, 'ok');
	} catch {
		toast.show('Copy failed: select the address bar instead', 3000, 'error');
	}
}
