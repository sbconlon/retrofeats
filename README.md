## Table of Contents
1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
   - 2.1. Download the prebuild dataset
   - 2.2. Build a customized datset
3. [Documentation](#3-documentation)
   - 3.1. List of features
   - 3.2. Design
   - 3.3. Processor execution
   - 3.4. Log
5. [To-do](#4-to-do)

## 1. Introduction

Retrofeats is a feature construction pipeline for event level baseball data. It takes [Retrosheet](https://www.retrosheet.org/eventfile.htm) event data as input and outputs a matrix of featurized game states at each timestep. Thereby providing an easy to use dataset for RL and ML applications. Currently supports data from 2000-2021, but plan to expand support to 1980 in the future. 

## 2. Getting Started

Two options for getting the dataset. One, a prebuilt dataset is available for download. Two, instructions are given for building the dataset yourself with a fully customizable feature selection.

### 2.1. Download the prebuilt dataset

* Contains all regular season games from 2000 to 2021.

* Batting features `[PA, K%, BB%, wOBA, wRAA]` are aggregated over `[40, 81, 162]` game intervals.

* Pitching features `[TBF, K%, BB%, GO/TBF, FIP]` are aggregated over `[5, 10, 20]` game intervals.

* Download [here](https://drive.google.com/file/d/1Q-H0nYokJ38u_vS6tT7FhM1zRC1iDuFl/view?usp=share_link).

### 2.2. Build a customized dataset

#### 2.1.1. Clone the repo

* `git clone https://github.com/sbconlon/retrofeats.git`

#### 2.1.2. Download Retrosheets event data

* This is the input for the dataset generation. 

* The Retrosheet events should be organized like `../path/to/retrosheet/{$year}eve` where `$year` is each year to be processed. This allows a convient way to iterate over the data by year and is how the data comes formatted from Retrosheets.

* The downloads can be found [here](https://www.retrosheet.org/game.htm) under the header "Regular Season Event Files".

#### 2.1.3. Install dependencies

* `pip install -r requirements.txt`

#### 2.1.4. Customize the features

* Populate the fields in `config.yaml`

* `batting_feats` is the list of batting features to be included in the feature vector. See Section 3.1.3. for a complete list of batting features.

* `pitching_feats` is the list of pitching features to be included in the feature vector. See Section 3.1.4. for a complete list of pitching features.

* `batting_intervals` is the list of intervals over which the batting stats are aggregated, in units of games. Default values are used if left blank.

* `pitching_intervals` is the list of intervals over which the pitching stats are aggregated, in units of games. Default values are used if left blank.

* `input_path` is the path to the high level directory containing the Retrosheet event files organized by season.

* `output_path` is the path where the game matrices will be output. If the path does not exist, it will be created.

* `log_path` is the path where the game logs will be output. If the path does not exist, it will be created.

#### 2.1.4. Run

* `python featurize.py config.yaml -y {$start_year}-{$end_year}`

* Required arguements are the configuration file and year. 

* The year arguement can either be a single year or a range of years, as shown in the above bullet.

* To process a single team use the `-t` or `-team` flag followed by the Retrosheet team id.

* To process a single game us the `-g` or `-game` flag followed by the Retrosheet game id.

## 3. Documentation

### 3.1. List of features

These features are collected at each timestep of the game.

#### 3.1.1. Basic game state information
| Name       | Type   | Description                                    | 
| ---------- | ------ | ---------------------------------------------- |
| `inning`   | int    | Inning number                                  |
| `bot`      | bool   | True if it is the bottom of an inning          |
| `outs`     | int    | Number of outs in the inning (between 0 and 2) |
| `away`     | int    | Away score                                     |
| `home`     | int    | Home score                                     |
| `1B`       | bool   | True if there is a runner on first base        |
| `2B`       | bool   | True if there is a runner on second base       |
| `3B`       | bool   | True if there is a runner on third base        |

#### 3.1.2. Constant game information

Wind direction, field condition, precipitation, and sky are encoded as one-hot vectors, where all entries are false if the information is unknown.

| Name             | Type   | Description                                      | 
| ---------------- | ------ | ------------------------------------------------ |
| `year`             | int    | Year the game was played in                      |
| `parkfactor`       | int    | Offensive rating of the stadium, computed by [FanGraphs](https://www.fangraphs.com/guts.aspx?type=pf&season=2018&teamid=0). |
| `windspeed`        | int    | Windspeed, -1 if unknown                         |
| `winddir_fromcf`   | bool   | True if the wind is blowing in from center field |
| `winddir_fromlf`   | bool   | True if the wind is blowing in from left field   |
| `winddir_fromrf`   | bool   | True if the wind is blowing in from right field  |
| `winddir_ltor`     | bool   | True if the wind is blowing from left to right   |
| `winddir_rtol`     | bool   | True if the wind is blowing from right to left   |
| `winddir_tocf`     | bool   | True if the wind is blowing out to center field  |
| `winddir_tolf`     | bool   | True if the wind is blowing out to left field    |
| `winddir_torf`     | bool   | True if the wind is blowing out to right field   |
| `fieldcond_dry`    | bool   | True if the field is dry                         |
| `fieldcond_soaked` | bool   | True if the field is soaked                      |
| `fieldcond_wet`    | bool   | True if the field is wet                         |
| `precips_none`     | bool   | True if there is no precipitation                |
| `precips_drizzle`  | bool   | True if there is a drizzle                       |
| `precips_rain`     | bool   | True if there is rain                            |
| `precips_showers`  | bool   | True if there are showers                        |
| `precips_snow`     | bool   | True if there is snow                            |
| `sky_cloudy`       | bool   | True if the sky is cloudy                        |
| `sky_dome`         | bool   | True if the game is played in a dome             |
| `sky_night`        | bool   | True if the game is played at night              |
| `sky_overcast`     | bool   | True if the sky is overcast                      |
| `sky_sunny`        | bool   | Ture if the sky is sunny                         |

#### 3.1.3. Player batting stats

See FanGraph's [Sabermetrics Library](https://library.fangraphs.com/getting-started/) for stat definitions.

All counting stats are derived from [Retrosplits](https://github.com/chadwickbureau/retrosplits).

Weighted stat constants are from [FanGraphs](https://www.fangraphs.com/guts.aspx?type=cn).

For weighted stats such as wOBA, the constants are defined with respect to single seasons. However, if we want to know a player's wOBA for the last 82 games he has played in, this may span multiple seasons. To account for this, the weighted total bases are calculated on a per year basis. Then, the per year weighted bases are summed to get a total weighted bases value that is used to calculate the wOBA over the multi-year span.

Prefix definitions:
- `A_` prefix is used to identify a player on the team that is currently at-bat.
- `F_` prefix is used to identify a player on the team that is currently in the field.
- `B{int}_` prefix gives the player's relative spot in the batting order.
- `G{int}_` prefix gives the number of games the stat was aggregated over.

Example: the feature `A_B2_G81_PA` is the number of plate appearances the player two batters away from batting on the at-bat team had in the past 81 games he played.

##### 3.1.3.1. Counting stats

| Name  | Type   | Description              |
| ----- | ------ | ------------------------ |
| `PA`  | int    | Plate appearances        |
| `AB`  | int    | At-bats                  |
| `R`   | int    | Runs scored              |
| `H`   | int    | Hits                     |
| `TB`  | int    | Total bases              |
| `1B`  | int    | Singles                  |
| `2B`  | int    | Doubles                  |
| `3B`  | int    | Triples                  |
| `HR`  | int    | Homeruns                 |
| `HR4` | int    | Inside the park homeruns |
| `RBI` | int    | Runs batted in           |
| `BB`  | int    | Walks                    |
| `IBB` | int    | Intentional walks        |
| `SO`  | int    | Strikeouts               |
| `GDP` | int    | Ground into double play  |
| `HP`  | int    | Hit by pitch             |
| `SH`  | int    | Sacrifice bunt           |
| `SF`  | int    | Sacrifice fly            |
| `SB`  | int    | Stolen base              |
| `CS`  | int    | Caught stealing          |

##### 3.1.3.2. Derived stats

| Name    | Type   | Description                      |
| ------- | ------ | -------------------------------- |
| `K%`    | float  | Strikeout frequency              |
| `BB%`   | float  | Walk frequency                   |
| `ISO`   | float  | Isolated power                   |
| `BABIP` | float  | Batting average on balls in play |
| `OBP`   | float  | On base percentage               |
| `SLG`   | float  | Slugging percentage              |
| `OPS`   | float  | On-base plus slugging            |
| `AVG`   | float  | Batting average                  |

##### 3.1.3.3. Weighted stats

| Name    | Type   | Description                      |
| ------- | ------ | -------------------------------- |
| `wOBA`  | float  | Weighted on-base percentage      |
| `wRAA`  | float  | Weighted runs above average      |

#### 3.1.4. Player pitching stats

See FanGraph's [Sabermetrics Library](https://library.fangraphs.com/getting-started/) for stat definitions.

All counting stats are derived from [Retrosplits](https://github.com/chadwickbureau/retrosplits).

Weighted stat constants are from [FanGraphs](https://www.fangraphs.com/guts.aspx?type=cn).

In-game stats are stats that are accumulated during the current game. For instance, the `PITCH` feature in the counting stats group is the number of pitches the player has thrown over a given number of past games. Whereas, the `Count` feature in the in-game stats group is the number of pitches the player has thrown in the current game.

Prefix definitions:
- `A_P_` prefix denotes the stats for the batting team's pitcher.
- `F_P_` prefix denotes the stats for the fielding team's pitcher.
- `G{int}_` prefix gives the number of games the stat was aggregated over.

Example: the feature `F_P_G10_FIP` is the fielding team's pitcher's FIP over the past 10 games he has appeared in.

##### 3.1.4.1. Counting stats

| Name     | Type   | Description                                            |
| -------- | ------ | ------------------------------------------------------ |
| `CG`     | int    | Complete games                                         |
| `SHO`    | int    | Complete game shutouts                                 |
| `GF`     | int    | Games finished (last pitcher to appear for their team) |
| `W`      | int    | Wins                                                   |
| `L`      | int    | Losses                                                 |
| `SV`     | int    | Save                                                   |
| `OUT`    | int    | Outs recorded                                          |
| `TBF`    | int    | Total batters faced                                    |
| `AB`     | int    | At-bats against                                        |
| `R`      | int    | Runs allowed                                           |
| `ER`     | int    | Earned runs allowed                                    |
| `H`      | int    | Hits allowed                                           |
| `TB`     | int    | Total bases                                            |
| `2B`     | int    | Doubles allowed                                        |
| `3B`     | int    | Triples allowed                                        |
| `HR`     | int    | Homeruns allowed                                       |
| `HR4`    | int    | Inside the park homeruns allowed                       |
| `BB`     | int    | Walks allowed                                          |
| `IBB`    | int    | Intentional walks allowed                              |
| `SO`     | int    | Strikeouts                                             |
| `GDP`    | int    | Ground ball double plays forced                        |
| `HP`     | int    | Hit batters                                            |
| `SH`     | int    | Sacrifice bunts allowed                                |
| `SF`     | int    | Sacrifice flys allowed                                 |
| `WP`     | int    | Wild pitches                                           |
| `BK`     | int    | Balks                                                  |
| `IR`     | int    | Inherited runners                                      |
| `IRS`    | int    | Inherited runners who scored                           |
| `GO`     | int    | Ground outs induced                                    |
| `AO`     | int    | Air outs induced                                       |
| `PITCH`  | int    | Pitches thrown                                         |
| `STRIKE` | int    | Strikes thrown                                         |

##### 3.1.4.2. Derived stats

| Name     | Type   | Description                      |
| -------- | ------ | -------------------------------- |
| `BB%`    | float  | Walk rate                        |
| `K%`     | float  | Strikeout rate                   |
| `BABIP`  | float  | Batting average on balls in play |
| `LOB%`   | float  | Left on base percent             |
| `HR/FB`  | float  | Homeruns per flyouts             |
| `ERA`    | float  | Earned run average               |
| `WHIP`   | float  | Walks hits over innings pitched  |
| `GO/TBF` | float  | Ground ball out rate             |

##### 3.1.4.3. Weighted stats

| Name    | Type   | Description                      |
| ------- | ------ | -------------------------------- |
| `FIP`   | float  | Fielding independent pitching    |

##### 3.1.4.4. Weighted stats

| Name    | Type   | Description                      |
| ------- | ------ | -------------------------------- |
| `Count` | int    | Pitch count                      |

#### 3.1.5. Labels

The final score is saved at the end of each feature vector. This captures the result of the game and allows for the widest set of labels possible for a ML dataset.

Examples of possible labels:
- Total runs scored (over/under prediction)
- Win margin (spread prediction)
- Outright winner (Moneyline prediction)

| Name         | Type   | Description                      |
| ------------ | ------ | -------------------------------- |
| `away_final` | int    | Away team final score            |
| `home_final` | int    | Home team final score            |

### 3.2. Design

Below is the ERD diagram showing the relationships between the class objects in the project.

![ERD Diagram](images/retrofeats-erd.png?raw=true "Data structure relationships")

### 3.3. Processor execution

This section follows the execution flow of the `Processor` object.

See the Retrosheets [documentation](https://www.retrosheet.org/eventfile.htm) for more detailed information on the event file formatting.

### 3.3.1. Processor initialization

* `featurize.py` takes the input configuration, initializes the processor, and calls `Processor.process_team()`.

#### 3.3.2. Process season

* `Processor.process_team()` reads the Retrosheet event file given season year and team.

* This is the high level processor function that reads the event file line by line.

* Different processor functions are called depending on the type of line read. 

#### 3.3.3. Process new game

* See `Processor.process_new_game()`.

* The first type of line encountered is the `id` which specifies the game id for a new game.

* A `Game` object is initialized using the given game id and stored in `Processor.game`.

* If we already have a game stored in `Processor.game`, then we know the processing for the old game is finished and can be output to disk.

* Example:
  ```
  id,SFN201404080
  ```

#### 3.3.4. Process game information

* See `Processor.process_game_info()`.

* The next line type in the Retrosheet event file is `info` which specifies general game information.

* `Team` objects are initialized using the team ids given for the home and away teams, and stored in `Processor.teams` list.
   
   Example:
   ```
   info,visteam,ARI
   info,hometeam,SFN
   ```
   
* The rest of the game information is stored in the `Processor.game.info` dictionary.
  
  Example:
  ```
  info,site,SFO03
  info,date,2014/04/08
  info,number,0
  info,starttime,1:36PM
  info,daynight,day
  info,usedh,false
  info,umphome,reynj901
  info,ump1b,barbs901
  info,ump2b,culbf901
  info,ump3b,gonzm901
  info,howscored,park
  info,pitches,pitches
  info,oscorer,feldd701
  info,temp,73
  info,winddir,tocf
  info,windspeed,5
  info,fieldcond,unknown
  info,precip,unknown
  info,sky,cloudy
  info,timeofgame,159
  info,attendance,42166
  info,wp,hudst001
  info,lp,cahit001
  info,save,
  ```

#### 3.3.4. Process starting lineups

* The next line type is `start` which specifies the starting lineups for each team.

* This information is used to create `Player` objects which are stored in each team's roster, `Processor.game.team[].roster`.

* The batting order and player positions are also specified at this time and used to populate the teams' batting orders, `Processor.game.team[].lineup`, and pitcher `Processor.game.team[].pitcher`.

* Example:
  ```
  start,pagaa001,"Angel Pagan",1,1,8
  start,beltb001,"Brandon Belt",1,2,3
  start,sandp001,"Pablo Sandoval",1,3,5
  start,poseb001,"Buster Posey",1,4,2
  start,pench001,"Hunter Pence",1,5,9
  start,morsm001,"Michael Morse",1,6,7
  start,crawb001,"Brandon Crawford",1,7,6
  start,hickb002,"Brandon Hicks",1,8,4
  start,hudst001,"Tim Hudson",1,9,1
  ```

#### 3.3.5. Process plays

* To this point, we have only considered line types which build the initial static representation of the game state. However, the `play` line type specifies the dynamics of the system. And, therefore, constitute actions that transform the game from one state to the next.

* This is the most complex part of the processor in which play types must be decoded and then used to evolve the game state.

* At the end of each play, the feature vector for the given game is saved in its `Game.past` list. When the game is finished, this list of feature vectors is written to disk.

* Example, Brandon Belt hits a homerun in the bottom of the first inning:
  ```
  play,1,1,beltb001,21,BFBX,HR/89/F.1-H
  ```

#### 3.3.6. Process substitutions

* The `sub` line type is a special kind of action that transforms a team's roster or lineup.

* Example, Gregor Blanco is substituted as a pinch runner:
  ```
  sub,blang001,"Gregor Blanco",1,6,12
  ```

### 3.4. Log

Log processor outputs game state representation at each timestep, followed by the action that transforms the current state into the next.

This is useful for debugging and verifying the processor's accuracy.

Example:
```
---------------------------------------------------
Top 2
Home: 0 Away: 0
Outs: 0

Pitcher: "Andrew Werner"
G 6 IP 33.0 FIP 4.37
Pitch Count: 12

Batter: "Buster Posey"
G 162 PA 669 wOBA 0.404 wRAA 47.7

  .
. - .
  .

Triple
---------------------------------------------------
```

## 4. To-Do
- [ ] Include 2022 data (not currently included in Retrosplits).
- [ ] Add team level multithreading.
- [ ] Add features to account for team's bullpen and bench strength.
- [ ] Add more advanced weighted features such as `OPS+`.
- [ ] Add Statcast data.
