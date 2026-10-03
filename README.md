# Night Tide

## TL;DR

A riverfront courier job in the rain. You have forged papers, one coin, and a sealed packet that was not meant to get wet. Type a number or free text. The referee labels which exit you meant; the code owns flags, inventory, HP, and the save.

No API key required. Python 3.10+ (this repo’s `.venv` is 3.13).

```
.venv/bin/python web.py          # browser UI at http://127.0.0.1:5050
.venv/bin/python cli.py          # terminal
```

## Story

Night. The quay. Two berths down, a tramp steamer called the *Marrow* works against the tide. You were paid to get aboard with the packet still closed.

Customs has a lantern and a book. Stevedores know a name — Voss — if you linger to hear it. You can flash papers, spend the coin, stay quiet, or try a line the buttons do not offer.

Four endings:

- **Clean berth** — aboard, packet intact, heat low. Nobody looks twice.
- **Watched berth** — aboard, but someone will remember your face.
- **Detained** — the watch house. The ship leaves without you.
- **Packet gone** — free enough to watch the *Marrow* go. Whoever paid you will not pay twice.

Nerve, caution, and heat (0–3) move with what you do. The packet is the job.

## Setup

Needs **Python 3.10 or newer**. System `python3` on this machine is 3.9 and cannot import the models. Use 3.13 if you have it:

```
/usr/local/bin/python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

That installs `pydantic` and `PyYAML`. Leave `TYPESAFE_API_KEY` unset and the stub referee plays the game. Set the key later (and install `typesafe-sdk`) to swap in live Jev. Groq is not wired.

## How to start

From the repo root:

```
.venv/bin/python web.py          # UI at http://127.0.0.1:5050
.venv/bin/python cli.py          # resume saves/game.json if it exists
.venv/bin/python cli.py --new    # wipe the save and start over
```

The web UI uses the same engine and `saves/game.json`. Click an exit or type a line. After an ending, **Read the story** replays the night. **Stories** keeps finished runs in `saves/archive/` so a new game does not erase them.

At the prompt:

- `1`, `2`, `3` — pick a listed exit
- free text — the referee maps it to an exit, or stays put
- `status` — reprint HP, metrics, inventory
- `new` — abandon the current save
- `quit` — pause (resume with `cli.py`)

Optional check after content or keyword edits:

```
.venv/bin/python eval_harness.py
```

## Layout

- `data/world.yaml` — metrics, items, flags, endings
- `data/nodes.yaml` — rooms and exits
- `data/tests.yaml` — eval utterances
- `cli.py` — REPL
- `web.py` — local Flask UI (`static/`)
- `saves/game.json` — current save (v1)
- `saves/story.txt` — concatenated passages

Jev is not called on load. Newer `save_version` is refused.

## Docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — ownership, turn pipeline, resolver, saves
- [`GRAPH.md`](GRAPH.md) — rooms, parser-only exits, ending lock
