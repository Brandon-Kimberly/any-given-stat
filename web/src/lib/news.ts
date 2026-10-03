// News feed helpers (pure): filtering items by team / players, injury labels, time labels.
// Items come from news.json or the local app's /api/news (pipeline news.py); loading lives in
// news.svelte.ts.

import type { NewsItem } from './types';

export const FANTASY_POSITIONS = new Set(['QB', 'RB', 'WR', 'TE', 'K', 'FB']);

export type NewsKind = 'all' | 'news' | 'injury';

export interface NewsFilter {
	team?: string | null;
	/** Items tagging any of these gsis ids. */
	players?: Iterable<string> | null;
	kind?: NewsKind;
}

/** Items matching every given filter (order kept: newest first). */
export function filterNews(items: NewsItem[], f: NewsFilter = {}): NewsItem[] {
	const ids = f.players ? new Set(f.players) : null;
	return items.filter(
		(i) =>
			(!f.kind || f.kind === 'all' || i.kind === f.kind) &&
			(!f.team || i.teams.includes(f.team)) &&
			(!ids || i.players.some((p) => ids.has(p)))
	);
}

/** Fantasy-relevant without a league: headlines that tag a player (or say fantasy), and
 * injury items for skill players with a status or a change. */
export function fantasyRelevant(i: NewsItem): boolean {
	if (i.kind === 'injury') {
		return FANTASY_POSITIONS.has(i.position ?? '') && (!!i.status || i.change === 'cleared');
	}
	return i.athletes.length > 0 || /fantasy/i.test(i.headline);
}

export type InjuryTone = 'out' | 'doubtful' | 'questionable' | 'cleared' | 'info';

export function injuryTone(i: NewsItem): InjuryTone {
	if (i.status === 'Out') return 'out';
	if (i.status === 'Doubtful') return 'doubtful';
	if (i.status === 'Questionable') return 'questionable';
	if (i.change === 'cleared') return 'cleared';
	return 'info';
}

/** Short status word for the badge: "Out", "Doubtful", "Quest.", "Cleared", "Practice". */
export function statusShort(i: NewsItem): string {
	if (i.status === 'Questionable') return 'Q';
	if (i.status) return i.status;
	if (i.change === 'cleared') return 'Cleared';
	return i.preliminary ? 'Practice' : 'No status';
}

const CHANGE: Record<string, string> = {
	new: 'New',
	worse: 'Downgraded',
	better: 'Upgraded',
	same: 'Unchanged'
};

/** "Downgraded" etc. against the previous report ('cleared' is the status itself). */
export function changeLabel(i: NewsItem): string | null {
	return (i.change && CHANGE[i.change]) ?? null;
}

/** "just now", "12 min ago", "5 h ago", "3 days ago". */
export function ago(iso: string | null | undefined, now = Date.now()): string {
	if (!iso) return '';
	const mins = Math.round((now - new Date(iso).getTime()) / 60000);
	if (!Number.isFinite(mins)) return '';
	if (mins < 1) return 'just now';
	if (mins < 60) return `${mins} min ago`;
	const hrs = Math.round(mins / 60);
	if (hrs < 36) return `${hrs} h ago`;
	return `${Math.round(hrs / 24)} days ago`;
}

function dayKey(d: Date): string {
	return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

/** "Today", "Yesterday", "Wednesday", or "Sep 24" (local time) for grouping a feed. */
export function dayLabel(iso: string, now = new Date()): string {
	const d = new Date(iso);
	if (dayKey(d) === dayKey(now)) return 'Today';
	const y = new Date(now);
	y.setDate(y.getDate() - 1);
	if (dayKey(d) === dayKey(y)) return 'Yesterday';
	const days = (now.getTime() - d.getTime()) / 86_400_000;
	if (days < 6 && days > 0) return d.toLocaleDateString('en-US', { weekday: 'long' });
	return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Consecutive runs of items sharing a day label. */
export function groupByDay(
	items: NewsItem[],
	now = new Date()
): { label: string; items: NewsItem[] }[] {
	const out: { label: string; items: NewsItem[] }[] = [];
	for (const i of items) {
		const label = dayLabel(i.published, now);
		const last = out.at(-1);
		if (last?.label === label) last.items.push(i);
		else out.push({ label, items: [i] });
	}
	return out;
}

/** "Updated 12 min ago" for the feed's headlines (or why there are none). */
export function updatedLabel(
	feed: { news_fetched_at: string | null; live: boolean } | null | undefined,
	now = Date.now()
): string {
	if (!feed) return '';
	if (!feed.news_fetched_at) return 'Headlines unavailable';
	return `Updated ${ago(feed.news_fetched_at, now)}`;
}
