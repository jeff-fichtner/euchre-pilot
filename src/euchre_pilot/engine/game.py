"""Euchre game orchestrator — runs a full game using player interfaces."""

from __future__ import annotations

from typing import Protocol, Optional

from euchre_pilot.engine.cards import Card, Suit
from euchre_pilot.engine.deck import Deck, Deal
from euchre_pilot.engine.state import (
    Seat, GamePhase, GameState, HandState, TrickState, BidAction,
)
from euchre_pilot.engine.rules import EuchreRules


class Player(Protocol):
    """Interface that any player implementation must satisfy."""

    def bid_round_1(self, seat: Seat, hand: list[Card], turned_up: Card,
                     dealer: Seat, bids_so_far: list[BidAction]) -> BidAction:
        """Decide whether to order up the turned card or pass."""
        ...

    def bid_round_2(self, seat: Seat, hand: list[Card], turned_up_suit: Suit,
                     dealer: Seat, bids_so_far: list[BidAction]) -> BidAction:
        """Name trump or pass (cannot name the turned-up suit)."""
        ...

    def discard(self, seat: Seat, hand: list[Card], turned_up: Card, trump: Suit) -> Card:
        """Dealer picks up turned card and discards one (6 cards -> 5)."""
        ...

    def play_card(self, seat: Seat, hand: list[Card], trick: TrickState,
                   hand_state: HandState) -> Card:
        """Choose a card to play."""
        ...


class EuchreGame:
    """Runs a complete Euchre game to the winning score."""

    def __init__(
        self,
        players: dict[Seat, Player],
        winning_score: int = 10,
        seed: int | None = None,
    ) -> None:
        self.players = players
        self.deck = Deck(seed=seed)
        self.state = GameState(winning_score=winning_score)
        self.rules = EuchreRules()

    def play_game(self) -> GameState:
        """Play a full game and return the final state."""
        while not self.state.is_game_over:
            hand_state = self._play_hand()
            points = self.rules.score_hand(hand_state)
            self.state.score[0] += points[0]
            self.state.score[1] += points[1]
            self.state.hand_history.append(hand_state)
            self.state.dealer_seat = self.state.next_dealer()

        return self.state

    def _play_hand(self) -> HandState:
        """Play a single hand (bidding + 5 tricks)."""
        deal = self.deck.deal(self.state.dealer_seat.value)

        hand_state = HandState(
            dealer=self.state.dealer_seat,
            hands={seat: list(deal.hands[seat.value]) for seat in Seat},
            turned_up=deal.turned_up,
        )
        self.state.current_hand = hand_state

        # Bidding
        trump_called = self._run_bidding(hand_state, deal)
        if not trump_called:
            # Stuck dealer — dealer must call in round 2
            # This is handled in _run_bidding by forcing dealer to call
            pass

        assert hand_state.trump is not None, "Trump must be set after bidding"
        hand_state.phase = GamePhase.PLAYING

        # Play 5 tricks
        lead_seat = hand_state.dealer.left
        for _trick_num in range(5):
            trick = self._play_trick(hand_state, lead_seat)
            hand_state.tricks.append(trick)
            lead_seat = trick.winner  # type: ignore[assignment]

        hand_state.phase = GamePhase.HAND_OVER
        return hand_state

    def _run_bidding(self, hand_state: HandState, deal: Deal) -> bool:
        """Run both bidding rounds. Returns True if trump was called."""
        dealer = hand_state.dealer
        turned_up = deal.turned_up
        assert turned_up is not None

        # Round 1: decide on the turned-up card
        hand_state.phase = GamePhase.BID_ROUND_1
        seat = dealer.left
        for _ in range(4):
            player = self.players[seat]
            bid = player.bid_round_1(
                seat, hand_state.hands[seat], turned_up, dealer, hand_state.bids,
            )
            hand_state.bids.append(bid)

            if bid.action in ("order_up", "alone"):
                hand_state.trump = turned_up.suit
                hand_state.caller = seat
                hand_state.going_alone = bid.action == "alone"
                if hand_state.going_alone:
                    hand_state.alone_seat = seat

                # Dealer picks up the turned-up card and discards
                self._dealer_pickup(hand_state, deal)
                return True

            seat = seat.left

        # Round 2: name any suit except the turned-up suit
        hand_state.phase = GamePhase.BID_ROUND_2
        seat = dealer.left
        for i in range(4):
            player = self.players[seat]
            is_stuck_dealer = (seat == dealer) and (i == 3)

            bid = player.bid_round_2(
                seat, hand_state.hands[seat], turned_up.suit, dealer, hand_state.bids,
            )
            hand_state.bids.append(bid)

            if bid.action in ("call", "alone") and bid.suit is not None:
                hand_state.trump = bid.suit
                hand_state.caller = seat
                hand_state.going_alone = bid.action == "alone"
                if hand_state.going_alone:
                    hand_state.alone_seat = seat
                return True

            if is_stuck_dealer and bid.action == "pass":
                # Stuck dealer: force a call. Pick the best suit.
                best_suit = self._pick_best_suit(hand_state.hands[seat], turned_up.suit)
                hand_state.trump = best_suit
                hand_state.caller = seat
                return True

            seat = seat.left

        return False

    def _dealer_pickup(self, hand_state: HandState, deal: Deal) -> None:
        """Dealer picks up the turned-up card and discards one."""
        hand_state.phase = GamePhase.DEALER_DISCARD
        dealer = hand_state.dealer
        turned_up = deal.turned_up

        # Add turned-up card to dealer's hand
        hand_state.hands[dealer].append(turned_up)

        # Dealer chooses a discard
        player = self.players[dealer]
        assert hand_state.trump is not None
        discard = player.discard(
            dealer, hand_state.hands[dealer], turned_up, hand_state.trump,
        )

        hand_state.hands[dealer].remove(discard)

    def _play_trick(self, hand_state: HandState, lead_seat: Seat) -> TrickState:
        """Play a single trick."""
        assert hand_state.trump is not None
        num_players = 3 if hand_state.going_alone else 4
        trick = TrickState(lead_seat=lead_seat, num_players=num_players)

        seat = lead_seat
        for _ in range(4):
            # Skip partner of lone player
            if hand_state.going_alone and seat == hand_state.alone_seat.partner:  # type: ignore
                seat = seat.left
                continue

            player = self.players[seat]
            card = player.play_card(seat, hand_state.hands[seat], trick, hand_state)

            # Validate play
            valid = self.rules.valid_plays(hand_state.hands[seat], trick, hand_state.trump)
            assert card in valid, f"{seat} played {card} but valid plays are {valid}"

            trick.cards_played.append((seat, card))
            hand_state.hands[seat].remove(card)
            seat = seat.left

        trick.winner = self.rules.trick_winner(trick, hand_state.trump)
        return trick

    @staticmethod
    def _pick_best_suit(hand: list[Card], excluded: Suit) -> Suit:
        """For stuck dealer — pick the suit with the most cards (excluding turned-up suit)."""
        from collections import Counter
        suit_counts = Counter(c.suit for c in hand if c.suit != excluded)
        if suit_counts:
            return suit_counts.most_common(1)[0][0]
        # Fallback: any suit not excluded
        from euchre_pilot.engine.cards import Suit as S
        for s in S:
            if s != excluded:
                return s
        raise RuntimeError("No valid suit to call")
