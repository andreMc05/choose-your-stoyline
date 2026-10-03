from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


class MetricDef(BaseModel):
    min: int = 0
    max: int = 3
    default: int = 0
    label: str | None = None


class Requirement(BaseModel):
    has_items: list[str] = Field(default_factory=list)
    lacks_items: list[str] = Field(default_factory=list)
    flags_eq: dict[str, Any] = Field(default_factory=dict)
    flags_neq: dict[str, Any] = Field(default_factory=dict)
    metrics_gte: dict[str, int] = Field(default_factory=dict)
    metrics_lte: dict[str, int] = Field(default_factory=dict)
    metrics_eq: dict[str, int] = Field(default_factory=dict)
    min_hp: int | None = None


class Effects(BaseModel):
    set_flags: dict[str, Any] = Field(default_factory=dict)
    add_items: list[str] = Field(default_factory=list)
    remove_items: list[str] = Field(default_factory=list)
    hp_delta: int = 0
    metrics_delta: dict[str, int] = Field(default_factory=dict)


class Exit(BaseModel):
    id: str
    button_label: str | None = None
    visible: bool = True
    criteria: str
    requirements: Requirement = Field(default_factory=Requirement)
    effects: Effects = Field(default_factory=Effects)
    next_node: str
    fail_node: str | None = None


class Node(BaseModel):
    id: str
    title: str
    passage: str
    tags: list[str] = Field(default_factory=list)
    exits: list[Exit]
    fail_flavor: str
    clarify_prompt: str
    noul_ids: list[str] = Field(default_factory=list)
    score_ids: list[str] = Field(default_factory=list)


class Item(BaseModel):
    id: str
    name: str
    description: str


class Ending(BaseModel):
    id: str
    kind: Literal["win", "lose", "bittersweet"]
    passage: str


class TestCase(BaseModel):
    node_id: str
    utterance: str
    expected_exit: str
    notes: str = ""


class World(BaseModel):
    title: str
    start_node: str
    hp_default: int = 3
    metrics: dict[str, MetricDef]
    items: dict[str, Item]
    endings: dict[str, Ending]
    nodes: dict[str, Node]
    starting_inventory: list[str]
    starting_flags: dict[str, Any]
    tests: list[TestCase] = Field(default_factory=list)


class PlayerState(BaseModel):
    node_id: str
    inventory: list[str]
    flags: dict[str, Any]
    hp: int = 3
    metrics: dict[str, int] = Field(default_factory=dict)
    turn: int = 0
    ended: bool = False
    ending_id: str | None = None


class JevState(BaseModel):
    node_id: str
    passage: str
    visible_options: list[str]
    inventory: list[str]
    flags: dict[str, Any]
    metrics: dict[str, int]
    player_input: str


class ChoiceAnswer(BaseModel):
    choice: str
    probabilities: dict[str, float]
    confidence: float


class ScoreAnswer(BaseModel):
    score: float
    probabilities: dict[str, float]
    confidence: float
    legend: dict[str, str] | None = None


class NoulAnswer(BaseModel):
    noul: float


class RefereeResult(BaseModel):
    exit: ChoiceAnswer
    nouls: dict[str, NoulAnswer] = Field(default_factory=dict)
    scores: dict[str, ScoreAnswer] = Field(default_factory=dict)
    raw_model: str | None = None


class TurnLog(BaseModel):
    turn: int
    node_id: str
    input_kind: Literal["button", "text"]
    player_input: str
    resolved_exit: str
    jev_choice: str
    jev_confidence: float
    jev_probs: dict[str, float]
    nouls: dict[str, float]
    scores: dict[str, float]
    resolver_overrode: bool
    stay_on_node: bool
    flags_after: dict[str, Any]
    inventory_after: list[str]
    metrics_after: dict[str, int]
    hp_after: int
    node_after: str | None = None
    ending_id: str | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_world(data_dir: Path | None = None) -> World:
    data_dir = data_dir or DATA
    raw_world = _load_yaml(data_dir / "world.yaml")
    raw_nodes = _load_yaml(data_dir / "nodes.yaml")
    tests_path = data_dir / "tests.yaml"
    raw_tests = _load_yaml(tests_path) if tests_path.exists() else {"tests": []}

    items = {
        item_id: Item(id=item_id, **spec)
        for item_id, spec in raw_world["items"].items()
    }
    endings = {
        ending_id: Ending(id=ending_id, **spec)
        for ending_id, spec in raw_world["endings"].items()
    }
    nodes: dict[str, Node] = {}
    for node_id, spec in raw_nodes["nodes"].items():
        nodes[node_id] = Node(id=node_id, **spec)

    tests = [TestCase(**row) for row in raw_tests.get("tests", [])]

    return World(
        title=raw_world["title"],
        start_node=raw_world["start_node"],
        hp_default=raw_world.get("hp_default", 3),
        metrics={k: MetricDef(**v) for k, v in raw_world["metrics"].items()},
        items=items,
        endings=endings,
        nodes=nodes,
        starting_inventory=list(raw_world["starting_inventory"]),
        starting_flags=dict(raw_world["starting_flags"]),
        tests=tests,
    )


def new_player(world: World) -> PlayerState:
    return PlayerState(
        node_id=world.start_node,
        inventory=list(world.starting_inventory),
        flags=dict(world.starting_flags),
        hp=world.hp_default,
        metrics={k: d.default for k, d in world.metrics.items()},
        turn=0,
    )


def is_ending(world: World, node_id: str) -> bool:
    return node_id in world.endings


def visible_exits(node: Node) -> list[Exit]:
    return [e for e in node.exits if e.visible and e.button_label]
