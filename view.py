from __future__ import annotations

import re

from engine import Game
from save import SaveBundle, archive_id_for
from world import TurnLog, World, visible_exits


def _prose(text: str) -> str:
    """Join YAML single-newline wraps; keep blank-line paragraphs."""
    return re.sub(r"(?<!\n)\n(?!\n)", " ", text.strip())


def story_entries(story: list[str], turns: list[TurnLog]) -> list[dict]:
    entries: list[dict] = []
    passages = [_prose(chunk) for chunk in story if chunk and chunk.strip()]
    index = 0
    if passages:
        entries.append({"kind": "passage", "text": passages[0]})
        index = 1
    for log in turns:
        line = (log.player_input or "").strip()
        if line and not (log.stay_on_node and line.isdigit()):
            entries.append({"kind": "action", "text": line, "stay": log.stay_on_node})
        if not log.stay_on_node and index < len(passages):
            entries.append({"kind": "passage", "text": passages[index]})
            index += 1
    while index < len(passages):
        entries.append({"kind": "passage", "text": passages[index]})
        index += 1
    return entries


def story_detail(world: World, bundle: SaveBundle) -> dict:
    ending = None
    ending_id = bundle.state.ending_id
    if bundle.state.ended and ending_id and ending_id in world.endings:
        spec = world.endings[ending_id]
        ending = {"id": spec.id, "kind": spec.kind, "passage": _prose(spec.passage)}
    return {
        "id": archive_id_for(bundle.started_at),
        "title": bundle.world_title,
        "started_at": bundle.started_at,
        "updated_at": bundle.updated_at,
        "turn": bundle.state.turn,
        "ended": bundle.state.ended,
        "ending": ending,
        "entries": story_entries(bundle.story, bundle.turns),
    }


def snapshot(world: World, game: Game, flavor: str | None = None) -> dict:
    state = game.state
    metrics = [
        {
            "id": key,
            "label": spec.label or key,
            "value": state.metrics.get(key, 0),
            "min": spec.min,
            "max": spec.max,
        }
        for key, spec in world.metrics.items()
    ]
    inventory = [
        {"id": item_id, "name": world.items[item_id].name}
        for item_id in state.inventory
        if item_id in world.items
    ]
    base = {
        "title": world.title,
        "ended": state.ended,
        "turn": state.turn,
        "hp": state.hp,
        "metrics": metrics,
        "inventory": inventory,
        "flavor": flavor,
        "story": [_prose(chunk) for chunk in game.story],
        "log": story_entries(game.story, game.turns),
    }
    if state.ended and state.ending_id:
        ending = world.endings[state.ending_id]
        return {
            **base,
            "ending": {
                "id": ending.id,
                "kind": ending.kind,
                "passage": _prose(ending.passage),
            },
            "node": None,
            "exits": [],
        }
    node = world.nodes[state.node_id]
    return {
        **base,
        "ending": None,
        "node": {
            "id": node.id,
            "title": node.title,
            "passage": _prose(node.passage),
        },
        "exits": [
            {"id": exit.id, "label": exit.button_label}
            for exit in visible_exits(node)
        ],
    }
