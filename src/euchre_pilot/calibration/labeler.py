"""LLM-based screenshot labeler — identifies cards and UI elements via vision API.

This is the one-time calibration step where we use a vision LLM to identify
what's on screen. The LLM sees each screenshot and returns structured data
about card locations, identities, and UI element positions.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
from pydantic import BaseModel

from euchre_pilot.analyst.llm import LLMClient

logger = logging.getLogger(__name__)


# --- Pydantic models for structured LLM responses ---

class CardDetection(BaseModel):
    """A single card detected in a screenshot."""
    rank: Literal["9", "10", "J", "Q", "K", "A"]
    suit: Literal["hearts", "diamonds", "clubs", "spades"]
    location: Literal["hand", "trick", "turned_up", "kitty"]
    position: int  # Position index within its location (0-4 for hand, 0-3 for trick seats)
    bounding_box: dict  # {"x": int, "y": int, "width": int, "height": int}
    confidence: str  # "high", "medium", "low"


class UIElementDetection(BaseModel):
    """A UI element detected in a screenshot."""
    element_type: str  # "order_up_button", "pass_button", "trump_indicator", etc.
    bounding_box: dict
    value: str | None = None  # e.g., suit name for trump indicator, score value


class ScreenAnalysis(BaseModel):
    """Full analysis of a single screenshot."""
    game_phase: str  # "bidding_round_1", "bidding_round_2", "playing", "between_hands", etc.
    cards: list[CardDetection] = []
    ui_elements: list[UIElementDetection] = []
    notes: str = ""  # Any additional observations


# --- Labeler ---

CALIBRATION_PROMPT = """You are analyzing a screenshot from Euchre 3D, an Android card game app.

Your job is to identify ALL visible cards and UI elements with pixel-accurate bounding boxes.

For each visible card:
1. Identify its rank (9, 10, J, Q, K, A) and suit (hearts, diamonds, clubs, spades)
2. Determine its location: "hand" (player's cards at bottom), "trick" (cards played to center), "turned_up" (card shown during bidding), or "kitty"
3. Give its position index (hand: 0-4 left to right, trick: 0=south, 1=west, 2=north, 3=east)
4. Provide a tight bounding box as {x, y, width, height} in pixels
5. Rate your confidence: "high" if clearly readable, "medium" if partially obscured, "low" if guessing

For UI elements, identify:
- "order_up_button", "pass_button", "alone_button" — action buttons
- "trump_indicator" — shows current trump suit (value = suit name)
- "score_team_0", "score_team_1" — score displays (value = score number)
- "new_game_button" — button to start a new game
- "suit_hearts", "suit_diamonds", "suit_clubs", "suit_spades" — suit selection buttons
- Any other interactive elements

Determine the game phase: "bidding_round_1", "bidding_round_2", "playing", "between_hands", "game_over", or "unknown".

Be precise with bounding boxes — they will be used to crop template images for future recognition.
Return your analysis as structured JSON matching the ScreenAnalysis schema."""


class LLMLabeler:
    """Uses a vision LLM to label cards and UI elements in screenshots."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def label_screenshot(self, image_path: Path) -> ScreenAnalysis:
        """Analyze a single screenshot and return structured detections."""
        image_bytes = image_path.read_bytes()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        # Determine media type
        suffix = image_path.suffix.lower()
        media_type = "image/png" if suffix == ".png" else "image/jpeg"

        response = self.llm.vision_structured(
            prompt=CALIBRATION_PROMPT,
            image_b64=b64_image,
            media_type=media_type,
            response_model=ScreenAnalysis,
        )

        logger.info(
            "Labeled %s: phase=%s, %d cards, %d UI elements",
            image_path.name, response.game_phase,
            len(response.cards), len(response.ui_elements),
        )

        return response

    def label_batch(self, image_paths: list[Path]) -> list[tuple[Path, ScreenAnalysis]]:
        """Label multiple screenshots. Returns list of (path, analysis) pairs."""
        results = []
        for i, path in enumerate(image_paths):
            logger.info("Labeling screenshot %d/%d: %s", i + 1, len(image_paths), path.name)
            try:
                analysis = self.label_screenshot(path)
                results.append((path, analysis))
            except Exception as e:
                logger.warning("Failed to label %s: %s", path.name, e)
        return results
