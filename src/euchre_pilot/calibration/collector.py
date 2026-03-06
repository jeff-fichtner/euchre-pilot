"""Screenshot collector — captures frames from Euchre 3D during AI-vs-AI games."""

from __future__ import annotations

import time
import logging
from pathlib import Path

from euchre_pilot.android.adb import AdbDevice

logger = logging.getLogger(__name__)


class ScreenshotCollector:
    """Captures screenshots at regular intervals during gameplay.

    Screenshots are saved with timestamps for later processing by the labeler.
    """

    def __init__(
        self,
        device: AdbDevice,
        output_dir: Path,
        interval: float = 2.0,
    ) -> None:
        self.device = device
        self.output_dir = output_dir
        self.interval = interval
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def collect(self, num_screenshots: int = 100, skip_duplicates: bool = True) -> list[Path]:
        """Capture a series of screenshots.

        Args:
            num_screenshots: Max screenshots to capture.
            skip_duplicates: Skip frames that are identical to the previous one.

        Returns:
            List of saved screenshot paths.
        """
        saved: list[Path] = []
        prev_hash: int | None = None

        logger.info("Starting screenshot collection (target: %d frames)", num_screenshots)

        for i in range(num_screenshots):
            try:
                # Wait for stable screen (no animation in progress)
                self.device.wait_for_stable_screen(max_wait=2.0)

                img = self.device.screenshot()

                if skip_duplicates:
                    current_hash = hash(img.tobytes()[:10000])  # Hash first chunk
                    if current_hash == prev_hash:
                        logger.debug("Frame %d: duplicate, skipping", i)
                        time.sleep(self.interval)
                        continue
                    prev_hash = current_hash

                filename = f"frame_{i:04d}_{int(time.time() * 1000)}.png"
                path = self.output_dir / filename

                import cv2
                cv2.imwrite(str(path), img)
                saved.append(path)

                logger.info("Captured frame %d/%d → %s", len(saved), num_screenshots, filename)

            except Exception as e:
                logger.warning("Frame %d capture failed: %s", i, e)

            time.sleep(self.interval)

        logger.info("Collection complete: %d unique frames saved", len(saved))
        return saved

    def collect_with_auto_play(
        self,
        num_games: int = 10,
        screenshots_per_game: int = 30,
        new_game_tap: tuple[int, int] | None = None,
    ) -> list[Path]:
        """Collect screenshots while automatically starting new games.

        This taps through the UI to keep games running while collecting frames.
        Requires the new game button coordinates (found during initial manual calibration).
        """
        all_saved: list[Path] = []

        for game_num in range(num_games):
            logger.info("=== Game %d/%d ===", game_num + 1, num_games)

            # Start a new game if we have the button coordinates
            if new_game_tap and game_num > 0:
                self.device.tap(*new_game_tap)
                time.sleep(2.0)  # Wait for game to start

            saved = self.collect(
                num_screenshots=screenshots_per_game,
                skip_duplicates=True,
            )
            all_saved.extend(saved)

            # Wait for game to finish (poll for "new game" state)
            time.sleep(5.0)

        return all_saved
