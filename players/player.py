# This file defines the player object

# Internal imports
from players.stats.batting import BattingStats
from players.stats.pitching import PitchingStats

# External imports
import numpy as np
import os
import pandas as pd
import sys

# Adding top level project directory
sys.path.insert(0, '../')

class Player:

    positions = { 1: 'P',
                  2: 'C',
                  3: '1B',
                  4: '2B',
                  5: '3B',
                  6: 'SS',
                  7: 'LF',
                  8: 'CF',
                  9: 'RF',
                 10: 'DH',
                 11: 'PH',
                 12: 'PR'}

    def __init__(self, pid, name):
        # Basic info
        self.id = pid
        self.name = name
        self.position = None
        # Stats
        self.pitching = None
        self.batting = None
        self.fielding = None
        # In-Game Stats
        #self.pcount = 0 # Pitches thrown
        # Features
        self.batting_features = None
        self.pitching_features = None
        self.fielding_features = None
        #
        # Special flag for when a pinch hitter is substituted into a
        # two strike count. In this case, the original batter is
        # responsible if his replacement strikes out.
        #
        # If the batter is responsible for his own strikeout, then the
        # variable is falsey.
        # Else, the variable holds the player who is responsible for the strikeout.
        self.ph_strikeout_ownership = ''

    # Featurize ingame pitcher stats
    def get_ingame_pfeats(self):
        vector = []
        columns = []
        #
        # Pitch count
        #vector.append(self.pcount)
        #columns.append('P_Count')
        return pd.Series(dict(zip(columns, vector)), dtype=np.float64)

    # Featurize stats that are accumulated in-game
    def get_ingame_features(self, facet):
        assert(facet in ('batting', 'pitching', 'fielding'))
        if facet == 'pitching':
            return self.get_ingame_pfeats()

    def featurize(self, facet):
        assert(facet in ['batting', 'pitching', 'fielding'])
        # Batting features
        if facet == 'batting':
            assert(self.batting)
            if self.batting_features is None:
                self.batting_features = self.batting.featurize()
            return self.batting_features
        # Pitching features
        if facet == 'pitching':
            if not self.pitching:
                print(f'Cant featurize pitching stats for {self.id}')
                assert(False)
            if self.pitching_features is None:
                self.pitching_features = self.pitching.featurize()
            ingame_feats = self.get_ingame_features('pitching')
            return pd.concat([self.pitching_features, ingame_feats])
        # Fielding features
        if facet == 'fielding':
            assert(self.fielding)
            if self.fielding_features is None:
                self.fielding_features = self.fielding.featurize()
            return self.fielding_features

    def save_stats(self, game_id, game_date, overwrite=False):
        player_file = f'./data/players-daybyday/{self.id}.csv'
        cols = ['B_'+bstat for bstat in BattingStats.counting_stats]
        cols += ['P_'+pstat for pstat in PitchingStats.counting_stats]
        cols += ['game.key', 'date']
        # Open the player's day by day stat df if it exists, else create it
        df = (
              pd.read_csv(player_file)
              if os.path.isfile(player_file)
              else pd.DataFrame(columns=cols)
        )
        # Skip if overwrite is not enabled and game already exists
        # Else, remove the old row.
        if any(df['game.key'] == game_id):
            if overwrite:
                df.drop(df['game.key'] == game_id, inplace=True)
            else:
                return
        # Else, add the row for the game in the dataframe and write the csv out to disk.
        row = dict.fromkeys(cols)
        row['game.key'] = game_id
        row['date'] = game_date
        if self.batting:
            for stat in BattingStats.counting_stats:
                row['B_'+stat] = self.batting.in_game_stats[stat]
        if self.pitching:
            for stat in PitchingStats.counting_stats:
                row['P_'+stat] = self.pitching.in_game_stats[stat]
        df.loc[len(df.index)] = pd.Series(row)
        df.sort_values(by='game.key', key=lambda col: [int(x[3:]) for x in col], inplace=True, ignore_index=True)
        df.to_csv(player_file, index=False)
