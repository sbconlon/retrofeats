# This file defines the pitching stats for each player.

# External imports
import numpy as np
import pandas as pd
import sys

# Adding top level project directory
sys.path.insert(0, '../../')

# It's difficult to define FIP across seasons because of the FIP constant is
# defined on a per season basis.
#
# The proper way to do this would be to calculate the FIP constant over the
# period of interest. This would be computationally expensive however.
#
# Instead, as an approximation, I will use a weighted average of FIP constants
# according to TBF per year.
def calcFIP(stats, consts):
    wc_sum = 0 # weighted FIP constant sum (numerator)
    for year, season_stats in stats.groupby(stats.date.dt.year):
        c = consts.loc[consts['Season'] == year]['cFIP'].iloc[0]
        wc_sum += c*season_stats['P_TBF'].sum()
    tbf = stats['P_TBF'].sum()
    wc = wc_sum/tbf if tbf != 0 else 0 # weighted FIP constant
    # Calculate FIP
    hr = stats['P_HR'].sum() + stats['P_HR4'].sum()
    bb = stats['P_BB'].sum()
    hp = stats['P_HP'].sum()
    so = stats['P_SO'].sum()
    ip = stats['P_OUT'].sum()/3
    return ((13*hr+3*(bb+hp)-2*so)/ip) + wc if ip != 0 else 0

# Class for storing historical pitching stats
class PitchingStats:
    # Path to pitching dataset
    path = 'data/players-daybyday'

    # Counting stats
    counting_stats = ['G',      # Game appearances
                      'GS',     # Games started
                      #'CG',     # Complete game
                      #'SHO',    # Complete game shutout
                      #'GF',     # Game finished (last pitcher to appear for their team)
                      #'W',      # Win
                      #'L',      # Loss
                      #'SV',     # Save
                      'OUT',    # Outs recorded
                      'TBF',    # Total batters faced
                      'AB',     # At-bats against
                      'R',      # Runs allowed
                      'ER',     # Earned runs allowed
                      'H',      # Hits allowed
                      'TB',     # Total bases allowed
                      '2B',     # Doubles allowed
                      '3B',     # Triples allowed
                      'HR',     # Homeruns allowed
                      'HR4',    # Grand slams allowed
                      'BB',     # Base on balls (walks) allowed
                      'IBB',    # Intentional walks allowed
                      'SO',     # Strikeouts
                      'GDP',    # Ground ball double plays forced
                      'HP',     # Hit batters
                      'SH',     # Sacrifice bunts allowed
                      'SF',     # Sacrifice flys allowed
                      'WP',     # Wild pitches
                      'BK',     # Balks
                      'IR',     # Inherited runners
                      'IRS',    # Inherited runners who scored
                      'GO',     # Ground outs
                      'AO',     # Air outs
                      'PITCH',  # Pitches thrown
                      'STRIKE'] # Strikes thrown

    # Derived stats:
    #  * K% - Strikeout rate
    #  * BB% - Walk rate
    #  * BABIP - Batting average on balls in play
    #  * LOB% - % left on base
    #  * HR/FB - homeruns per fly ball
    #  * ERA - Earned run average
    #  * FIP - Fielding independent pitching
    #  * WHIP - Walks hits over innings pitched
    #  * GB/TBF - ground ball rate (proxy for GB% because retrosplits doesn't track total ground balls)
    derived_stats = {'BB%': lambda df: df['BB']/df['TBF'] if df['TBF'] != 0 else 0,
                     'K%': lambda df: df['SO']/df['TBF'] if df['TBF'] != 0 else 0,
                     'BABIP': lambda df: (df['H']-df['HR'])/(df['AB']-df['SO']-df['HR']+df['SF']) if (df['AB']-df['SO']-df['HR']+df['SF']) != 0 else 0,
                     'LOB%': lambda df: (df['H']+df['BB']+df['HP']-df['R'])/(df['H']+df['BB']+df['HP']-(1.4*df['HR'])) if (df['H']+df['BB']+df['HP']-(1.4*df['HR'])) != 0 else 0,
                     'HR/FB': lambda df: df['HR']/df['AO'] if df['AO'] != 0 else 0,
                     'ERA': lambda df: 9*(df['ER']/(df['OUT']/3)) if df['OUT'] != 0 else 0,
                     'WHIP': lambda df: (df['BB']+df['H'])/(df['OUT']/3) if df['OUT'] != 0 else 0,
                     'GO/TBF': lambda df: df['GO']/df['TBF'] if df['TBF'] != 0 else 0}

    weighted_stats = {'FIP': calcFIP}

    stats = counting_stats + list(derived_stats.keys()) + list(weighted_stats.keys())

    def __init__(self, game_id, player_id, stat_features, intervals=(5, 10, 20)):
        #
        # Player associated with these stats
        self.gid = game_id
        self.pid = player_id
        #
        # Initialize in-game player counting stats
        self.in_game_stats = {stat_name: 0 for stat_name in PitchingStats.counting_stats}
        #
        # Initialize player stats over given intervals
        self.intervals = intervals
        self.historical_stats = None
        #
        # Stats from this player's pitching we want as features in our dataset
        for stat in stat_features:
            assert(stat in PitchingStats.stats)
        self.stat_features = stat_features
        self.features = None

    def read_historical_stats(self):
        # Initialize 2D dictionary: game iterval -> stat category -> stat value
        self.stats = {i: {s: None for s in PitchingStats.stats} for i in self.intervals}
        # Read stats from retrosplits
        stats_df = pd.read_csv(PitchingStats.path+f'/{self.pid}.csv')
        stats_df['date'] = pd.to_datetime(stats_df['date'])
        constants_df = pd.read_csv('data/wOBA-weights.csv')
        present = stats_df.index[stats_df['game.key'] == self.gid][0]
        # Populate from retrosplits into the batter stats object
        for past in self.intervals:
            # Get games in the given interval
            df = stats_df.iloc[max(present-past, 0):present]
            # Get counting stats from retrosplits
            for cs in PitchingStats.counting_stats:
                self.stats[past][cs] = df['P_'+cs].sum()
            # Calculate derived stats
            for ds in PitchingStats.derived_stats:
                self.stats[past][ds] = PitchingStats.derived_stats[ds](self.stats[past])
            # Calculate weighted stats (weighted based on year)
            for ws in PitchingStats.weighted_stats:
                self.stats[past][ws] = PitchingStats.weighted_stats[ws](df, constants_df)

    def featurize(self):
        if self.historical_stats is None:
            self.read_historical_stats()
        if self.features is None:
            feat_dict = {}
            for i in self.intervals:
                for stat in self.stat_features:
                    feat_dict[f'P_G{i}_{stat}'] = self.stats[i][stat]
            self.features = pd.Series(feat_dict, dtype=np.float64)
        return self.features

    # Increments count for the given list of stats
    def increment_stats(self, stats):
        for name in stats:
            self.in_game_stats[name] += 1

    # Adds the value to the given stat
    def add_to_stat(self, stat, value):
        self.in_game_stats[stat] += value

    # Get the player's stats for a given game
    def get_game_stats(self, game_id, stat_path):
        stats_df = pd.read_csv(stat_path+f'/{self.pid}.csv')
        return stats_df[stats_df['game.key'] == game_id].iloc[0]
