"""Game controller — automates Euchre 3D interactions via ADB.

This is the bridge between the agent's decisions and the Android app.
It translates high-level actions (play card, pass, order up) into tap sequences.
"""

from __future__ import annotations

import time
import logging

from euchre_pilot.android.adb import AdbDevice
from euchre_pilot.vision.regions import RegionMap
from euchre_pilot.vision.state_reader import ScreenStateReader, ScreenGameState

logger = logging.getLogger(__name__)


class GameController:
    """Controls Euchre 3D on an Android device."""

    def __init__(
        self,
        device: AdbDevice,
        region_map: RegionMap,
        state_reader: ScreenStateReader,
        action_delay: float = 0.5,
    ) -> None:
        self.device = device
        self.regions = region_map
        self.reader = state_reader
        self.action_delay = action_delay

    def get_state(self) -> ScreenGameState:
        """Capture screenshot and read game state."""
        self.device.wait_for_stable_screen(max_wait=3.0)
        screenshot = self.device.screenshot()
        return self.reader.read(screenshot)

    def tap_card(self, hand_index: int) -> None:
        """Tap a card in the player's hand by position index (0-4)."""
        if hand_index >= len(self.regions.hand_tap_targets):
            raise ValueError(f"No tap target for hand index {hand_index}")

        x, y = self.regions.hand_tap_targets[hand_index]
        logger.info("Tapping card at position %d (%d, %d)", hand_index, x, y)
        self.device.tap(x, y)
        time.sleep(self.action_delay)

    def tap_order_up(self) -> None:
        """Tap the 'Order Up' button."""
        box = self.regions.order_up_button
        if box is None:
            raise RuntimeError("Order up button region not calibrated")
        self.device.tap(box.x + box.width // 2, box.y + box.height // 2)
        time.sleep(self.action_delay)

    def tap_pass(self) -> None:
        """Tap the 'Pass' button."""
        box = self.regions.pass_button
        if box is None:
            raise RuntimeError("Pass button region not calibrated")
        self.device.tap(box.x + box.width // 2, box.y + box.height // 2)
        time.sleep(self.action_delay)

    def tap_alone(self) -> None:
        """Tap the 'Alone' / 'Go Alone' button."""
        box = self.regions.alone_button
        if box is None:
            raise RuntimeError("Alone button region not calibrated")
        self.device.tap(box.x + box.width // 2, box.y + box.height // 2)
        time.sleep(self.action_delay)

    def tap_suit(self, suit_name: str) -> None:
        """Tap a suit selection button during round 2 bidding."""
        box = self.regions.suit_buttons.get(suit_name)
        if box is None:
            raise RuntimeError(f"Suit button '{suit_name}' not calibrated")
        self.device.tap(box.x + box.width // 2, box.y + box.height // 2)
        time.sleep(self.action_delay)

    def tap_new_game(self) -> None:
        """Tap the 'New Game' button."""
        box = self.regions.new_game_button
        if box is None:
            raise RuntimeError("New game button region not calibrated")
        self.device.tap(box.x + box.width // 2, box.y + box.height // 2)
        time.sleep(self.action_delay)

    def wait_for_turn(self, timeout: float = 30.0, poll_interval: float = 0.5) -> ScreenGameState:
        """Poll until it's the player's turn (UI buttons visible or cards interactable)."""
        start = time.time()
        while time.time() - start < timeout:
            state = self.get_state()

            # Turn indicators: bidding buttons or cards in hand with a prompt
            has_action = (
                "order_up_button" in state.phase_hints
                or "pass_button" in state.phase_hints
                or (len(state.hand_cards) > 0 and state.hand_cards[0] is not None)
            )

            if has_action:
                return state

            time.sleep(poll_interval)

        logger.warning("Timed out waiting for turn after %.1fs", timeout)
        return self.get_state()
