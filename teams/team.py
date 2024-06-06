# This class defines the team object

# External imports
import numpy as np
import pandas as pd

# Internal imports
from players.stats.batting import BattingStats
from players.stats.pitching import PitchingStats

class Team:
    def __init__(self, tid):
        self.id = tid
        self.name = ''
        self.roster = {} # Maps player id -> player object.
        self.lineup = [None for _ in range(9)] # list of player ids.
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
            team_feats = pd.concat([team_feats, player_feats])
        return team_feats

    def featurize_pitching(self):
        return self.roster[self.pitcher].featurize('pitching')

    def featurize_fielding(self):
        return pd.Series(dtype=np.float64)

    def featurize(self):
        batting_feats = self.featurize_batting()
        pitching_feats = self.featurize_pitching()
        fielding_feats = self.featurize_fielding()
        return pd.concat([batting_feats, pitching_feats, fielding_feats])
    
    # NOTE - Should these be moved into a stats parent object?
    stat_dict = {'batting':  [BattingStats.counting_stats],
                 'pitching': [PitchingStats.counting_stats],
                 'both':     [BattingStats.counting_stats,
                              PitchingStats.counting_stats]}
    # Stat abreviations for space when printing the stats tables
    stat_abrv = {'PITCH': 'PTCH', 'STRIKE': 'STRK'}

    # Prints out player batting, pitching, or both stats for the game.
    # NOTE - right now, 'both' is hard coded
    def print_game_stats(self):
        # Get max width for each column type
        max_name_width = max([len(name) for name in [p.name for p in self.roster.values()]]) + 2
        max_stat_width = 5
        # Print team name
        print(self.name)
        print()
        # Print a different table for each stat type
        for stats in Team.stat_dict['both']:
            # Print this table's stat type
            print('Batting' if stats == BattingStats.counting_stats else 'Pitching')
            # Print the header that includes the stat names
            hdr = ' ' * max_name_width
            for stat in stats:
                # Stat that is actually printed
                prnt_stat = stat if not stat in Team.stat_abrv else Team.stat_abrv[stat]
                hdr += prnt_stat
                hdr += ' ' * (max_stat_width - len(prnt_stat))
            print(hdr)
            # Print a row of each player's stat line for this game
            for plyr in self.roster.values():
                row = ''
                row += plyr.name
                row += ' ' * (max_name_width - len(row))
                # Get the stats for the player according to the stat type
                plyr_stats_obj = (
                                    plyr.batting 
                                    if stats == BattingStats.counting_stats 
                                    else plyr.pitching
                )
                # Account for player's who don't have that stat
                # i.e. position players who didn't pitch
                # Don't include them in the table if they don't have that stat type.
                if not plyr_stats_obj:
                    continue
                plyr_stats_dict = plyr_stats_obj.in_game_stats
                for stat in stats:
                    value = str(plyr_stats_dict[stat])
                    row += value
                    row += ' ' * (max_stat_width - len(value))
                print(row)
            print()

    # Cross references the player stats with the retrosplit data.
    def verify_game_stats(self, game_id, stat_path):
        max_name_width = max([len(name) for name in [p.name for p in self.roster.values()]]) + 2
        max_stat_width = 5
        error_cnt = 0
        for plyr in self.roster.values():
            # For each stat type given, either 'batting', 'pitching', or 'both'.
            for stats in Team.stat_dict['both']:
                # Get the player's stat object and prefix according to the stat type.
                plyr_stats_obj, prefix = (
                                        (plyr.batting, 'B_') 
                                        if stats == BattingStats.counting_stats 
                                        else (plyr.pitching, 'P_')
                )
                # Get the truth dictionary from the input stat path.
                truth_dict = (
                            dict.fromkeys([prefix+stat for stat in stats], 0)
                            if not plyr_stats_obj
                            else plyr_stats_obj.get_game_stats(game_id, stat_path)
                )
                # Get the in-game stats dict from the player's stats object.
                plyr_stats_dict = (
                                    dict.fromkeys(stats, 0) 
                                    if not plyr_stats_obj
                                    else plyr_stats_obj.in_game_stats
                )
                # Check each of the player's stats against the truth.
                for stat in stats:
                    # This stat currently doesn't work if a pitcher inherts some runners,
                    # gets replaced, and the replacement pitcher allows those runners to
                    # score. In this case, both pitchers should be charged with IRSs.
                    #
                    # I've found inconsistencies between my calculation here, baseball 
                    # reference, and retrosplits on pitch counts. In these instances,
                    # my count agrees with baseball reference. To avoid throwing errors
                    # in these instances, I will forgo checking pitch stat and trust
                    # that my own count is more accurate than retrosplits.
                    #
                    if stat == 'IRS' or stat == 'PITCH' or stat == 'STRIKE':
                        continue
                    if truth_dict[prefix+stat] != plyr_stats_dict[stat]:
                        # Stat that is actually printed.
                        prnt_stat = stat if not stat in Team.stat_abrv else Team.stat_abrv[stat]
                        # Build the stat error string.
                        line = 'STAT ERROR: Player: ' + plyr.name
                        line += ' ' * (max_name_width - len(plyr.name))
                        line += 'Stat: ' + prnt_stat
                        line += ' ' * (max_stat_width + 1 - len(prnt_stat))
                        line += 'Expected: ' + str(int(truth_dict[prefix+stat]))
                        line += ' ' * (max_stat_width - len(str(int(truth_dict[prefix+stat]))))
                        line += 'Got: ' + str(plyr_stats_dict[stat])
                        error_cnt += 1
                        # Print a header with team stats if this is the first error
                        if error_cnt == 1:
                            print()
                            self.print_game_stats(stat_path)
                            print()
                            print()
                            print(f'{self.name} - Player stat verification')
                        # Print the stat error.
                        print(line)
        if error_cnt:
            print(f'{int(error_cnt)} stat error(s).')
            print()
            print('Game ID:', self.id)
            print()
        return (error_cnt == 0) # Return true if there are no errors.
    
    # Save the game stats for each player on the team.
    def save_stats(self, game_id, game_date, overwrite=False):
        for plyr in self.roster.values():
            plyr.save_stats(game_id, game_date, overwrite=overwrite)
