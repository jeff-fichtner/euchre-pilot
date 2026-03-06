"""Deck management — shuffling, dealing, kitty."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from euchre_pilot.engine.cards import Card, euchre_deck


@dataclass
class Deal:
    """Result of dealing a Euchre hand."""
    hands: list[list[Card]]  # 4 hands of 5 cards each, indexed by seat (0=south, 1=west, 2=north, 3=east)
    kitty: list[Card]        # 4 remaining cards, first is turned up
    dealer_seat: int         # 0-3

    @property
    def turned_up(self) -> Card:
        return self.kitty[0]


class Deck:
    """Shuffleable Euchre deck with standard dealing."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def deal(self, dealer_seat: int) -> Deal:
        """Deal a Euchre hand following standard dealing order.

        Deals 3-2-3-2 then 2-3-2-3 (or vice versa) starting left of dealer.
        """
        cards = euchre_deck()
        self._rng.shuffle(cards)

        hands: list[list[Card]] = [[] for _ in range(4)]
        idx = 0

        # First round: 3-2-3-2 starting left of dealer
        first_round = [3, 2, 3, 2]
        for i in range(4):
            seat = (dealer_seat + 1 + i) % 4
            count = first_round[i]
            hands[seat] = cards[idx:idx + count]
            idx += count

        # Second round: 2-3-2-3
        second_round = [2, 3, 2, 3]
        for i in range(4):
            seat = (dealer_seat + 1 + i) % 4
            count = second_round[i]
            hands[seat].extend(cards[idx:idx + count])
            idx += count

        kitty = cards[idx:]
        return Deal(hands=hands, kitty=kitty, dealer_seat=dealer_seat)
