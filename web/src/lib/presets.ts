// Example queries for the SQL explorer. Each runs against the `pbp` view
// (the seasons selected in the UI). Verified by pipeline/tests/test_presets.py.

export interface Preset {
	title: string;
	question: string;
	sql: string;
}

export const presets: Preset[] = [
	{
		title: '4th-down aggressiveness',
		question: 'Who goes for it on 4th and short in competitive games?',
		sql: `select posteam as team,
       count(*) as fourth_and_short,
       round(avg(case when play_type in ('pass', 'run') then 1 else 0 end), 3) as go_rate,
       round(avg(epa) filter (where play_type in ('pass', 'run')), 3) as epa_when_going
from pbp
where season_type = 'REG' and down = 4 and ydstogo <= 2
  and yardline_100 between 1 and 60
  and wp between 0.1 and 0.9
  and play_type in ('pass', 'run', 'punt', 'field_goal')
group by 1
order by go_rate desc, fourth_and_short desc`
	},
	{
		title: 'QBs on 3rd and long',
		question: 'Who actually converts when the defense knows a pass is coming?',
		sql: `select passer as qb, posteam as team,
       count(*) as dropbacks,
       round(avg(qb_epa), 3) as epa_per_db,
       round(avg(case when first_down = 1 or touchdown = 1 then 1 else 0 end), 3) as conv_rate
from pbp
where season_type = 'REG' and down = 3 and ydstogo >= 7 and pass = 1 and passer is not null
group by 1, 2
having count(*) >= 30
order by epa_per_db desc`
	},
	{
		title: 'Neutral early-down pass rate',
		question: 'Who passes on early downs when the game is close (the analytics-approved choice)?',
		sql: `select posteam as team,
       count(*) as plays,
       round(avg(pass), 3) as pass_rate,
       round(avg(pass - xpass), 3) as pass_rate_over_expected,
       round(avg(epa) filter (where pass = 1), 3) as pass_epa,
       round(avg(epa) filter (where rush = 1), 3) as rush_epa
from pbp
where season_type = 'REG' and down in (1, 2) and wp between 0.2 and 0.8
  and half_seconds_remaining > 120 and play_type in ('pass', 'run')
group by 1
order by pass_rate desc`
	},
	{
		title: 'Pass vs run, league-wide',
		question: 'Is passing really more efficient than running, by down?',
		sql: `select down,
       round(avg(epa) filter (where pass = 1), 3) as pass_epa,
       round(avg(epa) filter (where rush = 1), 3) as rush_epa,
       round(avg(success) filter (where pass = 1), 3) as pass_success,
       round(avg(success) filter (where rush = 1), 3) as rush_success,
       count(*) as plays
from pbp
where season_type = 'REG' and play_type in ('pass', 'run') and down is not null
  and wp between 0.1 and 0.9
group by 1
order by 1`
	},
	{
		title: 'Does wind hurt passing?',
		question: 'Pass EPA by wind speed in outdoor games.',
		sql: `select case when wind is null then 'unknown'
            when wind < 5 then '0-4 mph'
            when wind < 10 then '5-9 mph'
            when wind < 15 then '10-14 mph'
            when wind < 20 then '15-19 mph'
            else '20+ mph' end as wind,
       count(*) as dropbacks,
       round(avg(epa), 3) as pass_epa,
       round(avg(cpoe), 2) as cpoe
from pbp
where season_type = 'REG' and pass = 1 and roof in ('outdoors', 'open')
group by 1
order by min(coalesce(wind, 999))`
	},
	{
		title: 'Value by throw depth',
		question: 'How much is a deep shot worth compared with a checkdown?',
		sql: `select case when air_yards < 0 then 'behind LOS'
            when air_yards < 5 then '0-4'
            when air_yards < 10 then '5-9'
            when air_yards < 20 then '10-19'
            else '20+' end as depth,
       count(*) as attempts,
       round(avg(complete_pass), 3) as comp_rate,
       round(avg(epa), 3) as epa_per_att,
       round(avg(interception), 4) as int_rate
from pbp
where season_type = 'REG' and pass = 1 and air_yards is not null and sack = 0
group by 1
order by min(air_yards)`
	},
	{
		title: 'Biggest plays by win probability',
		question: 'The plays that swung games the most.',
		sql: `select season, week, posteam as offense, defteam as defense, qtr,
       round(wpa, 3) as wpa, round(epa, 2) as epa, "desc"
from pbp
where wpa is not null
order by abs(wpa) desc
limit 25`
	},
	{
		title: 'Shotgun vs under center runs',
		question: 'Are runs from shotgun more efficient, team by team?',
		sql: `select posteam as team,
       round(avg(epa) filter (where shotgun = 1), 3) as gun_epa,
       count(*) filter (where shotgun = 1) as gun_runs,
       round(avg(epa) filter (where shotgun = 0), 3) as under_center_epa,
       count(*) filter (where shotgun = 0) as uc_runs
from pbp
where season_type = 'REG' and rush = 1 and wp between 0.1 and 0.9
group by 1
order by gun_epa - under_center_epa desc`
	},
	{
		title: 'Two-minute drill',
		question: 'Which offenses are best at the end of the first half?',
		sql: `select posteam as team,
       count(*) as plays,
       round(avg(epa), 3) as epa_per_play,
       round(sum(epa), 1) as total_epa
from pbp
where season_type = 'REG' and qtr = 2 and half_seconds_remaining <= 120
  and play_type in ('pass', 'run')
group by 1
order by epa_per_play desc`
	},
	{
		title: 'Home field advantage',
		question: 'How big is home field, measured in EPA per play?',
		sql: `select season,
       round(avg(epa) filter (where posteam = home_team), 3) as home_epa,
       round(avg(epa) filter (where posteam = away_team), 3) as away_epa,
       round(avg(epa) filter (where posteam = home_team)
           - avg(epa) filter (where posteam = away_team), 3) as home_edge
from pbp
where season_type = 'REG' and play_type in ('pass', 'run')
group by 1
order by 1`
	}
];
