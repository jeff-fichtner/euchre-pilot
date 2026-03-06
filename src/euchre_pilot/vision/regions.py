"""Screen region definitions for Euchre 3D.

Each region is a bounding box (x, y, width, height) in pixels.
These are populated during calibration and stored in a config file.
Different device resolutions require different region maps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class BoundingBox:
    """A rectangular region on screen."""
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    def to_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def crop_slice(self) -> tuple[slice, slice]:
        """Return numpy-style slices for cropping: img[y:y2, x:x2]."""
        return (slice(self.y, self.y2), slice(self.x, self.x2))


@dataclass
class RegionMap:
    """All screen regions for a specific device/resolution.

    Populated during calibration, saved to JSON, loaded at runtime.
    """
    device_name: str
    resolution: tuple[int, int]  # (width, height)

    # Player hand card slots (your cards, bottom of screen)
    hand_slots: list[BoundingBox] = field(default_factory=list)  # Up to 5

    # Played cards in the trick area (one per seat)
    trick_south: BoundingBox | None = None
    trick_west: BoundingBox | None = None
    trick_north: BoundingBox | None = None
    trick_east: BoundingBox | None = None

    # Turned-up card (during bidding)
    turned_up: BoundingBox | None = None

    # Trump indicator
    trump_indicator: BoundingBox | None = None

    # Score displays
    score_team_0: BoundingBox | None = None
    score_team_1: BoundingBox | None = None

    # UI buttons / prompts
    order_up_button: BoundingBox | None = None
    pass_button: BoundingBox | None = None
    alone_button: BoundingBox | None = None
    new_game_button: BoundingBox | None = None

    # Suit selection buttons (for round 2 bidding)
    suit_buttons: dict[str, BoundingBox] = field(default_factory=dict)

    # Tap targets for playing cards (center of each hand slot)
    hand_tap_targets: list[tuple[int, int]] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Serialize to JSON."""
        data = {
            "device_name": self.device_name,
            "resolution": list(self.resolution),
            "hand_slots": [_box_to_dict(b) for b in self.hand_slots],
            "trick_south": _box_to_dict(self.trick_south),
            "trick_west": _box_to_dict(self.trick_west),
            "trick_north": _box_to_dict(self.trick_north),
            "trick_east": _box_to_dict(self.trick_east),
            "turned_up": _box_to_dict(self.turned_up),
            "trump_indicator": _box_to_dict(self.trump_indicator),
            "score_team_0": _box_to_dict(self.score_team_0),
            "score_team_1": _box_to_dict(self.score_team_1),
            "order_up_button": _box_to_dict(self.order_up_button),
            "pass_button": _box_to_dict(self.pass_button),
            "alone_button": _box_to_dict(self.alone_button),
            "new_game_button": _box_to_dict(self.new_game_button),
            "suit_buttons": {k: _box_to_dict(v) for k, v in self.suit_buttons.items()},
            "hand_tap_targets": self.hand_tap_targets,
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> RegionMap:
        """Deserialize from JSON."""
        data = json.loads(path.read_text())
        rm = cls(
            device_name=data["device_name"],
            resolution=tuple(data["resolution"]),
        )
        rm.hand_slots = [_dict_to_box(d) for d in data.get("hand_slots", []) if d]
        rm.trick_south = _dict_to_box(data.get("trick_south"))
        rm.trick_west = _dict_to_box(data.get("trick_west"))
        rm.trick_north = _dict_to_box(data.get("trick_north"))
        rm.trick_east = _dict_to_box(data.get("trick_east"))
        rm.turned_up = _dict_to_box(data.get("turned_up"))
        rm.trump_indicator = _dict_to_box(data.get("trump_indicator"))
        rm.score_team_0 = _dict_to_box(data.get("score_team_0"))
        rm.score_team_1 = _dict_to_box(data.get("score_team_1"))
        rm.order_up_button = _dict_to_box(data.get("order_up_button"))
        rm.pass_button = _dict_to_box(data.get("pass_button"))
        rm.alone_button = _dict_to_box(data.get("alone_button"))
        rm.new_game_button = _dict_to_box(data.get("new_game_button"))
        rm.suit_buttons = {
            k: _dict_to_box(v) for k, v in data.get("suit_buttons", {}).items() if v
        }
        rm.hand_tap_targets = [tuple(t) for t in data.get("hand_tap_targets", [])]
        return rm


def _box_to_dict(box: BoundingBox | None) -> dict | None:
    if box is None:
        return None
    return {"x": box.x, "y": box.y, "width": box.width, "height": box.height}


def _dict_to_box(d: dict | None) -> BoundingBox | None:
    if d is None:
        return None
    return BoundingBox(x=d["x"], y=d["y"], width=d["width"], height=d["height"])
