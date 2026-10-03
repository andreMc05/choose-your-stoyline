from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from world import PlayerState, TurnLog, World


GAME_ID = "night_tide"
SAVE_VERSION = 1


class SaveError(Exception):
    pass


class SaveManifest(BaseModel):
    record: Literal["save"] = "save"
    save_version: int
    game_id: str
    world_title: str
    started_at: str
    updated_at: str
    turn_count: int = 0
    node_id: str
    ended: bool = False
    ending_id: str | None = None


class SaveBundle(BaseModel):
    record: Literal["save"] = "save"
    save_version: int = SAVE_VERSION
    game_id: str = GAME_ID
    world_title: str
    started_at: str
    updated_at: str
    turns: list[TurnLog] = Field(default_factory=list)
    story: list[str] = Field(default_factory=list)
    state: PlayerState


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_path(saves_dir: Path) -> Path:
    return saves_dir / "game.json"


def v0_log_path(saves_dir: Path) -> Path:
    return saves_dir / "turns.jsonl"


class SaveStore:
    def __init__(self, saves_dir: Path, world: World):
        self.saves_dir = saves_dir
        self.world = world
        self.path = save_path(saves_dir)
        self.started_at = _now()

    def exists(self) -> bool:
        return self.path.exists() or (
            v0_log_path(self.saves_dir).exists() and v0_log_path(self.saves_dir).stat().st_size > 0
        )

    def clear(self) -> None:
        self.started_at = _now()
        for name in ("game.json", "turns.jsonl", "story.txt"):
            p = self.saves_dir / name
            if p.exists():
                p.unlink()

    def write(self, state: PlayerState, turns: list[TurnLog], story: list[str]) -> SaveBundle:
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        bundle = SaveBundle(
            save_version=SAVE_VERSION,
            game_id=GAME_ID,
            world_title=self.world.title,
            started_at=self.started_at,
            updated_at=_now(),
            turns=turns,
            story=story,
            state=state,
        )
        if self.path.exists():
            try:
                prev = SaveBundle.model_validate_json(self.path.read_text(encoding="utf-8"))
                bundle.started_at = prev.started_at
            except Exception:
                pass
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self.path)
        story_path = self.saves_dir / "story.txt"
        story_path.write_text("\n\n".join(story) + "\n", encoding="utf-8")
        return bundle

    def load(self) -> SaveBundle:
        raw_path = self.path
        if raw_path.exists():
            data = _read_json(raw_path)
            version = int(data.get("save_version", SAVE_VERSION))
            bundle = _migrate(data, version, self.world)
            if bundle.save_version != SAVE_VERSION:
                self.write(bundle.state, bundle.turns, bundle.story)
            self.started_at = bundle.started_at
            return bundle

        v0 = v0_log_path(self.saves_dir)
        if v0.exists() and v0.stat().st_size > 0:
            bundle = _migrate_v0_jsonl(v0, self.world)
            backup = self.saves_dir / "turns.v0.jsonl"
            if not backup.exists():
                v0.replace(backup)
            else:
                v0.unlink()
            self.write(bundle.state, bundle.turns, bundle.story)
            self.started_at = bundle.started_at
            return bundle

        raise SaveError("no save to load")


def _read_json(path: Path) -> dict[str, Any]:
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SaveError(f"save is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise SaveError(f"save root must be an object: {path}")
    return data


def _migrate(data: dict[str, Any], version: int, world: World) -> SaveBundle:
    if version > SAVE_VERSION:
        raise SaveError(
            f"save_version {version} is newer than this build ({SAVE_VERSION}). "
            "Update the game before loading this file."
        )
    if version < 1:
        raise SaveError(f"unknown save_version {version}")
    if data.get("game_id") and data["game_id"] != GAME_ID:
        raise SaveError(f"save is for game {data['game_id']!r}, not {GAME_ID!r}")

    if version == 1:
        return SaveBundle.model_validate(data)

    # Future: version == 2: return migrate_v1_to_v2(data)
    raise SaveError(f"no migrator for save_version {version}")


def _migrate_v0_jsonl(path: Path, world: World) -> SaveBundle:
    """Bare TurnLog jsonl written before save versioning."""
    from restore import replay

    turns: list[TurnLog] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        turns.append(TurnLog.model_validate_json(line))
    state, story = replay(world, turns)
    story_file = path.parent / "story.txt"
    if story_file.exists():
        chunks = [c.strip() for c in story_file.read_text(encoding="utf-8").split("\n\n") if c.strip()]
        if chunks:
            story = chunks
    return SaveBundle(
        save_version=SAVE_VERSION,
        game_id=GAME_ID,
        world_title=world.title,
        started_at=_now(),
        updated_at=_now(),
        turns=turns,
        story=story,
        state=state,
    )
