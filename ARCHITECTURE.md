# Night Tide architecture

CLI choose-your-own-adventure. **Jev labels intent. Code owns truth.**

The referee (Jev live, or `StubReferee`) only maps player text to an exit id. Flags, inventory, HP, metrics, destinations, endings, and saves are applied in Python. The model never writes state.

Story graph and ending rules live in [`GRAPH.md`](GRAPH.md). This file is the code map.

## Runtime

System `python3` on this machine is 3.9 and cannot import the models (`str | None`). Use the 3.13 venv:

```
.venv/bin/python cli.py          # restore saves/game.json
.venv/bin/python cli.py --new    # wipe and start over
.venv/bin/python eval_harness.py # stub referee vs data/tests.yaml
```

No `TYPESAFE_API_KEY` → `StubReferee`. Key set and `typesafe-sdk` importable → `TypesafeReferee`. Import failure falls back to stub. Groq is not wired.

## Ownership

| Layer | Owns | Must not |
|---|---|---|
| `data/world.yaml` | title, start, HP default, metrics, items, starting inventory/flags, endings | rooms or exits |
| `data/nodes.yaml` | rooms, prose, exits, noul/score ids | metric definitions |
| `data/tests.yaml` | eval utterances → expected exit | runtime state |
| `questions.py` | Jev question specs, noul/score catalogs, `UNMAPPED` | state mutation |
| `referee.py` | label utterance → `RefereeResult` | flags, inventory, HP, destinations |
| `resolver.py` | stay vs advance, requirements, thresholds | invent exits |
| `engine.py` | turn loop, story append, persist | interpret text |
| `save.py` / `restore.py` | versioned save, replay | call Jev |
| `render.py` / `cli.py` | display and input | game rules |

`nodes.yaml` prose is **LOCKED**. Do not rewrite canon passages in prompts or refactors.

## Turn pipeline

`cli.py` → `parse_input` → `Game.submit`:

1. Refuse if `state.ended`.
2. `build_jev_state` — passage, visible exit ids, inventory, flags, metrics, raw line. Visible exits are `visible and button_label`.
3. `referee.interpret` — returns one choice (always including `unmapped`), probabilities, confidence, optional nouls/scores.
4. `resolve` — stay or advance. See rules below.
5. On advance: `apply_exit` mutates a copy of state, increments turn, appends destination passage.
6. On stay: increment turn, print `fail_flavor` or `clarify_prompt`.
7. Append `TurnLog`, `persist` to `saves/game.json` + `saves/story.txt`.

Numbered CLI input becomes the button label and `input_kind=button`. Free text stays `text`.

```
player line
    → referee (label only)
    → resolve (gates)
    → apply_exit (state)   or stay + canned flavor
    → TurnLog + save
```

## Resolver rules

Constants in `resolver.py`: `CONFIDENCE_FLOOR = 0.55`, `PROB_FLOOR = 0.55`, `OVERRIDE_NOUL_FLOOR = 0.7`.

Checked in this order:

1. `tries_to_override_state` noul ≥ 0.7 → stay, `injection_ignored`, `fail_flavor`.
2. Choice is `unmapped` or not on this node → stay, `unmapped`, `fail_flavor`.
3. Confidence or top probability below floor → stay, `low_confidence`, `clarify_prompt`.
4. Requirements fail:
   - exit has `fail_node` and id is **not** `hide_out` → advance via that fail dest (`requirements_fail_node`, marked override).
   - else stay, `requirements_rejected`, `fail_flavor`.
5. Else advance to `next_node`.

**Scores are logged only.** `resolve` does not read `score_ids`.

**Hardcoded heat gate:** `apply_exit` reroutes `hide_out` to `fail_node` when `wanted_heat >= 2`. Jev only labels the hide action. Do not move that branch into YAML without changing code.

`overrode` is true if the resolver rejected/injected, or the applied exit id ≠ Jev's choice.

## Exits and requirements

Each exit: `id`, `criteria` (for Jev/stub), `next_node`, optional `button_label`, `visible`, `requirements`, `effects`, `fail_node`.

- Button exits: `visible: true` and a `button_label`.
- Parser-only: `visible: false`, `button_label: null`. Current: `name_voss`, `dump_packet`, `ask_voss_door`.
- Effects may `set_flags`, add/remove items, `hp_delta`, `metrics_delta` (clamped to metric min/max).
- Requirements: `has_items`, `lacks_items`, `flags_eq` / `flags_neq`, `metrics_*`, `min_hp`.
- `next_node` / `fail_node` may be a room id or an ending id from `world.yaml`. Ending dest sets `ended` and `ending_id`.

New exit ids need a `StubReferee.KEYWORDS` entry or the stub will only match via label/token overlap.

New `noul_ids` / `score_ids` on a node must exist in `NOUL_CATALOG` / `SCORE_CATALOG`.

## Saves

`saves/game.json` is save v1: manifest + `turns[]` + `story[]` + `state`. `game_id` must be `night_tide`. Newer `save_version` is refused. Writes are atomic (`game.json.tmp` then replace).

Load **does not call Jev**. `restore.replay` reapplies resolved exits for story order; **TurnLog snapshots win** for flags, inventory, metrics, HP, node, ending.

Bare `turns.jsonl` migrates once → `turns.v0.jsonl`. `cli.py --new` or in-game `new` deletes `game.json`, `turns.jsonl`, `story.txt`.

## Referee contract

`Referee.interpret(node, state, jev_state) -> RefereeResult`.

- Must pick an existing exit id or `unmapped`. Never invent exits.
- Must not mutate `state`.
- Stub: keyword fixtures, then label + token overlap vs `criteria`. Injection phrases force `unmapped`.
- Live: `build_questions` → TypeSafe System One `Choice` / `Noul` / `Score`.

## Eval

`eval_harness.py` runs `data/tests.yaml` through stub + resolver. Confusion pairs print as `node | utterance | expected -> got`. Extra assert: `offer_coin` still fails without `silver_coin`.

After changing exits, criteria, keywords, or resolver thresholds, run the harness.

## Module map

| File | Role |
|---|---|
| `world.py` | Pydantic models, `load_world`, `new_player`, `visible_exits` |
| `questions.py` | Jev payload + catalogs |
| `referee.py` | Stub + Typesafe + `make_referee` |
| `resolver.py` | Gates + `apply_exit` |
| `engine.py` | `Game.submit` / `restore` / `persist` |
| `render.py` | Status, node text, numbered input |
| `cli.py` | REPL |
| `save.py` | Envelope, migrate, write |
| `restore.py` | Deterministic replay |
| `eval_harness.py` | Stub accuracy |
