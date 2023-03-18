# This file defines the game processor object.

# External imports
import datetime
import numpy as np
import pandas as pd
import re
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

    def __init__(self, config):
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
        """
        # Player features
        self.batting_feats = batting_feats
        self.pitching_feats = pitching_feats
        # Output path to save featurized games
        self.featpath = featpath
        """
        # Create logger
        """
        self.logpath = logpath
        """
        self.logger = None
        """
        # Path to historical player stats
        self.statpath = statpath
        """
        # Boolean to control batting order check
        # We want to verify batting order under normal circumstances
        # however when teams bat out of order we need to be able to
        # bipass the check.
        self.ignore_bat_order = False


    def process_new_game(self, row):
        assert(row[0] == 'id')

        # If we already have a game that has been processed,
        # save it to disk before starting the new game.
        if self.game:
            # Save game
            self.game.add_result(self.next_score)
            self.game.save(self.config.output_path+f'/{self.game.date.year}eve')

        # Start new game
        self.game = GameState(row[1][:-1]) # game id
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
        name = row[2]
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


    def process_substitutions(self, row):
        assert(self.game)
        assert(row[0] == 'sub')

        # Unpack row
        pid = row[1]
        name = row[2]
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
            # Log
            self.logger.log('---------------------------------------------------')
            old_pos = Player.positions[temp_pos] if temp_pos else temp_pos
            new_pos = Player.positions[fld_pos]
            self.logger.log(f'Switch {old_player.name} from {old_pos} to {new_pos}')
            self.game.checkpoint()
            return

        # Handle case where the pitcher takes the DH spot
        # Note: we don't vacate the pitching position yet
        if (pid == self.game.teams[team].pitcher and
            old_player.position == 10):
            # Add the pitcher in the DH's place in the lineup.
            self.game.teams[team].lineup[bat_pos] = pid
            # Remove the DH's position
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

        # Handle pitching substitution
        if new_player.position == 1:
            new_player.pitching = PitchingStats(self.game.id,
                                                pid,
                                                self.config.pitching_feats,
                                                self.config.pitching_intervals)
            self.game.teams[team].pitcher = new_player.id

        # Log
        npos_str = Player.positions[new_player.position]
        opos_str = Player.positions[old_pos] if old_pos else '-'
        self.logger.log('---------------------------------------------------')
        self.logger.log(f'Substitute {npos_str} {new_player.name} for {opos_str} {old_player.name}')
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
    def advance_runners(self, runners):
        # Sort runner advancements in descending order
        runner_order = {'B': 0, '1': 1, '2': 2, '3': 3}
        runners.sort(key=lambda r: runner_order[r[0]], reverse=True)

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
                print(runner)
                assert(False)

            strt = False if runner[0] == 'B' else int(runner[0])
            fnsh = False if runner[2] == 'H' else int(runner[2])


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
            if is_out:
                self.next_outs += 1 # Out
                # End of the inning so we don't care anymore
                # about base path advancements.
                if self.next_outs == 3:
                    break

            if strt:
                # check we have a runner at the starting base
                if not self.next_runners[strt-1]:
                    self.logger.log('---------------------------------------------------')
                    self.logger.log(f'Expected a runner at {strt} but got {self.next_runners}.')
                    assert(False)
                self.next_runners[strt-1] = False

            if not is_out and fnsh:
                # check we don't already have a runner at the finishing base
                if self.next_runners[fnsh-1]:
                    self.logger.log('---------------------------------------------------')
                    self.logger.log(f'Expected no runner at {fnsh} but got {self.next_runners}.')
                    assert(False)
                self.next_runners[fnsh-1] = True
            elif not is_out:
                assert(runner[2] == 'H')
                self.next_score[self.game.is_bot] += 1 # Scored

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
            # Check for explicit advancement
            # Ex: SB2.1-3(WP)
            # Note: we skip the batter advancement here because stealing first
            #       is handled differently.
            if any([strt_base == int(a[0])-1 for a in adv if a[0] != 'B']):
                continue
            # Else, add implicit advancement
            adv.append(str(strt_base+1)+'-'+stl[2])

    # Get number of pitches thrown for a given pitch string.
    def get_pitches_thrown(self, pstr):
        # Set of pitch codes for pitches thrown
        pitch_set = set(['B', 'C', 'F', 'I', 'K', 'L', 'M', 'O',
                         'P', 'Q', 'R', 'S', 'T', 'U', 'X', 'Y'])
        n = 0
        for p in pstr:
            if p in pitch_set:
                n += 1
        return n


    def process_single_fielder(self, play, adv):
        # Check if an error allowed the runner to
        # reach base
        if 'E' in play:
            self.add_implicit_adv(1, adv)
        else:
            self.next_outs += 1
        self.next_bpos = (self.next_bpos+1)%9

    def process_putout(self, play, adv):
        self.next_outs += 1
        self.next_bpos = (self.next_bpos+1)%9

    def process_force_out(self, play, adv):
        self.next_outs += 1
        self.next_bpos = (self.next_bpos+1)%9
        # Remove the runner who was forced out from the basepaths
        # Ex pattern: 54(1), number in parenthesis should be [1-3]
        base = int(play[play.find('(')+1])-1
        assert(self.next_runners[base])
        self.next_runners[base] = False
        # Add implicit batter advancement if one is not given explicitly
        if not any([a[0] == 'B' for a in adv]):
            self.add_implicit_adv(1, adv)

    def process_dbl_ply(self, play, adv):
        # Update next outs and next batter
        self.next_outs += 2
        self.next_bpos = (self.next_bpos+1)%9
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
        # If the batter isn't retired in the double play then it needs
        # to be added to the advancements
        if len(bases) == 2 and not 'B' in bases:
            if not any([a[0] == 'B' for a in adv]):
                self.add_implicit_adv(1, adv)

    def process_trpl_ply(self, play, adv):
        self.next_outs += 3
        self.next_bpos = (self.next_bpos+1)%9
        bases = []
        for idx in range(1, len(play)):
            if play[idx-1] == '(':
                if play[idx] != 'B':
                    bases.append(int(play[idx])-1)
        for b in bases:
            assert(self.next_runners[b])
            self.next_runners[b] = False

    def process_intrfrnc(self, play, adv):
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_single(self, play, adv):
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_double(self, play, adv):
        self.add_implicit_adv(2, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_triple(self, play, adv):
        self.add_implicit_adv(3, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_gr_double(self, play, adv):
        self.add_implicit_adv(2, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_error(self, play, adv):
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_fielders_ch(self, play, adv):
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_foul_fly_error(self, play, adv):
        pass

    def process_homerun(self, play, adv):
        # Account for batter scoring
        # Any baserunners will be accounted for in runner advancement
        if all([a[0] != 'B' for a in adv]):
            self.next_score[self.game.is_bot] += 1
        self.next_bpos = (self.next_bpos+1)%9

    def process_hbp(self, play, adv):
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9

    def process_k(self, play, adv):
        play_str = 'Strikeout'
        self.next_bpos = (self.next_bpos+1)%9
        """
        # Remove a batter getting out on basepaths after a strikeout
        # It is redundant because we already acount for the out here.
        #
        # Alternatively, if a batter reaches base after striking out
        # don't count their out or remove them from the base runner
        # advancements list.
        is_out = True
        elem = ''
        for i, r in enumerate(adv):
            if r[0] == 'B':
                is_out = (r[1] == 'X')
                elem = r
                break
        if is_out:
            self.next_outs += 1
            if elem:
                adv.remove(elem)
        """
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
                self.process_stln_base(kevt, adv)
            elif Processor.caught_stln_ptrn.match(kevt):
                play_str += ' w/ Caught Stealing'
                self.process_caught_stln(kevt, adv)
            elif Processor.other_adv_ptrn.match(kevt):
                play_str += 'w/ Other Advancement'
            elif Processor.pickoff_ptrn.match(kevt):
                play_str += 'w/ Pickoff'
                self.process_pickoff(kevt, adv)
            elif Processor.pickoff_off_ptrn.match(kevt):
                play_str += 'w/ Pickoff Off base'
                self.process_pickoff_off(kevt, adv)
            elif Processor.past_ball_ptrn.match(kevt):
                play_str += 'w/ Pass Ball'
            elif Processor.wild_pitch_ptrn.match(kevt):
                play_str += 'w/ Wild Pitch'
            elif Processor.error_ptrn.match(kevt):
                play_str += 'w/ Error'
            elif Processor.def_indiff_ptrn.match(kevt):
                play_str += 'w/ Defense Indifference'
            else:
                self.logger.log(f'Unrecognized event following strikeout: {kevt}')
                assert(False)
        return play_str

    def process_walk(self, play, adv):
        play_str = 'Walk'
        self.add_implicit_adv(1, adv)
        self.next_bpos = (self.next_bpos+1)%9
        # Handle event after walk
        if Processor.walk_w_event_ptrn.match(play):
            wevt = play[play.find('+')+1:]
            if Processor.stln_base_ptrn.match(wevt):
                play_str += 'w/ Stolen Base'
                self.process_stln_base(wevt, adv)
            elif Processor.caught_stln_ptrn.match(wevt):
                play_str += 'w/ Caught Stealing'
                self.process_caught_stln(wevt, adv)
            elif Processor.pickoff_ptrn.match(wevt):
                play_str += 'w/ Pickoff'
                self.process_pickoff(wevt, adv)
            elif Processor.pickoff_off_ptrn.match(wevt):
                play_str += 'w/ Pickoff Off Base'
                self.process_pickoff_off(wevt, adv)
            elif Processor.past_ball_ptrn.match(wevt):
                play_str += 'w/ Passed Ball'
            elif Processor.wild_pitch_ptrn.match(wevt):
                play_str += 'w/ Wild Pitch'
            elif Processor.error_ptrn.match(wevt):
                play_str += 'w/ Error'
            elif Processor.def_indiff_ptrn.match(wevt):
                play_str += 'w/ Defense Indifference'
            elif Processor.other_adv_ptrn.match(wevt):
                play_str += 'w/ Other Advancement'
            else:
                self.logger.log(f'Unrecognized event following strikeout: {wevt}')
                assert(False)
        return play_str

    def process_caught_stln(self, play, adv):
        base = int(play[2])-2 if play[2] in ('2', '3') else 2
        assert(self.game.runners[base])
        # If there was no error on the play then record the out
        # and remove the runner from the base paths.
        if not 'E' in play:
            self.next_runners[base] = False
            self.next_outs += 1
        # Else, if there was an error but no explicit advancement was
        # given, then add an implicit one.
        elif all([int(a[0]) != base+1 for a in adv if a[0] != 'B']):
            next_base = str(base+2) if base+1 != 3 else 'H'
            adv.append(f'{base+1}-'+next_base)
            adv.sort(reverse=True, key=lambda a: int(a[0]))

    def process_pickoff(self, play, adv):
        if not 'E' in play:
            base = int(play[2])-1
            assert(self.game.runners[base])
            self.next_runners[base] = False
            self.next_outs += 1

    def process_pickoff_off(self, play, adv):
        base = int(play[4])-2 if play[4] in ('2', '3') else 2
        assert(self.game.runners[base])
        if not 'E' in play:
            self.next_runners[base] = False
            self.next_outs += 1
        else:
            # If an error occurs during the run down, then we need to add
            # an implicit advancement if an explicit one isn't given.
            if not any([a[0] == str(base+1) for a in adv]):
                adv.append(str(base+1) + '-' + play[4])

    def process_stln_base(self, play, adv):
        self.advance_stolen_bases(play, adv)

    def process_play(self, row):
        assert(self.game)
        assert(row[0] == 'play')

        # Unpack row
        inning = row[1]
        team = int(row[2])
        batter_id = row[3]
        count = row[4]
        pitches = row[5]
        event = row[6][:-1]

        # Update game state
        self.game.inning = inning
        self.game.is_bot = team
        self.game.outs = self.next_outs
        self.game.score = self.next_score[:]
        self.game.runners[:] = self.next_runners[:]
        self.game.batter = batter_id

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

        # ---------------------------------------------------------------------------
        # Process each event based on type
        # ---------------------------------------------------------------------------
        play_str = ''
        #
        # Single fielder out
        if Processor.single_fielder_ptrn.match(play):
            play_str = 'Out'
            self.process_single_fielder(play, adv)
        #
        # Force Out
        elif Processor.force_out_ptrn.match(play):
            play_str = 'Force Out'
            self.process_force_out(play, adv)
        #
        # Multi-Fielder Out or Put Out
        elif Processor.multi_fielder_ptrn.match(play) or Processor.putout_ptrn.match(play):
            play_str = 'Out'
            self.process_putout(play, adv)
        #
        # Double Play
        elif Processor.dbl_ply_ptrn.match(play):
            if 'GDP' in mods:
                play_str = 'Ground Ball Double Play'
            elif 'LDP' in mods:
                play_str = 'Line Out Double Play'
            else:
                play_str = 'Double Play'
            self.process_dbl_ply(play, adv)
        #
        # Triple Play
        elif Processor.trpl_ply_ptrn.match(play):
            if 'GTP' in mods:
                play_str = 'Ground Ball Triple Play'
            elif 'LTP' in mods:
                play_str = 'Line Out Triple Play'
            else:
                play_str = 'Triple Play'
            self.process_trpl_ply(play, adv)
        #
        # Catchers Interference
        elif Processor.intrfrnc_ptrn.match(play):
            play_str = 'Catcher Interference'
            self.process_intrfrnc(play, adv)
        #
        # Single
        elif Processor.single_ptrn.match(play):
            play_str = 'Single'
            self.process_single(play, adv)
        #
        # Double
        elif Processor.double_ptrn.match(play):
            play_str = 'Double'
            self.process_double(play, adv)
        #
        # Triple
        elif Processor.triple_ptrn.match(play):
            play_str = 'Triple'
            self.process_triple(play, adv)
        #
        # Ground Rule Double
        elif Processor.gr_double_ptrn.match(play):
            play_str = 'Ground Rule Double'
            self.process_gr_double(play, adv)
        #
        # Error
        elif Processor.error_ptrn.match(play):
            play_str = 'Error'
            self.process_error(play, adv)
        #
        # Fielder's Choice
        elif Processor.fielders_ch_ptrn.match(play):
            play_str = "Fielders Choice"
            self.process_fielders_ch(play, adv)
        #
        # Foul Fly Error
        elif Processor.foul_fly_error_ptrn.match(play):
            play_str = 'Error on Foul Fly'
            self.process_foul_fly_error(play, adv)
        #
        # Home run
        elif Processor.homerun_ptrn.match(play):
            play_str = 'Homerun'
            self.process_homerun(play, adv)
        #
        # Hit by pitch
        elif Processor.hbp_ptrn.match(play):
            play_str = 'Hit by Pitch'
            self.process_hbp(play, adv)
        #
        # Strikeout wo/ event
        # or
        # Strikeout w/ event
        elif Processor.k_no_event_ptrn.match(play) or Processor.k_w_event_ptrn.match(play):
            play_str = self.process_k(play, adv)
        #
        # No Play
        elif Processor.no_play_ptrn.match(play):
            play_str = 'No Play'
        #
        # Walk
        elif Processor.walk_ptrn.match(play) or Processor.walk_w_event_ptrn.match(play):
            play_str = self.process_walk(play, adv)
        #
        # Balk
        elif Processor.balk_ptrn.match(play):
            play_str = 'Balk'
        #
        # Caught Stealing
        elif Processor.caught_stln_ptrn.match(play):
            play_str = 'Caught Stealing'
            self.process_caught_stln(play, adv)
        #
        # Defensive indifference
        elif Processor.def_indiff_ptrn.match(play):
            play_str = 'Defensive Indifference'
        #
        # Other advancement
        elif Processor.other_adv_ptrn.match(play):
            play_str = 'Other Advancement'
        #
        # Passed ball
        elif Processor.past_ball_ptrn.match(play):
            play_str = 'Passed Ball'
        #
        # Wild pitch
        elif Processor.wild_pitch_ptrn.match(play):
            play_str = 'Wild Pitch'
        #
        # Picked off
        elif Processor.pickoff_ptrn.match(play):
            play_str = 'Pickoff'
            self.process_pickoff(play, adv)
        #
        # Picked off off base
        elif Processor.pickoff_off_ptrn.match(play):
            play_str = 'Picked Off, Off Base'
            self.process_pickoff_off(play, adv)
        #
        # Stolen base
        elif Processor.stln_base_ptrn.match(play):
            play_str = 'Stolen Base'
            self.process_stln_base(play, adv)
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
        if self.next_outs != 3:
            self.advance_runners(adv)

        # Print state
        self.logger.log('---------------------------------------------------')
        self.logger.log(self.game)
        self.logger.log(play_str)

        # Save game state
        self.game.checkpoint()

        # Update pitch count
        pitcher = self.game.teams[not self.game.is_bot].roster[self.game.teams[not self.game.is_bot].pitcher]
        pitcher.pcount += self.get_pitches_thrown(pitches)

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
        self.next_runners[base] = True
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
    # feature path provided at initialization time, self.featpath
    #
    # Input:
    #  - sznpath (string):  path to the retrosheets season directory
    #  - evtfile (string):  name of the team's event file in filepath.
    #                       ex. '2020SFN.EVN'
    #  - game_id (string):  specifies an individual game to be processed.
    #                       all games are processed if not specified.
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
                self.process_game_info(row)

            # Process starting lineup
            # row = ['start', player id, player name, team, batting pos, fielding pos]
            if row[0] == 'start':
                self.process_starting_lineup(row)

            # Process substitutions
            # row = ['sub', player id, name, team, batting pos, fielding pos]
            # Example:  ['sub', 'florw001', '"Wilmer Flores"', '1', '4', '11\n']
            if row[0] == 'sub':
                self.process_substitutions(row)

            # Process Play
            # Note: think about this as evolving the game from one state to the next
            #
            # row = ['play', inning, team at bat, batter id, count, pitches, event]
            # Example play: ['play', '9', '0', 'owinc001', '32', '.BTCBFBFX', 'T8/F89D+\n']
            if row[0] == 'play':
                self.process_play(row)

            # Process runner adjustment
            # Note: used for runners starting at 2nd base in extra innings
            if row[0] == 'radj':
                self.process_runner_adj(row)

            # Process lineup adjustment
            # Note: used for teams batting out of order
            if row[0] == 'ladj':
                self.process_lineup_adj(row)
