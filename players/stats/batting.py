# This file defines the batting stats for each player.

# External imports
import numpy as np
import pandas as pd
import sys

# Adding top level project directory
sys.path.insert(0, '../../')

woba_cols = ['AB', 'BB', 'HP', 'H', '2B', '3B', 'HR', 'HR4', 'IBB', 'SF', 'PA']
wTB = lambda w, x: float(w['wBB']*x['BB']+w['wHBP']*x['HP']+w['w1B']*x['1B']+w['w2B']*x['2B']+w['w3B']*x['3B']+w['wHR']*(x['HR']+x['HR4']))
wOBA = lambda w, x: float(x['wTB']/(x['AB']+x['BB']-x['IBB']+x['SF']+x['HP']))

# Calculate wOBA accounting for weighting differences between years
def calcwOBA(stats, consts):
    # Calculate total weighted bases for each year
    wtb = 0
    for year, season_stats in stats.groupby(stats.date.dt.year):
        w = consts.loc[consts['Season'] == year]
        sts = {col: season_stats['B_'+col].sum() for col in woba_cols}
        sts['1B'] = sts['H'] - sts['2B'] - sts['3B'] - sts['HR'] - sts['HR4']
        wtb += wTB(w, sts)
    # Divide total weighted bases by total plate appearances (minus intentional walks)
    sts = {col: stats['B_'+col].sum() for col in woba_cols}
    sts['wTB'] = wtb
    return wOBA(w, sts) if (sts['AB']+sts['BB']-sts['IBB']+sts['SF']+sts['HP']) != 0 else 0


wRAA = lambda w, x: float(((x['wOBA']-w['wOBA'])/w['wOBAScale'])*x['PA'])

def calcwRAA(stats, consts):
    # Accumulate total wRAA over the years
    wraa = 0
    for year, season_stats in stats.groupby(stats.date.dt.year):
        w = consts.loc[consts['Season'] == year]
        sts = {col: season_stats['B_'+col].sum() for col in woba_cols}
        sts['1B'] = sts['H'] - sts['2B'] - sts['3B'] - sts['HR'] - sts['HR4']
        sts['wTB'] = wTB(w, sts)
        sts['wOBA'] = wOBA(w, sts) if (sts['AB']+sts['BB']-sts['IBB']+sts['SF']+sts['HP']) != 0 else 0
        wraa += wRAA(w, sts)
    return wraa


# Class for storing historical batting stats
class BattingStats:
    # Path to input dataset
    path = 'data/players-daybyday'

    # Historical Counting stats
    counting_stats = ['G',     # Games
                      'PA',    # Plate appearances
                      'AB',    # At-bats
                      'R',     # Runs
                      'H',     # Hits
                      'TB',    # Total bases
                      '2B',    # Doubles
                      '3B',    # Triples
                      'HR',    # Homeruns
                      'HR4',   # Grand slams
                      'RBI',   # Runs batted in
                      'BB',    # Base on balls (walks)
                      'IBB',   # Intentional walks
                      'SO',    # Strikeouts
                      'GDP',   # Ground into double play
                      'HP',    # Hit by pitch
                      'SH',    # Sacrifice bunt
                      'SF',    # Sacrifice fly
                      'SB',    # Stolen base
                      'CS']    # Caught stealing

    # Historical Derived Stats
    #  * K%  - Strikeout frequency
    #  * BB% - Walk frequency
    #  * ISO - Isolated power
    #  * BABIP - Batting average on balls in play
    #  * OBP - On-base percentage
    #  * SLG - Slugging percentage
    #  * OPS - On-base plus slugging
    #  * AVG - Batting average
    derived_stats = {'1B': lambda df: df['H']-df['2B']-df['3B']-df['HR']-df['HR4'],
                     'K%': lambda df: df['SO']/df['PA'] if df['PA'] != 0 else 0,
                     'BB%': lambda df: df['BB']/df['PA'] if df['PA'] != 0 else 0,
                     'ISO': lambda df: (df['2B']+2*df['3B']+3*(df['HR']+df['HR4']))/df['AB'] if df['AB'] != 0 else 0,
                     'BABIP': lambda df: (df['H']-df['HR'])/(df['AB']-df['SO']-df['HR']+df['SF']) if (df['AB']-df['SO']-df['HR']+df['SF']) != 0 else 0,
                     'OBP': lambda df: (df['H']+df['BB']+df['HP'])/(df['AB']+df['BB']+df['SF']+df['HP']) if (df['AB']+df['BB']+df['SF']+df['HP']) != 0 else 0,
                     'SLG': lambda df: df['TB']/df['AB'] if df['AB'] != 0 else 0,
                     'OPS': lambda df: df['OBP']+df['SLG'],
                     'AVG': lambda df: df['H']/df['AB'] if df['AB'] != 0 else 0}

    # Weighted stats
    #  * wTB  - weighted total bases (numberator of wOBA formula)
    #  * wOBA - Weighted on-base percentage
    #  * wRAA - Weighted runs above average
    weighted_stats = {'wOBA': calcwOBA,
                      'wRAA': calcwRAA}

    stats = counting_stats + list(derived_stats.keys()) + list(weighted_stats.keys())

    # Populate player's batting stats upon construction
    def __init__(self, game_id, player_id, stat_features, intervals=(40, 81, 162)):
        
        # Player associated with these stats
        self.gid = game_id
        self.pid = player_id
        
        # Initialize in-game player counting stats
        self.in_game_stats = {stat_name: 0 for stat_name in BattingStats.counting_stats}

        # Initialize player stats over given intervals
        self.intervals = intervals
        self.historical_stats = None 

        # Features from this player's batting we want in our dataset
        for stat in stat_features:
            assert(stat in BattingStats.stats)
        self.stat_features = stat_features
        self.features = None

    
    def read_historical_stats(self):
        # Initialize 2D dictionary: game iterval -> stat category -> stat value
        self.stats = {i: {s: None for s in BattingStats.stats} for i in self.intervals}
        # Read stats from retrosplits for the given game
        stats_df = pd.read_csv(BattingStats.path+f'/{self.pid}.csv')
        stats_df['date'] = pd.to_datetime(stats_df['date'])
        constants_df = pd.read_csv('./data/wOBA-weights.csv')
        if (stats_df['game.key'] == self.gid).any():
            present = stats_df.index[stats_df['game.key'] == self.gid][0]
        else:
            print(f'Error while processing {self.gid}.')
            print(f'Couldnt find {self.gid} in {self.pid} stats')
            assert(False)
        # Populate from retrosplits into the batter stats object
        for past in self.intervals:
            # Get games in the given interval
            df = stats_df.iloc[max(present-past, 0):present]
            # Get counting stats from retrosplits
            for cs in BattingStats.counting_stats:
                self.stats[past][cs] = df['B_'+cs].sum()
            # Calculate derived stats
            for ds in BattingStats.derived_stats:
                self.stats[past][ds] = BattingStats.derived_stats[ds](self.stats[past])
            # Calculate weighted stats (weighted based on year)
            for ws in BattingStats.weighted_stats:
                self.stats[past][ws] = BattingStats.weighted_stats[ws](df, constants_df)

    def featurize(self):
        if self.historical_stats is None:
            self.read_historical_stats()
        if self.features is None:
            feat_dict = {}
            for i in self.intervals:
                for stat in self.stat_features:
                    feat_dict[f'G{i}_{stat}'] = self.stats[i][stat]
            self.features = pd.Series(feat_dict, dtype=np.float64)
        return self.features

    # Increments count for the given list of stats    
    def increment_stats(self, stats):
        for name in stats:
            self.in_game_stats[name] += 1
    
    # Get the player's stats for a given game
    def get_game_stats(self, game_id, stat_path):
        stats_df = pd.read_csv(stat_path+f'/{self.pid}.csv')
        return stats_df[stats_df['game.key'] == game_id].iloc[0]