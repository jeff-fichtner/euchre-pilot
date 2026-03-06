"""Template matching engine — pure OpenCV, no LLM calls at runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import logging

import cv2
import numpy as np

from euchre_pilot.engine.cards import Card, Suit, Rank

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of matching a screen region against templates."""
    card: Card
    confidence: float
    template_name: str


class TemplateMatcher:
    """Matches cropped screen regions against a library of card/UI templates.

    The template library is built during calibration and stored as PNG files
    with a manifest mapping filenames to card identities.
    """

    def __init__(self, template_dir: Path, confidence_threshold: float = 0.85) -> None:
        self.template_dir = template_dir
        self.threshold = confidence_threshold
        self._card_templates: dict[str, tuple[Card, np.ndarray]] = {}
        self._ui_templates: dict[str, np.ndarray] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all templates from disk."""
        manifest_path = self.template_dir / "manifest.json"
        if not manifest_path.exists():
            logger.warning("No template manifest found at %s — run calibration first", manifest_path)
            return

        manifest = json.loads(manifest_path.read_text())

        # Load card templates
        cards_dir = self.template_dir / "cards"
        for entry in manifest.get("cards", []):
            img_path = cards_dir / entry["filename"]
            if not img_path.exists():
                logger.warning("Missing template: %s", img_path)
                continue

            img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if img is None:
                logger.warning("Failed to read template: %s", img_path)
                continue

            card = Card.from_str(entry["card"])
            self._card_templates[entry["filename"]] = (card, img)

        # Load UI templates (trump indicators, buttons, etc.)
        ui_dir = self.template_dir / "ui"
        for entry in manifest.get("ui", []):
            img_path = ui_dir / entry["filename"]
            if not img_path.exists():
                continue
            img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if img is not None:
                self._ui_templates[entry["name"]] = img

        self._loaded = True
        logger.info(
            "Loaded %d card templates, %d UI templates",
            len(self._card_templates), len(self._ui_templates),
        )

    def match_card(self, region: np.ndarray) -> MatchResult | None:
        """Match a cropped card region against all card templates.

        Returns the best match above the confidence threshold, or None.
        """
        if not self._loaded:
            self.load()

        best_match: MatchResult | None = None
        best_confidence = 0.0

        for name, (card, template) in self._card_templates.items():
            # Resize template to match region if needed
            t = self._resize_template(template, region.shape[:2])

            result = cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_confidence and max_val >= self.threshold:
                best_confidence = max_val
                best_match = MatchResult(card=card, confidence=max_val, template_name=name)

        return best_match

    def match_ui_element(self, region: np.ndarray, element_name: str) -> float:
        """Check if a UI element (button, indicator) is present in a region.

        Returns confidence score (0-1).
        """
        if not self._loaded:
            self.load()

        template = self._ui_templates.get(element_name)
        if template is None:
            return 0.0

        t = self._resize_template(template, region.shape[:2])
        result = cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return float(max_val)

    def match_trump_suit(self, region: np.ndarray) -> Suit | None:
        """Identify the trump suit from the trump indicator region."""
        best_suit = None
        best_conf = 0.0

        for suit in Suit:
            name = f"trump_{suit.value}"
            conf = self.match_ui_element(region, name)
            if conf > best_conf and conf >= self.threshold:
                best_conf = conf
                best_suit = suit

        return best_suit

    @staticmethod
    def _resize_template(template: np.ndarray, target_shape: tuple[int, ...]) -> np.ndarray:
        """Resize template to fit within the target region."""
        th, tw = template.shape[:2]
        rh, rw = target_shape[:2]

        if th > rh or tw > rw:
            scale = min(rh / th, rw / tw)
            new_w = int(tw * scale)
            new_h = int(th * scale)
            return cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)

        return template

    @property
    def coverage(self) -> dict[str, int]:
        """Report how many templates are loaded per category."""
        return {
            "cards": len(self._card_templates),
            "ui": len(self._ui_templates),
        }

    @property
    def missing_cards(self) -> list[str]:
        """List card identifiers that don't have templates yet."""
        have = {name.split("_")[0] for name in self._card_templates}
        need = {f"{r}{s.value[0].upper()}" for s in Suit for r in ["9","10","J","Q","K","A"]}
        return sorted(need - have)
