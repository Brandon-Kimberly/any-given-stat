// Shapes of the JSON files written by pipeline/src/ags/build.py.

export type Scope = 'all' | 'no_garbage';

export interface SeasonStatus {
	season: number;
	reg_games: number;
	last_week: number;
	complete: boolean;
}

export interface Meta {
	generated_at: string;
	seasons: SeasonStatus[];
	explorer_files: { season: number; file: string; bytes: number }[];
	source: string;
}

type SideMetrics<P extends string> = {
	[
		K in
			| 'plays'
			| 'epa_play'
			| 'pass_epa'
			| 'rush_epa'
			| 'success_rate'
			| 'pass_success'
			| 'rush_success'
			| 'pass_rate'
			| 'early_down_pass_rate'
			| 'proe'
			| 'explosive_rate'
			| 'turnover_rate'
			| 'sack_rate'
			| 'adot'
			| 'third_down_rate'
			| 'drives'
			| 'points_per_drive'
			| 'rz_trips'
			| 'rz_td_rate' as `${P}_${K}`
	]: number | null;
};

export type TeamSeason = {
	scope: Scope;
	season: number;
	team: string;
	net_epa_play: number;
} & SideMetrics<'off'> &
	SideMetrics<'def'> &
	Adjusted;

export interface TeamWeek {
	season: number;
	week: number;
	team: string;
	opp: string;
	pf: number;
	pa: number;
	off_epa: number;
	off_plays: number;
	def_epa: number;
	def_plays: number;
}

export interface Luck {
	season: number;
	team: string;
	games: number;
	wins: number;
	points_for: number;
	points_against: number;
	one_score_games: number;
	one_score_wins: number | null;
	pythag_wins: number;
	wins_over_pythag: number;
	fumbles: number | null;
	fumble_recovery_rate: number | null;
	takeaways: number | null;
	giveaways: number | null;
	turnover_margin: number | null;
}

export interface QB {
	scope: Scope;
	season: number;
	player_id: string;
	name: string;
	team: string;
	teams: string;
	dropbacks: number;
	epa_db: number;
	epa_db_lo: number;
	epa_db_hi: number;
	dropback_epa: number;
	success_rate: number;
	cpoe: number | null;
	adot: number | null;
	sack_rate: number;
	scramble_rate: number;
	int_rate: number;
	pass_tds: number;
	ints: number;
	pass_yards: number;
	designed_runs: number;
	designed_run_epa: number;
	total_epa: number;
}

export interface Receiver {
	season: number;
	team: string;
	player_id: string;
	name: string;
	targets: number;
	receptions: number;
	yards: number;
	tds: number;
	air_yards: number;
	adot: number | null;
	epa_target: number;
	total_epa: number;
	success_rate: number;
	catch_rate_oe: number | null;
	yac_oe: number | null;
	target_share: number;
	air_yards_share: number | null;
	wopr: number | null;
}

export interface Rusher {
	season: number;
	player_id: string;
	name: string;
	team: string;
	carries: number;
	yards: number;
	tds: number;
	epa_rush: number;
	total_epa: number;
	success_rate: number;
	explosive_rate: number;
	stuff_rate: number;
	ypc: number;
}

export interface StabilityMetric {
	key: string;
	label: string;
	group: string;
	denominator: string;
	split_half_r: number | null;
	split_half_pairs: number;
	avg_half_n: number | null;
	yoy_r: number | null;
	yoy_pairs: number;
	avg_season_n: number | null;
	full_season_reliability: number | null;
	n_for_half_signal: number | null;
}

export interface Stability {
	metrics: StabilityMetric[];
	yoy_pairs: Record<string, { unit: string; season: number; y1: number; y2: number }[]>;
}

export interface Adjusted {
	adj_off_epa: number | null;
	adj_def_epa: number | null;
	adj_net_epa: number | null;
}

export interface GamePrediction {
	season: number;
	week: number;
	game_id: string;
	gameday: string;
	home: string;
	away: string;
	neutral: boolean;
	/** Predicted home margin in points (positive = home favored). */
	model: number;
	/** Closing Vegas home margin (nflverse spread_line, positive = home favored). */
	vegas: number | null;
	home_wp: number;
	/** Points the starting-QB adjustment adds to each side (starter vs the QBs behind its rating). */
	home_qb_pts: number;
	away_qb_pts: number;
	home_qb: string | null;
	away_qb: string | null;
	result?: number;
}

export interface BacktestStats {
	games: number;
	model_mae: number;
	vegas_mae: number;
	model_su: number;
	vegas_su: number;
	ats_w: number;
	ats_l: number;
	edge3_w: number;
	edge3_l: number;
}

export interface Predictions {
	params: {
		lambda: number;
		half_life_weeks: number | null;
		points_per_epa: number;
		qb_weight: number;
		home_points: number;
		sigma: number;
		fit_seasons: [number, number];
		validate_seasons: [number, number];
		test_seasons: [number, number];
	};
	summary: (BacktestStats & { split: 'fit' | 'validate' | 'test' })[];
	by_season: (BacktestStats & { season: number })[];
	games: (GamePrediction & { result: number })[];
	upcoming: GamePrediction[];
}

export interface Rating {
	season: number;
	week: number;
	team: string;
	off: number;
	def: number;
	net: number;
	/** Net rating in points per game vs an average team on a neutral field. */
	points: number;
	off_points: number;
	def_points: number;
	rank: number;
}

export interface TeamSplit {
	season: number;
	team: string;
	side: 'off' | 'def';
	split: string;
	bucket: string;
	plays: number;
	epa: number;
	success: number;
	rank: number;
	ord: number;
}

export interface BetScore {
	games: number;
	mae: number;
	vegas_mae: number;
	bets: number;
	wins: number;
	win_rate: number | null;
	p_value: number | null;
}

type Prefixed<P extends string> = { [K in keyof BetScore as `${P}_${K}`]: BetScore[K] };

export type LabRow = { variant: string; threshold: number; beta: number[] } & Prefixed<'fit'> &
	Prefixed<'val'>;

export interface Lab {
	protocol: {
		fit_seasons: [number, number];
		validate_seasons: [number, number];
		test_seasons: [number, number];
		breakeven: number;
		thresholds: number[];
		min_validate_bets: number;
	};
	variants: Record<string, string[]>;
	selection: LabRow[];
	chosen: { variant: string; threshold: number } | null;
	test: BetScore | null;
}
