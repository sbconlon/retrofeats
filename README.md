## Table of Contents
1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Documentation](#3-documentation)
4. [To-do](#4-to-do)

## 1. Introduction

Retrofeats takes [Retrosheet](https://www.retrosheet.org/eventfile.htm) event data as input and outputs a matrix of featurized game states at each timestep. Thereby providing an easy to use dataset for RL and ML applications.

## 2. Getting Started

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

<br/>

### 3.2. Data Structures

Below is the ERD diagram showing the relationships between the class objects in the project.

![ERD Diagram](images/retrofeats-erd.png?raw=true "Data structure relationships")

#### 3.2.1. GameState

See `retrofeats/games/game.py`.

This is the top level representation of the game.

Data members

| Name             | Type     | Description                                                        |
| ---------------- | -------- | ------------------------------------------------------------------ |
| `id`             | string   | Unique identifier given to the game by Retrosheets                 |
| `date`           | datetime | Date of the game                                                   |
| `teams`          | list     | List containing the `Team` objects for the home and away teams     |
| `inning`         | int      | Inning the game is in                                              |
| `is_bot`         | bool     | True if the game is in the bottom of the inning                    |
| `outs`           | int      | Outs in the inning                                                 |
| `score`          | list     | Two element list, [Away score, home score]                         |
| `runners`        | list     | Three element list of bools representing whether or not there is a </br> runner on a given base |
| `batter`         | string   | Unique player identifier for the current batter, used for </br> validation with the Retrosheet data |
| `past`           | list     | List of feature vectors for past game states                       |
| `info`           | dict     | Dictionary of game information given in the Retrosheet game header |
| `const_features` | series   | Cached vector of constant features                                 |

#### 3.2.2. Team

See `retrofeats/teams/team.py`.

Each game contains a team object for the home and away teams.



<br/>
<br/>
<br/>
<br/>
<br/>
<br/>

For example, below is a snippet from a Retrofeats log file.
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
The game state in this example is 

## 4. To-Do
