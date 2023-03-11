## Table of Contents
1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Documentation](#3-documentation)
4. [To-do](#4-to-do)

## 1. Introduction

Retrofeats takes [Retrosheet](https://www.retrosheet.org/eventfile.htm) event data as input and outputs a matrix of featurized game states at each timestep. Thereby providing an easy to use dataset for RL and ML applications.

## 2. Getting Started

## 3. Documentation

#### List of features

*Basic game state information*
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

<br/>

*Constant game information*

Wind direction, field condition, precipitation, and sky are encoded as one-hot vectors, where all entries are false if the information in unknown.

| Name             | Type   | Description                                      | 
| ---------------- | ------ | ------------------------------------------------ |
| `year`             | int    | Year the game was played in                      |
| `parkfactor`       | int    | Offensive rating of the stadium, computed by [FanGraphs](https://www.fangraphs.com/guts.aspx?type=pf&season=2018&teamid=0).          |
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

<br/>

*Player batting stats*

Prefixes:
- `A_` and `F_` prefixes are used to destinguish batting stats for a player on the 'At-bat' team and a player on the 'Fielding' team, respectively.
- `B{int}_` prefix gives the number of batters until that player is at-bat where 0 indicates the current batter for that team.
- `G{int}_` prefix gives the number of games the stat was aggregated over.

For instance, the feature name `A_B2_G81_PA` contains the number of plate appearances the player two batters away from batting on the at-bat team had in the past 82 games he played.

All batting counting stats are derived from [Retrosplits](https://github.com/chadwickbureau/retrosplits)

| Name  | Type   | Description              |
| ----- | ------ | ------------------------ |
| `PA`  | int    | Plate appearances        |
| `AB`  | int    | At-bats                  |
| `R`   | int    | Runs scored              |
| `H`   | int    | Hits                     |
| `TB`  | int    | Total bases              |
| `2B`  | int    | Doubles                  |
| `3B`  | int    | Triples                  |
| `HR`  | int    | Homeruns                 |
| `HR4` | int    | Inside the park homeruns |
| `RBI` | int    | Runs batted in           |
| `BB`  | int    | Walks                    |
| `IBB` | int    | Intentional walks        |
| `SO`  | int    | Strikeouts               |
|

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
