"""Game event logger — records every decision and outcome during play."""

from __future__ import annotations

import logging
from typing import Optional

from euchre_pilot.engine.cards import Card
from euchre_pilot.engine.state import Seat, HandState, TrickState, GameState
from euchre_pilot.engine.rules import EuchreRules
from euchre_pilot.recorder.database import GameDatabase

logger = logging.getLogger(__name__)


class GameLogger:
    """Logs game events to the database in real time."""

    def __init__(self, db: GameDatabase, source: str = "engine") -> None:
        self.db = db
        self.source = source
        self._game_id: int | None = None
        self._hand_id: int | None = None
        self._hand_number: int = 0

    def start_game(self, metadata: dict | None = None) -> int:
        self._game_id = self.db.insert_game(source=self.source, metadata=metadata)
        self._hand_number = 0
        logger.info("Started game %d", self._game_id)
        return self._game_id

    def end_game(self, state: GameState) -> None:
        assert self._game_id is not None
        self.db.finish_game(self._game_id, state.score[0], state.score[1])
        logger.info("Game %d finished: %d-%d", self._game_id, state.score[0], state.score[1])

    def log_hand(self, hand_state: HandState) -> int:
        """Log a completed hand with all its data."""
        assert self._game_id is not None
        self._hand_number += 1

        # Compute scoring
        points = EuchreRules.score_hand(hand_state)
        tricks = hand_state.tricks_won
        caller_team = hand_state.caller.team if hand_state.caller else 0
        was_euchred = tricks[caller_team] < 3

        # Serialize initial hands (we need to store them before cards are played)
        initial_hands = None  # Would need to be captured at deal time

        self._hand_id = self.db.insert_hand(
            game_id=self._game_id,
            hand_number=self._hand_number,
            dealer_seat=hand_state.dealer.value,
            trump_suit=hand_state.trump.value if hand_state.trump else None,
            caller_seat=hand_state.caller.value if hand_state.caller else None,
            going_alone=hand_state.going_alone,
            tricks_0=tricks[0],
            tricks_1=tricks[1],
            points_0=points[0],
            points_1=points[1],
            was_euchred=was_euchred,
            initial_hands=initial_hands,
            turned_up=str(hand_state.turned_up) if hand_state.turned_up else None,
        )

        # Log each trick
        for i, trick in enumerate(hand_state.tricks):
            if trick.winner is None:
                continue
            cards = [(seat.value, str(card)) for seat, card in trick.cards_played]
            self.db.insert_trick(
                hand_id=self._hand_id,
                trick_number=i + 1,
                lead_seat=trick.lead_seat.value,
                cards_played=cards,
                winner_seat=trick.winner.value,
            )

        # Log bid decisions
        for bid in hand_state.bids:
            self.db.insert_decision(
                hand_id=self._hand_id,
                trick_number=None,
                seat=bid.seat.value,
                decision_type="bid_r1" if bid.suit is None and bid.action != "call" else "bid_r2",
                chosen=bid.action + (f"_{bid.suit.value}" if bid.suit else ""),
            )

        return self._hand_id

    def log_decision(
        self,
        seat: Seat,
        decision_type: str,
        chosen: str,
        alternatives: list[str] | None = None,
        hand_held: list[str] | None = None,
        trick_number: int | None = None,
        context: dict | None = None,
    ) -> None:
        """Log a single decision point (for detailed analysis later)."""
        if self._hand_id is None:
            return

        self.db.insert_decision(
            hand_id=self._hand_id,
            trick_number=trick_number,
            seat=seat.value,
            decision_type=decision_type,
            chosen=chosen,
            alternatives=alternatives,
            hand_held=hand_held,
            context=context,
        )
