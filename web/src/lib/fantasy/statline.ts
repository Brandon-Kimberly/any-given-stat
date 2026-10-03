// One player's (or one team defense's) stats in one game, as written by the pipeline
// (pipeline/src/ags/statlines.py). Keys follow Sleeper's scoring-setting names where one
// exists, so most Sleeper rules apply directly. Zero values are omitted: read with `?? 0`.
//
// Box scores and fantasy scoring both read these lines, so a box score number and the
// fantasy points built from it can never disagree.

export interface StatLine {
	// Passing
	pass_att?: number;
	pass_cmp?: number;
	pass_inc?: number;
	pass_yd?: number;
	pass_td?: number;
	pass_int?: number;
	pass_int_td?: number; // interceptions returned for a TD (pick-sixes thrown)
	pass_sack?: number;
	pass_sack_yd?: number;
	pass_fd?: number;
	pass_2pt?: number;
	pass_cmp_40p?: number; // completions of 40+ yards
	pass_lng?: number;
	pass_epa?: number; // qb_epa on dropbacks
	pass_td_yds?: number[]; // length of each TD pass

	// Rushing (official: includes scrambles and kneels)
	rush_att?: number;
	rush_yd?: number;
	rush_td?: number;
	rush_fd?: number;
	rush_2pt?: number;
	rush_40p?: number;
	rush_lng?: number;
	rush_epa?: number;
	rush_td_yds?: number[];

	// Receiving
	rec_tgt?: number;
	rec?: number;
	rec_yd?: number;
	rec_td?: number;
	rec_fd?: number;
	rec_2pt?: number;
	rec_40p?: number;
	rec_lng?: number;
	rec_yac?: number;
	rec_epa?: number;
	rec_td_yds?: number[];
	rec_0_4?: number; // receptions by gain: 0-4, 5-9, 10-19, 20-29, 30-39 yards (40+ = rec_40p)
	rec_5_9?: number;
	rec_10_19?: number;
	rec_20_29?: number;
	rec_30_39?: number;

	// Ball security
	fum?: number;
	fum_lost?: number;
	fum_rec_td?: number; // recovered a teammate's/own fumble for a TD

	// Returns (player lines; team totals on DEF lines)
	kr?: number;
	kr_yd?: number;
	kr_td?: number;
	kr_lng?: number;
	pr?: number;
	pr_yd?: number;
	pr_td?: number;
	pr_lng?: number;

	// Kicking
	fga?: number;
	fgm?: number;
	fgmiss?: number;
	fg_lng?: number;
	fgm_dists?: number[]; // distance of each made field goal
	fgmiss_dists?: number[];
	xpa?: number;
	xpm?: number;
	xpmiss?: number;

	// Punting
	punts?: number;
	punt_yd?: number;
	punt_in20?: number;
	punt_tb?: number;
	punt_lng?: number;

	// Defense: individual (IDP / box score) and team (DEF lines)
	tkl_solo?: number;
	tkl_ast?: number;
	tkl_loss?: number;
	sack?: number; // half sacks count 0.5
	sack_yd?: number;
	qb_hit?: number;
	def_int?: number;
	int_ret_yd?: number;
	def_pd?: number; // passes defensed
	def_ff?: number;
	def_fum_rec?: number;
	def_td?: number; // interception or fumble return TDs
	def_safe?: number;
	blk_kick?: number;

	// Special-teams TDs. Players: every TD they scored on a kick play (returns, blocked-kick
	// returns, recoveries), so it already includes kr_td + pr_td. DEF: the team's total.
	st_td?: number;

	// Team defense / special teams only (position 'DEF')
	pts_allow?: number; // opponent points minus the opponent's own return TDs (6 each)
	yds_allow?: number; // opponent offensive yards (net of sacks)
}

export type StatKey = keyof StatLine;
export type NumericStatKey = {
	[K in StatKey]-?: NonNullable<StatLine[K]> extends number ? K : never;
}[StatKey];

// Player positions as the site uses them. Team defenses use 'DEF' with the team code as id.
export type FantasyPos = 'QB' | 'RB' | 'WR' | 'TE' | 'K' | 'DEF' | 'DL' | 'LB' | 'DB' | 'P' | 'OL';

/** fantasy/<season>.json: every regular- and postseason stat line of a season. */
export interface FantasySeason {
	season: number;
	/** id -> [display name, position]; ids are gsis ids, or team codes for 'DEF'. */
	players: Record<string, [string, FantasyPos]>;
	/** game_id -> [week, season_type ('REG' | 'POST'), home, away]. */
	games: Record<string, [number, string, string, string]>;
	/** [game_id, player id, team, stats] */
	lines: [string, string, string, StatLine][];
}

/** fantasy_ids.json: other platforms' player ids -> gsis id (players in our stat lines). */
export interface FantasyIds {
	sleeper: Record<string, string>;
	espn: Record<string, string>;
}
