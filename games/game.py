# This file defines the game state.

# External imports
import numpy as np
import os
import pandas as pd
import sys

# Adding top level project directory
sys.path.insert(0, '../')

class GameState:
    def __init__(self, game_id):
        # Id
        self.id = game_id
        self.date = None
        # State features
        self.teams = [None, None] # [away, home]
        self.inning = None
        self.is_bot = None # is bottom of the inning? (bool)
        self.outs = None
        self.score = [0, 0] #
        self.runners = [False, False, False]
        self.batter = ""
        self.past = None
        # General game info
        self.info = {}
        self.const_features = None

    def get_state_features(self):
        vector = []
        columns = []
        #
        # Inning
        assert(not self.inning is None)
        vector.append(self.inning)
        columns.append('Inning')
        #
        # Is bottom?
        assert(not self.is_bot is None)
        vector.append(self.is_bot)
        columns.append('Bot')
        #
        # Outs
        assert(not self.outs is None)
        vector.append(self.outs)
        columns.append('Outs')
        #
        # Score
        assert(self.score)
        vector += self.score
        columns += ['Away', 'Home']
        #
        # Runners
        vector += [int(r) for r in self.runners]
        columns += ['1B', '2B', '3B']

        return pd.Series(dict(zip(columns, vector)), dtype=np.float64)

    def get_parkfactor(self):
        assert(self.teams[1] and self.date)
        name = self.teams[1].name
        parks_df = pd.read_csv('./data/parkfactors.csv')
        return parks_df.loc[(parks_df['Season'] == self.date.year) & (parks_df['Team'] == name)]['Basic'].to_numpy()[0]

    def get_const_features(self):
        if self.const_features is None:
            vector = []
            columns = []
            #
            # Year
            vector.append(self.date.year)
            columns.append('year')
            #
            # Park factor
            vector.append(self.get_parkfactor())
            columns.append('parkfactor')
            #
            # Temperature
            vector.append(int(self.info['temp']))
            columns.append('windspeed')
            #
            # Wind direction
            wind_directions = ['fromcf', 'fromlf', 'fromrf', 'ltor', 'rtol', 'tocf', 'tolf', 'torf']
            assert(self.info['winddir'] in wind_directions+['unknown'])
            vector += [int(wdir == self.info['winddir']) for wdir in wind_directions]
            columns += ['winddir_'+ wdir for wdir in wind_directions]
            #
            # Wind speed
            vector.append(int(self.info['windspeed']))
            columns += ['windspeed']
            #
            # Field condition
            field_conds = ['dry', 'soaked', 'wet']
            assert(self.info['fieldcond'] in field_conds+['unknown'])
            vector += [int(cond == self.info['fieldcond']) for cond in field_conds]
            columns += ['fieldcond_' + cond for cond in field_conds]
            #
            # Precipitation
            precips = ['none', 'drizzle', 'rain', 'showers', 'snow']
            assert(self.info['precip'] in precips+['unknown'])
            vector += [int(p == self.info['precip']) for p in precips]
            columns += ['precips_' + p for p in precips]
            #
            # Sky
            skies = ['cloudy', 'dome', 'night', 'overcast', 'sunny']
            assert(self.info['sky'] in skies+['unknown'])
            vector += [int(s == self.info['sky']) for s in skies]
            columns += ['sky_'+s for s in skies]
            #
            # Save game info features
            self.const_features = pd.Series(dict(zip(columns, vector)), dtype=np.float64)

        return self.const_features

    def featurize(self):
        # Get game features
        state_feats = self.get_state_features()
        const_feats = self.get_const_features()
        # Get team features
        # Add 'A_' and 'F_' prefixes to differentiate at-bat and in the field teams
        atbat_team_feats = self.teams[self.is_bot].featurize()
        atbat_team_feats = atbat_team_feats.rename(lambda s: 'A_'+s)
        field_team_feats = self.teams[not self.is_bot].featurize()
        field_team_feats = field_team_feats.rename(lambda s: 'F_'+s)
        # Append the feature types into a single feature vector
        return state_feats.append(const_feats).append(atbat_team_feats).append(field_team_feats)

    def checkpoint(self):
        feats = self.featurize()
        if self.past is None:
            self.past = pd.DataFrame([], columns=feats.index)
        self.past = self.past.append(feats, ignore_index=True)

    def add_result(self, final):
        # Add result to the past dataframe
        # True if home team won
        # final (score) = [away, home]
        rows = self.past.shape[0]
        away_final = pd.Series(np.ones(rows), dtype=np.float64) * final[0]
        home_final = pd.Series(np.ones(rows), dtype=np.float64) * final[1]
        self.past['away_final'] = away_final
        self.past['home_final'] = home_final

    def save(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
        self.past.to_csv(path+f'/{self.id}.csv', index=False)

    def __str__(self):
        # Get batter and pitcher
        pitcher_id = self.teams[(self.is_bot+1)%2].pitcher
        pitcher = self.teams[(self.is_bot+1)%2].roster[pitcher_id]
        batter = self.teams[self.is_bot].roster[self.batter]
        # Get batting and pitching intervals
        p_int = pitcher.pitching.intervals[-1]
        b_int = batter.batting.intervals[-1]
        # Build game state string
        inning_str = 'Bot' if self.is_bot else 'Top'
        state_str =  f"{inning_str} {self.inning}\n"
        state_str += f"Home: {self.score[1]} Away: {self.score[0]}\n"
        state_str += f"Outs: {self.outs}\n"
        state_str += f"\n"
        state_str += f"Pitcher: " + pitcher.name + "\n"
        state_str += f"G {pitcher.pitching.stats[p_int]['G']} IP {round(pitcher.pitching.stats[p_int]['OUT']/3, 1)} FIP {round(pitcher.pitching.stats[p_int]['FIP'], 2)}\n"
        state_str += f"Pitch Count: {pitcher.pcount}\n"
        state_str += f"\n"
        state_str += f"Batter: " + batter.name + "\n"
        state_str += f"G {batter.batting.stats[b_int]['G']} PA {batter.batting.stats[b_int]['PA']} wOBA {round(batter.batting.stats[b_int]['wOBA'],3)} wRAA {round(batter.batting.stats[b_int]['wRAA'],1)}\n"
        state_str += f"\n"
        state_str += f"  {'o' if self.runners[1] else '.'}\n"
        state_str += f"{'o' if self.runners[2] else '.'} - {'o' if self.runners[0] else '.'}\n"
        state_str += f"  .\n"
        return state_str
