#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from engine import Game, open_game
from referee import make_referee
from save import SaveBundle, SaveError, SaveStore
from view import snapshot, story_detail
from world import load_world

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")

_world = None
_store = None
_referee = None
_game: Game | None = None
_flavor: str | None = None


def _boot(*, new: bool = False) -> Game:
    global _world, _store, _referee, _game, _flavor
    if _world is None:
        _world = load_world()
        _store = SaveStore(ROOT / "saves", _world)
        _referee = make_referee()
    try:
        _game = open_game(_world, _referee, _store, new=new)
    except SaveError:
        _game = open_game(_world, _referee, _store, new=True)
    if _game.state.ended:
        _store.archive_if_ended(_game.state, _game.turns, _game.story)
    _flavor = None
    return _game


def _live_bundle() -> SaveBundle:
    game = _current()
    return SaveBundle(
        world_title=_world.title,
        started_at=_store.started_at,
        updated_at=_store.started_at,
        turns=game.turns,
        story=game.story,
        state=game.state,
    )


def _current() -> Game:
    return _game or _boot()


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/game")
def get_game():
    game = _current()
    return jsonify(snapshot(_world, game, _flavor))


@app.post("/api/turn")
def post_turn():
    global _flavor
    game = _current()
    if game.state.ended:
        return jsonify(snapshot(_world, game)), 200
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    kind = str(payload.get("kind") or "text")
    if kind not in {"text", "button"}:
        kind = "text"
    if not text:
        return jsonify({"error": "empty"}), 400
    result = game.submit(text, input_kind=kind)
    _flavor = result.get("flavor")
    return jsonify(snapshot(_world, game, _flavor))


@app.post("/api/new")
def post_new():
    game = _boot(new=True)
    return jsonify(snapshot(_world, game))


@app.get("/api/stories")
def get_stories():
    _current()
    if _game.state.ended:
        _store.archive_if_ended(_game.state, _game.turns, _game.story)
    return jsonify({"stories": _store.list_stories()})


@app.get("/api/stories/<story_id>")
def get_story(story_id: str):
    _current()
    if story_id == "current":
        return jsonify(story_detail(_world, _live_bundle()))
    try:
        bundle = _store.load_story(story_id)
    except SaveError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(story_detail(_world, bundle))


def main() -> None:
    _boot()
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
