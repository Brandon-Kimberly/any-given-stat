// One transient status message at a time (copied link, downloaded chart, shortcuts).

let message = $state<string | null>(null);
let timer: ReturnType<typeof setTimeout> | undefined;

export const toast = {
	get message() {
		return message;
	},
	show(text: string, ms = 2200) {
		message = text;
		clearTimeout(timer);
		timer = setTimeout(() => (message = null), ms);
	}
};

export async function copyLink(href = location.href): Promise<void> {
	try {
		await navigator.clipboard.writeText(href);
		toast.show('Link copied');
	} catch {
		toast.show('Copy failed: select the address bar instead');
	}
}
