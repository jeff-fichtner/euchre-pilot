"""CLI entry points for all euchre-pilot commands."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def simulate() -> None:
    """Run engine-only simulated games (no Android device needed)."""
    parser = argparse.ArgumentParser(description="Simulate Euchre games")
    parser.add_argument("-n", "--num-games", type=int, default=100, help="Number of games to simulate")
    parser.add_argument("-s", "--seed", type=int, default=None, help="Random seed")
    parser.add_argument("-d", "--db", type=str, default="data/games.db", help="Database path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    logger = logging.getLogger("simulate")

    from euchre_pilot.engine.game import EuchreGame
    from euchre_pilot.engine.state import Seat
    from euchre_pilot.player import RuleBasedPlayer, RandomPlayer
    from euchre_pilot.recorder.database import GameDatabase
    from euchre_pilot.recorder.logger import GameLogger

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    players = {
        Seat.SOUTH: RuleBasedPlayer(),
        Seat.WEST: RuleBasedPlayer(),
        Seat.NORTH: RuleBasedPlayer(),
        Seat.EAST: RuleBasedPlayer(),
    }

    with GameDatabase(db_path) as db:
        game_logger = GameLogger(db, source="simulation")

        wins = {0: 0, 1: 0}
        for i in range(args.num_games):
            game = EuchreGame(players=players, seed=args.seed + i if args.seed else None)
            game_id = game_logger.start_game(metadata={"sim_index": i})

            state = game.play_game()

            for hand in state.hand_history:
                game_logger.log_hand(hand)

            game_logger.end_game(state)

            if state.winner is not None:
                wins[state.winner] += 1

            if (i + 1) % 10 == 0:
                logger.info(
                    "Games: %d/%d | Team 0: %d wins | Team 1: %d wins",
                    i + 1, args.num_games, wins[0], wins[1],
                )

        logger.info("=== Final Results ===")
        logger.info("Team 0 wins: %d (%.1f%%)", wins[0], 100 * wins[0] / args.num_games)
        logger.info("Team 1 wins: %d (%.1f%%)", wins[1], 100 * wins[1] / args.num_games)
        logger.info("Database: %s (%d total games)", db_path, db.get_game_count())


def calibrate() -> None:
    """Run the calibration process to build template library."""
    parser = argparse.ArgumentParser(description="Calibrate screen reader from Euchre 3D")
    parser.add_argument("-d", "--device", type=str, default=None, help="ADB device ID")
    parser.add_argument("-o", "--output", type=str, default="templates", help="Template output dir")
    parser.add_argument("-n", "--num-frames", type=int, default=100, help="Screenshots to capture")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    logger = logging.getLogger("calibrate")

    from euchre_pilot.android.adb import AdbDevice
    from euchre_pilot.analyst.llm import LLMClient, LLMProvider
    from euchre_pilot.calibration.collector import ScreenshotCollector
    from euchre_pilot.calibration.labeler import LLMLabeler
    from euchre_pilot.calibration.extractor import TemplateExtractor
    from euchre_pilot.calibration.validator import CoverageValidator

    device = AdbDevice(device_id=args.device)
    if not device.is_connected():
        logger.error("No Android device found. Connect via USB and enable ADB.")
        sys.exit(1)

    resolution = device.resolution
    logger.info("Device connected: %dx%d", *resolution)

    # Step 1: Collect screenshots
    raw_dir = Path(args.output) / "raw_screenshots"
    collector = ScreenshotCollector(device, raw_dir, interval=2.0)
    logger.info("Collecting screenshots — play Euchre 3D or let AI play...")
    screenshots = collector.collect(num_screenshots=args.num_frames)

    if not screenshots:
        logger.error("No screenshots captured. Is Euchre 3D running?")
        sys.exit(1)

    # Step 2: Label with LLM
    provider = LLMProvider.ANTHROPIC if args.provider == "anthropic" else LLMProvider.OPENAI
    llm = LLMClient(provider=provider)
    labeler = LLMLabeler(llm)
    labeled = labeler.label_batch(screenshots)

    # Step 3: Extract templates
    template_dir = Path(args.output)
    extractor = TemplateExtractor(template_dir)
    for path, analysis in labeled:
        extractor.process(path, analysis)
    manifest = extractor.finalize()

    # Build and save region map
    region_map = extractor.build_region_map("euchre_3d", resolution)
    region_map.save(template_dir / "regions.json")

    # Step 4: Validate
    validator = CoverageValidator(template_dir)
    report = validator.check()
    print("\n" + report.summary())

    if not report.is_ready:
        logger.warning("Template library incomplete — run more games and re-calibrate")


def play() -> None:
    """Run the live game agent against Euchre 3D."""
    parser = argparse.ArgumentParser(description="Play Euchre 3D with the AI agent")
    parser.add_argument("-d", "--device", type=str, default=None)
    parser.add_argument("-t", "--templates", type=str, default="templates")
    parser.add_argument("--db", type=str, default="data/games.db")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    logger = logging.getLogger("play")

    logger.info("Live play mode — not yet implemented")
    logger.info("Use 'euchre-simulate' to run engine-only games")
    logger.info("Use 'euchre-calibrate' to build the template library first")


def analyze() -> None:
    """Run LLM analysis on recorded games."""
    parser = argparse.ArgumentParser(description="Analyze recorded games")
    parser.add_argument("--db", type=str, default="data/games.db")
    parser.add_argument("-n", "--num-hands", type=int, default=10, help="Hands to analyze")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    logger = logging.getLogger("analyze")

    from euchre_pilot.analyst.llm import LLMClient, LLMProvider
    from euchre_pilot.analyst.analyzer import HandAnalyzer
    from euchre_pilot.recorder.database import GameDatabase

    provider = LLMProvider.ANTHROPIC if args.provider == "anthropic" else LLMProvider.OPENAI
    llm = LLMClient(provider=provider)

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error("No database found at %s — run simulations first", db_path)
        sys.exit(1)

    with GameDatabase(db_path) as db:
        analyzer = HandAnalyzer(llm, db)

        # Get recent hands
        hands = db.conn.execute(
            "SELECT id FROM hands ORDER BY id DESC LIMIT ?", (args.num_hands,)
        ).fetchall()

        for row in hands:
            hand_id = row[0]
            logger.info("Analyzing hand %d...", hand_id)
            try:
                result = analyzer.analyze_hand(hand_id)
                print(f"\n=== Hand {hand_id} ===")
                print(f"Assessment: {result.overall_assessment}")
                if result.key_mistake:
                    print(f"Key mistake: {result.key_mistake}")
                for lesson in result.lessons:
                    print(f"  - {lesson}")
            except Exception as e:
                logger.warning("Failed to analyze hand %d: %s", hand_id, e)


def dashboard() -> None:
    """Start the local web dashboard."""
    parser = argparse.ArgumentParser(description="Start Euchre Pilot dashboard")
    parser.add_argument("--db", type=str, default="data/games.db")
    parser.add_argument("-p", "--port", type=int, default=8420)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    import uvicorn
    from euchre_pilot.dashboard.app import create_app

    db_path = Path(args.db)
    app = create_app(db_path)
    print(f"Euchre Pilot Dashboard: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
