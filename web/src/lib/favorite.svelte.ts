// The visitor's favorite team, kept in localStorage: badges get a ring, table rows a highlight,
// and the home page a card for it. Optional everywhere; nothing depends on it being set.

const KEY = 'ags-favorite-team';

function read(): string | null {
	try {
		return localStorage.getItem(KEY);
	} catch {
		return null;
	}
}

let team = $state<string | null>(typeof localStorage === 'undefined' ? null : read());

export const favorite = {
	get team() {
		return team;
	},
	set(t: string | null) {
		team = t;
		try {
			if (t) localStorage.setItem(KEY, t);
			else localStorage.removeItem(KEY);
		} catch {
			/* private mode: keep it for this visit only */
		}
	},
	toggle(t: string) {
		this.set(team === t ? null : t);
	}
};
