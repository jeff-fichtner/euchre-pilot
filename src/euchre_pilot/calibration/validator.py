"""Coverage validator — checks that the template library is complete."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from euchre_pilot.engine.cards import Suit, Rank

logger = logging.getLogger(__name__)

# All 24 Euchre cards
ALL_CARDS = {
    f"{r}{s}": (r, s)
    for s in ["H", "D", "C", "S"]
    for r in ["9", "10", "J", "Q", "K", "A"]
}

REQUIRED_UI = [
    "order_up_button",
    "pass_button",
    "trump_hearts",
    "trump_diamonds",
    "trump_clubs",
    "trump_spades",
]

OPTIONAL_UI = [
    "alone_button",
    "new_game_button",
    "score_team_0",
    "score_team_1",
    "suit_hearts",
    "suit_diamonds",
    "suit_clubs",
    "suit_spades",
]


@dataclass
class CoverageReport:
    """Results of a coverage check."""
    total_cards: int = 24
    found_cards: int = 0
    missing_cards: list[str] = None  # type: ignore
    found_ui: list[str] = None  # type: ignore
    missing_required_ui: list[str] = None  # type: ignore
    missing_optional_ui: list[str] = None  # type: ignore
    card_coverage_pct: float = 0.0
    is_ready: bool = False

    def __post_init__(self) -> None:
        if self.missing_cards is None:
            self.missing_cards = []
        if self.found_ui is None:
            self.found_ui = []
        if self.missing_required_ui is None:
            self.missing_required_ui = []
        if self.missing_optional_ui is None:
            self.missing_optional_ui = []

    def summary(self) -> str:
        lines = [
            f"Card coverage: {self.found_cards}/{self.total_cards} ({self.card_coverage_pct:.0%})",
        ]
        if self.missing_cards:
            lines.append(f"Missing cards: {', '.join(self.missing_cards)}")
        if self.missing_required_ui:
            lines.append(f"Missing required UI: {', '.join(self.missing_required_ui)}")
        if self.missing_optional_ui:
            lines.append(f"Missing optional UI: {', '.join(self.missing_optional_ui)}")
        lines.append(f"Ready for play: {'YES' if self.is_ready else 'NO'}")
        return "\n".join(lines)


class CoverageValidator:
    """Checks template library completeness."""

    def __init__(self, template_dir: Path) -> None:
        self.template_dir = template_dir

    def check(self) -> CoverageReport:
        """Run a full coverage check."""
        manifest_path = self.template_dir / "manifest.json"
        if not manifest_path.exists():
            report = CoverageReport()
            report.missing_cards = list(ALL_CARDS.keys())
            report.missing_required_ui = list(REQUIRED_UI)
            report.missing_optional_ui = list(OPTIONAL_UI)
            return report

        manifest = json.loads(manifest_path.read_text())

        # Check card coverage
        found_card_ids: set[str] = set()
        for entry in manifest.get("cards", []):
            found_card_ids.add(entry["card"])

        missing = sorted(set(ALL_CARDS.keys()) - found_card_ids)
        found_count = len(ALL_CARDS) - len(missing)

        # Check UI coverage
        found_ui_names: set[str] = set()
        for entry in manifest.get("ui", []):
            found_ui_names.add(entry["name"])

        missing_req = [u for u in REQUIRED_UI if u not in found_ui_names]
        missing_opt = [u for u in OPTIONAL_UI if u not in found_ui_names]

        report = CoverageReport(
            found_cards=found_count,
            missing_cards=missing,
            found_ui=sorted(found_ui_names),
            missing_required_ui=missing_req,
            missing_optional_ui=missing_opt,
            card_coverage_pct=found_count / 24,
            is_ready=(found_count == 24 and len(missing_req) == 0),
        )

        logger.info(report.summary())
        return report
