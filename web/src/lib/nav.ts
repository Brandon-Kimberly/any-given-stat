// Site map: drives the header menus, the mobile drawer and the command palette.

export interface NavItem {
	href: string;
	label: string;
	blurb: string;
}

export interface NavGroup {
	label: string;
	items: NavItem[];
}

export const navGroups: NavGroup[] = [
	{
		label: 'Teams',
		items: [
			{
				href: '/tiers/',
				label: 'Team tiers',
				blurb: 'Offense vs defense, raw or opponent-adjusted'
			},
			{ href: '/ratings/', label: 'Power ratings', blurb: 'Predictive ratings, week by week' },
			{
				href: '/odds/',
				label: 'Playoff odds',
				blurb: '10,000 simulated seasons, replayable week by week'
			},
			{ href: '/teams/', label: 'Team stats', blurb: 'Every efficiency stat, sortable' },
			{ href: '/luck/', label: 'Luck', blurb: 'Record vs points, and who regresses' },
			{ href: '/fourth/', label: 'Fourth downs', blurb: 'Who leaves points on the field' }
		]
	},
	{
		label: 'Players',
		items: [
			{ href: '/qbs/', label: 'Quarterbacks', blurb: 'EPA per dropback, CPOE, intervals' },
			{ href: '/receivers/', label: 'Receivers', blurb: 'Target share, air yards, WOPR' },
			{ href: '/rushers/', label: 'Rushers', blurb: 'Efficiency on designed runs' }
		]
	},
	{
		label: 'Games',
		items: [
			{ href: '/games/', label: 'Scores & game charts', blurb: 'Win probability for every game' },
			{
				href: '/predictions/',
				label: 'Predictions vs Vegas',
				blurb: 'Model lines and the attempt to beat the market'
			}
		]
	},
	{
		label: 'History',
		items: [
			{ href: '/records/', label: 'Record book', blurb: 'Best and worst seasons, wildest games' },
			{ href: '/coaches/', label: 'Coaches', blurb: '4th-down nerve, records, ATS' },
			{ href: '/referees/', label: 'Referees', blurb: 'Flags and home-field lean' }
		]
	},
	{
		label: 'Learn',
		items: [
			{
				href: '/learn/',
				label: 'How football works',
				blurb: 'Expected points, win probability, 4th down math'
			},
			{ href: '/stability/', label: 'Signal vs noise', blurb: 'Which stats predict themselves' },
			{ href: '/glossary/', label: 'Glossary', blurb: 'Every metric, defined' }
		]
	},
	{
		label: 'Explore',
		items: [
			{ href: '/compare/', label: 'Compare', blurb: 'Any two teams or players, any seasons' },
			{ href: '/explore/', label: 'SQL explorer', blurb: 'Query every play in your browser' }
		]
	}
];

export const allPages: NavItem[] = [
	{ href: '/', label: 'Home', blurb: 'This week in numbers' },
	...navGroups.flatMap((g) => g.items)
];

/** Which group (if any) owns a path, for highlighting the active menu. */
export function groupFor(path: string): string | null {
	if (path.startsWith('/team/')) return 'Teams';
	if (path.startsWith('/player/')) return 'Players';
	if (path.startsWith('/game/')) return 'Games';
	if (path.startsWith('/odds/')) return 'Teams';
	for (const g of navGroups) if (g.items.some((i) => path.startsWith(i.href))) return g.label;
	return null;
}
