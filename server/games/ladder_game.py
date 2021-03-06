import logging
import asyncio

import server.db as db
from server.abc.base_game import InitMode
from server.players import Player

logger = logging.getLogger(__name__)

from .game import Game, ValidityState

import operator
import config


class LadderGame(Game):
    """Class for 1v1 ladder game"""
    init_mode = InitMode.AUTO_LOBBY
    
    def __init__(self, id, *args, **kwargs):
        super(self.__class__, self).__init__(id, *args, **kwargs)

        self.max_players = 2

    def rate_game(self):
        if self.validity == ValidityState.VALID:
            new_ratings = self.compute_rating()
            self.persist_rating_change_stats(new_ratings, rating='ladder1v1')

    def is_winner(self, player: Player):
        return self.get_army_result(self.get_player_option(player.id, 'Army')) > 0

    def on_game_end(self):
        super().on_game_end()
        if self.validity != ValidityState.VALID:
            return
        asyncio.async(self._on_game_end())

    @asyncio.coroutine
    def _on_game_end(self):
        if self.is_draw:
            with (yield from db.db_pool) as conn:
                with (yield from conn.cursor()) as cursor:
                    yield from cursor.execute("UPDATE table_map_features SET num_draws = (num_draws +1) "
                                              "WHERE map_id = %s", (self.map_id, ))
            return

        # The highest league of any player in the game, and a flag indicating if all players are in
        # the same league.
        maxleague = max(iter(self.players), key=operator.itemgetter("league"))
        evenLeague = all(self.players, lambda p: p.league == self.players[0].league)

        with (yield from db.db_pool) as conn:
            with (yield from conn.cursor()) as cursor:
                for player in self.players:
                    if self.is_winner(player):
                        score_change = 1
                        if not evenLeague:
                            if player.league == maxleague:
                                score_change = 0.5
                            else:
                                score_change = 1.5
                    else:
                        score_change = -0.5
                        if not evenLeague:
                            if player.league == maxleague:
                                score_change = 1
                            else:
                                score_change = 0

                    yield from cursor.execute("UPDATE {} "
                                              "SET score = GREATEST(0, (score + %s))"
                                              "WHERE idUser = %s".format(config.LADDER_SEASON),
                                              (score_change, player.id))

                    yield from cursor.execute("SELECT league, score FROM {}"
                                              "WHERE `idUser` = %s".format(config.LADDER_SEASON),
                                              (player.id, ))

                    pleague, pscore = yield from cursor.fetchone()
                    # Minimum scores, by league, to move to next league
                    # But, but, these are defined in the database (threshold values)
                    #  Why are they hardcoded here?!
                    # This query shouldprobably be replaced with a trigger that makes sure to update
                    # league counters whenever an update happens.
                    # Alternatively, and perhaps preferably, we can just stop tracking leagues
                    # explicitly in the database: just store scores and infer leagues from it using
                    # thresholds defined in a league-defining table.
                    league_incr_min = {1: 50, 2: 75, 3: 100, 4: 150}
                    if pleague in league_incr_min and pscore > league_incr_min[pleague]:
                        pleague += 1
                        yield from cursor.execute("UPDATE {} SET league = %s, score = 0"
                                                  "WHERE `idUser` = %s".format(config.LADDER_SEASON),
                                                  (player.id, pleague))

                    yield from cursor.execute("SELECT name "
                                              "FROM `ladder_division` "
                                              "WHERE `league` = ? AND threshold >= ?"
                                              "ORDER BY threshold ASC LIMIT 1",
                                              (pleague, pscore))

                    player.division = yield from cursor.fetchone()

    @property
    def is_draw(self):
        for army in self.armies:
            for result in self._results[army]:
                if result[1] == 'draw':
                    return True
        return False

    def get_army_result(self, army):
        """
        The head-to-head matchup ranking uses only win/loss as a factor
        :param army:
        :return:
        """
        for result in self._results[army]:
            if result[1] == 'victory':
                return 1
        return 0


