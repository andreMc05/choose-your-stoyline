# Night Tide — v1 graph

## Win / lose (LOCKED)

- **Win (`end_clean_berth`)**: Aboard, packet still sealed (or safely stashed), `wanted_heat <= 1`.
- **Bittersweet (`end_watched_berth`)**: Aboard, but the crew or watch will remember you (`wanted_heat >= 2`, opened packet delivered, or you report yourself).
- **Lose detained (`end_detained`)**: Customs keeps you. Packet seized or you run from the desk.
- **Lose packet (`end_packet_gone`)**: You are not in a cell, but the packet is gone.

Fourth ending is extra; spec asked for at least three.

## Flag payoff (two nodes earlier)

`crate_stack.listen_stevedore` sets `heard_voss`.
Parser-only `watch_stoop.name_voss` requires that flag. Buttons on the stoop stay honest (papers / coin / silence). Same flag later unlocks parser-only `deck.ask_voss_door`.

## Parser-only exits (bonus, not required)

- `watch_stoop.name_voss` — type “Voss sent me”
- `search_room.dump_packet` — type “I ditch the packet”
- `deck.ask_voss_door` — type “take me to Voss”

## Metrics used in v1

`nerve`, `caution`, `wanted_heat` — all 0–3, declared in `data/world.yaml`. Other games replace the block.

## Graph

```mermaid
flowchart TD
  docks_night[docks_night] --> watch_stoop
  docks_night --> crate_stack
  docks_night --> pier_end
  pier_end --> watch_stoop
  pier_end --> crate_stack
  crate_stack -->|listen sets heard_voss| stevedore_aside
  crate_stack --> gangway
  crate_stack --> watch_stoop
  stevedore_aside --> watch_stoop
  stevedore_aside --> gangway
  watch_stoop -->|flash_papers| customs_desk
  watch_stoop -->|offer_coin| gangway
  watch_stoop -->|stay_quiet| customs_desk
  watch_stoop -.->|parser name_voss if heard_voss| gangway
  customs_desk --> gangway
  customs_desk --> search_room
  customs_desk --> end_detained
  search_room --> end_detained
  search_room -.->|parser dump_packet| end_packet_gone
  gangway --> deck
  deck --> hold
  deck -.->|parser Voss door if heard_voss| cabin_door
  cabin_door --> voss_cabin
  cabin_door --> hold
  hold --> sea_horn
  voss_cabin --> end_clean_berth
  voss_cabin --> end_watched_berth
  voss_cabin --> end_packet_gone
  sea_horn -->|hide and heat low| end_clean_berth
  sea_horn -->|hide and heat high / report| end_watched_berth
  sea_horn --> end_packet_gone
```

Dotted = parser-only.

## Node count

12 playable rooms + 4 endings. Vertical slice is complete.
