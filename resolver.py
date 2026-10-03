from __future__ import annotations

from dataclasses import dataclass

from questions import UNMAPPED
from world import Exit, Node, PlayerState, Requirement, World, is_ending


CONFIDENCE_FLOOR = 0.55
PROB_FLOOR = 0.55
OVERRIDE_NOUL_FLOOR = 0.7


@dataclass
class ResolveDecision:
    stay: bool
    exit: Exit | None
    reason: str
    overrode: bool
    next_node: str | None
    flavor: str | None = None


def requirements_ok(req: Requirement, state: PlayerState) -> bool:
    inv = set(state.inventory)
    for item in req.has_items:
        if item not in inv:
            return False
    for item in req.lacks_items:
        if item in inv:
            return False
    for key, value in req.flags_eq.items():
        if state.flags.get(key) != value:
            return False
    for key, value in req.flags_neq.items():
        if state.flags.get(key) == value:
            return False
    for key, value in req.metrics_gte.items():
        if state.metrics.get(key, 0) < value:
            return False
    for key, value in req.metrics_lte.items():
        if state.metrics.get(key, 0) > value:
            return False
    for key, value in req.metrics_eq.items():
        if state.metrics.get(key, 0) != value:
            return False
    if req.min_hp is not None and state.hp < req.min_hp:
        return False
    return True


def clamp_metric(world: World, name: str, value: int) -> int:
    spec = world.metrics[name]
    return max(spec.min, min(spec.max, value))


def apply_exit(world: World, exit: Exit, state: PlayerState) -> PlayerState:
    new = state.model_copy(deep=True)
    for key, value in exit.effects.set_flags.items():
        new.flags[key] = value
    for item in exit.effects.add_items:
        if item not in world.items:
            raise ValueError(f"Unknown item in effects: {item}")
        if item not in new.inventory:
            new.inventory.append(item)
    for item in exit.effects.remove_items:
        new.inventory = [i for i in new.inventory if i != item]
    new.hp += exit.effects.hp_delta
    for key, delta in exit.effects.metrics_delta.items():
        if key not in world.metrics:
            raise ValueError(f"Unknown metric in effects: {key}")
        new.metrics[key] = clamp_metric(world, key, new.metrics.get(key, 0) + delta)

    dest = exit.next_node
    # Heat gate on hide_out: same action, code picks ending.
    if exit.id == "hide_out" and exit.fail_node and new.metrics.get("wanted_heat", 0) >= 2:
        dest = exit.fail_node
    new.node_id = dest
    if is_ending(world, dest):
        new.ended = True
        new.ending_id = dest
    return new


def find_exit(node: Node, exit_id: str) -> Exit | None:
    for exit in node.exits:
        if exit.id == exit_id:
            return exit
    return None


def resolve(
    world: World,
    node: Node,
    state: PlayerState,
    choice_id: str,
    confidence: float,
    top_prob: float,
    nouls: dict[str, float],
) -> ResolveDecision:
    if nouls.get("tries_to_override_state", 0.0) >= OVERRIDE_NOUL_FLOOR:
        return ResolveDecision(
            stay=True,
            exit=None,
            reason="injection_ignored",
            overrode=True,
            next_node=None,
            flavor=node.fail_flavor,
        )

    if choice_id == UNMAPPED or choice_id not in {e.id for e in node.exits}:
        return ResolveDecision(
            stay=True,
            exit=None,
            reason="unmapped",
            overrode=False,
            next_node=None,
            flavor=node.fail_flavor,
        )

    if confidence < CONFIDENCE_FLOOR or top_prob < PROB_FLOOR:
        return ResolveDecision(
            stay=True,
            exit=None,
            reason="low_confidence",
            overrode=False,
            next_node=None,
            flavor=node.clarify_prompt,
        )

    exit = find_exit(node, choice_id)
    assert exit is not None

    if not requirements_ok(exit.requirements, state):
        if exit.fail_node and exit.id != "hide_out":
            return ResolveDecision(
                stay=False,
                exit=exit,
                reason="requirements_fail_node",
                overrode=True,
                next_node=exit.fail_node,
                flavor=None,
            )
        return ResolveDecision(
            stay=True,
            exit=exit,
            reason="requirements_rejected",
            overrode=True,
            next_node=None,
            flavor=node.fail_flavor,
        )

    return ResolveDecision(
        stay=False,
        exit=exit,
        reason="advance",
        overrode=False,
        next_node=exit.next_node,
    )
