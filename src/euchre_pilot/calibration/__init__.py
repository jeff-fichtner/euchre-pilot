"""Calibration system — LLM-assisted template library builder.

Run this once per device to build the template library.
The LLM identifies cards and UI elements in screenshots,
crops and labels them, and validates coverage.
"""

from euchre_pilot.calibration.collector import ScreenshotCollector
from euchre_pilot.calibration.labeler import LLMLabeler
from euchre_pilot.calibration.extractor import TemplateExtractor
from euchre_pilot.calibration.validator import CoverageValidator

__all__ = ["ScreenshotCollector", "LLMLabeler", "TemplateExtractor", "CoverageValidator"]
