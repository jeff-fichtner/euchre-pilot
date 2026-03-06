"""SQLite database for storing game history."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class GameDatabase:
    """SQLite-backed storage for complete game histories.

    Schema:
    - games: one row per game (final scores, winner, timestamp)
    - hands: one row per hand (trump, caller, tricks won, points scored)
    - tricks: one row per trick (lead, cards played, winner)
    - decisions: one row per decision point (bid or card play, what was chosen, alternatives)
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> GameDatabase:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected — call connect() first")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL NOT NULL,
                ended_at REAL,
                score_team_0 INTEGER DEFAULT 0,
                score_team_1 INTEGER DEFAULT 0,
                winner INTEGER,  -- 0 or 1
                source TEXT DEFAULT 'engine',  -- 'engine' or 'live'
                metadata TEXT  -- JSON blob for extra info
            );

            CREATE TABLE IF NOT EXISTS hands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL REFERENCES games(id),
                hand_number INTEGER NOT NULL,
                dealer_seat INTEGER NOT NULL,
                trump_suit TEXT,
                caller_seat INTEGER,
                going_alone INTEGER DEFAULT 0,
                tricks_team_0 INTEGER DEFAULT 0,
                tricks_team_1 INTEGER DEFAULT 0,
                points_team_0 INTEGER DEFAULT 0,
                points_team_1 INTEGER DEFAULT 0,
                was_euchred INTEGER DEFAULT 0,
                initial_hands TEXT,  -- JSON: {seat: [card_strs]}
                turned_up TEXT  -- card string
            );

            CREATE TABLE IF NOT EXISTS tricks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hand_id INTEGER NOT NULL REFERENCES hands(id),
                trick_number INTEGER NOT NULL,
                lead_seat INTEGER NOT NULL,
                cards_played TEXT NOT NULL,  -- JSON: [[seat, card_str], ...]
                winner_seat INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hand_id INTEGER NOT NULL REFERENCES hands(id),
                trick_number INTEGER,  -- NULL for bids
                seat INTEGER NOT NULL,
                decision_type TEXT NOT NULL,  -- 'bid_r1', 'bid_r2', 'discard', 'play'
                chosen TEXT NOT NULL,  -- What was chosen (card string or action)
                alternatives TEXT,  -- JSON: list of other legal options
                hand_held TEXT,  -- JSON: cards in hand at decision time
                context TEXT  -- JSON: any additional state info
            );

            CREATE INDEX IF NOT EXISTS idx_hands_game ON hands(game_id);
            CREATE INDEX IF NOT EXISTS idx_tricks_hand ON tricks(hand_id);
            CREATE INDEX IF NOT EXISTS idx_decisions_hand ON decisions(hand_id);
        """)

    # --- Insert operations ---

    def insert_game(self, source: str = "engine", metadata: dict | None = None) -> int:
        cursor = self.conn.execute(
            "INSERT INTO games (started_at, source, metadata) VALUES (?, ?, ?)",
            (time.time(), source, json.dumps(metadata) if metadata else None),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def finish_game(self, game_id: int, score_0: int, score_1: int) -> None:
        winner = 0 if score_0 > score_1 else 1
        self.conn.execute(
            "UPDATE games SET ended_at=?, score_team_0=?, score_team_1=?, winner=? WHERE id=?",
            (time.time(), score_0, score_1, winner, game_id),
        )
        self.conn.commit()

    def insert_hand(
        self,
        game_id: int,
        hand_number: int,
        dealer_seat: int,
        trump_suit: str | None,
        caller_seat: int | None,
        going_alone: bool,
        tricks_0: int,
        tricks_1: int,
        points_0: int,
        points_1: int,
        was_euchred: bool,
        initial_hands: dict[int, list[str]] | None = None,
        turned_up: str | None = None,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO hands (game_id, hand_number, dealer_seat, trump_suit,
                caller_seat, going_alone, tricks_team_0, tricks_team_1,
                points_team_0, points_team_1, was_euchred, initial_hands, turned_up)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (game_id, hand_number, dealer_seat, trump_suit,
             caller_seat, int(going_alone), tricks_0, tricks_1,
             points_0, points_1, int(was_euchred),
             json.dumps(initial_hands) if initial_hands else None,
             turned_up),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def insert_trick(
        self,
        hand_id: int,
        trick_number: int,
        lead_seat: int,
        cards_played: list[tuple[int, str]],
        winner_seat: int,
    ) -> int:
        cursor = self.conn.execute(
            "INSERT INTO tricks (hand_id, trick_number, lead_seat, cards_played, winner_seat) VALUES (?, ?, ?, ?, ?)",
            (hand_id, trick_number, lead_seat, json.dumps(cards_played), winner_seat),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def insert_decision(
        self,
        hand_id: int,
        trick_number: int | None,
        seat: int,
        decision_type: str,
        chosen: str,
        alternatives: list[str] | None = None,
        hand_held: list[str] | None = None,
        context: dict | None = None,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO decisions (hand_id, trick_number, seat, decision_type,
                chosen, alternatives, hand_held, context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (hand_id, trick_number, seat, decision_type, chosen,
             json.dumps(alternatives) if alternatives else None,
             json.dumps(hand_held) if hand_held else None,
             json.dumps(context) if context else None),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    # --- Query operations ---

    def get_game_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM games").fetchone()
        return row[0]

    def get_recent_games(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM games ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_hand_details(self, hand_id: int) -> dict:
        hand = dict(self.conn.execute("SELECT * FROM hands WHERE id=?", (hand_id,)).fetchone())
        tricks = [dict(r) for r in self.conn.execute(
            "SELECT * FROM tricks WHERE hand_id=? ORDER BY trick_number", (hand_id,)
        ).fetchall()]
        decisions = [dict(r) for r in self.conn.execute(
            "SELECT * FROM decisions WHERE hand_id=? ORDER BY id", (hand_id,)
        ).fetchall()]
        return {"hand": hand, "tricks": tricks, "decisions": decisions}

    def get_win_rate(self, team: int = 0) -> float:
        total = self.conn.execute("SELECT COUNT(*) FROM games WHERE winner IS NOT NULL").fetchone()[0]
        if total == 0:
            return 0.0
        wins = self.conn.execute("SELECT COUNT(*) FROM games WHERE winner=?", (team,)).fetchone()[0]
        return wins / total

    def get_decision_stats(self, decision_type: str) -> list[dict]:
        """Get aggregate stats for a decision type."""
        rows = self.conn.execute(
            """SELECT chosen, COUNT(*) as count,
                      hand_held, context
               FROM decisions
               WHERE decision_type=?
               GROUP BY chosen
               ORDER BY count DESC""",
            (decision_type,),
        ).fetchall()
        return [dict(r) for r in rows]
