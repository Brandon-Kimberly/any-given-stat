// Shapes of the JSON files written by pipeline/src/ags/build.py.
import type { FantasyPos, StatLine } from './fantasy/statline';

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
	full_name?: string | null;
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
	full_name?: string | null;
	position?: string | null;
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
	full_name?: string | null;
	position?: string | null;
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
	/** Market blend (line + k * (model - line)): the best single estimate. */
	blend?: number;
	/** The blend as a home win probability (upcoming games). */
	blend_wp?: number | null;
	/** Local kickoff time, "HH:MM" (upcoming games). */
	gametime?: string | null;
}

/** schedule/<season>.json: every game of a season, played or not (nflverse schedule). */
export interface ScheduleGame {
	game_id: string;
	season: number;
	game_type: 'REG' | 'WC' | 'DIV' | 'CON' | 'SB' | string;
	week: number;
	gameday: string;
	gametime: string | null;
	away: string;
	home: string;
	away_score: number | null;
	home_score: number | null;
	/** Home margin; null until played. */
	result: number | null;
	/** Closing line, home margin (positive = home favored). */
	vegas: number | null;
	roof: string | null;
	stadium: string | null;
	neutral: boolean;
	away_coach: string | null;
	home_coach: string | null;
	referee: string | null;
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
		/** The frozen round-3 forecast that produced `model` (lab3.json). */
		model?: string | null;
		/** Market blend weight: line + k * (model - line). */
		blend_k?: number;
	};
	summary: (BacktestStats & { split: 'fit' | 'validate' | 'test' })[];
	by_season: (BacktestStats & { season: number })[];
	games: (GamePrediction & { result: number })[];
	upcoming: GamePrediction[];
	/** Each team's next game when it has none in `upcoming` (a bye, or it played Thursday). */
	next_games?: GamePrediction[];
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
	mae: number | null;
	vegas_mae: number | null;
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

export interface TeamMeta {
	team: string;
	name: string;
	nick: string;
	conf: string;
	division: string;
	color: string;
	color2: string;
	color_light: string;
	color_dark: string;
	badge_fg: string;
	/** Logo tile under /data (logos/<TEAM>.png) when the build could fetch it. */
	logo?: string;
}

export interface Player {
	player_id: string;
	name: string;
	position: string | null;
	position_group: string | null;
	rookie_season: number | null;
	draft_year: number | null;
	draft_round: number | null;
	draft_pick: number | null;
	college: string | null;
	/** NFL.com headshot URL (loaded by the browser; may be missing or blocked). */
	headshot: string | null;
}

export interface Concepts {
	seasons: [number, number];
	ep_curve: { down: number; yardline_100: number; ep: number; n: number }[];
	wp_grid: { score_diff: number; minutes_left: number; wp: number; n: number }[];
	situations: {
		down: number;
		distance: string;
		ord: number;
		plays: number;
		pass_rate: number;
		pass_epa: number | null;
		run_epa: number | null;
		pass_success: number | null;
		run_success: number | null;
	}[];
	epa_hist: { kind: 'Pass' | 'Run'; bin: number; share: number }[];
	fourth: {
		conversion: { ydstogo: number; attempts: number; rate: number }[];
		field_goals: { distance: number; attempts: number; made_rate: number }[];
	};
}

export interface FourthBucket {
	distance: string;
	field: string;
	dist_ord: number;
	field_ord: number;
	go_epa: number | null;
	go_n: number;
	punt_epa: number | null;
	punt_n: number;
	fg_epa: number | null;
	fg_n: number;
	best: 'go' | 'punt' | 'fg' | null;
	margin: number | null;
}

export interface FourthTeam {
	season: number;
	team: string;
	fourth_downs: number;
	go_rate: number;
	clear_go: number;
	went_when_clear_go: number;
	epa_lost: number;
	rank: number;
}

export interface FourthDowns {
	buckets: FourthBucket[];
	teams: FourthTeam[];
	meta: {
		reference_seasons: [number, number];
		clear_margin: number;
		min_n: number;
		caveat: string;
	};
}

export interface BoxSide {
	plays: number;
	epa_play: number | null;
	success_rate: number | null;
	pass_epa: number | null;
	rush_epa: number | null;
	yards: number;
	turnovers: number;
}

export interface GameDetail {
	game_id: string;
	season: number;
	week: number;
	season_type: string;
	home: string;
	away: string;
	home_score: number | null;
	away_score: number | null;
	gameday: string | null;
	wp: [number, number][];
	top_plays: {
		qtr: number;
		time: string | null;
		posteam: string;
		desc: string;
		home_wpa: number;
		epa: number | null;
	}[];
	box: { home: BoxSide | null; away: BoxSide | null };
}

export interface GameIndexEntry {
	season: number;
	file: string;
	games: number;
}

export interface QBGame {
	season: number;
	week: number;
	game_id: string;
	player_id: string;
	name: string;
	team: string;
	opp: string;
	dropbacks: number;
	epa_db: number;
	cpoe: number | null;
	success_rate: number;
	pass_yards: number;
	tds: number;
	ints: number;
	sacks: number;
}

/** One play in games/<season>/<game_id>.json (column order = GamePlays.plays_columns). */
export type PlayRow = [
	qtr: number,
	time: string | null,
	posteam: string,
	down: number | null,
	ydstogo: number | null,
	/** Yards from the offense's own goal line. */
	yl: number | null,
	play_type: string | null,
	desc: string,
	epa: number | null,
	home_wp_after: number | null,
	home_score: number | null,
	away_score: number | null,
	/** Letters: T touchdown, I interception, F fumble lost, S sack, P penalty, X explosive, 4 fourth-down try. */
	flags: string,
	drive: number | null
];

export interface Drive {
	n: number;
	posteam: string;
	qtr: number | null;
	start_clock: string | null;
	start_yl: number | null;
	end_yl: number | null;
	plays: number;
	yards: number | null;
	result: string | null;
	top: string | null;
	points: number | null;
}

export interface GamePlays {
	game_id: string;
	plays_columns: string[];
	flags: Record<string, string>;
	drives: Drive[];
	plays: PlayRow[];
	/** Full box score (statlines.py); missing in files built before it existed. */
	box?: GameBox | null;
}

/** Team box score for one game (pipeline statlines.season_lines "teams"). */
export interface TeamBox {
	first_downs: number;
	first_downs_pass: number;
	first_downs_rush: number;
	first_downs_pen: number;
	/** [converted, attempts] */
	third: [number, number];
	fourth: [number, number];
	plays: number;
	yards: number;
	/** Net of sack yardage. */
	pass_yds: number;
	rush_yds: number;
	/** [sacks, yards lost] */
	sacked: [number, number];
	/** [count, yards] */
	penalties: [number, number];
	turnovers: number;
	fumbles_lost: number;
	ints: number;
	top_sec: number;
	/** [touchdowns, trips] */
	red_zone: [number, number];
	ret_yds: number;
}

export interface GameBox {
	/** id -> [name, position]; team defenses use the team code as id and 'DEF'. */
	players: Record<string, [string, FantasyPos]>;
	/** [id, team, stats] */
	lines: [string, string, StatLine][];
	teams: Record<string, TeamBox>;
}

export interface PlayoffOddsRow {
	team: string;
	/** 0 = preseason; w = after week w. */
	week: number;
	mean_wins: number;
	wins_p10: number;
	wins_p90: number;
	p_playoffs: number;
	p_division: number;
	p_bye: number;
	p_conf: number;
	p_sb: number;
	mean_seed_if_in: number | null;
}

export interface PlayoffOdds {
	season: number;
	sims: number;
	seeds: number;
	byes: number;
	weeks: number[];
	rows: PlayoffOddsRow[];
	/** The simulator's game model (v2). */
	model?: {
		b_epa: number;
		b_mov: number;
		b_home: number;
		sigma: number;
		tau_preseason: number;
		tau_late: number;
	};
	/** What actually happened, once the season is over. */
	actual: Record<
		string,
		{ made_playoffs: boolean; won_division: boolean; sb_winner: boolean }
	> | null;
}

export interface PlayoffIndexEntry {
	season: number;
	file: string;
	weeks: number[];
}

export interface RecordTeam {
	season: number;
	team: string;
	games: number;
	wins: number;
	losses: number;
	ties: number;
	net_epa: number;
	off_epa: number;
	def_epa: number;
}
export interface RecordPlayer {
	season: number;
	player_id: string;
	name: string;
	full_name?: string | null;
	position?: string | null;
	team: string;
	dropbacks?: number;
	targets?: number;
	carries?: number;
	yards?: number;
	epa_db?: number;
	epa_target?: number;
	epa_rush?: number;
	cpoe?: number | null;
	total_epa: number;
}
export interface RecordUpset {
	game_id: string;
	season: number;
	week: number;
	game_type: string;
	home: string;
	away: string;
	home_score: number;
	away_score: number;
	spread: number;
	underdog: string;
	favorite: string;
}
export interface RecordGame {
	game_id: string;
	season: number;
	week: number;
	season_type: string;
	home: string;
	away: string;
	home_score: number;
	away_score: number;
	winner: string | null;
	excitement: number;
	winner_min_wp: number | null;
}
export interface RecordPlay {
	game_id: string;
	season: number;
	week: number;
	season_type: string;
	posteam: string;
	defteam: string;
	qtr: number;
	time: string | null;
	wpa: number;
	epa: number | null;
	desc: string;
}
export interface Records {
	seasons: [number, number];
	thresholds: { min_team_games: number; min_qb_dropbacks: number; min_rush_carries: number };
	wp_note: string;
	team_best: RecordTeam[];
	team_worst: RecordTeam[];
	offense_best: RecordTeam[];
	defense_best: RecordTeam[];
	qb_best: RecordPlayer[];
	qb_worst: RecordPlayer[];
	receiver_best: RecordPlayer[];
	rusher_best: RecordPlayer[];
	upsets: RecordUpset[];
	excitement: RecordGame[];
	comebacks: RecordGame[];
	biggest_plays: RecordPlay[];
}

interface CoachStats {
	coach: string;
	games: number;
	wins: number;
	losses: number;
	ties: number;
	ats_w: number;
	ats_l: number;
	ats_push: number;
	point_diff: number;
	/** Fourth downs where going for it was clearly right (the 4th-down model's "clear go"). */
	clear_go: number;
	net_epa: number;
	go_rate_clear: number | null;
	proe: number | null;
}
export type CoachSeason = CoachStats & { season: number; team: string };
export type CoachCareer = CoachStats & {
	seasons: number;
	teams: string;
	win_pct: number;
	ats_pct: number | null;
	first: number;
	last: number;
};
export interface Coaches {
	seasons: CoachSeason[];
	careers: CoachCareer[];
}

interface RefStats {
	referee: string;
	games: number;
	penalties_pg: number;
	penalty_yards_pg: number;
	home_penalty_share: number;
	home_win_pct: number;
	points_pg: number;
}
export type RefSeason = RefStats & { season: number };
export type RefCareer = RefStats & { seasons: number; first: number; last: number };
export interface Referees {
	seasons: RefSeason[];
	careers: RefCareer[];
}

export interface Lab2Game {
	game_id: string;
	week: number;
	gameday: string;
	home: string;
	away: string;
	vegas: number | null;
	/** Predicted home margin. */
	model: number;
	result: number | null;
	/** Team the model bets on (|model - line| >= threshold), else null. */
	bet: string | null;
	won: boolean | null;
	/** Kicked off after the freeze date: part of the clean test. */
	sealed: boolean;
}

export interface Lab2Upcoming extends Lab2Game {
	factors: { feature: string; label: string; points: number }[];
	injuries: Record<
		'home' | 'away',
		{ name: string; pos: string; status: string; impact: number }[]
	>;
	weather: {
		roof: string | null;
		temp: number | null;
		wind: number | null;
		source: 'recorded' | 'forecast' | null;
	};
}

export interface Lab2 {
	protocol: Lab['protocol'] & {
		freeze_date: string;
		live_season: number;
		status_weights: Record<string, number>;
		role_games: number;
		has_injuries: boolean;
		teams_with_final_statuses: number | null;
		teams_playing: number;
	};
	market_check: {
		feature: string;
		label: string;
		vs_ratings: number;
		vs_ratings_se: number;
		vs_line: number;
		vs_line_se: number;
		share_nonzero: number;
	}[];
	variants: Record<string, string[]>;
	labels: Record<string, string>;
	selection: (Omit<LabRow, 'beta'> & { beta?: number[] })[];
	chosen: { variant: string; threshold: number };
	selection_agrees: boolean;
	test: BetScore;
	coefficients: {
		feature: string;
		label: string;
		beta: number;
		se: number;
		typical_points: number;
	}[];
	live: { pre_freeze: BetScore; sealed: BetScore; games: Lab2Game[] };
	upcoming: Lab2Upcoming[];
}

export interface ForecastMetrics {
	games: number;
	rmse?: number;
	mae?: number;
	log_loss?: number;
	brier?: number;
	winner?: number;
}

export interface PairedDiff {
	games: number;
	/** Mean (squared error of a) - (squared error of b); negative favors a. */
	diff: number;
	se: number;
}

export type Lab3Split = Record<
	'round3' | 'blend' | 'vegas' | 'round2' | 'round1',
	ForecastMetrics
> &
	Record<'round3_vs_vegas' | 'round3_vs_round1' | 'blend_vs_vegas', PairedDiff | null>;

export interface Lab3 {
	protocol: {
		fit_seasons: [number, number];
		validate_seasons: [number, number];
		test_seasons: [number, number];
		freeze_date: string;
		live_season: number;
	};
	variants: Record<string, string[]>;
	labels: Record<string, string>;
	selection: ({ variant: string; features: number; sigma: number } & {
		[K in keyof Required<ForecastMetrics> as `fit_${K}` | `val_${K}`]: number;
	})[];
	chosen: { variant: string };
	selection_agrees: boolean;
	sigma: number;
	blend_k: number;
	coefficients: {
		feature: string;
		label: string;
		beta: number;
		se: number;
		typical_points: number;
	}[];
	comparison: Record<'fit' | 'validate' | 'test' | 'pre_freeze' | 'sealed', Lab3Split>;
	by_season: {
		season: number;
		round3: number | null;
		vegas: number | null;
		round1: number | null;
		games: number;
	}[];
	sim: {
		b_epa: number;
		b_mov: number;
		b_home: number;
		sigma: number;
		seasons: {
			season: number;
			brier_playoffs: number | null;
			brier_division: number | null;
			v1_brier_playoffs: number | null;
			v1_brier_division: number | null;
		}[];
	};
	upcoming: {
		game_id: string;
		week: number;
		home: string;
		away: string;
		vegas: number | null;
		model: number;
		blend: number;
		home_wp: number;
		blend_wp: number;
		factors: { feature: string; label: string; points: number }[];
		injuries: Lab2Upcoming['injuries'];
	}[];
}
