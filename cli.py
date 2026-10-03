#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from engine import Game, open_game
from referee import make_referee
from render import parse_input, render_node, render_status
from save import SAVE_VERSION, SaveError, SaveStore
from world import load_world


def main() -> None:
    parser = argparse.ArgumentParser(description="Night Tide")
    parser.add_argument("--new", action="store_true", help="wipe save and start over")
    args = parser.parse_args()

    saves = Path(__file__).parent / "saves"
    saves.mkdir(exist_ok=True)
    world = load_world()
    store = SaveStore(saves, world)
    referee = make_referee()

    if args.new:
        game = open_game(world, referee, store, new=True)
        print("New game.")
    elif store.exists():
        try:
            game = open_game(world, referee, store)
        except SaveError as exc:
            print(f"Could not load save: {exc}")
            print("Pass --new to start over.")
            return
        print(
            f"Restored {len(game.turns)} turn(s) "
            f"(save v{SAVE_VERSION}). Jev was not called."
        )
    else:
        game = open_game(world, referee, store)

    print(f"{world.title}")
    print("Type a number, free text, or quit. status / new also work.\n")

    while True:
        print(render_status(world, game.state))
        print(render_node(world, game.state))
        if game.state.ended:
            game.persist()
            print(f"\nSave written to {store.path}")
            print(f"Story: {saves / 'story.txt'}")
            break
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            game.persist()
            print("\nPaused. Resume with: python3 cli.py")
            break
        if not raw:
            continue
        lower = raw.lower()
        if lower in {"quit", "exit", "q"}:
            game.persist()
            print("Paused. Resume with: python3 cli.py")
            break
        if lower == "status":
            continue
        if lower == "new":
            store.clear()
            game = Game(world, referee, store=store)
            print("New game.")
            continue
        utterance, kind = parse_input(world, game.state, raw)
        result = game.submit(utterance, input_kind=kind)
        if result.get("stay") and result.get("flavor"):
            print(f"\n{result['flavor']}")


if __name__ == "__main__":
    main()
