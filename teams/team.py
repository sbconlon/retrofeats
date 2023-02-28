# This class defines the team object

# External imports
import numpy as np
import pandas as pd

class Team:
    def __init__(self, tid):
        self.id = tid
        self.name = ''
        self.roster = {}
        self.lineup = [None for _ in range(9)]
        self.pitcher = None
        self.bpos = 0 # Batting position (zero-indexed)

    # Adds team name
    #
    # Input:
    #  - teamspath (str): path to teams dataframe in retrosheets season dir
    #
    # Output:
    #  None
    def add_team_name(self, teamspath):
        teams_df = pd.read_csv(teamspath, header=None)
        teams_df.columns = ['id', 'league', 'city', 'name']
        if not np.any(teams_df['id'] == self.id):
            print(f'{self.id} not found in {teamspath}')
            assert(False)
        self.name = teams_df.loc[teams_df['id'] == self.id]['name'].to_numpy()[0]

    def featurize_batting(self):
        team_feats = pd.Series(dtype=np.float64)
        for i, p in enumerate(range(self.bpos, self.bpos+9)):
            player_feats = self.roster[self.lineup[p%9]].featurize('batting')
            player_feats = player_feats.rename(lambda s: f'B{i}_'+s)
            team_feats = team_feats.append(player_feats)
        return team_feats

    def featurize_pitching(self):
        return self.roster[self.pitcher].featurize('pitching')

    def featurize_fielding(self):
        return pd.Series(dtype=np.float64)

    def featurize(self):
        batting_feats = self.featurize_batting()
        pitching_feats = self.featurize_pitching()
        fielding_feats = self.featurize_fielding()
        return batting_feats.append(pitching_feats).append(fielding_feats)
