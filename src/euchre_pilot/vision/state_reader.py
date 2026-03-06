"""Compose ADB capture + template matching into game state extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import logging

import numpy as np

from euchre_pilot.engine.cards import Card, Suit
from euchre_pilot.vision.regions import RegionMap, BoundingBox
from euchre_pilot.vision.matcher import TemplateMatcher, MatchResult

logger = logging.getLogger(__name__)


@dataclass
class ScreenGameState:
    """Game state as read from a screenshot. May be partial/uncertain."""
    hand_cards: list[Card | None] = field(default_factory=list)
    hand_confidences: list[float] = field(default_factory=list)
    trick_cards: dict[str, Card | None] = field(default_factory=dict)  # seat_name -> card
    turned_up: Card | None = None
    trump_suit: Suit | None = None
    score: tuple[int | None, int | None] = (None, None)
    phase_hints: dict[str, float] = field(default_factory=dict)  # UI element -> confidence
    timestamp: float = 0.0

    @property
    def is_reliable(self) -> bool:
        """Check if all detected cards meet minimum confidence."""
        min_conf = min(self.hand_confidences) if self.hand_confidences else 0.0
        return min_conf >= 0.80 and len(self.hand_cards) > 0


class ScreenStateReader:
    """Reads game state from a screenshot using region map + template matcher."""

    def __init__(self, region_map: RegionMap, matcher: TemplateMatcher) -> None:
        self.regions = region_map
        self.matcher = matcher

    def read(self, screenshot: np.ndarray) -> ScreenGameState:
        """Extract full game state from a screenshot."""
        state = ScreenGameState()

        # Read hand cards
        for i, slot in enumerate(self.regions.hand_slots):
            region = self._crop(screenshot, slot)
            result = self.matcher.match_card(region)
            if result:
                state.hand_cards.append(result.card)
                state.hand_confidences.append(result.confidence)
            else:
                state.hand_cards.append(None)
                state.hand_confidences.append(0.0)

        # Read trick cards
        trick_regions = {
            "south": self.regions.trick_south,
            "west": self.regions.trick_west,
            "north": self.regions.trick_north,
            "east": self.regions.trick_east,
        }
        for seat_name, region_box in trick_regions.items():
            if region_box is None:
                continue
            region = self._crop(screenshot, region_box)
            result = self.matcher.match_card(region)
            state.trick_cards[seat_name] = result.card if result else None

        # Read turned-up card
        if self.regions.turned_up:
            region = self._crop(screenshot, self.regions.turned_up)
            result = self.matcher.match_card(region)
            state.turned_up = result.card if result else None

        # Read trump suit
        if self.regions.trump_indicator:
            region = self._crop(screenshot, self.regions.trump_indicator)
            state.trump_suit = self.matcher.match_trump_suit(region)

        # Check UI state (what buttons/prompts are visible)
        ui_checks = {
            "order_up_button": self.regions.order_up_button,
            "pass_button": self.regions.pass_button,
            "alone_button": self.regions.alone_button,
            "new_game_button": self.regions.new_game_button,
        }
        for name, region_box in ui_checks.items():
            if region_box is None:
                continue
            region = self._crop(screenshot, region_box)
            confidence = self.matcher.match_ui_element(region, name)
            if confidence > 0.5:
                state.phase_hints[name] = confidence

        return state

    def read_hand_only(self, screenshot: np.ndarray) -> list[Card | None]:
        """Quick read of just the hand cards — for the fast game loop."""
        cards = []
        for slot in self.regions.hand_slots:
            region = self._crop(screenshot, slot)
            result = self.matcher.match_card(region)
            cards.append(result.card if result else None)
        return cards

    @staticmethod
    def _crop(img: np.ndarray, box: BoundingBox) -> np.ndarray:
        """Crop a region from the screenshot."""
        y_slice, x_slice = box.crop_slice()
        return img[y_slice, x_slice]
