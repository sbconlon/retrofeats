# External imports
import argparse
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
import re

# Internal imports
from processors.processor import Processor

# Parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument('-g', '--game')
parser.add_argument('-t', '--team')
parser.add_argument('-y', '--year')
args = parser.parse_args()

# Define configuration
year = int(args.year)
RETROSHEET_PATH = 'C:/Users/SBC98/Desktop/Projects/retrosheet'
RETROSPLITS_PATH = 'C:/Users/SBC98/Desktop/Projects/retrosplits'
sznpath = RETROSHEET_PATH + f"/regular-season-eve/{year}eve"

# Define processor parameters
batting_feats = ['PA', 'K%', 'BB%', 'wOBA', 'wRAA']
pitching_feats = ['TBF', 'K%', 'BB%', 'GO/TBF', 'FIP']
logpath = sznpath + "/logs"
featpath = sznpath + "/featurized"
statpath = RETROSPLITS_PATH

# Initialize processor
proc = Processor(batting_feats,
                 pitching_feats,
                 featpath,
                 logpath,
                 statpath)

# Get list of games for the given year
teams_df = pd.read_csv(sznpath+f'/TEAM{year}', header=None)
teams_df.columns = ['id', 'league', 'city', 'name']

# If an individual game is specified in the command line, then process it.
if args.game:
    team = teams_df.loc[teams_df['id'] == args.game[:3]].iloc[0]
    print(f'PROCESSING {args.game}')
    proc.process_team(sznpath,
                      f"{year}{team['id']}.EV{team['league']}",
                      game_id=args.game)
# Else, if an indiviual game is specified in the command line, then process it.
elif args.team:
    team = teams_df.loc[teams_df['id'] == args.team].iloc[0]
    print(f"PROCESSING {year} {team['city']} {team['name']}")
    proc.process_team(sznpath,
                      f"{year}{team['id']}.EV{team['league']}",
                      game_id=args.game)
# Else, process games for all teams.
else:
    for i in range(teams_df.shape[0]):
        team = teams_df.iloc[i]
        print(f"PROCESSING {year} {team['city']} {team['name']}")
        proc.process_team(sznpath, f"{year}{team['id']}.EV{team['league']}")
