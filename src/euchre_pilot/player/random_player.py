"""Random player — picks legal moves at random. Useful as a baseline."""

from __future__ import annotations

import random

from euchre_pilot.engine.cards import Card, Suit
from euchre_pilot.engine.state import Seat, BidAction, TrickState, HandState
from euchre_pilot.engine.rules import EuchreRules


class RandomPlayer:
    """Plays randomly from legal options. Good for testing and baseline metrics."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def bid_round_1(self, seat: Seat, hand: list[Card], turned_up: Card,
                     dealer: Seat, bids_so_far: list[BidAction]) -> BidAction:
        if self._rng.random() < 0.3:
            return BidAction(seat=seat, action="order_up")
        return BidAction(seat=seat, action="pass")

    def bid_round_2(self, seat: Seat, hand: list[Card], turned_up_suit: Suit,
                     dealer: Seat, bids_so_far: list[BidAction]) -> BidAction:
        if self._rng.random() < 0.4:
            suits = [s for s in Suit if s != turned_up_suit]
            chosen = self._rng.choice(suits)
            return BidAction(seat=seat, action="call", suit=chosen)
        return BidAction(seat=seat, action="pass")

    def discard(self, seat: Seat, hand: list[Card], turned_up: Card, trump: Suit) -> Card:
        non_trump = [c for c in hand if c.effective_suit(trump) != trump]
        if non_trump:
            return min(non_trump, key=lambda c: c.rank.value)
        return min(hand, key=lambda c: c.trump_rank(trump))

    def play_card(self, seat: Seat, hand: list[Card], trick: TrickState,
                   hand_state: HandState) -> Card:
        assert hand_state.trump is not None
        valid = EuchreRules.valid_plays(hand, trick, hand_state.trump)
        return self._rng.choice(valid)
