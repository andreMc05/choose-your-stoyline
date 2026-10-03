from __future__ import annotations

from pathlib import Path

from questions import build_jev_state
from referee import Referee
from resolver import apply_exit, resolve
from save import SaveStore
from world import TurnLog, World, load_world, new_player


class Game:
    def __init__(self, world: World, referee: Referee, store: SaveStore | None = None):
        self.world = world
        self.referee = referee
        self.store = store
        self.state = new_player(world)
        self.turns: list[TurnLog] = []
        self.story: list[str] = []
        self._append_story(world.nodes[world.start_node].passage)

    @classmethod
    def restore(cls, world: World, referee: Referee, store: SaveStore) -> Game:
        bundle = store.load()
        game = cls(world, referee, store=store)
        game.state = bundle.state
        game.turns = bundle.turns
        game.story = bundle.story or [world.nodes[world.start_node].passage.strip()]
        return game

    def persist(self) -> None:
        if self.store:
            self.store.write(self.state, self.turns, self.story)

    def current_passage(self) -> str:
        if self.state.ended and self.state.ending_id:
            return self.world.endings[self.state.ending_id].passage
        return self.world.nodes[self.state.node_id].passage

    def _append_story(self, text: str) -> None:
        self.story.append(text.strip())

    def submit(self, raw: str, input_kind: str = "text") -> dict:
        if self.state.ended:
            return {"ended": True, "ending_id": self.state.ending_id}

        node = self.world.nodes[self.state.node_id]
        player_input = raw.strip()
        jev_state = build_jev_state(self.world, node, self.state, player_input)
        result = self.referee.interpret(node, self.state, jev_state)

        choice = result.exit.choice
        top_prob = result.exit.probabilities.get(choice, 0.0)
        nouls = {k: v.noul for k, v in result.nouls.items()}
        scores = {k: v.score for k, v in result.scores.items()}

        decision = resolve(
            self.world,
            node,
            self.state,
            choice,
            result.exit.confidence,
            top_prob,
            nouls,
        )

        resolved_id = decision.exit.id if decision.exit else "unmapped"
        overrode = decision.overrode or (decision.exit is not None and decision.exit.id != choice)

        if not decision.stay and decision.exit is not None:
            self.state = apply_exit(self.world, decision.exit, self.state)
            self.state.turn += 1
            self._append_story(self.current_passage())
            flavor = None
        else:
            self.state.turn += 1
            flavor = decision.flavor

        log = TurnLog(
            turn=self.state.turn,
            node_id=node.id,
            input_kind=input_kind,  # type: ignore[arg-type]
            player_input=player_input,
            resolved_exit=resolved_id,
            jev_choice=choice,
            jev_confidence=result.exit.confidence,
            jev_probs=result.exit.probabilities,
            nouls=nouls,
            scores=scores,
            resolver_overrode=overrode,
            stay_on_node=decision.stay,
            flags_after=dict(self.state.flags),
            inventory_after=list(self.state.inventory),
            metrics_after=dict(self.state.metrics),
            hp_after=self.state.hp,
            node_after=self.state.node_id if not decision.stay else node.id,
            ending_id=self.state.ending_id,
        )
        self.turns.append(log)
        self.persist()

        return {
            "stay": decision.stay,
            "reason": decision.reason,
            "flavor": flavor,
            "resolved_exit": resolved_id,
            "overrode": overrode,
            "ended": self.state.ended,
            "ending_id": self.state.ending_id,
            "state": self.state,
            "log": log,
        }


def open_game(world: World, referee: Referee, store: SaveStore, *, new: bool = False) -> Game:
    if new:
        store.clear()
        return Game(world, referee, store=store)
    if store.exists():
        return Game.restore(world, referee, store)
    return Game(world, referee, store=store)


def boot(referee: Referee | None = None) -> Game:
    from referee import make_referee

    world = load_world()
    store = SaveStore(Path(__file__).parent / "saves", world)
    return open_game(world, referee or make_referee(), store)
