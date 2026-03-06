"""Euchre rules — valid plays, trick evaluation, scoring."""

from __future__ import annotations

from euchre_pilot.engine.cards import Card, Suit, Rank
from euchre_pilot.engine.state import Seat, HandState, TrickState


class EuchreRules:
    """Stateless rules engine for Euchre."""

    @staticmethod
    def valid_plays(hand: list[Card], trick: TrickState, trump: Suit) -> list[Card]:
        """Determine which cards from hand are legal to play.

        Must follow the effective suit of the lead card if possible.
        If you can't follow suit, any card is valid.
        """
        if not trick.cards_played:
            # Leading — any card is valid
            return list(hand)

        lead_card = trick.lead_card
        assert lead_card is not None
        lead_suit = lead_card.effective_suit(trump)

        # Cards that match the lead suit (accounting for bowers)
        following = [c for c in hand if c.effective_suit(trump) == lead_suit]

        if following:
            return following
        return list(hand)

    @staticmethod
    def trick_winner(trick: TrickState, trump: Suit) -> Seat:
        """Determine who won a completed trick."""
        assert trick.is_complete, "Cannot evaluate incomplete trick"

        lead_suit = trick.cards_played[0][1].effective_suit(trump)
        best_seat = trick.cards_played[0][0]
        best_card = trick.cards_played[0][1]

        for seat, card in trick.cards_played[1:]:
            if _beats(card, best_card, lead_suit, trump):
                best_seat = seat
                best_card = card

        return best_seat

    @staticmethod
    def score_hand(hand_state: HandState) -> tuple[int, int]:
        """Score a completed hand. Returns (team_0_points, team_1_points).

        Scoring rules:
        - Calling team takes 3-4 tricks: 1 point
        - Calling team takes all 5 tricks (march): 2 points
        - Calling team is euchred (takes <3 tricks): defending team gets 2 points
        - Lone hand takes all 5: 4 points
        - Lone hand takes 3-4: 1 point
        - Lone hand is euchred: defending team gets 2 points (some play 4)
        """
        assert hand_state.is_complete, "Cannot score incomplete hand"
        assert hand_state.caller is not None

        calling_team = hand_state.caller.team
        defending_team = 1 - calling_team
        tricks = hand_state.tricks_won

        calling_tricks = tricks[calling_team]

        if calling_tricks == 5:
            # March
            if hand_state.going_alone:
                return (4, 0) if calling_team == 0 else (0, 4)
            return (2, 0) if calling_team == 0 else (0, 2)
        elif calling_tricks >= 3:
            # Made it
            return (1, 0) if calling_team == 0 else (0, 1)
        else:
            # Euchred
            return (2, 0) if defending_team == 0 else (0, 2)

    @staticmethod
    def count_trump(hand: list[Card], trump: Suit) -> int:
        """Count trump cards in a hand (including left bower)."""
        return sum(1 for c in hand if c.effective_suit(trump) == trump)

    @staticmethod
    def hand_strength(hand: list[Card], trump: Suit) -> float:
        """Estimate hand strength on a 0-1 scale for bidding decisions.

        Factors: number of trump, presence of bowers, off-suit aces.
        This is a heuristic, not a perfect evaluation.
        """
        score = 0.0

        trump_cards = [c for c in hand if c.effective_suit(trump) == trump]
        off_cards = [c for c in hand if c.effective_suit(trump) != trump]

        # Trump count value
        score += len(trump_cards) * 0.12

        # Bower bonuses
        for c in trump_cards:
            if c.is_right_bower(trump):
                score += 0.20
            elif c.is_left_bower(trump):
                score += 0.15
            elif c.rank == Rank.ACE:
                score += 0.08
            elif c.rank == Rank.KING:
                score += 0.04

        # Off-suit aces
        for c in off_cards:
            if c.rank == Rank.ACE:
                score += 0.10

        # Void suits (useful for trumping)
        suits_held = {c.effective_suit(trump) for c in hand}
        non_trump_suits = {s for s in Suit if s != trump}
        voids = non_trump_suits - suits_held
        score += len(voids) * 0.05

        return min(score, 1.0)


def _beats(challenger: Card, current_best: Card, lead_suit: Suit, trump: Suit) -> bool:
    """Does the challenger card beat the current best card?"""
    challenger_eff = challenger.effective_suit(trump)
    best_eff = current_best.effective_suit(trump)

    # Trump beats non-trump
    if challenger_eff == trump and best_eff != trump:
        return True
    if challenger_eff != trump and best_eff == trump:
        return False

    # Both trump — compare trump rank
    if challenger_eff == trump and best_eff == trump:
        return challenger.trump_rank(trump) > current_best.trump_rank(trump)

    # Neither trump — must follow lead suit to win
    if challenger_eff == lead_suit and best_eff != lead_suit:
        return True
    if challenger_eff != lead_suit and best_eff == lead_suit:
        return False
    if challenger_eff == lead_suit and best_eff == lead_suit:
        return challenger.rank.value > current_best.rank.value

    # Off-suit, non-trump, doesn't match lead — can't beat
    return False
