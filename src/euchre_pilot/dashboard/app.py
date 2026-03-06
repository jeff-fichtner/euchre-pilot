"""FastAPI dashboard — local web UI for game history and analysis."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from euchre_pilot.recorder.database import GameDatabase

TEMPLATE_DIR = Path(__file__).parent / "templates"


def create_app(db_path: Path) -> FastAPI:
    app = FastAPI(title="Euchre Pilot Dashboard")
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    def get_db() -> GameDatabase:
        db = GameDatabase(db_path)
        db.connect()
        return db

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        db = get_db()
        try:
            games = db.get_recent_games(limit=50)
            win_rate = db.get_win_rate(team=0)
            game_count = db.get_game_count()
            return templates.TemplateResponse("index.html", {
                "request": request,
                "games": games,
                "win_rate": win_rate,
                "game_count": game_count,
            })
        finally:
            db.close()

    @app.get("/api/games")
    async def api_games(limit: int = 50):
        db = get_db()
        try:
            return {"games": db.get_recent_games(limit=limit)}
        finally:
            db.close()

    @app.get("/api/games/{game_id}/hands")
    async def api_game_hands(game_id: int):
        db = get_db()
        try:
            rows = db.conn.execute(
                "SELECT * FROM hands WHERE game_id=? ORDER BY hand_number", (game_id,)
            ).fetchall()
            return {"hands": [dict(r) for r in rows]}
        finally:
            db.close()

    @app.get("/api/hands/{hand_id}")
    async def api_hand_detail(hand_id: int):
        db = get_db()
        try:
            return db.get_hand_details(hand_id)
        finally:
            db.close()

    @app.get("/api/stats")
    async def api_stats():
        db = get_db()
        try:
            return {
                "game_count": db.get_game_count(),
                "win_rate": db.get_win_rate(team=0),
                "bid_stats": db.get_decision_stats("bid_r1"),
            }
        finally:
            db.close()

    return app
