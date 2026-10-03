#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter

from questions import UNMAPPED, build_jev_state
from referee import StubReferee
from resolver import requirements_ok, resolve
from world import PlayerState, load_world, new_player


def state_for(world, node_id: str) -> PlayerState:
    state = new_player(world)
    state.node_id = node_id
    # Parser-only Voss tests assume the early flag was set two rooms ago.
    if node_id in {"watch_stoop", "deck", "cabin_door", "voss_cabin"}:
        state.flags["heard_voss"] = True
    return state


def main() -> None:
    world = load_world()
    ref = StubReferee()
    confusion: list[tuple[str, str, str, str]] = []
    tallies = Counter()

    for case in world.tests:
        node = world.nodes[case.node_id]
        state = state_for(world, case.node_id)
        jev_state = build_jev_state(world, node, state, case.utterance)
        result = ref.interpret(node, state, jev_state)
        choice = result.exit.choice
        top = result.exit.probabilities.get(choice, 0.0)
        nouls = {k: v.noul for k, v in result.nouls.items()}
        decision = resolve(world, node, state, choice, result.exit.confidence, top, nouls)

        got = UNMAPPED if decision.stay and choice == UNMAPPED else (
            UNMAPPED if decision.stay and decision.reason in {"unmapped", "low_confidence"} else
            (decision.exit.id if decision.exit else UNMAPPED)
        )
        # Injection must stay unmapped even if stub labeled something else.
        if decision.reason == "injection_ignored":
            got = UNMAPPED

        ok = got == case.expected_exit
        tallies["ok" if ok else "miss"] += 1
        if not ok:
            confusion.append((case.node_id, case.utterance, case.expected_exit, got))

        # Code must still reject missing-item exits.
        if got == "offer_coin":
            broke = state.model_copy(deep=True)
            broke.inventory = [i for i in broke.inventory if i != "silver_coin"]
            exit = next(e for e in node.exits if e.id == "offer_coin")
            assert not requirements_ok(exit.requirements, broke)

    print(f"tests {tallies['ok'] + tallies['miss']}  pass {tallies['ok']}  miss {tallies['miss']}")
    if confusion:
        print("\nconfusion pairs (node | utterance | expected -> got)")
        for node_id, utt, exp, got in confusion:
            print(f"  {node_id:16} | {utt!r:48} | {exp} -> {got}")


if __name__ == "__main__":
    main()
