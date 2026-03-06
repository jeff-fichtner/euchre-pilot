"""ADB wrapper — screenshot capture, tap, swipe, device info."""

from __future__ import annotations

import subprocess
import time
import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class AdbDevice:
    """Interface to an Android device via ADB."""

    def __init__(self, device_id: str | None = None) -> None:
        """Initialize with optional device ID (for multiple connected devices)."""
        self.device_id = device_id
        self._resolution: tuple[int, int] | None = None

    def _adb(self, *args: str, timeout: float = 10.0) -> subprocess.CompletedProcess:
        """Run an ADB command."""
        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, timeout=timeout)

    def screenshot(self) -> np.ndarray:
        """Capture a screenshot and return as numpy array (BGR).

        Uses adb screencap piped directly — no temp file on device.
        """
        result = self._adb("exec-out", "screencap", "-p")
        if result.returncode != 0:
            raise RuntimeError(f"ADB screencap failed: {result.stderr.decode()}")

        # Decode PNG from raw bytes
        img_array = np.frombuffer(result.stdout, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("Failed to decode screenshot")

        return img

    def screenshot_to_file(self, path: Path) -> None:
        """Capture screenshot and save to a local file."""
        img = self.screenshot()
        cv2.imwrite(str(path), img)

    def tap(self, x: int, y: int) -> None:
        """Tap at screen coordinates."""
        result = self._adb("shell", "input", "tap", str(x), str(y))
        if result.returncode != 0:
            logger.warning("ADB tap failed: %s", result.stderr.decode())

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        """Swipe from (x1,y1) to (x2,y2)."""
        self._adb("shell", "input", "swipe",
                   str(x1), str(y1), str(x2), str(y2), str(duration_ms))

    def key_event(self, keycode: int) -> None:
        """Send a key event (e.g., KEYCODE_BACK=4)."""
        self._adb("shell", "input", "keyevent", str(keycode))

    def back(self) -> None:
        """Press the back button."""
        self.key_event(4)

    @property
    def resolution(self) -> tuple[int, int]:
        """Get device screen resolution (width, height)."""
        if self._resolution is None:
            result = self._adb("shell", "wm", "size")
            output = result.stdout.decode().strip()
            # Output: "Physical size: 1080x1920"
            size_str = output.split(":")[-1].strip()
            w, h = size_str.split("x")
            self._resolution = (int(w), int(h))
        return self._resolution

    def is_connected(self) -> bool:
        """Check if device is connected and responsive."""
        try:
            result = self._adb("get-state", timeout=5.0)
            return result.stdout.decode().strip() == "device"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def wait_for_device(self, timeout: float = 30.0) -> bool:
        """Wait for device to become available."""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_connected():
                return True
            time.sleep(1.0)
        return False

    def is_screen_stable(self, delay: float = 0.2, threshold: float = 0.99) -> bool:
        """Check if screen has stopped changing (animations complete).

        Takes two screenshots separated by delay and compares them.
        """
        img1 = self.screenshot()
        time.sleep(delay)
        img2 = self.screenshot()

        # Compare using normalized correlation
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
        similarity = result[0][0]

        return similarity >= threshold

    def wait_for_stable_screen(self, max_wait: float = 5.0, check_interval: float = 0.3) -> bool:
        """Wait until the screen stops changing."""
        start = time.time()
        while time.time() - start < max_wait:
            if self.is_screen_stable(delay=check_interval):
                return True
            time.sleep(0.1)
        return False
