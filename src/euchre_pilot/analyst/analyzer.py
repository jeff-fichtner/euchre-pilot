"""Hand and game analyzer — uses LLM to evaluate play quality."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from pydantic import BaseModel

from euchre_pilot.analyst.llm import LLMClient
from euchre_pilot.analyst.prompts import (
    HAND_ANALYSIS_SYSTEM,
    HAND_ANALYSIS_TEMPLATE,
    PATTERN_ANALYSIS_TEMPLATE,
)
from euchre_pilot.recorder.database import GameDatabase

logger = logging.getLogger(__name__)


# --- Structured response models ---

class DecisionEval(BaseModel):
    """Evaluation of a single decision."""
    trick_number: int | None  # None for bids
    seat: int
    decision_type: str
    chosen: str
    optimal_choice: str
    was_correct: bool
    impact: str  # "high", "medium", "low"
    explanation: str


class HandAnalysisResult(BaseModel):
    """Complete analysis of a hand."""
    overall_assessment: str
    calling_decision_correct: bool
    decision_evaluations: list[DecisionEval]
    key_mistake: str | None  # The single biggest error, if any
    key_mistake_trick: int | None
    score_impact: str  # How the mistakes affected the score
    lessons: list[str]


class PatternAnalysisResult(BaseModel):
    """Analysis of patterns across multiple games."""
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    priority_fix: str  # Single most impactful change


# --- Analyzer ---

class HandAnalyzer:
    """Analyzes completed hands and games using an LLM."""

    def __init__(self, llm: LLMClient, db: GameDatabase) -> None:
        self.llm = llm
        self.db = db

    def analyze_hand(self, hand_id: int) -> HandAnalysisResult:
        """Analyze a single completed hand."""
        details = self.db.get_hand_details(hand_id)
        hand = details["hand"]
        tricks = details["tricks"]
        decisions = details["decisions"]

        # Format the hand for the prompt
        prompt = self._format_hand_prompt(hand, tricks, decisions)

        result = self.llm.structured(
            prompt=prompt,
            response_model=HandAnalysisResult,
            system=HAND_ANALYSIS_SYSTEM,
        )

        logger.info("Analyzed hand %d: %s", hand_id, "correct" if not result.key_mistake else result.key_mistake)
        return result

    def analyze_patterns(self, num_games: int = 50) -> PatternAnalysisResult:
        """Analyze patterns across recent games."""
        games = self.db.get_recent_games(limit=num_games)
        if not games:
            raise ValueError("No games to analyze")

        win_rate = self.db.get_win_rate(team=0)
        bid_stats = self.db.get_decision_stats("bid_r1")

        # Build aggregate stats
        prompt = PATTERN_ANALYSIS_TEMPLATE.format(
            num_games=len(games),
            win_rate=win_rate,
            euchre_rate=0.0,  # TODO: compute from hand data
            avg_tricks_calling=0.0,  # TODO: compute
            alone_success_rate=0.0,  # TODO: compute
            bidding_stats=json.dumps(bid_stats[:10], indent=2),
            common_mistakes="(To be populated from individual hand analyses)",
        )

        return self.llm.structured(
            prompt=prompt,
            response_model=PatternAnalysisResult,
            system=HAND_ANALYSIS_SYSTEM,
        )

    def _format_hand_prompt(self, hand: dict, tricks: list[dict], decisions: list[dict]) -> str:
        """Format hand data into the analysis prompt."""
        seat_names = {0: "South", 1: "West", 2: "North", 3: "East"}

        # Parse initial hands if available
        initial_hands_str = "Not recorded"
        if hand.get("initial_hands"):
            ih = json.loads(hand["initial_hands"])
            lines = []
            for seat_id, cards in ih.items():
                lines.append(f"  {seat_names.get(int(seat_id), seat_id)}: {', '.join(cards)}")
            initial_hands_str = "\n".join(lines)

        # Format bidding
        bid_lines = []
        for d in decisions:
            if d["decision_type"] in ("bid_r1", "bid_r2"):
                bid_lines.append(f"  {seat_names.get(d['seat'], '?')}: {d['chosen']}")
        bidding_str = "\n".join(bid_lines) if bid_lines else "Not recorded"

        # Format tricks
        trick_lines = []
        for t in tricks:
            cards = json.loads(t["cards_played"])
            cards_str = ", ".join(f"{seat_names.get(s, '?')}:{c}" for s, c in cards)
            winner = seat_names.get(t["winner_seat"], "?")
            trick_lines.append(f"  Trick {t['trick_number']}: {cards_str} → {winner} wins")
        tricks_str = "\n".join(trick_lines) if trick_lines else "Not recorded"

        caller_seat = hand.get("caller_seat", 0)
        calling_team = caller_seat % 2 if caller_seat is not None else 0
        calling_tricks = hand.get(f"tricks_team_{calling_team}", 0)

        if calling_tricks >= 5:
            outcome = "march"
        elif calling_tricks >= 3:
            outcome = "made it"
        else:
            outcome = "EUCHRED"

        scoring_team = calling_team if calling_tricks >= 3 else (1 - calling_team)
        points = hand.get(f"points_team_{scoring_team}", 0)

        alone_note = ", going alone" if hand.get("going_alone") else ""

        return HAND_ANALYSIS_TEMPLATE.format(
            dealer=seat_names.get(hand["dealer_seat"], "?"),
            dealer_seat=hand["dealer_seat"],
            trump=hand.get("trump_suit", "?"),
            caller=seat_names.get(caller_seat, "?"),
            caller_seat=caller_seat,
            alone_note=alone_note,
            turned_up=hand.get("turned_up", "?"),
            initial_hands=initial_hands_str,
            bidding_log=bidding_str,
            tricks_log=tricks_str,
            calling_team=calling_team,
            calling_tricks=calling_tricks,
            outcome=outcome,
            points=points,
            scoring_team=scoring_team,
        )
