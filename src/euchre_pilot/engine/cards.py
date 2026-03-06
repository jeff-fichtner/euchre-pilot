"""Card primitives for Euchre — Suit, Rank, Card, and Euchre-specific ordering."""

from __future__ import annotations

from enum import Enum
from functools import total_ordering


class Suit(Enum):
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"

    @property
    def color(self) -> str:
        return "red" if self in (Suit.HEARTS, Suit.DIAMONDS) else "black"

    @property
    def complement(self) -> Suit:
        """The same-color suit (used for left bower determination)."""
        return {
            Suit.HEARTS: Suit.DIAMONDS,
            Suit.DIAMONDS: Suit.HEARTS,
            Suit.CLUBS: Suit.SPADES,
            Suit.SPADES: Suit.CLUBS,
        }[self]

    def __str__(self) -> str:
        return self.value


class Rank(Enum):
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Rank):
            return NotImplemented
        return self.value < other.value

    def __str__(self) -> str:
        names = {9: "9", 10: "10", 11: "J", 12: "Q", 13: "K", 14: "A"}
        return names[self.value]


@total_ordering
class Card:
    """A single playing card. Immutable and hashable."""

    __slots__ = ("rank", "suit")

    def __init__(self, rank: Rank, suit: Suit) -> None:
        object.__setattr__(self, "rank", rank)
        object.__setattr__(self, "suit", suit)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("Card is immutable")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        if self.suit == other.suit:
            return self.rank < other.rank
        return self.suit.value < other.suit.value

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))

    def __repr__(self) -> str:
        return f"Card({self.rank!s}{self.suit_symbol})"

    def __str__(self) -> str:
        return f"{self.rank!s}{self.suit_symbol}"

    @property
    def suit_symbol(self) -> str:
        symbols = {
            Suit.HEARTS: "\u2665",
            Suit.DIAMONDS: "\u2666",
            Suit.CLUBS: "\u2663",
            Suit.SPADES: "\u2660",
        }
        return symbols[self.suit]

    def effective_suit(self, trump: Suit) -> Suit:
        """A card's effective suit in the context of trump.

        The left bower (jack of the same-color suit) is treated as trump.
        """
        if self.rank == Rank.JACK and self.suit == trump.complement:
            return trump
        return self.suit

    def is_right_bower(self, trump: Suit) -> bool:
        return self.rank == Rank.JACK and self.suit == trump

    def is_left_bower(self, trump: Suit) -> bool:
        return self.rank == Rank.JACK and self.suit == trump.complement

    def is_bower(self, trump: Suit) -> bool:
        return self.is_right_bower(trump) or self.is_left_bower(trump)

    def trump_rank(self, trump: Suit) -> int:
        """Numeric rank for ordering trump cards. Higher is better.

        Right bower: 7, Left bower: 6, then A=5, K=4, Q=3, 10=2, 9=1.
        Returns 0 for non-trump cards.
        """
        if self.effective_suit(trump) != trump:
            return 0
        if self.is_right_bower(trump):
            return 7
        if self.is_left_bower(trump):
            return 6
        # A=5, K=4, Q=3, 10=2, 9=1
        return self.rank.value - 9

    @classmethod
    def from_str(cls, s: str) -> Card:
        """Parse a card from string like '9H', 'JC', 'AS', '10D'."""
        s = s.strip().upper()
        suit_map = {"H": Suit.HEARTS, "D": Suit.DIAMONDS, "C": Suit.CLUBS, "S": Suit.SPADES}
        rank_map = {"9": Rank.NINE, "10": Rank.TEN, "J": Rank.JACK, "Q": Rank.QUEEN,
                     "K": Rank.KING, "A": Rank.ACE}

        suit_char = s[-1]
        rank_str = s[:-1]

        if suit_char not in suit_map:
            raise ValueError(f"Unknown suit character: {suit_char!r} in {s!r}")
        if rank_str not in rank_map:
            raise ValueError(f"Unknown rank: {rank_str!r} in {s!r}")

        return cls(rank_map[rank_str], suit_map[suit_char])


def euchre_deck() -> list[Card]:
    """Return the standard 24-card Euchre deck."""
    return [Card(rank, suit) for suit in Suit for rank in Rank]
