"""Template extractor — crops labeled regions and saves as template images."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from euchre_pilot.calibration.labeler import ScreenAnalysis, CardDetection, UIElementDetection
from euchre_pilot.vision.regions import RegionMap, BoundingBox

logger = logging.getLogger(__name__)


class TemplateExtractor:
    """Crops card and UI regions from labeled screenshots and builds the template library."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.cards_dir = output_dir / "cards"
        self.ui_dir = output_dir / "ui"
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self.ui_dir.mkdir(parents=True, exist_ok=True)

        # Track all detections for majority voting
        self._card_observations: dict[str, list[tuple[np.ndarray, str, float]]] = defaultdict(list)
        self._ui_observations: dict[str, list[tuple[np.ndarray, dict]]] = defaultdict(list)
        self._region_observations: dict[str, list[BoundingBox]] = defaultdict(list)

    def process(
        self,
        image_path: Path,
        analysis: ScreenAnalysis,
    ) -> None:
        """Extract templates from a single labeled screenshot."""
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("Failed to read image: %s", image_path)
            return

        # Extract card templates
        for card in analysis.cards:
            self._extract_card(img, card, image_path.name)

        # Extract UI element templates
        for element in analysis.ui_elements:
            self._extract_ui_element(img, element, image_path.name)

    def _extract_card(self, img: np.ndarray, detection: CardDetection, source: str) -> None:
        """Crop and store a card detection."""
        bb = detection.bounding_box
        box = BoundingBox(x=bb["x"], y=bb["y"], width=bb["width"], height=bb["height"])

        # Validate bounding box is within image
        h, w = img.shape[:2]
        if box.x < 0 or box.y < 0 or box.x2 > w or box.y2 > h:
            logger.warning("Bounding box out of bounds for %s%s: %s", detection.rank, detection.suit, bb)
            return

        crop = img[box.y:box.y2, box.x:box.x2]
        if crop.size == 0:
            return

        card_id = f"{detection.rank}_{detection.suit}"
        location_key = f"{detection.location}_{detection.position}"
        template_key = f"{card_id}_{location_key}"

        # Store for later majority voting
        self._card_observations[template_key].append((crop, source, 1.0 if detection.confidence == "high" else 0.5))

        # Also track region positions
        region_key = f"{detection.location}_{detection.position}"
        self._region_observations[region_key].append(box)

    def _extract_ui_element(self, img: np.ndarray, detection: UIElementDetection, source: str) -> None:
        """Crop and store a UI element detection."""
        bb = detection.bounding_box
        box = BoundingBox(x=bb["x"], y=bb["y"], width=bb["width"], height=bb["height"])

        h, w = img.shape[:2]
        if box.x < 0 or box.y < 0 or box.x2 > w or box.y2 > h:
            return

        crop = img[box.y:box.y2, box.x:box.x2]
        if crop.size == 0:
            return

        self._ui_observations[detection.element_type].append((crop, bb))
        self._region_observations[detection.element_type].append(box)

    def finalize(self) -> dict:
        """Save best templates and generate manifest.

        Uses majority voting: for each card identity, pick the crop from the
        highest-confidence observation.
        """
        manifest: dict = {"cards": [], "ui": []}

        # Save card templates
        for template_key, observations in self._card_observations.items():
            if not observations:
                continue

            # Pick highest confidence crop
            best_crop, best_source, best_conf = max(observations, key=lambda x: x[2])
            filename = f"{template_key}.png"
            cv2.imwrite(str(self.cards_dir / filename), best_crop)

            parts = template_key.split("_")
            card_str = f"{parts[0]}{parts[1][0].upper()}"  # e.g., "9H", "JC"

            manifest["cards"].append({
                "filename": filename,
                "card": card_str,
                "observations": len(observations),
                "confidence": best_conf,
            })

        # Save UI templates
        for element_type, observations in self._ui_observations.items():
            if not observations:
                continue

            best_crop, _ = observations[0]  # Take first observation
            filename = f"{element_type}.png"
            cv2.imwrite(str(self.ui_dir / filename), best_crop)

            manifest["ui"].append({
                "filename": filename,
                "name": element_type,
                "observations": len(observations),
            })

        # Save manifest
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.info(
            "Finalized: %d card templates, %d UI templates",
            len(manifest["cards"]), len(manifest["ui"]),
        )

        return manifest

    def build_region_map(self, device_name: str, resolution: tuple[int, int]) -> RegionMap:
        """Build a RegionMap from accumulated observations.

        Uses median bounding box positions across all observations.
        """
        region_map = RegionMap(device_name=device_name, resolution=resolution)

        # Compute median positions for hand slots
        for pos in range(5):
            key = f"hand_{pos}"
            boxes = self._region_observations.get(key, [])
            if boxes:
                region_map.hand_slots.append(self._median_box(boxes))

        # Trick positions
        for seat, attr in [("0", "trick_south"), ("1", "trick_west"),
                            ("2", "trick_north"), ("3", "trick_east")]:
            key = f"trick_{seat}"
            boxes = self._region_observations.get(key, [])
            if boxes:
                setattr(region_map, attr, self._median_box(boxes))

        # UI elements
        ui_attrs = {
            "order_up_button": "order_up_button",
            "pass_button": "pass_button",
            "alone_button": "alone_button",
            "new_game_button": "new_game_button",
            "trump_indicator": "trump_indicator",
            "score_team_0": "score_team_0",
            "score_team_1": "score_team_1",
        }
        for key, attr in ui_attrs.items():
            boxes = self._region_observations.get(key, [])
            if boxes:
                setattr(region_map, attr, self._median_box(boxes))

        # Hand tap targets (center of each hand slot)
        for slot in region_map.hand_slots:
            region_map.hand_tap_targets.append(
                (slot.x + slot.width // 2, slot.y + slot.height // 2)
            )

        return region_map

    @staticmethod
    def _median_box(boxes: list[BoundingBox]) -> BoundingBox:
        """Compute median bounding box from multiple observations."""
        xs = sorted(b.x for b in boxes)
        ys = sorted(b.y for b in boxes)
        ws = sorted(b.width for b in boxes)
        hs = sorted(b.height for b in boxes)
        mid = len(boxes) // 2
        return BoundingBox(x=xs[mid], y=ys[mid], width=ws[mid], height=hs[mid])
