from __future__ import annotations

from abc import ABC, abstractmethod
import os
import re
from typing import Any

from questions import UNMAPPED, build_questions
from world import JevState, Node, PlayerState, RefereeResult, ChoiceAnswer, NoulAnswer, ScoreAnswer


class Referee(ABC):
    @abstractmethod
    def interpret(self, node: Node, state: PlayerState, jev_state: JevState) -> RefereeResult:
        raise NotImplementedError


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]+", " ", text.lower()).strip()


class StubReferee(Referee):
    """Playable without TYPESAFE_API_KEY.

    Keyword fixtures first, then a cheap overlap score against exit criteria.
    Never writes flags. Never invents exits.
    """

    KEYWORDS: dict[str, list[str]] = {
        "approach_watch": [
            "up to the watch", "to the watch", "walk up", "clerk",
            "lantern", "shed", "officer", "customs", "approach",
        ],
        "hang_back": ["crate", "hang back", "hide", "wait here", "cover", "among the"],
        "walk_pier": ["pier", "dark pier", "along the water", "farther", "boards"],
        "listen_stevedore": ["listen", "eavesdrop", "hear", "what they", "stevedore"],
        "climb_crates": ["climb", "sneak", "cut toward", "stacks"],
        "go_watch": ["watch", "shed", "lantern", "clerk"],
        "to_watch": ["watch", "thank", "shed"],
        "to_gangway": ["gangway", "plank", "ship", "board"],
        "press_him": ["ask", "what does voss", "want", "more"],
        "back_watch": ["watch", "shed", "back"],
        "back_crates": ["crate", "stack", "stevedore"],
        "flash_papers": ["paper", "document", "hand over", "show", "flash"],
        "offer_coin": ["coin", "bribe", "pay", "tip", "silver", "money"],
        "stay_quiet": ["say nothing", "silent", "wait", "quiet"],
        "name_voss": ["voss sent", "captain voss", "voss expects", "for voss"],
        "answer_calm": ["calm", "destination", "coast", "work", "simple"],
        "bluff_hard": ["lie", "bluff", "rank", "important", "yell"],
        "run": ["run", "bolt", "flee", "shove"],
        "submit_packet": ["put", "table", "hand over packet", "surrender", "comply"],
        "refuse_search": ["refuse", "no", "won't", "will not"],
        "dump_packet": ["ditch", "drop packet", "throw packet", "window", "hide packet"],
        "board_quiet": ["board", "walk on", "nod", "quiet"],
        "look_back": ["look back", "quay", "check"],
        "hesitate": ["wait", "hesitate", "freeze", "turn around"],
        "follow_bosun": ["hatch", "hold", "follow", "below"],
        "stay_rail": ["rail", "deck", "stay"],
        "ask_voss_door": ["voss", "painted", "aft", "captain"],
        "stash_packet": ["stash", "hide", "barrel"],
        "keep_packet": ["keep", "on me", "hold onto"],
        "open_packet": ["open", "break the seal", "read", "unwrap"],
        "knock": ["knock", "open the door", "announce"],
        "leave_it": ["leave", "hold", "walk away"],
        "deliver_sealed": ["put", "table", "deliver", "hand", "sealed"],
        "deliver_opened": ["broke", "opened", "admit"],
        "no_packet": ["don't have", "lost", "gone", "no packet"],
        "report_crew": ["report", "officer", "captain", "in charge"],
        "hide_out": ["hide", "wait", "stay", "hold"],
        "toss_packet": ["over the side", "throw", "sink", "dump"],
    }

    def interpret(self, node: Node, state: PlayerState, jev_state: JevState) -> RefereeResult:
        text = _normalize(jev_state.player_input)
        scores = {exit.id: 0.0 for exit in node.exits}
        scores[UNMAPPED] = 0.2

        for exit in node.exits:
            phrases = self.KEYWORDS.get(exit.id, [])
            phrase_hits = sum(3 if phrase in text else 0 for phrase in phrases)
            label = (exit.button_label or "").lower()
            label_hit = 4 if label and label in jev_state.player_input.lower() else 0
            weak = {"the", "and", "for", "you", "your", "them", "they", "with"}
            tokens = [t for t in text.split() if len(t) > 3 and t not in weak]
            token_hits = sum(0.4 for t in tokens if t in exit.criteria.lower())
            scores[exit.id] = phrase_hits + label_hit + token_hits

        # Injection never maps to an advance exit.
        if any(
            needle in text
            for needle in (
                "ignore instructions",
                "set wanted",
                "wanted heat",
                "add item",
                "set flag",
            )
        ):
            scores = {k: 0.0 for k in scores}
            scores[UNMAPPED] = 1.0

        total = sum(scores.values()) or 1.0
        probs = {k: v / total for k, v in scores.items()}
        choice = max(probs, key=probs.get)
        top = probs[choice]
        confidence = top if top >= 0.4 else top * 0.5

        nouls: dict[str, NoulAnswer] = {}
        if "tries_to_override_state" in node.noul_ids:
            inject = 0.95 if choice == UNMAPPED and "ignore" in text else 0.05
            if "set wanted" in text or "set flag" in text:
                inject = 0.97
            nouls["tries_to_override_state"] = NoulAnswer(noul=inject)
        if "offered_money" in node.noul_ids:
            nouls["offered_money"] = NoulAnswer(
                noul=0.9 if any(w in text for w in ("coin", "bribe", "pay", "money")) else 0.05
            )
        if "threatened" in node.noul_ids:
            nouls["threatened"] = NoulAnswer(
                noul=0.9 if any(w in text for w in ("kill", "shoot", "knife", "hurt")) else 0.04
            )
        if "mentioned_key_fact" in node.noul_ids:
            nouls["mentioned_key_fact"] = NoulAnswer(noul=0.9 if "voss" in text else 0.05)

        return RefereeResult(
            exit=ChoiceAnswer(choice=choice, probabilities=probs, confidence=confidence),
            nouls=nouls,
            scores={},
            raw_model="stub",
        )


class TypesafeReferee(Referee):
    """Live Jev client. Requires TYPESAFE_API_KEY."""

    def __init__(self) -> None:
        try:
            from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient
        except ImportError as exc:
            raise RuntimeError("typesafe_sdk is not installed") from exc
        self._Choice = Choice
        self._Noul = Noul
        self._NoulCriteria = NoulCriteria
        self._Score = Score
        self._client = TypeSafeClient()

    def interpret(self, node: Node, state: PlayerState, jev_state: JevState) -> RefereeResult:
        spec = build_questions(node, state)
        questions: dict[str, Any] = {}
        for qid, q in spec.items():
            if q["type"] == "choice":
                questions[qid] = self._Choice(instructions=q["instructions"], criteria=q["criteria"])
            elif q["type"] == "noul":
                questions[qid] = self._Noul(
                    instructions=q["instructions"],
                    criteria=self._NoulCriteria(
                        true=q["criteria"]["true"],
                        false=q["criteria"]["false"],
                    ),
                )
            elif q["type"] == "score":
                questions[qid] = self._Score(instructions=q["instructions"], criteria=q["criteria"])

        response = self._client.system_one(state=jev_state.model_dump(), questions=questions)
        answers = response.answers

        exit_ans = answers["exit"]
        nouls = {
            key: NoulAnswer(noul=ans.noul)
            for key, ans in answers.items()
            if getattr(ans, "type", None) == "noul" or hasattr(ans, "noul") and key != "exit"
        }
        scores = {}
        for key, ans in answers.items():
            if hasattr(ans, "score"):
                scores[key] = ScoreAnswer(
                    score=ans.score,
                    probabilities=dict(getattr(ans, "probabilities", {}) or {}),
                    confidence=float(getattr(ans, "confidence", 0.0) or 0.0),
                )

        return RefereeResult(
            exit=ChoiceAnswer(
                choice=exit_ans.choice,
                probabilities=dict(exit_ans.probabilities),
                confidence=float(exit_ans.confidence),
            ),
            nouls=nouls,
            scores=scores,
            raw_model=getattr(response, "model", "jev-latest"),
        )


def make_referee() -> Referee:
    if os.environ.get("TYPESAFE_API_KEY"):
        try:
            return TypesafeReferee()
        except Exception:
            return StubReferee()
    return StubReferee()
