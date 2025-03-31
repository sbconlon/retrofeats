# This file defines the game processor object.

# External imports
import datetime
import numpy as np
import os
import pandas as pd
import re
import shutil
import sys

# Internal imports
from configuration import Configuration
from games.game import GameState
from players.player import Player
from players.stats.batting import BattingStats
from players.stats.pitching import PitchingStats
from processors.log import Logger
from teams.team import Team

# Adding top level project directory
sys.path.insert(0, '../')

class Processor:

    # Define regex patterns for each event type
    single_fielder_ptrn = re.compile(r'^(\d(!)?)(E.)?(!+)?$')
    multi_fielder_ptrn  = re.compile(r'^(\d+(!+)?)+$')
    putout_ptrn         = re.compile(r'^(\d(!)?)+\(B\)$')
    force_out_ptrn      = re.compile(r'^(\d(!+)?)+\(\d\)(!+)?$')
    dbl_ply_ptrn        = re.compile(r'^(\d(!)?)+\([B123]\)(!+)?(\d(!)?)+(\([B123]\))?$') # Ex. '64(1)3' or '8(B)84(2)'
    trpl_ply_ptrn       = re.compile(r'^\d+\([B123]\)\d+\([B123]\)\d+(\([B123]\))?$') # Ex. '5(2)4(1)3' or '1(B)16(2)63(1)'
    intrfrnc_ptrn       = re.compile(r'^C(/E[1-3])?$')
    single_ptrn         = re.compile(r'^S(!+)?((\d(!)?)+)?$')
    double_ptrn         = re.compile(r'^D((\d+(!+)?)+)?$')
    triple_ptrn         = re.compile(r'^T(\d+)?$')
    gr_double_ptrn      = re.compile(r'^DGR(\d+)?$')
    error_ptrn          = re.compile(r'^(\d+)?E\d$')
    fielders_ch_ptrn    = re.compile(r'^FC(\d(!)?)?$')
    foul_fly_error_ptrn = re.compile(r'^FLE\d(#)?$')
    homerun_ptrn        = re.compile(r'^HR?(\d+)?$')
    hbp_ptrn            = re.compile(r'^HP$')
    k_no_event_ptrn     = re.compile(r'^K((\d(!)?)+)?$')
    k_w_event_ptrn      = re.compile(r'^K((\d(!)?)+)?\+')
    no_play_ptrn        = re.compile(r'^NP$')
    walk_ptrn           = re.compile(r'^I?W$')
    walk_w_event_ptrn   = re.compile(r'^I?W\+')
    balk_ptrn           = re.compile(r'^BK$')
    caught_stln_ptrn    = re.compile(r'^CS[23H]')
    def_indiff_ptrn     = re.compile(r'^DI$')
    other_adv_ptrn      = re.compile(r'^OA$')
    past_ball_ptrn      = re.compile(r'^PB$')
    wild_pitch_ptrn     = re.compile(r'^WP$')
    pickoff_ptrn        = re.compile(r'^PO[123](\(.+\))?$')
    pickoff_off_ptrn    = re.compile(r'^POCS[23H]')
    stln_base_ptrn      = re.compile(r'^SB[23H](\((.+)\))?(;SB[23H](\((.+)\))?)?(;SB[23H](\((.+)\))?)?$')
    adv_ind_ptrn        = re.compile(r'\((.*?)\)')
    adv_putout_ptrn     = re.compile(r'^(\d+(!)?)+(\/TH)?$') # used for runner advancements

    # Define regex patterns for ground and air out modifiers
    #
    # NOTE - Plays involving bunts do not count as GOs or AOs.
    #
    go_mod_ptrns = set([# Ground ball (+: hard, -: soft)
                        re.compile(r'^G(\d+?([A-Z]+)?)?(#?)([\+,\-])?$'),
                        # Ground ball double or triple play
                        re.compile(r'^G[D,T]P(#)?$')])

    ao_mod_ptrns = set([# Flyball (+: hard, -: soft)
                        re.compile(r'^(\d?)F(\d?([A-N,P-Z]+)?)?([\+,\-]?)$'),
                        # Lineout (+: hard, -: soft)
                        re.compile(r'^L((\d+)?([A-Z]+)?)?([\+,\-])?$'),
                        # Flyball or line drive double play
                        re.compile(r'^[F,L]DP$'), 
                        # Pop up Ex: 'P' or 'P3F'
                        re.compile(r'^P((\d+)?([A-Z]+)?)?([\+,\-])?$'),
                        # Infield fly
                        re.compile(r'^IF$')])     

    bunt_ptrn = re.compile(r'^B[G, P](\d)?(DP)?(LF)?$')

    is_bunt = lambda modifiers: any([
                                        bool(Processor.bunt_ptrn.match(m)) for m in modifiers
                                    ])
    
    is_sacrifice = lambda modifiers: ('SH' in modifiers or 'SF' in modifiers)

    is_ground_out = lambda modifiers: (# Exclude sacrifices
                                       not 'SH' in modifiers
                                       and not 'SF' in modifiers
                                       # Exclude bunts
                                       and not Processor.is_bunt(modifiers)
                                       # Check for ground out modifiers
                                       and 
                                       any([
                                           any([
                                               bool(ptrn.match(mod)) for mod in modifiers
                                           ]) for ptrn in Processor.go_mod_ptrns
                                        ]))
    
    is_air_out = lambda modifiers: (
                                    (
                                        # Exclude bunts
                                        not any([
                                                    bool(Processor.bunt_ptrn.match(m)) 
                                                    for m in modifiers
                                                ])
                                        # Check for air out modifiers
                                        and
                                            any([
                                                any([
                                                    bool(ptrn.match(mod)) for mod in modifiers
                                                ]) for ptrn in Processor.ao_mod_ptrns
                                            ])
                                    )
                                    # Assume Batter Interence is a pop-up unless
                                    # a ground out is explicitly given
                                    # Ex: CLE200006300
                                    #or (
                                    #    'BINT' in modifiers and
                                    #    not (
                                    #            Processor.is_ground_out(modifiers)
                                    #            or
                                    #            Processor.is_bunt(modifiers)
                                    #    )
                                    )
                                    
                                    


    def __init__(self, config, save_state=True, save_stats=False, overwrite=False, verify_path=''):
        # Configuration parameters
        self.config = config
        # Current game state
        self.game = None
        # Values caclulated after current play that are reflected
        # in the next state.
        self.next_outs = 0
        self.next_score = [0, 0]
        self.next_runners = [False, False, False]
        self.next_bpos = 0
        # Create logger
        self.logger = None
        # Boolean to control batting order check
        # We want to verify batting order under normal circumstances
        # however when teams bat out of order we need to be able to
        # bipass the check.
        self.ignore_bat_order = False
        # This field is for the rare occurance when a pitching substitution is
        # made mid at-bat and there's a specific count.
        self.is_pitcher_sub_count = False
        self.mid_atbat_pitcher_owner = ''
        # Check that the save state and save stats parameters are not both set.
        # The stats must be built before the states can be featurized.
        assert(save_state != save_stats)
        self.save_state = save_state
        self.save_stats = save_stats
        self.overwrite = overwrite
        self.verify_path = verify_path
        # If we are saving the stats, then we need to create the player stat
        # directory if it doesn't already exit.
        # Else, we are saving features and the stats directory should already be
        # created.
        stats_dir = './data/players-daybyday'
        if self.save_stats and not os.path.exists(stats_dir):
            os.makedirs(stats_dir)
        assert(os.path.exists(stats_dir))



    def process_new_game(self, row):
        assert(row[0] == 'id')
        # If we already have a game that has been processed,
        # save it to disk before starting the new game.
        if self.game:
            # Save game
            self.game.end(self.next_score, 
                          self.config.output_path+f'/{self.game.date.year}eve', 
                          save_state=self.save_state,
                          save_stats=self.save_stats,
                          verify_stats_path=self.verify_path)
        # Start new game
        self.game = GameState(row[1][:-1]) # game id
        print(self.game.id)
        year = row[1][3:7] # pull year from game id
        self.logger = Logger(self.config.log_path+f'/{year}eve/{row[1][:-1]}.log')
        self.logger.log('---------------------------------------------------')
        self.logger.log(self.game.id)
        # Values caclulated after current play that are reflected
        # in the next state.
        self.next_outs = 0
        self.next_score = [0, 0]
        self.next_runners = [False, False, False]
        self.next_bpos = 0


    def process_game_info(self, row):
        assert(row[0] == 'info')
        assert(self.game)

        # Unpack row
        key = row[1]
        value = row[2]

        # Create teams
        if key == 'visteam':
            assert(self.game)
            assert(not self.game.teams[0])
            self.game.teams[0] = Team(value[:-1]) # team id
        elif key == 'hometeam':
            assert(self.game)
            assert(not self.game.teams[1])
            self.game.teams[1] = Team(value[:-1]) # team id

        # Get date
        elif key == 'date':
            assert(self.game)
            date = [int(num) for num in value[:-1].split('/')]
            self.game.date = datetime.date(date[0], date[1], date[2])
            self.logger.log(self.game.date)

        # Or store generic game information
        else:
            assert(self.game)
            self.game.info[key] = value[:-1]

        # If we have enough info to determine our team names, then do so.
        if ((self.game.teams[0] and self.game.teams[1] and self.game.date) and
                not (self.game.teams[0].name and self.game.teams[1].name)):
            year = self.game.date.year
            self.game.teams[0].add_team_name(self.config.input_path+f'/{year}eve/TEAM{year}')
            self.game.teams[1].add_team_name(self.config.input_path+f'/{year}eve/TEAM{year}')


    def process_starting_lineup(self, row):
        assert(self.game)
        assert(row[0] == 'start')

        # Unpack row
        pid = row[1]
        name = row[2].replace('"', '')
        team = int(row[3])
        bat_pos = int(row[4]) - 1 # 0-index batting position
        fld_pos = int(row[5])

        # Build player
        player = Player(pid, name)
        player.position = fld_pos
        player.batting = BattingStats(self.game.id,
                                      player.id,
                                      self.config.batting_feats,
                                      self.config.batting_intervals)
        
        # Increment the games played for this player
        player.batting.increment_stats(['G'])

        # Add player to the game
        self.game.teams[team].roster[player.id] = player
        if bat_pos > -1:
            self.game.teams[team].lineup[bat_pos] = player.id

        # Handle case where the player is the pitcher
        if player.position == 1:
            player.pitching = PitchingStats(self.game.id,
                                            player.id,
                                            self.config.pitching_feats,
                                            self.config.pitching_intervals)
            self.game.teams[team].pitcher = player.id
            player.pitching.increment_stats(['G', 'GS'])


    def process_substitutions(self, row):
        assert(self.game)
        assert(row[0] == 'sub')

        # Unpack row
        pid = row[1]
        name = row[2].replace('"', '') # Remove the quotation marks around the name
        team = int(row[3])
        bat_pos = int(row[4]) - 1 # 0-index batting position
        fld_pos = int(row[5])
        """
        print()
        print('Positions')
        for p in self.game.teams[team].roster.values():
            if p.position is None:
                print(p.name, None)
            else:
                print(p.name, Player.positions[p.position])
        """
        # Get old player by batting position
        # (or by pitcher field for non-hitting pitchers)
        if bat_pos != -1:
            old_pid = self.game.teams[team].lineup[bat_pos]
        else:
            old_pid = self.game.teams[team].pitcher
        old_player = self.game.teams[team].roster[old_pid]

        # Check for positional switch (i.e. same player moving positions)
        if pid == old_pid:
            # Remove the player from the position we are switching to.
            for player in self.game.teams[team].roster.values():
                if player.position == fld_pos:
                    # Check for redundant substitution.
                    # (i.e. switching a player into a position we
                    #       already have him playing)
                    if player.id == old_pid:
                        return
                    player.position = None
                    break
            # Place the player at the new position
            temp_pos = old_player.position # for logging purposes
            old_player.position = fld_pos
            # Handle if this is a pitching substitution
            if old_player.position == 1:
                old_player.pitching = PitchingStats(self.game.id,
                                                    pid,
                                                    self.config.pitching_feats,
                                                    self.config.pitching_intervals)
                self.game.teams[team].pitcher = old_player.id
                old_player.pitching.increment_stats(['G'])
                old_player.pitching.add_to_stat('IR', sum([bool(base) for base 
                                                        in self.game.runners]))
            # Log
            self.logger.log('---------------------------------------------------')
            old_pos = Player.positions[temp_pos] if temp_pos else temp_pos
            new_pos = Player.positions[fld_pos]
            self.logger.log(f'Switch {old_player.name} from {old_pos} to {new_pos}')
            if self.save_state:
                self.game.checkpoint()
            return

        # Handle case where the pitcher takes the batting spot of a hitter.
        #
        # Note: we don't vacate the pitching position yet
        #
        # Note: the second condition is for the rare case when the pitcher is swapped with
        # a position player, then the pitcher assumes the DH position.
        # Ex: TBA200904300
        #
        if (pid == self.game.teams[team].pitcher 
             or (
                 pid in self.game.teams[team].roster and 
                 self.game.teams[team].roster[pid].pitching
             )
            ): 
            # Add the pitcher in the DH's place in the lineup.
            self.game.teams[team].lineup[bat_pos] = pid
            # Remove the old player's position
            old_player.position = None
            # Change the pitcher's position if its not PR or PH.
            if fld_pos != 10 or fld_pos != 11 or fld_pos != 12:
                self.game.teams[team].roster[pid].position = fld_pos
            # Log
            self.logger.log('---------------------------------------------------')
            self.logger.log(f'DH position has been terminated')
            self.logger.log(f'P {self.game.teams[team].roster[pid].name} moves to {Player.positions[fld_pos]} in {old_player.name} batting spot')
            return

        # Build new player
        new_player = Player(pid, name) # player id, name
        self.game.teams[team].roster[pid] = new_player
        new_player.batting = BattingStats(self.game.id,
                                          new_player.id,
                                          self.config.batting_feats,
                                          self.config.batting_intervals)
        
        # Increment the games played stat for this player.
        new_player.batting.increment_stats(['G'])

        # Substitute new player for old player in the lineup
        if bat_pos != -1:
            self.game.teams[team].lineup[bat_pos] = new_player.id

        # Assign the new player's position and set the old player's
        # position to none.
        new_player.position = fld_pos
        old_pos = old_player.position
        old_player.position = None

        # Handle batter substitution
        if old_player.id == self.game.batter:
            self.game.batter = new_player.id
            # Check for strikeout ownership rule.
            # (See game object for a more detailed description.)
            if self.game.count[1] == 2: # If there's two strikes
                new_player.ph_strikeout_ownership = old_player.id

        # Handle pitching substitution
        if new_player.position == 1:
            new_player.pitching = PitchingStats(self.game.id,
                                                pid,
                                                self.config.pitching_feats,
                                                self.config.pitching_intervals)
            old_pitcher_id = self.game.teams[team].pitcher
            self.game.teams[team].pitcher = new_player.id
            new_player.pitching.increment_stats(['G'])
            new_player.pitching.add_to_stat('IR', sum([bool(base) for base 
                                                        in self.game.runners]))
            if self.is_pitcher_sub_count:
                self.logger.log(f'{old_pitcher_id} OWNS THE NEXT AT-BAT')
                self.mid_atbat_pitcher_owner = old_pitcher_id
                self.is_pitcher_sub_count = False

        # Handle pitch runner
        # Swap in the new player's id on the base paths
        if old_player.id in [base[0] for base in self.game.runners if base]:
            found = False
            for base in range(3):
                if self.game.runners[base] and self.game.runners[base][0] == old_player.id:
                    self.next_runners[base][0] = new_player.id
                    found = True
            assert(found)

        # Log
        npos_str = Player.positions[new_player.position]
        opos_str = Player.positions[old_pos] if old_pos else '-'
        self.logger.log('---------------------------------------------------')
        self.logger.log(f'Substitute {npos_str} {new_player.name} for {opos_str} {old_player.name}')
        if self.save_state:
            self.game.checkpoint()


    # Function to add batter advancement if it
    # was implicit based on play type.
    def add_implicit_adv(self, base, advancements):
        if not any([r[0] == 'B' for r in advancements]):
            advancements.append('B-'+str(base))


    # This function does the following:
    #     * Advances runners in the runners list.
    #     * Updates runner locations in bases.
    #     * Updates the number of runners who scored and the number of outs in
    #       in the inning after accounting for outs on the base paths.
    def advance_runners(self, runners, batter, pitcher, eligble_for_rbi, 
                                                        is_error, 
                                                        is_ptchr_owner_swap):
        # Sort runner advancements in descending order
        runner_order = {'B': 0, '1': 1, '2': 2, '3': 3}
        runners.sort(key=lambda r: runner_order[r[0]], reverse=True)

        # The pitcher at which the ownership swap occurs, only used when
        # is_ptchr_owner_swap = TRUE.
        owner_swap_pitcher = ''
        owner_swap_base = ''
        """
        if is_ptchr_owner_swap:
            print()
            print(pitcher.name)
            print(runners)
        """
        # Process advancements
        for runner in runners:
            # Check that the runner token is well formatted:
            # 1st char = (start base or 'B' for batter)
            # 2nd char = ('-' or 'X' if safe or not*)
            # 3rd char = (finish base or 'H' if scored)
            #
            # * - When errors occur on the base paths, the runner
            # is marked out, 'X', but is followed by an error
            # specifier. (1X2(1E4);B-1)
            if len(runner) < 3:
                assert(False)

            #if is_ptchr_owner_swap:
            #    print(runner)

            # Get the indicators for this advancement.
            indicators = re.findall(Processor.adv_ind_ptrn, runner[3:])

            # Process wild pitch indicator
            if 'WP' in indicators:
                pitcher.pitching.increment_stats(['WP'])

            # Determine the starting and ending base for the runner.
            # If the runner starts (B) or finishes at home (H), then False is assigned.
            strt = False if runner[0] == 'B' else int(runner[0])
            fnsh = False if runner[2] == 'H' else int(runner[2])

            # Ignore runner advancements after 3 outs have been made that
            # don't result in a run scored.
            if self.next_outs == 3 and runner[2] != 'H':
                continue

            # Determine if an error occured during the runner advancement.
            # Note: errors can occur with the runner still being thrown out.
            # In these cases, the putout should be recorded as a seperate
            # indicator. So, if we have an error with no putout, then the
            # runner is safe. Else, the runner is out.
            has_putout = False
            has_error = False
            for ind in re.findall(Processor.adv_ind_ptrn, runner[3:]):
                if 'E' in ind:
                    has_error = True
                if Processor.adv_putout_ptrn.match(ind):
                    has_putout = True
            # The only time the runner isn't out is if an error occurs without
            # a putout being specified. Else, the runner is out.
            is_out = ((runner[1] == 'X') and (not has_error or has_putout))
            # Handle out on the base paths
            #
            # Get the pitcher who we will swap ownership onto.
            #
            if is_out:
                #if is_ptchr_owner_swap:
                #    print('Is out')
                if is_ptchr_owner_swap and not owner_swap_pitcher and strt:
                    owner_swap_pitcher = self.game.runners[strt-1][1]
                    owner_swap_base = strt
                    #print(owner_swap_pitcher)
                    #print(f'owner_swap_base: {owner_swap_base}')
                self.next_outs += 1 # Out
            
            # Get the (runner id, pitcher id) for the base
            # If we don't have a starting base for this runner, then its the batter.
            runner_tuple = (self.next_runners[strt-1] if strt else [batter.id, pitcher.id])

            if strt:
                # check we have a runner at the starting base
                if not self.next_runners[strt-1]:
                    self.logger.log('---------------------------------------------------')
                    self.logger.log(f'Expected a runner at {strt} but got {self.next_runners}.')
                    assert(False)
                # Get the (runner id, pitcher id) at the starting base.
                runner_tuple = self.next_runners[strt-1]
                # Remove them from their starting base
                self.next_runners[strt-1] = False

            if not is_out and fnsh:
                # check we don't already have a runner at the finishing base
                if self.next_runners[fnsh-1]:
                    self.logger.log('---------------------------------------------------')
                    self.logger.log(f'Expected no runner at {fnsh} but got {self.next_runners}.')
                    assert(False)
                # Advance the runner to the next base.
                # If runner is False here, then the runner must be the batter.
                self.next_runners[fnsh-1] = runner_tuple

            elif not is_out:
                assert(runner[2] == 'H')
                # Count the run for the runner and owner pitcher's stats
                # The 'owner_pitcher' is the pitcher who owns this runner
                #    i.e. the pitcher who allowed this runner on base.
                runner = self.game.teams[self.game.is_bot].roster[runner_tuple[0]]
                owner_pitcher = self.game.teams[not self.game.is_bot].roster[runner_tuple[1]] if runner_tuple[1] else None
                runner.batting.increment_stats(['R'])
                if owner_pitcher:
                    owner_pitcher.pitching.increment_stats(['R'])
                # Check for inherited run scored.
                if owner_pitcher and owner_pitcher.id != pitcher.id:
                    pitcher.pitching.increment_stats(['IRS'])
                #
                # Determine whether or not to award an RBI.
                #
                # Runs are assumed to be RBIs for the batter unless explicitly
                # stated with a no RBI indicator, or an error occured on the
                # runner's advancement.
                #
                # OR
                #
                # If an RBI is not possible for the play type.
                # i.e. if a runner steals home, then the batter is not
                # awarded an RBI for that run
                #
                # OR
                #
                # The runner scores on a error not from third base.
                #
                # OR
                #
                # If the run scores due to a wild pitch.
                #
                # Note - indicators can come with modifiers so we take the first
                #        token in front of '/' to sort out any mods.
                if (
                    not (   'NORBI' in indicators or
                            'NR'    in indicators or
                            'WP'    in indicators or
                            'PB'    in indicators or
                            any([Processor.error_ptrn.match(ind.split('/')[0]) for
                                    ind in indicators]) or
                            (is_error and strt != 3))

                    and 
                        eligble_for_rbi
                    ):
                    batter.batting.increment_stats(['RBI'])
                #
                # Determine whether or not to count an earned run.
                if owner_pitcher and not 'UR' in indicators:
                    owner_pitcher.pitching.increment_stats(['ER'])
                # Update the score for the next game state
                self.next_score[self.game.is_bot] += 1 # Scored
        #
        # Perform the ownership swap
        #
        # The swap is performed on the leading base which is not already
        # owned by the swap pitcher.
        #
        if is_ptchr_owner_swap and owner_swap_pitcher and owner_swap_base:          
            for idx in range(owner_swap_base-1, -1, -1):
                #print(self.next_runners[idx])
                # Handle case where we have runners owned by multiple
                # former pitchers, in which case we want to cascade the
                # change backward.
                # Ex: CIN200004040
                if (self.next_runners[idx] and
                        (self.next_runners[idx][1] != pitcher.id or
                         self.next_runners[idx][1] != owner_swap_pitcher)):
                    #print(f'Swapping {self.next_runners[idx][0]} at base {idx+1} owner from {self.next_runners[idx][1]} to {owner_swap_pitcher}')
                    #print(f'Changing owner_swap_pitcher from {owner_swap_pitcher} to {self.next_runners[idx][1]}')
                    tmp = self.next_runners[idx][1]
                    self.next_runners[idx][1] = owner_swap_pitcher
                    owner_swap_pitcher = tmp
                # Handle case where the runner ownership is swapped between the current pitcher and the 
                # former pitcher who's runner was retired.
                elif (self.next_runners[idx] and
                      self.next_runners[idx][1] == pitcher.id):
                    #print(f'Swapping {self.next_runners[idx][0]} at base {idx+1} owner from {self.next_runners[idx][1]} to {owner_swap_pitcher}')
                    self.next_runners[idx][1] = owner_swap_pitcher
                    break
            


    def advance_stolen_bases(self, stls, adv):
        # Given a steal token, return the starting base index
        def start_base(token):
            return int(token[2])-2 if token[2] in ('2', '3') else 2
        # Sort the steals in descending order of starting base
        stl_list = stls.split(';')
        stl_list.sort(key=start_base, reverse=True)
        # Process each steal
        for stl in stl_list:
            strt_base = start_base(stl)
            if strt_base == 2:
                assert(stl[2] == 'H')
            # Atribute a stolen base to the player.
            pid = self.game.runners[strt_base][0]
            player = self.game.teams[self.game.is_bot].roster[pid]
            player.batting.increment_stats(['SB'])
            # Check for explicit advancement
            # Ex: SB2.1-3(WP)
            # Note: we skip the batter advancement here because stealing first
            #       is handled differently.
            if any([strt_base == int(a[0])-1 for a in adv if a[0] != 'B']):
                continue
            # Else, add implicit advancement
            adv.append(str(strt_base+1)+'-'+stl[2:])

    # Get number of pitches thrown for a given pitch string.
    def get_pitches_thrown(self, pstr):
        # Set of pitch codes for pitches thrown
        pitch_set = set(['B', 'C', 'F', 'H', 'I', 'K', 'L', 'M', 'O',
                         'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'X', 'Y'])
        n = 0
        for p in pstr:
            if p in pitch_set:
                n += 1
        return n
    
    # Get number of strikes thrown for a given pitch string.
    def get_strikes_thrown(self, pstr):
        # Set of pitch codes for pitches thrown
        strike_set = set(['C', 'F', 'K', 'L', 'M', 'O', 'Q', 'R', 'S', 
                          'T', 'X', 'Y'])
        n = 0
        for p in pstr:
            if p in strike_set:
                n += 1
        return n

    def process_single_fielder(self, play, mods, adv, batter, pitcher):
        if Processor.is_ground_out(mods):
            self.logger.log('--> Is GO')
        if Processor.is_air_out(mods):
            self.logger.log('--> Is AO')
        # Add a plate appearance for the batter and pitcher
        batter.batting.increment_stats(['PA'])
        pitcher.pitching.increment_stats(['TBF'])
        # Increment GDP stat if it is credited in the modifiers
        batter.batting.increment_stats(['GDP'] if ('GDP' in mods  or 'GDP#' in mods) else [])
        pitcher.pitching.increment_stats(['GDP'] if ('GDP' in mods  or 'GDP#' in mods) else [])
        # Increment ground ball or fly out stats for the pitcher.
        pitcher.pitching.increment_stats((['AO'] if Processor.is_air_out(mods) else []) + 
                                         (['GO'] if Processor.is_ground_out(mods) else []))
        # Check for implicit air or ground outs.
        if (
            not (
                    Processor.is_air_out(mods) or 
                    Processor.is_ground_out(mods)
                )
            and not (
                    Processor.is_bunt(mods) or 
                    Processor.is_sacrifice(mods)
                )
        ):
            # Check for implicit throwing error ground out
            # Ex: CHA200004270
            throwing_error_ptrn = re.compile('^[1,4,5,6]E3*')
            if (not ('SH' in mods or 'BG' in mods) and throwing_error_ptrn.match(play)):
                pitcher.pitching.increment_stats(['GO'])
            # Assume that a single fielder out made in the outfield is an airout
            # if not marked.
            elif (play in ('7', '8', '9')
                  and not 'SH' in mods
                  and not 'SF' in mods
                  and not 'BG' in mods
                  and not 'BF' in mods):
                pitcher.pitching.increment_stats(['AO'])
            # Assume a single fielder double play is an air out. (?)
            # Ex: SLN200008040
            elif ('DP' in mods):
                pitcher.pitching.increment_stats(['AO'])
            # Assume a single fielder batter interference was on a pop up. (?)
            # Ex: CLE200006300
            elif 'BINT' in mods:
                pitcher.pitching.increment_stats(['AO'])
        # Account for sacrifices
        # Note: if its not a sacrifice then its a normal at-bat
        if 'SF' in mods:
            batter.batting.increment_stats(['SF'])
            pitcher.pitching.increment_stats(['SF'])
            if not Processor.is_air_out(mods):
                pitcher.pitching.increment_stats(['AO'])
        elif 'SH' in mods:
            batter.batting.increment_stats(['SH'])
            pitcher.pitching.increment_stats(['SH'])
        else:
            batter.batting.increment_stats(['AB'])
            pitcher.pitching.increment_stats(['AB'])
        # Check if an error allowed the runner to reach base
        if 'E' in play:
            self.add_implicit_adv(1, adv)
        else:
            self.next_outs += 1
        self.next_bpos = (self.next_bpos+1)%9

    def process_putout(self, play, mods, adv, batter, pitcher):
        if Processor.is_ground_out(mods):
            self.logger.log('--> Is GO')
        if Processor.is_air_out(mods):
            self.logger.log('--> Is AO')
        batter.batting.increment_stats(['PA'])
        pitcher.pitching.increment_stats(['TBF'])
        # Account for sacrifice hits
        if 'SH' in mods:
            batter.batting.increment_stats(['SH'])
            pitcher.pitching.increment_stats(['SH'])
        else:
            batter.batting.increment_stats(['AB'])
            pitcher.pitching.increment_stats(['AB'])
        # Increment ground ball or fly out stats for the pitcher.
        pitcher.pitching.increment_stats((['AO'] if Processor.is_air_out(mods) else []) + 
                                         (['GO'] if Processor.is_ground_out(mods) else []))
        # Check for implicit air out or ground out
        
        putout_go_ptrn = re.compile('^[1,4,5,6][1-6]?3$')
        # Check for implicit air or ground outs.
        if (
            not (
                    Processor.is_air_out(mods) or 
                    Processor.is_ground_out(mods)
                )
            and not (
                    Processor.is_bunt(mods) or 
                    Processor.is_sacrifice(mods)
                )
        ):
            # Check for implicit gound out
            # Ex: CHA200006200
            # Add an optional intermediate throw in the regex.
            # Ex: KCA200004070
            if putout_go_ptrn.match(play):
                self.logger.log(f'Implied GO: {play}')
                pitcher.pitching.increment_stats(['GO'])
            # Assume a ground out if the batter interfered on a mutliplayer out.
            elif 'BINT' in mods:
                self.logger.log(f'Implied GO: {play}')
                pitcher.pitching.increment_stats(['GO'])
        self.next_outs += 1
        self.next_bpos = (self.next_bpos+1)%9

    def process_force_out(self, play, mods, adv, batter, pitcher):
        #if Processor.is_ground_out(mods):
        #    self.logger.log('--> Is GO')
        batter.batting.increment_stats(['PA'])
        pitcher.pitching.increment_stats(['TBF'])
        # Check for sacrifice fly modifier
        if 'SF' in mods:
            batter.batting.increment_stats(['SF'])
            pitcher.pitching.increment_stats(['SF'])
        else:
            batter.batting.increment_stats(['AB'])
            pitcher.pitching.increment_stats(['AB'])
        # Check for GDP modifier
        batter.batting.increment_stats(['GDP'] if ('GDP' in mods  or 'GDP#' in mods) else [])
        pitcher.pitching.increment_stats(['GDP'] if ('GDP' in mods  or 'GDP#' in mods) else [])
        # Increment ground ball or fly out stats for the pitcher.
        # Assume ground out if not air out or bunt or sacrifice
        if Processor.is_air_out(mods):
            self.logger.log('--> Is AO')
            pitcher.pitching.increment_stats(['AO'])
        elif not(Processor.is_bunt(mods) or 'SH' in mods or 'SF' in mods):
            self.logger.log('--> Is GO')
            pitcher.pitching.increment_stats(['GO'])
            #pitcher.pitching.increment_stats((['AO'] if Processor.is_air_out(mods) else []) + 
            #                                 (['GO'] if Processor.is_ground_out(mods) else []))
        # Update game state
        #self.next_outs += 1
        self.next_bpos = (self.next_bpos+1)%9
        # Add explicit out for the runner who was forced out from the basepaths
        # Ex pattern: 54(1), number in parenthesis should be [1-3]
        base = int(play[play.find('(')+1])
        assert(self.next_runners[base-1])
        if not any([a[0] == str(base) for a in adv]):
            adv.append(str(base)+'X'+ (str(base+1) if base+1 < 4 else 'H'))
        # Add implicit batter advancement if one is not given explicitly
        if not any([a[0] == 'B' for a in adv]):
            self.add_implicit_adv(1, adv)

    def process_dbl_ply(self, play, mods, adv, batter, pitcher):
        if Processor.is_ground_out(mods):
            self.logger.log('--> Is GO')
        if Processor.is_air_out(mods):
            self.logger.log('--> Is AO')
        # Increment batter stats
        batting_stats = ['PA']
        batting_stats += ['GDP'] if ('GDP' in mods  or 'GDP#' in mods) else []
        batting_stats += ['SF'] if 'SF' in mods else ['AB']
        batter.batting.increment_stats(batting_stats)
        # Increment pitcher stats
        pitching_stats =  ['TBF']
        pitching_stats += ['GDP'] if ('GDP' in mods  or 'GDP#' in mods) else []
        pitching_stats += ['SF']  if  'SF' in mods else ['AB']
        pitching_stats += ['AO']  if  Processor.is_air_out(mods) else []
        pitching_stats += ['GO']  if  Processor.is_ground_out(mods) else []
        pitcher.pitching.increment_stats(pitching_stats)
        # Assume AO or GO based on first fielder and runner
        if (
                not (
                        Processor.is_air_out(mods) or 
                        Processor.is_ground_out(mods)
                    )
                and not (
                        Processor.is_bunt(mods) or 
                        Processor.is_sacrifice(mods)
                    )
            ):
            outfielder = set(['7', '8', '9'])
            if play[0] in outfielder and play[2] == 'B':
                pitcher.pitching.increment_stats(['AO'])
            elif not play[0] in outfielder:
                pitcher.pitching.increment_stats(['GO'])
        """
        # Update next outs and next batter
        self.next_outs += 2
        self.next_bpos = (self.next_bpos+1) % 9
        # Determine which players were retired in the
        # double play.
        bases = []
        for idx in range(1, len(play)):
            if play[idx-1] == '(':
                bases.append(play[idx])
        # Handle the two forms of double plays:
        # 1. Only one base is specified explicitly and it is implied
        #    the batter was retired Ex. 64(1)3
        #
        # 2. Two bases are specified in which case we don't need to
        #    worry about the implicit batter out. Ex. 8(B)84(2)
        assert(len(bases) == 1 or len(bases) == 2)
        for b in bases:
            if b != 'B':
                assert(b in ('1', '2', '3'))
                assert(self.next_runners[int(b)-1])
                self.next_runners[int(b)-1] = False
        """
        self.next_bpos = (self.next_bpos+1) % 9
        # Determine which players were retired in the
        # double play.
        bases = []
        for idx in range(1, len(play)):
            if play[idx-1] == '(':
                bases.append(play[idx])
        # Handle the two forms of double plays:
        # 1. Only one base is specified explicitly and it is implied
        #    the batter was retired Ex. 64(1)3
        #
        # 2. Two bases are specified in which case we don't need to
        #    worry about the implicit batter out. Ex. 8(B)84(2)
        assert(len(bases) == 1 or len(bases) == 2)
        for b in bases:
            if b != 'B':
                assert(b in ('1', '2', '3'))
                assert(self.next_runners[int(b)-1])
                adv.append(b+'X'+(str(int(b)+1) if int(b)<4 else 'H'))
            else:
                adv.append('BX1')
        if len(bases) == 1:
            adv.append('BX1')
        # If the batter isn't retired in the double play then it needs
        # to be added to the advancements
        # Note - no implicit advance if the inning is over.
        if len(bases) == 2 and not 'B' in bases and self.next_outs != 3:
            if not any([a[0] == 'B' for a in adv]):
                self.add_implicit_adv(1, adv)

    def process_trpl_ply(self, play, mods, adv, batter, pitcher):
        if Processor.is_air_out(mods):
            self.logger.log('--> Is AO')
        if Processor.is_ground_out(mods):
            self.logger.log('--> Is GO')
        # Increment batter stats
        batter.batting.increment_stats(['AB', 'PA'])
        # Increment pitcher stats
        pitcher.pitching.increment_stats(['AB', 'TBF'])
        # Increment ground ball or fly out stats for the pitcher.
        pitcher.pitching.increment_stats((['AO'] if Processor.is_air_out(mods) else []) + 
                                         (['GO'] if Processor.is_ground_out(mods) else []))
        # Assume AO or GO based on first fielder and runner
        if not (Processor.is_air_out(mods) or Processor.is_ground_out(mods)):
            outfielder = set(['7', '8', '9'])
            if play[0] in outfielder and play[2] == 'B':
                pitcher.pitching.increment_stats(['AO'])
            elif not play[0] in outfielder:
                pitcher.pitching.increment_stats(['GO'])
        # Update game state
        self.next_outs += 3
        self.next_bpos = (self.next_bpos+1) % 9
        bases = []
        for idx in range(1, len(play)):
            if play[idx-1] == '(':
                if play[idx] != 'B':
                    bases.append(int(play[idx])-1)
        for b in bases:
            assert(self.next_runners[b])
            self.next_runners[b] = False

    def process_intrfrnc(self, play, adv, batter, pitcher):
        batter.batting.increment_stats(['PA'])
        pitcher.pitching.increment_stats(['TBF'])
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_single(self, play, adv, batter, pitcher):
        batter.batting.increment_stats(['PA', 'AB', 'H', 'TB'])
        pitcher.pitching.increment_stats(['TBF', 'AB', 'H', 'TB'])
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_double(self, play, adv, batter, pitcher):
        batter.batting.increment_stats(['PA', 'AB', 'H', '2B'] + 2*['TB'])
        pitcher.pitching.increment_stats(['TBF', 'AB', 'H', '2B'] + 2*['TB'])
        self.add_implicit_adv(2, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_triple(self, play, adv, batter, pitcher):
        batter.batting.increment_stats(['PA', 'AB', 'H', '3B'] + 3*['TB'])
        pitcher.pitching.increment_stats(['TBF', 'AB', 'H', '3B'] + 3*['TB'])
        self.add_implicit_adv(3, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_gr_double(self, play, adv, batter, pitcher):
        batter.batting.increment_stats(['PA', 'AB', 'H', '2B'] + 2*['TB'])
        pitcher.pitching.increment_stats(['TBF', 'AB', 'H', '2B'] + 2*['TB'])
        self.add_implicit_adv(2, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_error(self, play, mods, adv, batter, pitcher):
        # The play counts as a sacrifice hit/fly even if an error is made.
        if 'SH' in mods:
            batter.batting.increment_stats(['PA', 'SH'])
            pitcher.pitching.increment_stats(['TBF', 'SH'])
        elif 'SF' in mods:
            batter.batting.increment_stats(['PA', 'SF'])
            pitcher.pitching.increment_stats(['TBF', 'SF'])
        else:
            batter.batting.increment_stats(['PA', 'AB'])
            pitcher.pitching.increment_stats(['TBF', 'AB'])
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_fielders_ch(self, play, mods, adv, batter, pitcher):
        #if Processor.is_ground_out(mods):
        #    self.logger.log('--> Is GO')
        # Check for sacrifice hits or flys modifier
        batting_stats = ['PA']
        pitching_stats = ['TBF']
        if 'SH' in mods:
            batting_stats += ['SH']
            pitching_stats += ['SH']
        elif 'SF' in mods:
            batting_stats += ['SF']
            pitching_stats += ['SF']
        else:
            batting_stats += ['AB']
            pitching_stats += ['AB']
        # Check for GDP
        if 'GDP' in mods:
            batting_stats += ['GDP']
            pitching_stats += ['GDP']
        # Increment ground ball or fly out stats for the pitcher.
        # NOTE - Not counted as a GO in SFN201004230
        #pitcher.pitching.increment_stats((['AO'] if 'F' in mods else []) + 
        #                                 (['GO'] if Processor.is_ground_out(mods) else []))
        # Apply the stats
        batter.batting.increment_stats(batting_stats)
        pitcher.pitching.increment_stats(pitching_stats)
        # Update game state
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_foul_fly_error(self, play, adv, batter, pitcher):
        pass

    def process_homerun(self, play, adv, batter, pitcher):
        # Increment homerun stats for the batter.
        batter.batting.increment_stats(['PA', 'AB', 'H', 'HR'] + 4*['TB'])
        pitcher.pitching.increment_stats(['TBF', 'AB', 'H', 'HR'] + 4*['TB'])
        if all(self.game.runners):
            batter.batting.increment_stats(['HR4'])
            pitcher.pitching.increment_stats(['HR4'])
        # Account for batter scoring
        # Any baserunners will be accounted for in runner advancement
        # Note - we increment the run here for the batter's stats if the
        # advancement is not explicitly given.
        if all([a[0] != 'B' for a in adv]):
            self.next_score[self.game.is_bot] += 1
            batter.batting.increment_stats(['R', 'RBI'])
            pitcher.pitching.increment_stats(['R', 'ER'])
        self.next_bpos = (self.next_bpos+1)%9

    def process_hbp(self, play, adv, batter, pitcher):
        batter.batting.increment_stats(['PA', 'HP'])
        pitcher.pitching.increment_stats(['TBF', 'HP'])
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_k(self, play, adv, batter, pitcher):
        # Check if the batter owns this strikeout.
        if batter.ph_strikeout_ownership:
            batter = self.game.teams[self.game.is_bot].roster[batter.ph_strikeout_ownership]
        batter.batting.increment_stats(['PA', 'AB', 'SO'])
        pitcher.pitching.increment_stats(['TBF', 'AB', 'SO'])
        play_str = 'Strikeout'
        self.next_bpos = (self.next_bpos+1)%9
        # If the batter is not in the list of runner advancements, then
        # mark him out here; otherwise, let the advance runners function
        # figure out whether the batter is out.
        if not any([a[0] == 'B' for a in adv]):
            self.next_outs += 1
        # Handle strikeouts followed by events
        if Processor.k_w_event_ptrn.match(play):
            kevt = play[play.find('+')+1:]
            if Processor.stln_base_ptrn.match(kevt):
                play_str += ' w/ Stolen Base'
                self.process_stln_base(kevt, adv, batter, pitcher)
            elif Processor.caught_stln_ptrn.match(kevt):
                play_str += ' w/ Caught Stealing'
                self.process_caught_stln(kevt, adv, batter, pitcher)
            elif Processor.other_adv_ptrn.match(kevt):
                play_str += ' w/ Other Advancement'
            elif Processor.pickoff_ptrn.match(kevt):
                play_str += ' w/ Pickoff'
                self.process_pickoff(kevt, adv, batter, pitcher)
            elif Processor.pickoff_off_ptrn.match(kevt):
                play_str += ' w/ Pickoff Off base'
                self.process_pickoff_off(kevt, adv, batter, pitcher)
            elif Processor.past_ball_ptrn.match(kevt):
                play_str += ' w/ Pass Ball'
            elif Processor.wild_pitch_ptrn.match(kevt):
                play_str += ' w/ Wild Pitch'
                pitcher.pitching.increment_stats(['WP'])
            elif Processor.error_ptrn.match(kevt):
                play_str += ' w/ Error'
            elif Processor.def_indiff_ptrn.match(kevt):
                play_str += ' w/ Defense Indifference'
            else:
                self.logger.log(f'Unrecognized event following strikeout: {kevt}')
                assert(False)
        return play_str

    def process_walk(self, play, adv, batter, pitcher):
        batter.batting.increment_stats(['PA'] + (['IBB', 'BB'] if play[0] == 'I' else ['BB']))
        pitcher.pitching.increment_stats(['TBF'] + (['IBB', 'BB'] if play[0] == 'I' else ['BB']))
        play_str = 'Walk'
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9
        # Handle event after walk
        if Processor.walk_w_event_ptrn.match(play):
            wevt = play[play.find('+')+1:]
            if Processor.stln_base_ptrn.match(wevt):
                play_str += ' w/ Stolen Base'
                self.process_stln_base(wevt, adv, batter, pitcher)
            elif Processor.caught_stln_ptrn.match(wevt):
                play_str += ' w/ Caught Stealing'
                self.process_caught_stln(wevt, adv, batter, pitcher)
            elif Processor.pickoff_ptrn.match(wevt):
                play_str += ' w/ Pickoff'
                self.process_pickoff(wevt, adv, batter, pitcher)
            elif Processor.pickoff_off_ptrn.match(wevt):
                play_str += ' w/ Pickoff Off Base'
                self.process_pickoff_off(wevt, adv, batter, pitcher)
            elif Processor.past_ball_ptrn.match(wevt):
                play_str += ' w/ Passed Ball'
            elif Processor.wild_pitch_ptrn.match(wevt):
                play_str += ' w/ Wild Pitch'
                pitcher.pitching.increment_stats(['WP'])
            elif Processor.error_ptrn.match(wevt):
                play_str += ' w/ Error'
            elif Processor.def_indiff_ptrn.match(wevt):
                play_str += ' w/ Defense Indifference'
            elif Processor.other_adv_ptrn.match(wevt):
                play_str += ' w/ Other Advancement'
            else:
                self.logger.log(f'Unrecognized event following strikeout: {wevt}')
                assert(False)
        return play_str

    def process_caught_stln(self, play, adv, batter, pitcher):
        base = int(play[2])-2 if play[2] in ('2', '3') else 2
        assert(self.game.runners[base])
        # Record the caught stealing in the runner's stats.
        runner = self.game.teams[self.game.is_bot].roster[self.game.runners[base][0]]
        runner.batting.increment_stats(['CS'])
        # If there was no error on the play then record the out
        # and remove the runner from the base paths.
        if not 'E' in play:
            self.next_runners[base] = False
            self.next_outs += 1
        # Else, if there was an error but no explicit advancement was
        # given, then add an implicit one.
        elif all([int(a[0]) != base+1 for a in adv if a[0] != 'B']):
            next_base = str(base+2) if base+1 != 3 else 'H'
            # Add any modifiers to the assumed advancement.
            # Ex: ARI200006240
            # play,5,0,huntb002,01,CB,CSH(E5)(UR)
            adv.append(f'{base+1}-' + next_base + play[3:])
            adv.sort(reverse=True, key=lambda a: int(a[0]))

    def process_pickoff(self, play, adv, batter, pitcher):
        if not 'E' in play:
            base = int(play[2])-1
            assert(self.game.runners[base])
            self.next_runners[base] = False
            self.next_outs += 1

    def process_pickoff_off(self, play, adv, batter, pitcher):
        # Get the base the runner started at.
        base = int(play[4])-2 if play[4] in ('2', '3') else 2
        assert(self.game.runners[base])
        # Runner is charged a caught stealing.
        runner = self.game.teams[self.game.is_bot].roster[self.game.runners[base][0]]
        runner.batting.increment_stats(['CS'])
        # Remove the runner from the base paths.
        # Or advance them if there's an error.
        if not 'E' in play:
            self.next_runners[base] = False
            self.next_outs += 1
        else:
            # If an error occurs during the run down, then we need to add
            # an implicit advancement if an explicit one isn't given.
            if not any([a[0] == str(base+1) for a in adv]):
                adv.append(str(base+1) + '-' + play[4])

    def process_stln_base(self, play, adv, batter, pitcher):
        # Note - stolen base stats are accumulated in advance_stolen_bases()
        self.advance_stolen_bases(play, adv)

    # Set of play strings for events that end the at-bat
    end_of_atbat_plays = set(['Out',
                              'Force Out',
                              'Ground Ball Double Play',
                              'Line Out Double Play',
                              'Double Play',
                              'Ground Ball Triple Play',
                              'Line Out Triple Play',
                              'Catcher Interference',
                              'Single',
                              'Double',
                              'Triple',
                              'Ground Rule Double',
                              'Error',
                              'Fielders Choice',
                              'Homerun',
                              'Hit by Pitch',
                              'Strikeout',
                              'Strikeout w/ Stolen Base',
                              'Strikeout w/ Caught Stealing',
                              'Strikeout w/ Other Advancement',
                              'Strikeout w/ Pickoff',
                              'Strikeout w/ Pickoff Off base',
                              'Strikeout w/ Pass Ball',
                              'Strikeout w/ Wild Pitch',
                              'Strikeout w/ Error',
                              'Strikeout w/ Defense Indifference',
                              'Walk',
                              'Walk w/ Stolen Base',
                              'Walk w/ Caught Stealing',
                              'Walk w/ Pickoff',
                              'Walk w/ Pickoff Off Base',
                              'Walk w/ Passed Ball',
                              'Walk w/ Wild Pitch',
                              'Walk w/ Error',
                              'Walk w/ Defense Indifference',
                              'Walk w/ Other Advancement'])

    is_end_of_atbat = lambda play_str: play_str in Processor.end_of_atbat_plays

    def process_play(self, row):
        assert(self.game)
        assert(row[0] == 'play')

        # Unpack row
        inning = row[1]
        team = int(row[2])
        batter_id = row[3]
        count = [int(row[4][0]), int(row[4][1])]
        pitches = row[5]
        event = row[6][:-1]

        # Update game state
        self.game.inning = inning
        self.game.is_bot = team
        self.game.outs = self.next_outs
        self.game.score = self.next_score[:]
        self.game.runners[:] = self.next_runners[:]
        self.game.batter = batter_id
        self.game.count = count

        # Parse action string into play, advance, and modifier strings
        play, mods, adv = '', [], []
        period_pos, slash_pos = -1, -1
        inparen = False
        for i, char in enumerate(event):
            if char == '/' and not inparen and slash_pos == -1:
                slash_pos = i
            if char == '.' and not inparen:
                assert(period_pos == -1)
                period_pos = i
            if char == '(':
                inparen = True
            if char == ')':
                assert(inparen)
                inparen = False

        # Have both advancements and modifiers
        if slash_pos != -1 and period_pos != -1:
            play = event[:slash_pos]
            mods = event[slash_pos+1:period_pos].split('/')
            adv = event[period_pos+1:].split(';')
        # Just have modifiers
        elif slash_pos != -1:
            play = event[:slash_pos]
            mods = event[slash_pos+1:].split('/')
        # Just have advancements
        elif period_pos != -1:
            play = event[:period_pos]
            adv = event[period_pos+1:].split(';')
        # Only play
        else:
            play = event

        # Verify that our team's batting position matches the batter provided
        # by retrosheets.
        if not 'BOOT' in mods:
            if self.game.batter != self.game.teams[self.game.is_bot].lineup[self.next_bpos]:
                self.logger.log(f'Expected {self.game.teams[self.game.is_bot].lineup[self.next_bpos]} but got {self.game.batter}')
                self.logger.log()
                self.logger.log('Batting Lineup')
                for i, pid in enumerate(self.game.teams[self.game.is_bot].lineup):
                    if i == self.next_bpos:
                        self.logger.log(f'*{i} {pid}')
                    else:
                        self.logger.log(f' {i} {pid}')
                assert(False)

        # Update batting position
        self.game.teams[self.game.is_bot].bpos = self.next_bpos

        # Get batter player
        batter = self.game.teams[self.game.is_bot].roster[batter_id]

        # Get the pitcher
        pitcher = self.game.teams[not self.game.is_bot].roster[self.game.teams[not self.game.is_bot].pitcher]

        # Whether or not the batter is eligble for an RBI on this play.
        # Instances where they're not eligble are when they do not put the ball
        # in play, such as stolen base plays.
        eligble_for_rbi = True

        # If the play type is an error.
        # This is passed to advance_runners to determine the RBI stat.
        is_error = False

        # Is force out or is fielder's choice
        # This is used to determine which pitcher owns a given runner.
        is_ptchr_owner_swap = False

        # ---------------------------------------------------------------------------
        # Process each event based on type
        # ---------------------------------------------------------------------------
        play_str = '' # String used for logging the play
        #
        # Single fielder out
        if Processor.single_fielder_ptrn.match(play):
            play_str = 'Single Fielder Out'
            self.process_single_fielder(play, mods, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Force Out
        elif Processor.force_out_ptrn.match(play):
            play_str = 'Force Out'
            self.process_force_out(play, mods, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
            # Mark force out for tracking pitcher-runner ownership.
            is_ptchr_owner_swap = True
        #
        # Multi-Fielder Out or Put Out
        elif Processor.multi_fielder_ptrn.match(play) or Processor.putout_ptrn.match(play):
            play_str = 'Out'
            self.process_putout(play, mods, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Double Play
        elif Processor.dbl_ply_ptrn.match(play):
            if 'GDP' in mods:
                play_str = 'Ground Ball Double Play'
            elif 'LDP' in mods:
                play_str = 'Line Out Double Play'
            else:
                play_str = 'Double Play'
            self.process_dbl_ply(play, mods, adv, batter, pitcher)
            if not 'SF' in mods:
                eligble_for_rbi = False
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
            # Mark for tracking pitcher-runner ownership.
            is_ptchr_owner_swap = True
        #
        # Triple Play
        elif Processor.trpl_ply_ptrn.match(play):
            if 'GTP' in mods:
                play_str = 'Ground Ball Triple Play'
            elif 'LTP' in mods:
                play_str = 'Line Out Triple Play'
            else:
                play_str = 'Triple Play'
            self.process_trpl_ply(play, mods, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Catchers Interference
        elif Processor.intrfrnc_ptrn.match(play):
            play_str = 'Catcher Interference'
            self.process_intrfrnc(play, adv, batter, pitcher)
            # RBIs are only credited for catcher's interference
            # if the bases are loaded.
            if not all(self.game.runners):
                eligble_for_rbi = False
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Single
        elif Processor.single_ptrn.match(play):
            play_str = 'Single'
            self.process_single(play, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Double
        elif Processor.double_ptrn.match(play):
            play_str = 'Double'
            self.process_double(play, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Triple
        elif Processor.triple_ptrn.match(play):
            play_str = 'Triple'
            self.process_triple(play, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Ground Rule Double
        elif Processor.gr_double_ptrn.match(play):
            play_str = 'Ground Rule Double'
            self.process_gr_double(play, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Error
        elif Processor.error_ptrn.match(play):
            play_str = 'Error'
            self.process_error(play, mods, adv, batter, pitcher)
            is_error = True
            #
            # Whether or not an RBI is awarded on an error depends on whether
            # the error caused the run to score. This is a subjective judgement
            # made by the scorer and not always clearly indicated by a NORBI
            # indicator.
            #
            # If its ruled a sacrifice fly, then the rbi can be counted.
            if 'SF' in mods:
                eligble_for_rbi = True
            #
            # If the out is made, then the run wouldn't score.
            elif self.game.outs == 2: 
                eligble_for_rbi = False
            #
            # If the fly ball is caught, then the runners don't advance.
            elif 'F' in mods: 
                eligble_for_rbi = False
            #
            # The batter should've been forced out so he cannot earn a rbi.
            #
            # If there's less than two outs and a runner on third, then we assume
            # the runner would've scored regardless if the force out at first was 
            # made or not.
            elif 'FO' in mods and not self.game.runners[2]:
                eligble_for_rbi = False
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Fielder's Choice
        elif Processor.fielders_ch_ptrn.match(play):
            play_str = "Fielders Choice"
            self.process_fielders_ch(play, mods, adv, batter, pitcher)
            if 'GDP' in mods:
                eligble_for_rbi = False
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
            # Mark fielder's choice to track pitcher-runner ownership
            is_ptchr_owner_swap = True
        #
        # Foul Fly Error
        elif Processor.foul_fly_error_ptrn.match(play):
            play_str = 'Error on Foul Fly'
            self.process_foul_fly_error(play, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Home run
        elif Processor.homerun_ptrn.match(play):
            play_str = 'Homerun'
            self.process_homerun(play, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Hit by pitch
        elif Processor.hbp_ptrn.match(play):
            play_str = 'Hit by Pitch'
            self.process_hbp(play, adv, batter, pitcher)
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Strikeout wo/ event
        # or
        # Strikeout w/ event
        elif Processor.k_no_event_ptrn.match(play) or Processor.k_w_event_ptrn.match(play):
            play_str = self.process_k(play, adv, batter, pitcher)
            eligble_for_rbi = False
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # No Play
        elif Processor.no_play_ptrn.match(play):
            play_str = 'No Play'
            # The batter only belongs to the old pitcher in certain counts.
            if count in [[2, 0], [2, 1], [3, 0], [3, 1], [3, 2]]:
                #print(f'IS PITCHER SUB COUNT {count}')
                self.logger.log(f'IS PITCHER SUB COUNT {count}')
                self.is_pitcher_sub_count = True
        #
        # Walk
        elif Processor.walk_ptrn.match(play) or Processor.walk_w_event_ptrn.match(play):
            if self.mid_atbat_pitcher_owner:
                #print(f'{self.mid_atbat_pitcher_owner} owns the walk')
                pitcher = self.game.teams[not self.game.is_bot].roster[self.mid_atbat_pitcher_owner]
                self.mid_atbat_pitcher_owner = ''
            play_str = self.process_walk(play, adv, batter, pitcher)
            # Handle stats associated with the event after the walk
            if Processor.walk_w_event_ptrn.match(play):
                wevt = play[play.find('+')+1:]
                # If a runner steals home after a walk, then that run does not count as an
                # rbi for the batter.
                if Processor.stln_base_ptrn.match(wevt):
                    eligble_for_rbi = False
                # Wild pitches do not count as RBIs unless the run is forced home
                # from 3rd by the walk.
                if Processor.wild_pitch_ptrn.match(wevt):
                    if all(self.game.runners):
                        batter.batting.increment_stats(['RBI'])
                    eligble_for_rbi = False
            # Clear strikeout ownership if it is set.
            batter.ph_strikeout_ownership = ''
        #
        # Balk
        elif Processor.balk_ptrn.match(play):
            play_str = 'Balk'
            eligble_for_rbi = False
            pitcher.pitching.increment_stats(['BK'])
        #
        # Caught Stealing
        elif Processor.caught_stln_ptrn.match(play):
            play_str = 'Caught Stealing'
            self.process_caught_stln(play, adv, batter, pitcher)
            eligble_for_rbi = False
        #
        # Defensive indifference
        elif Processor.def_indiff_ptrn.match(play):
            play_str = 'Defensive Indifference'
        #
        # Other advancement
        elif Processor.other_adv_ptrn.match(play):
            play_str = 'Other Advancement'
            eligble_for_rbi = False
        #
        # Passed ball
        elif Processor.past_ball_ptrn.match(play):
            play_str = 'Passed Ball'
            eligble_for_rbi = False
        #
        # Wild pitch
        elif Processor.wild_pitch_ptrn.match(play):
            play_str = 'Wild Pitch'
            eligble_for_rbi = False
            pitcher.pitching.increment_stats(['WP'])
        #
        # Picked off
        elif Processor.pickoff_ptrn.match(play):
            play_str = 'Pickoff'
            self.process_pickoff(play, adv, batter, pitcher)
            eligble_for_rbi = False
        #
        # Picked off off base
        elif Processor.pickoff_off_ptrn.match(play):
            play_str = 'Picked Off, Off Base'
            self.process_pickoff_off(play, adv, batter, pitcher)
            eligble_for_rbi = False
        #
        # Stolen base
        elif Processor.stln_base_ptrn.match(play):
            play_str = 'Stolen Base'
            self.process_stln_base(play, adv, batter, pitcher)
            eligble_for_rbi = False
        #
        # No pattern match - throw error
        else:
            self.logger.log('---------------------------------------------------')
            self.logger.log('Play pattern is not recognized!')
            self.logger.log(f'Play: {play}')
            assert(False)


        # ---------------------------------------------------------------------------
        # Advance runners
        # ---------------------------------------------------------------------------
        #
        self.advance_runners(adv, batter, pitcher, eligble_for_rbi,
                                                   is_error,
                                                   is_ptchr_owner_swap)

        # Print state
        self.logger.log('---------------------------------------------------')
        self.logger.log(self.game)
        self.logger.log(play_str)

        # Save game state
        if self.save_state:
            self.game.checkpoint()

        # Update pitcher stats
        #
        # Retrosheets carries over the pitch records when events occur during at-bats
        #
        # Ex: when a pickoff play happens mid at-bat
        #
        # As such, we must wait until the end of the at-bat to count the pitches
        # for the at-bat.
        #
        # NOTE - What about mid-at-bat pinch hitters?
        #
        if (Processor.is_end_of_atbat(play_str) or self.next_outs == 3):
            pitcher.pitching.add_to_stat('PITCH', self.get_pitches_thrown(pitches))
            pitcher.pitching.add_to_stat('STRIKE', self.get_strikes_thrown(pitches))
            self.mid_atbat_pitcher_owner = '' # Clear mid at-bat pitcher change field
            self.is_pitcher_sub_count = False

        # Increment outs stats
        pitcher.pitching.add_to_stat('OUT',   self.next_outs - self.game.outs)

        #
        # Reset after new inning
        assert(self.next_outs <= 3)
        if self.next_outs == 3:
            self.logger.log('---------------------------------------------------')
            self.next_outs = 0
            self.next_runners = [False, False, False]
            self.game.teams[self.game.is_bot].bpos = self.next_bpos
            self.next_bpos = self.game.teams[not self.game.is_bot].bpos


    def process_runner_adj(self, row):
        assert(row[0] == 'radj')
        base = int(row[2])-1
        assert(self.next_runners[base] == False)
        self.next_runners[base] = [row[1], None]
        self.logger.log('---------------------------------------------------')
        self.logger.log(f'Runner Adjustment - Adding Runner to Base {base}')

    def process_lineup_adj(self, row):
        team = int(row[1])
        bpos = int(row[2][:-1])-1 # zero-indexed
        self.next_bpos = bpos
        pid = self.game.teams[team].lineup[bpos]
        self.logger.log('---------------------------------------------------')
        self.logger.log(f'Lineup Adjustment - {self.game.teams[team].name} batting position is now {self.next_bpos}')
        self.logger.log(f'{self.game.teams[team].roster[pid].name} is now batting.')

    # Featurizes a given team's home games (this is the way retrosheets
    # organizes the event files). Saves featurized game matricies to the
    # output path provided at initialization time.
    #
    # Input:
    #  - year (int) - season to be processed
    #  - team_id (string) - Retrosheet team id
    #  - team_lg (char) - Retrosheet league id (either 'A' or 'N')
    #  - game_id (string) - optional, Retrosheet game id to be processed
    #
    # Output:
    #    None
    #
    def process_team(self, year, team_id, team_lg, game_id=''):
        # Open event file for the given year and team
        filepath = self.config.input_path+f'/{year}eve/'
        filename = f'{year}{team_id}.EV{team_lg}'
        file = open(filepath+filename, 'r')
        lines = file.readlines()
        skip = False
        for line in lines:
            print(line)
            # Parse string row
            row = line.split(',')

            # Process new game
            # row = ['id', game id]
            if row[0] == 'id':
                if game_id:
                    skip = (row[1][:-1] != game_id)
                    if skip:
                        continue
                self.process_new_game(row)

            # Skip this game's rows?
            if skip:
                continue

            # Process teams
            # row = ['info', home or away, team id]
            #    or
            # row = ['info', key, value]
            if row[0] == 'info':
                self.logger.log(line)
                self.process_game_info(row)

            # Process starting lineup
            # row = ['start', player id, player name, team, batting pos, fielding pos]
            if row[0] == 'start':
                self.logger.log(line)
                self.process_starting_lineup(row)

            # Process substitutions
            # row = ['sub', player id, name, team, batting pos, fielding pos]
            # Example:  ['sub', 'florw001', '"Wilmer Flores"', '1', '4', '11\n']
            if row[0] == 'sub':
                self.logger.log(line)
                self.process_substitutions(row)

            # Process Play
            # Note: think about this as evolving the game from one state to the next
            #
            # row = ['play', inning, team at bat, batter id, count, pitches, event]
            # Example play: ['play', '9', '0', 'owinc001', '32', '.BTCBFBFX', 'T8/F89D+\n']
            if row[0] == 'play':
                self.logger.log(line)
                self.process_play(row)

            # Process runner adjustment
            # Note: used for runners starting at 2nd base in extra innings
            if row[0] == 'radj':
                self.logger.log(line)
                self.process_runner_adj(row)

            # Process lineup adjustment
            # Note: used for teams batting out of order
            if row[0] == 'ladj':
                self.logger.log(line)
                self.process_lineup_adj(row)

        # Save last game in the team
        self.game.end(self.next_score,
                      self.config.output_path+f'/{self.game.date.year}eve',
                      save_state=self.save_state,
                      save_stats=self.save_stats,
                      verify_stats_path=self.verify_path,
                      overwrite=self.overwrite)
