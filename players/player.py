# This file defines the player object

# External imports
import numpy as np
import pandas as pd

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
        # Historic Stats
        self.pitching = None
        self.batting = None
        self.fielding = None
        # In-Game Stats
        self.pcount = 0 # Pitches thrown
        # Features
        self.batting_features = None
        self.pitching_features = None
        self.fielding_features = None

    # Featurize ingame pitcher stats
    def get_ingame_pfeats(self):
        vector = []
        columns = []
        #
        # Pitch count
        vector.append(self.pcount)
        columns.append('P_Count')
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
            return self.pitching_features.append(ingame_feats)
        # Fielding features
        if facet == 'fielding':
            assert(self.fielding)
            if self.fielding_features is None:
                self.fielding_features = self.fielding.featurize()
            return self.fielding_features
