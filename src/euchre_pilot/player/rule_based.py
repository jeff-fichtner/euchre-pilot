"""Rule-based Euchre player implementing sound fundamental strategy.

Strategy principles:
- Bid when holding 3+ trump or 2 trump with a bower
- Lead trump to pull opponents' trump when you have strength
- Play high to win, low to lose — don't waste mid cards
- Second hand low, third hand high
- Track bowers and manage trump count
"""

from __future__ import annotations

from euchre_pilot.engine.cards import Card, Suit, Rank
from euchre_pilot.engine.state import Seat, BidAction, TrickState, HandState
from euchre_pilot.engine.rules import EuchreRules


class RuleBasedPlayer:
    """Competent rule-based Euchre player."""

    # Bidding thresholds
    BID_R1_THRESHOLD = 0.45       # Order up turned card
    BID_R1_ALONE_THRESHOLD = 0.80 # Go alone on turned card
    BID_R2_THRESHOLD = 0.40       # Call trump in round 2
    BID_R2_ALONE_THRESHOLD = 0.75 # Go alone calling trump

    def bid_round_1(self, seat: Seat, hand: list[Card], turned_up: Card,
                     dealer: Seat, bids_so_far: list[BidAction]) -> BidAction:
        trump = turned_up.suit
        strength = EuchreRules.hand_strength(hand, trump)

        # If we're the dealer, we get the turned-up card — factor that in
        if seat == dealer:
            hypothetical = list(hand) + [turned_up]
            # Remove the weakest non-trump card
            worst = self._weakest_card(hypothetical, trump)
            hypothetical.remove(worst)
            strength = EuchreRules.hand_strength(hypothetical, trump)

        # Partner is dealer — be slightly more aggressive ordering up
        if seat == dealer.partner:
            strength += 0.05

        if strength >= self.BID_R1_ALONE_THRESHOLD:
            return BidAction(seat=seat, action="alone")
        if strength >= self.BID_R1_THRESHOLD:
            return BidAction(seat=seat, action="order_up")
        return BidAction(seat=seat, action="pass")

    def bid_round_2(self, seat: Seat, hand: list[Card], turned_up_suit: Suit,
                     dealer: Seat, bids_so_far: list[BidAction]) -> BidAction:
        best_suit = None
        best_strength = 0.0

        for suit in Suit:
            if suit == turned_up_suit:
                continue
            s = EuchreRules.hand_strength(hand, suit)
            if s > best_strength:
                best_strength = s
                best_suit = suit

        if best_suit is None:
            return BidAction(seat=seat, action="pass")

        if best_strength >= self.BID_R2_ALONE_THRESHOLD:
            return BidAction(seat=seat, action="alone", suit=best_suit)
        if best_strength >= self.BID_R2_THRESHOLD:
            return BidAction(seat=seat, action="call", suit=best_suit)
        return BidAction(seat=seat, action="pass")

    def discard(self, seat: Seat, hand: list[Card], turned_up: Card, trump: Suit) -> Card:
        """Discard the weakest card after picking up the turned-up card."""
        return self._weakest_card(hand, trump)

    def play_card(self, seat: Seat, hand: list[Card], trick: TrickState,
                   hand_state: HandState) -> Card:
        assert hand_state.trump is not None
        trump = hand_state.trump
        valid = EuchreRules.valid_plays(hand, trick, trump)

        if len(valid) == 1:
            return valid[0]

        if not trick.cards_played:
            return self._lead_strategy(valid, hand_state)

        position = len(trick.cards_played)

        if position == 1:
            return self._second_hand_strategy(valid, trick, trump)
        elif position == 2:
            return self._third_hand_strategy(valid, trick, trump, seat)
        else:
            return self._fourth_hand_strategy(valid, trick, trump)

    # --- Leading ---

    def _lead_strategy(self, valid: list[Card], hand_state: HandState) -> Card:
        """Choose a lead card."""
        trump = hand_state.trump
        assert trump is not None

        trump_cards = sorted(
            [c for c in valid if c.effective_suit(trump) == trump],
            key=lambda c: c.trump_rank(trump),
            reverse=True,
        )
        off_cards = [c for c in valid if c.effective_suit(trump) != trump]

        # If we have strong trump, lead it to pull opponents' trump
        if trump_cards and trump_cards[0].trump_rank(trump) >= 6:
            return trump_cards[0]

        # Lead off-suit aces
        off_aces = [c for c in off_cards if c.rank == Rank.ACE]
        if off_aces:
            return off_aces[0]

        # Lead lowest off-suit card
        if off_cards:
            return min(off_cards, key=lambda c: c.rank.value)

        # All trump — lead lowest
        return trump_cards[-1] if trump_cards else valid[0]

    # --- Positional play ---

    def _second_hand_strategy(self, valid: list[Card], trick: TrickState,
                                trump: Suit) -> Card:
        """Second hand low — don't waste high cards early."""
        lead_card = trick.lead_card
        assert lead_card is not None

        # If we can't beat the lead, play lowest
        beaters = [c for c in valid if self._card_beats(c, lead_card, lead_card.effective_suit(trump), trump)]

        if not beaters:
            return min(valid, key=lambda c: c.rank.value)

        # Play lowest card that beats the lead
        return min(beaters, key=lambda c: (c.trump_rank(trump) if c.effective_suit(trump) == trump else c.rank.value))

    def _third_hand_strategy(self, valid: list[Card], trick: TrickState,
                               trump: Suit, seat: Seat) -> Card:
        """Third hand high — partner led, try to win it."""
        assert len(trick.cards_played) == 2
        lead_seat, lead_card = trick.cards_played[0]
        _, second_card = trick.cards_played[1]

        # Is partner currently winning?
        current_best = lead_card
        current_winner = lead_seat
        if self._card_beats(second_card, current_best, lead_card.effective_suit(trump), trump):
            current_best = second_card
            current_winner = trick.cards_played[1][0]

        partner_winning = current_winner.team == seat.team

        if partner_winning:
            # Don't waste a good card — play lowest
            return min(valid, key=lambda c: c.rank.value)

        # Try to win with the lowest winning card
        beaters = [c for c in valid if self._card_beats(c, current_best, lead_card.effective_suit(trump), trump)]
        if beaters:
            return min(beaters, key=lambda c: (c.trump_rank(trump) if c.effective_suit(trump) == trump else c.rank.value))

        # Can't win — play lowest
        return min(valid, key=lambda c: c.rank.value)

    def _fourth_hand_strategy(self, valid: list[Card], trick: TrickState,
                                trump: Suit) -> Card:
        """Last to play — win cheaply or dump."""
        lead_card = trick.lead_card
        assert lead_card is not None
        lead_suit = lead_card.effective_suit(trump)

        # Find current winner
        current_best = trick.cards_played[0][1]
        for _, card in trick.cards_played[1:]:
            if self._card_beats(card, current_best, lead_suit, trump):
                current_best = card

        # Check if partner is winning
        current_winner_idx = 0
        best = trick.cards_played[0][1]
        for i, (_, card) in enumerate(trick.cards_played):
            if i == 0:
                continue
            if self._card_beats(card, best, lead_suit, trump):
                best = card
                current_winner_idx = i

        partner_seats = {0, 2} if trick.cards_played[0][0].value % 2 == 0 else {1, 3}
        # Simplified: just check if we need to win
        beaters = [c for c in valid if self._card_beats(c, current_best, lead_suit, trump)]

        if beaters:
            # Win with the cheapest card
            return min(beaters, key=lambda c: (c.trump_rank(trump) if c.effective_suit(trump) == trump else c.rank.value))

        # Can't win — dump lowest
        return min(valid, key=lambda c: c.rank.value)

    # --- Helpers ---

    @staticmethod
    def _weakest_card(hand: list[Card], trump: Suit) -> Card:
        """Find the weakest card in hand (lowest non-trump, or lowest trump)."""
        non_trump = [c for c in hand if c.effective_suit(trump) != trump]
        if non_trump:
            return min(non_trump, key=lambda c: c.rank.value)
        return min(hand, key=lambda c: c.trump_rank(trump))

    @staticmethod
    def _card_beats(challenger: Card, current: Card, lead_suit: Suit, trump: Suit) -> bool:
        """Check if challenger beats current card given lead suit and trump."""
        c_eff = challenger.effective_suit(trump)
        b_eff = current.effective_suit(trump)

        if c_eff == trump and b_eff != trump:
            return True
        if c_eff != trump and b_eff == trump:
            return False
        if c_eff == trump and b_eff == trump:
            return challenger.trump_rank(trump) > current.trump_rank(trump)
        if c_eff == lead_suit and b_eff != lead_suit:
            return True
        if c_eff != lead_suit and b_eff == lead_suit:
            return False
        if c_eff == lead_suit and b_eff == lead_suit:
            return challenger.rank.value > current.rank.value
        return False
