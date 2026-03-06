"""Tests for the core Euchre engine."""

import pytest

from euchre_pilot.engine.cards import Card, Suit, Rank, euchre_deck
from euchre_pilot.engine.deck import Deck
from euchre_pilot.engine.state import Seat, GamePhase, TrickState
from euchre_pilot.engine.rules import EuchreRules
from euchre_pilot.engine.game import EuchreGame
from euchre_pilot.player import RuleBasedPlayer, RandomPlayer


class TestCard:
    def test_from_str(self):
        c = Card.from_str("JH")
        assert c.rank == Rank.JACK
        assert c.suit == Suit.HEARTS

    def test_from_str_10(self):
        c = Card.from_str("10S")
        assert c.rank == Rank.TEN
        assert c.suit == Suit.SPADES

    def test_right_bower(self):
        jh = Card(Rank.JACK, Suit.HEARTS)
        assert jh.is_right_bower(Suit.HEARTS)
        assert not jh.is_right_bower(Suit.DIAMONDS)

    def test_left_bower(self):
        jd = Card(Rank.JACK, Suit.DIAMONDS)
        assert jd.is_left_bower(Suit.HEARTS)
        assert not jd.is_left_bower(Suit.CLUBS)

    def test_effective_suit_left_bower(self):
        jd = Card(Rank.JACK, Suit.DIAMONDS)
        assert jd.effective_suit(Suit.HEARTS) == Suit.HEARTS
        assert jd.effective_suit(Suit.CLUBS) == Suit.DIAMONDS

    def test_trump_rank_ordering(self):
        trump = Suit.HEARTS
        right = Card(Rank.JACK, Suit.HEARTS)
        left = Card(Rank.JACK, Suit.DIAMONDS)
        ace = Card(Rank.ACE, Suit.HEARTS)
        nine = Card(Rank.NINE, Suit.HEARTS)

        assert right.trump_rank(trump) > left.trump_rank(trump)
        assert left.trump_rank(trump) > ace.trump_rank(trump)
        assert ace.trump_rank(trump) > nine.trump_rank(trump)

    def test_suit_complement(self):
        assert Suit.HEARTS.complement == Suit.DIAMONDS
        assert Suit.CLUBS.complement == Suit.SPADES

    def test_immutable(self):
        c = Card(Rank.ACE, Suit.SPADES)
        with pytest.raises(AttributeError):
            c.rank = Rank.KING  # type: ignore

    def test_euchre_deck_size(self):
        deck = euchre_deck()
        assert len(deck) == 24
        assert len(set(deck)) == 24


class TestDeck:
    def test_deal_produces_correct_sizes(self):
        deck = Deck(seed=42)
        deal = deck.deal(dealer_seat=0)
        assert all(len(h) == 5 for h in deal.hands)
        assert len(deal.kitty) == 4

    def test_deal_uses_all_cards(self):
        deck = Deck(seed=42)
        deal = deck.deal(dealer_seat=0)
        all_cards = []
        for h in deal.hands:
            all_cards.extend(h)
        all_cards.extend(deal.kitty)
        assert len(all_cards) == 24
        assert len(set(all_cards)) == 24

    def test_different_seeds_different_deals(self):
        d1 = Deck(seed=1).deal(0)
        d2 = Deck(seed=2).deal(0)
        assert d1.hands[0] != d2.hands[0]


class TestRules:
    def test_valid_plays_must_follow_suit(self):
        trump = Suit.HEARTS
        hand = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.NINE, Suit.HEARTS),
        ]
        trick = TrickState(lead_seat=Seat.WEST)
        trick.cards_played.append((Seat.WEST, Card(Rank.TEN, Suit.SPADES)))

        valid = EuchreRules.valid_plays(hand, trick, trump)
        assert Card(Rank.ACE, Suit.SPADES) in valid
        assert Card(Rank.KING, Suit.SPADES) in valid
        assert Card(Rank.NINE, Suit.HEARTS) not in valid

    def test_valid_plays_any_card_if_void(self):
        trump = Suit.HEARTS
        hand = [
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.NINE, Suit.HEARTS),
        ]
        trick = TrickState(lead_seat=Seat.WEST)
        trick.cards_played.append((Seat.WEST, Card(Rank.TEN, Suit.SPADES)))

        valid = EuchreRules.valid_plays(hand, trick, trump)
        assert len(valid) == 2

    def test_trick_winner_trump_beats_lead(self):
        trump = Suit.HEARTS
        trick = TrickState(lead_seat=Seat.SOUTH)
        trick.cards_played = [
            (Seat.SOUTH, Card(Rank.ACE, Suit.SPADES)),
            (Seat.WEST, Card(Rank.NINE, Suit.HEARTS)),
            (Seat.NORTH, Card(Rank.KING, Suit.SPADES)),
            (Seat.EAST, Card(Rank.TEN, Suit.SPADES)),
        ]
        winner = EuchreRules.trick_winner(trick, trump)
        assert winner == Seat.WEST

    def test_trick_winner_right_bower_wins(self):
        trump = Suit.HEARTS
        trick = TrickState(lead_seat=Seat.SOUTH)
        trick.cards_played = [
            (Seat.SOUTH, Card(Rank.ACE, Suit.HEARTS)),
            (Seat.WEST, Card(Rank.JACK, Suit.DIAMONDS)),  # Left bower
            (Seat.NORTH, Card(Rank.JACK, Suit.HEARTS)),   # Right bower
            (Seat.EAST, Card(Rank.KING, Suit.HEARTS)),
        ]
        winner = EuchreRules.trick_winner(trick, trump)
        assert winner == Seat.NORTH

    def test_hand_strength_strong_hand(self):
        trump = Suit.HEARTS
        hand = [
            Card(Rank.JACK, Suit.HEARTS),   # Right bower
            Card(Rank.JACK, Suit.DIAMONDS), # Left bower
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
        ]
        strength = EuchreRules.hand_strength(hand, trump)
        assert strength > 0.7

    def test_hand_strength_weak_hand(self):
        trump = Suit.HEARTS
        hand = [
            Card(Rank.NINE, Suit.SPADES),
            Card(Rank.TEN, Suit.CLUBS),
            Card(Rank.NINE, Suit.DIAMONDS),
            Card(Rank.TEN, Suit.DIAMONDS),
            Card(Rank.QUEEN, Suit.CLUBS),
        ]
        strength = EuchreRules.hand_strength(hand, trump)
        assert strength < 0.2


class TestFullGame:
    def test_game_completes(self):
        players = {seat: RuleBasedPlayer() for seat in Seat}
        game = EuchreGame(players=players, seed=42)
        state = game.play_game()
        assert state.is_game_over
        assert state.winner in (0, 1)
        assert max(state.score) >= 10

    def test_game_with_random_players(self):
        players = {seat: RandomPlayer(seed=seat.value) for seat in Seat}
        game = EuchreGame(players=players, seed=99)
        state = game.play_game()
        assert state.is_game_over

    def test_multiple_games_deterministic(self):
        players = {seat: RuleBasedPlayer() for seat in Seat}
        g1 = EuchreGame(players=players, seed=42).play_game()
        g2 = EuchreGame(players=players, seed=42).play_game()
        assert g1.score == g2.score
        assert len(g1.hand_history) == len(g2.hand_history)
