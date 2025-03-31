# External imports
import argparse
import datetime
from joblib import Parallel, delayed
import numpy as np
import pandas as pd
from pathlib import Path
import re
import time
import yaml


# Internal imports
from configuration import Configuration
from processors.processor import Processor

# Parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument('config')
parser.add_argument('-y', '--year')
parser.add_argument('-g', '--game')
parser.add_argument('-t', '--team')
parser.add_argument('-j', '--jobs', default=1)
args = parser.parse_args()

# Get config
if not args.config:
    raise Exception('Config arguement not found.')
with open(args.config, 'r') as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)

# Get years
if not args.year:
    raise Exception('Year arguement not found.')
# years must be between 2000-2023
year_ptrn = re.compile(r'(20[0-1]\d|202[0-4])')
input_years = re.findall(year_ptrn, args.year)
if len(input_years) == 2:
    years = range(int(input_years[0]), int(input_years[1])+1)
elif len(input_years) == 1:
    years = range(int(input_years[0]), int(input_years[0])+1)
else:
    raise Exception(f'{args.year} pattern is not recognized.')

start = time.time()
for year in years:
    # Get list of games for the given year
    teams_df = pd.read_csv(config.input_path+f'/{year}eve'+f'/TEAM{year}', header=None)
    teams_df.columns = ['id', 'league', 'city', 'name']
    # If an individual game is specified in the command line, then process it.
    if args.game:
        # Initialize processor
        proc = Processor(config)
        # Validate the given game happened during the current year
        if year != int(args.game[3:7]):
            print(f'Warning: {args.agame} is not in {year}')
            continue
        team = teams_df.loc[teams_df['id'] == args.game[:3]].iloc[0]
        print(f'PROCESSING {args.game}')
        proc.process_team(year, team['id'], team['league'], args.game)
    # Else, if an indiviual game is specified in the command line, then process it.
    elif args.team:
        # Initialize processor
        proc = Processor(config)
        team = teams_df.loc[teams_df['id'] == args.team].iloc[0]
        print(f"PROCESSING {year} {team['city']} {team['name']}")
        proc.process_team(year, team['id'], team['league'])
    # Else, process all games for all teams for the year.
    else:
        # Define parameters
        njobs = int(args.jobs)
        nteams = len(teams_df)
        # Initialize processors for each team
        #procs = [Processor(config)] * nteams
        # Define wrapper function to log the parallel execution
        def proc_wrapper(config, team_idx):
            team = teams_df.iloc[team_idx]
            print(f"PROCESSING {year} {team['city']} {team['name']}")
            proc = Processor(config)
            #procs[i].process_team(year, team['id'], team['league'])
            proc.process_team(year, team['id'], team['league'])
        # Launch parallel jobs
        Parallel(n_jobs=njobs)(delayed(proc_wrapper)(config, idx) for idx in range(nteams))

    print()
print(f'--> Execution time: {time.time() - start}')
