// Link previews (Discord, Slack, iMessage, X, ...): the title and description each page shows
// when someone shares it. Crawlers don't run JavaScript, so these go into every prerendered
// page's <head> at build time (src/hooks.server.ts fills app.html's __OG_*__ tokens). Pages
// keyed by query string (/team/?t=DET) share their route's entry.

export interface PageMeta {
	title: string;
	description: string;
}

export const SITE_NAME = 'Any Given Stat';
/** Bump after re-rendering static/og.png (scripts/og-card.mjs): chat apps cache by image URL. */
export const OG_IMAGE_VERSION = 2;

const HOME: PageMeta = {
	title: 'Any Given Stat · NFL analytics that show their work',
	description:
		'Opponent-adjusted power ratings, win probability for every game since 2016, playoff odds from 10,000 simulated seasons, fantasy scored your way, and a weekly forecast graded honestly against Vegas. Free, no ads.'
};

const PAGES: Record<string, PageMeta> = {
	'/tiers/': {
		title: 'Team tiers',
		description:
			"Every NFL offense and defense on one chart, by EPA per play, raw or adjusted for opponents. See who's actually good, not just who's winning."
	},
	'/ratings/': {
		title: 'Power ratings',
		description:
			"Predictive NFL power ratings in points vs an average team, updated every week, with each team's climb or slide all season."
	},
	'/odds/': {
		title: 'Playoff odds',
		description:
			"Every team's chances to make the playoffs, win the division, earn a bye and win the Super Bowl, from 10,000 simulated seasons with real tiebreakers."
	},
	'/teams/': {
		title: 'Team stats',
		description:
			'Every NFL team efficiency stat in one sortable table: EPA, success rate, explosive plays, red zone and more.'
	},
	'/luck/': {
		title: 'Luck',
		description:
			"Which NFL teams' records outrun their point differential, and who's due to regress: Pythagorean wins, one-score games and fumble luck."
	},
	'/fourth/': {
		title: 'Fourth downs',
		description:
			'Which NFL coaches go for it when the math says to, and how many points the cautious ones leave on the field.'
	},
	'/qbs/': {
		title: 'Quarterbacks',
		description:
			'Every NFL quarterback by EPA per dropback and completion % over expected, with error bars that show how sure we really are.'
	},
	'/receivers/': {
		title: 'Receivers',
		description:
			'NFL receivers by target share, air yards, WOPR and yards after catch over expected.'
	},
	'/rushers/': {
		title: 'Rushers',
		description:
			'NFL running backs measured on designed runs: EPA per carry, success rate and explosive runs, garbage time stripped out.'
	},
	'/fantasy/': {
		title: 'Fantasy',
		description:
			"Connect your Sleeper league and every fantasy number uses your league's exact scoring: rankings, value over replacement, matchups and news on your roster."
	},
	'/news/': {
		title: 'News',
		description:
			"NFL headlines and this week's injury report, filtered by team or by the players on your fantasy roster."
	},
	'/games/': {
		title: 'Scores & game charts',
		description:
			'Win-probability charts for every NFL game since 2016, with the plays that swung each one and an excitement index.'
	},
	'/predictions/': {
		title: 'Predictions vs Vegas',
		description:
			"This week's NFL forecast next to the Vegas line, factor by factor, with a public scorecard of how accurate it has been. Spoiler: Vegas is hard to beat."
	},
	'/records/': {
		title: 'Record book',
		description:
			'The best and worst NFL seasons, the wildest comebacks and the biggest plays since 2016.'
	},
	'/coaches/': {
		title: 'Coaches',
		description:
			'Every NFL head coach since 2016: records, against the spread, and fourth-down aggressiveness.'
	},
	'/referees/': {
		title: 'Referees',
		description: 'NFL officiating crews by flags per game and home-field lean.'
	},
	'/learn/': {
		title: 'How football works, in numbers',
		description:
			'An interactive primer on expected points, win probability and fourth-down math, built on every NFL play since 2016.'
	},
	'/stability/': {
		title: 'Signal vs noise',
		description:
			'Which NFL stats predict themselves and which are mostly luck, measured across a decade of seasons.'
	},
	'/glossary/': {
		title: 'Glossary',
		description:
			'Every metric on Any Given Stat in plain English: EPA, CPOE, success rate, WOPR and more.'
	},
	'/compare/': {
		title: 'Compare',
		description: 'Put any two NFL teams or players side by side, tale-of-the-tape style.'
	},
	'/explore/': {
		title: 'SQL explorer',
		description: 'Query every NFL play since 2016 with SQL, right in your browser.'
	},
	'/team/': {
		title: 'Team pages',
		description:
			"Any NFL team's season at a glance: schedule, power rating, playoff odds, key players and news."
	},
	'/player/': {
		title: 'Player pages',
		description:
			"Any NFL player's season and career: efficiency, game logs, fantasy points and news."
	},
	'/game/': {
		title: 'Game charts',
		description:
			'The full story of an NFL game: win probability, the plays that decided it, the drive chart, play-by-play and box score.'
	}
};

/** Preview title and description for a path relative to the site base ("/odds/"). */
export function pageMeta(path: string): PageMeta {
	const p = PAGES[path];
	return p ? { title: `${p.title} · ${SITE_NAME}`, description: p.description } : HOME;
}

const ESCAPES: Record<string, string> = {
	'&': '&amp;',
	'<': '&lt;',
	'>': '&gt;',
	'"': '&quot;',
	"'": '&#39;'
};
export const escapeAttr = (s: string): string => s.replace(/[&<>"']/g, (c) => ESCAPES[c]);
