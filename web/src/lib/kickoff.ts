// Kickoff labels from nflverse's schedule fields: gameday "YYYY-MM-DD" and gametime "HH:MM"
// (US Eastern, 24-hour).

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/** Sortable kickoff key, e.g. "2026-10-04T13:00" (no time sorts last that day). */
export function kickoffKey(gameday: string, gametime?: string | null): string {
	return `${gameday}T${gametime ?? '99:99'}`;
}

/** "Sun 10/4 · 1:00 PM" (date only when the time is unknown). */
export function kickoffLabel(gameday: string, gametime?: string | null): string {
	const [y, m, d] = gameday.split('-').map(Number);
	if (!y || !m || !d) return gameday;
	const day = DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
	const date = `${day} ${m}/${d}`;
	const t = gametime?.match(/^(\d{1,2}):(\d{2})/);
	if (!t) return date;
	const h = +t[1];
	return `${date} · ${h % 12 || 12}:${t[2]} ${h < 12 ? 'AM' : 'PM'}`;
}

/** kickoffLabel from a kickoffKey (DataTable formatters only see the value). */
export function kickoffLabelFromKey(key: string): string {
	const [day, time] = key.split('T');
	return kickoffLabel(day, time === '99:99' ? null : time);
}
