from __future__ import annotations

from pathlib import Path

from resolver import apply_exit, find_exit
from world import PlayerState, TurnLog, World, is_ending, new_player


def read_turns(path: Path) -> list[TurnLog]:
    if not path.exists():
        return []
    turns: list[TurnLog] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        turns.append(TurnLog.model_validate_json(line))
    return turns


def replay(world: World, turns: list[TurnLog]) -> tuple[PlayerState, list[str]]:
    """Rebuild state from logged resolved exits. Never calls Jev."""
    state = new_player(world)
    story = [world.nodes[world.start_node].passage.strip()]
    if not turns:
        return state, story

    for log in turns:
        state.turn = log.turn
        if log.stay_on_node or log.resolved_exit in {"unmapped", ""}:
            _apply_snapshot(world, state, log)
            if not log.node_after:
                state.node_id = log.node_id
            continue
        node = world.nodes[log.node_id]
        exit = find_exit(node, log.resolved_exit)
        if exit is None:
            _apply_snapshot(world, state, log)
            continue
        state = apply_exit(world, exit, state)
        state.turn = log.turn
        _apply_snapshot(world, state, log)
        dest = state.node_id
        if is_ending(world, dest):
            story.append(world.endings[dest].passage.strip())
        else:
            story.append(world.nodes[dest].passage.strip())
    return state, story


def _apply_snapshot(world: World, state: PlayerState, log: TurnLog) -> None:
    # Snapshots are the save. Effects replay is for story order; snapshot wins.
    state.flags = dict(log.flags_after)
    state.inventory = list(log.inventory_after)
    state.metrics = dict(log.metrics_after)
    state.hp = log.hp_after
    if log.ending_id:
        state.ended = True
        state.ending_id = log.ending_id
        state.node_id = log.ending_id
        return
    if log.node_after:
        state.node_id = log.node_after
        if is_ending(world, log.node_after):
            state.ended = True
            state.ending_id = log.node_after


def write_story(path: Path, story: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(story) + "\n", encoding="utf-8")
