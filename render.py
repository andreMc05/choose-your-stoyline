from __future__ import annotations

from world import World, PlayerState, visible_exits, is_ending


def render_status(world: World, state: PlayerState) -> str:
    inv = ", ".join(world.items[i].name for i in state.inventory) or "nothing"
    metrics = "  ".join(
        f"{world.metrics[k].label or k} {state.metrics.get(k, 0)}"
        for k in world.metrics
    )
    return f"HP {state.hp}   {metrics}\nInventory: {inv}"


def render_node(world: World, state: PlayerState) -> str:
    if state.ended and state.ending_id:
        ending = world.endings[state.ending_id]
        return f"\n== {ending.kind.upper()} ==\n{ending.passage.strip()}\n"
    node = world.nodes[state.node_id]
    lines = [f"\n-- {node.title} --", node.passage.strip(), ""]
    for i, exit in enumerate(visible_exits(node), start=1):
        lines.append(f"  {i}. {exit.button_label}")
    lines.append("  or type what you do.")
    return "\n".join(lines)


def parse_input(world: World, state: PlayerState, raw: str) -> tuple[str, str]:
    """Return (utterance, kind). Numbered input becomes the button label text."""
    text = raw.strip()
    if state.ended or is_ending(world, state.node_id):
        return text, "text"
    if text.isdigit():
        node = world.nodes[state.node_id]
        options = visible_exits(node)
        idx = int(text) - 1
        if 0 <= idx < len(options):
            label = options[idx].button_label or options[idx].id
            return label, "button"
    return text, "text"
