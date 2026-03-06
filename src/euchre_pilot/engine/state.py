"""Game state representations for Euchre."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from euchre_pilot.engine.cards import Card, Suit


class Seat(Enum):
    """Seat positions at the table. Partners sit across from each other."""
    SOUTH = 0   # "You" — the human/agent seat
    WEST = 1
    NORTH = 2   # Partner of South
    EAST = 3

    @property
    def partner(self) -> Seat:
        return Seat((self.value + 2) % 4)

    @property
    def left(self) -> Seat:
        return Seat((self.value + 1) % 4)

    @property
    def right(self) -> Seat:
        return Seat((self.value + 3) % 4)

    @property
    def team(self) -> int:
        """Team 0 = South/North, Team 1 = West/East."""
        return self.value % 2


class GamePhase(Enum):
    DEALING = "dealing"
    BID_ROUND_1 = "bid_round_1"     # Deciding on turned-up card
    BID_ROUND_2 = "bid_round_2"     # Naming trump after all passed
    DEALER_DISCARD = "dealer_discard"  # Dealer picks up and discards
    PLAYING = "playing"
    HAND_OVER = "hand_over"
    GAME_OVER = "game_over"


@dataclass
class BidAction:
    """A bid decision."""
    seat: Seat
    action: str  # "order_up", "pass", "call", "alone"
    suit: Optional[Suit] = None  # Only set for "call" in round 2


@dataclass
class TrickState:
    """State of a single trick in progress or completed."""
    lead_seat: Seat
    cards_played: list[tuple[Seat, Card]] = field(default_factory=list)
    winner: Optional[Seat] = None
    num_players: int = 4  # 3 when someone goes alone

    @property
    def lead_card(self) -> Optional[Card]:
        if self.cards_played:
            return self.cards_played[0][1]
        return None

    @property
    def is_complete(self) -> bool:
        return len(self.cards_played) == self.num_players

    @property
    def next_to_play(self) -> Optional[Seat]:
        if self.is_complete:
            return None
        seat = self.lead_seat
        for _ in range(len(self.cards_played)):
            seat = seat.left
        return seat


@dataclass
class HandState:
    """State of a single hand (5 tricks, one trump call)."""
    dealer: Seat
    hands: dict[Seat, list[Card]]  # Current cards held by each player
    trump: Optional[Suit] = None
    caller: Optional[Seat] = None  # Who called trump
    going_alone: bool = False
    alone_seat: Optional[Seat] = None
    turned_up: Optional[Card] = None
    bids: list[BidAction] = field(default_factory=list)
    tricks: list[TrickState] = field(default_factory=list)
    phase: GamePhase = GamePhase.BID_ROUND_1

    @property
    def current_trick(self) -> Optional[TrickState]:
        if self.tricks and not self.tricks[-1].is_complete:
            return self.tricks[-1]
        return None

    @property
    def tricks_won(self) -> dict[int, int]:
        """Tricks won per team (team 0 and team 1)."""
        counts = {0: 0, 1: 0}
        for trick in self.tricks:
            if trick.winner is not None:
                counts[trick.winner.team] += 1
        return counts

    @property
    def is_complete(self) -> bool:
        return len(self.tricks) == 5 and all(t.is_complete for t in self.tricks)


@dataclass
class GameState:
    """Full game state — score, current hand, history."""
    score: list[int] = field(default_factory=lambda: [0, 0])  # Team 0, Team 1
    current_hand: Optional[HandState] = None
    hand_history: list[HandState] = field(default_factory=list)
    dealer_seat: Seat = Seat.SOUTH
    winning_score: int = 10

    @property
    def is_game_over(self) -> bool:
        return self.score[0] >= self.winning_score or self.score[1] >= self.winning_score

    @property
    def winner(self) -> Optional[int]:
        if self.score[0] >= self.winning_score:
            return 0
        if self.score[1] >= self.winning_score:
            return 1
        return None

    def next_dealer(self) -> Seat:
        return self.dealer_seat.left
