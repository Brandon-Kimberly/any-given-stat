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
	SideMetrics<'def'>;

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
