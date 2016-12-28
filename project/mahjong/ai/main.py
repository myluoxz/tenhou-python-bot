# -*- coding: utf-8 -*-
from mahjong.ai.agari import Agari
from mahjong.ai.base import BaseAI
from mahjong.ai.defence import Defence
from mahjong.ai.shanten import Shanten
from mahjong.ai.strategies.honitsu import HonitsuStrategy
from mahjong.ai.strategies.main import BaseStrategy
from mahjong.ai.strategies.tanyao import TanyaoStrategy
from mahjong.ai.strategies.yakuhai import YakuhaiStrategy
from mahjong.constants import HAKU, CHUN, HATSU
from mahjong.hand import HandDivider
from mahjong.meld import Meld
from mahjong.tile import TilesConverter
from mahjong.utils import is_pin, is_honor, is_chi, is_pon, is_man


class MainAI(BaseAI):
    version = '0.1.0'

    agari = None
    shanten = None
    defence = None
    hand_divider = None
    previous_shanten = 7

    current_strategy = None

    def __init__(self, table, player):
        super(MainAI, self).__init__(table, player)

        self.agari = Agari()
        self.shanten = Shanten()
        self.defence = Defence(table)
        self.hand_divider = HandDivider()
        self.previous_shanten = 7
        self.current_strategy = None

    def erase_state(self):
        self.current_strategy = None

    def discard_tile(self):
        results, shanten = self.calculate_outs(self.player.tiles, self.player.closed_hand)
        self.previous_shanten = shanten

        if shanten == 0:
            self.player.in_tempai = True

        # we are win!
        if shanten == Shanten.AGARI_STATE:
            return Shanten.AGARI_STATE

        # Disable defence for now
        # if self.defence.go_to_defence_mode():
        #     self.player.in_tempai = False
        #     tile_in_hand = self.defence.calculate_safe_tile_against_riichi()
        #     if we wasn't able to find a safe tile, let's discard a random one
        #     if not tile_in_hand:
        #         tile_in_hand = self.player.tiles[random.randrange(len(self.player.tiles) - 1)]
        # else:
        #     tile34 = results[0]['discard']
        #     tile_in_hand = TilesConverter.find_34_tile_in_136_array(tile34, self.player.tiles)

        # we are in agari state, but we can't win because we don't have yaku
        # in that case let's do tsumogiri
        if not results:
            return self.player.last_draw
        else:
            tile34 = results[0]['discard']
            tile_in_hand = TilesConverter.find_34_tile_in_136_array(tile34, self.player.tiles)

            return tile_in_hand

    def calculate_outs(self, tiles, closed_hand):
        """
        :param tiles: array of tiles in 136 format
        :param closed_hand: array of tiles in 136 format
        :return:
        """
        tiles_34 = TilesConverter.to_34_array(tiles)
        closed_tiles_34 = TilesConverter.to_34_array(closed_hand)
        shanten = self.shanten.calculate_shanten(tiles_34, self.player.is_open_hand)

        # win
        if shanten == Shanten.AGARI_STATE:
            return [], shanten

        raw_data = {}
        for i in range(0, 34):
            if not tiles_34[i]:
                continue

            if not closed_tiles_34[i]:
                continue

            # let's keep valued pair of tiles for later game
            if closed_tiles_34[i] >= 2 and i in self.valued_honors:
                continue

            tiles_34[i] -= 1

            raw_data[i] = []
            for j in range(0, 34):
                if i == j or tiles_34[j] >= 4:
                    continue

                tiles_34[j] += 1
                if self.shanten.calculate_shanten(tiles_34, self.player.is_open_hand) == shanten - 1:
                    raw_data[i].append(j)
                tiles_34[j] -= 1

            tiles_34[i] += 1

            if raw_data[i]:
                raw_data[i] = {
                    'tile': i,
                    'tiles_count': self.count_tiles(raw_data[i], tiles_34),
                    'waiting': raw_data[i]
                }

        # in honitsu mode we should discard tiles from other suit, even if it is better to save them
        if self.current_strategy and self.current_strategy.type == BaseStrategy.HONITSU:
            for i in range(0, 34):
                if not tiles_34[i]:
                    continue

                if not closed_tiles_34[i]:
                    continue

                if not self.current_strategy.is_tile_suitable(i * 4):
                    raw_data[i] = {
                        'tile': i,
                        'tiles_count': 1,
                        'waiting': []
                    }

        results = []
        tiles_34 = TilesConverter.to_34_array(self.player.tiles)
        for tile in range(0, len(tiles_34)):
            if tile in raw_data and raw_data[tile] and raw_data[tile]['tiles_count']:
                item = raw_data[tile]

                waiting = []

                for item2 in item['waiting']:
                    waiting.append(item2)

                results.append({
                    'discard': item['tile'],
                    'waiting': waiting,
                    'tiles_count': item['tiles_count']
                })

        # if we have character and honor candidates to discard with same tiles count,
        # we need to discard honor tile first
        results = sorted(results, key=lambda x: (x['tiles_count'], x['discard']), reverse=True)

        # in honitsu mode we should discard tiles from other suit, even if it is better to save them
        if self.current_strategy and self.current_strategy.type == BaseStrategy.HONITSU:
            results = sorted(results, key=lambda x: self.current_strategy.is_tile_suitable(x['discard'] * 4), reverse=False)

        return results, shanten

    def count_tiles(self, raw_data, tiles):
        n = 0
        for i in range(0, len(raw_data)):
            n += 4 - tiles[raw_data[i]]
        return n

    def try_to_call_meld(self, tile, enemy_seat):
        if not self.current_strategy:
            return None, None

        return self.current_strategy.try_to_call_meld(tile, enemy_seat)

    def determine_strategy(self):
        if self.current_strategy:
            return False

        # order is important
        strategies = [
            YakuhaiStrategy(BaseStrategy.YAKUHAI, self.player),
            HonitsuStrategy(BaseStrategy.HONITSU, self.player),
            TanyaoStrategy(BaseStrategy.TANYAO, self.player),
        ]

        for strategy in strategies:
            if strategy.should_activate_strategy():
                self.current_strategy = strategy

        return self.current_strategy and True or False

    @property
    def valued_honors(self):
        return [CHUN, HAKU, HATSU, self.player.table.round_wind, self.player.player_wind]
