---
name: generate-map
description: Generate, revise, and validate playable WATCH MY ESCAPE map JSON documents from scenario descriptions. Use when Codex needs to create or improve built-in or custom maps, puzzle chains, entity behavior JSON, inventory/item triggers, map_data files, or solution walkthroughs for this project.
---

# Generate Map

## Output Contract

Create a complete `PremadeMapDocument` JSON object for WATCH MY ESCAPE:

```json
{
  "description": "Selection-screen room description without puzzle answers.",
  "map": {
    "id": "lowercase-kebab-map-id",
    "name": "Thematic Room Name",
    "width": 15,
    "height": 15,
    "agent_start": { "x": 7, "y": 7 },
    "entities": [
      {
        "entity": {
          "id": "example-entity",
          "icon": "?",
          "color": null,
          "description": "Text shown when examined. It may include {state}.",
          "passable": true,
          "active": true,
          "notable": true,
          "state": "default",
          "behaviors": []
        },
        "position": { "x": 7, "y": 8 }
      }
    ],
    "unplaced_entities": []
  }
}
```

Unless the user asks for something narrower, provide:

1. Narrative setting metadata.
2. Puzzle logic design.
3. Complete JSON.
4. Step-by-step solution walkthrough.

If adding a built-in map to the repo, write it to `src/watch_my_escape/game/map_data/<map-id>.json`; the loader discovers JSON files in that package.

## Workflow

1. Design the solution path before writing JSON. List the required actions and the entity ids each action touches.
2. Place the room on the fixed `15x15` grid. Coordinates are `0` through `14`; `x` is column and `y` is row.
3. Seal the perimeter. Every border coordinate must start with an active impassable entity, usually a non-notable wall, except intentional exits or gates that are also impassable at the start.
4. Author entities and behaviors. Keep all ids unique across placed and unplaced entities.
5. Validate with:

```bash
uv run python .agents/skills/generate-map/scripts/validate_map.py path/to/map.json
```

If returning JSON only in chat, validate it through a temporary file first.

## Project Rules

- Models reject unknown fields. Use only schema fields from `watch_my_escape.game.models`, `watch_my_escape.game.maps`, and `watch_my_escape.game.premade_maps`.
- `width` and `height` must both be `15`.
- `agent_start` must be inside the room, passable, and not occupied by an active impassable entity.
- Only one entity may occupy a coordinate.
- Entity ids and map ids should be lowercase kebab case.
- Do not reuse one wall id for every wall. Use unique ids such as `wall-0-0`, `wall-1-0`, and so on.
- Put static walls on the border with `passable: false`, `active: true`, and `notable: false`.
- Use `notable: true` only for objects the agent should see in the observation list.
- Every entity referenced by a behavior must exist in either `entities` or `unplaced_entities`.
- Entities added to inventory with `add_inventory` are usually unplaced entities or placed pickup items that deactivate after pickup.
- There is no create-entity effect. To reveal a placed object later, place it initially with `active: false`, then use `set_entity_active`.
- The root `description` appears in map selection. Keep it atmospheric and do not reveal answers there.

## Behavior Rules

Actions are:

```text
examine, pick_up, open, close, push, pull, talk_to, operate, use_item
```

Use these trigger shapes:

```json
{ "action": "examine" }
{ "action": "open", "actions": ["open", "pull", "operate"] }
{ "action": "use_item", "item": "brass-key" }
{ "action": "talk_to", "phrase": "keyboard" }
```

When `actions` is present, it must include `action` and cannot be combined with `item` or `phrase`. `item` is only valid for `use_item`. `phrase` is only valid for `talk_to`; matching is case-insensitive and ignores whitespace.

Conditions check entity state:

```json
{ "state": "locked" }
{ "entity_id": "other-entity", "state": "open" }
```

Omit `entity_id` or set it to `null` to check the host entity.

Effects are evaluated in order:

```json
{ "type": "message", "text": "The panel opens." }
{ "type": "add_inventory", "entity_id": "brass-key" }
{ "type": "remove_inventory", "entity_id": "brass-key" }
{ "type": "set_entity_state", "state": "open" }
{ "type": "set_entity_passable", "passable": true, "entity_id": "locked-gate" }
{ "type": "set_entity_active", "active": false }
{ "type": "escape_map" }
```

For `set_entity_state`, `set_entity_passable`, and `set_entity_active`, omitting `entity_id` targets the current entity.

## Puzzle Patterns

- Lock and key: pickup item adds inventory and deactivates the item; `use_item` on the door removes the item, opens or deactivates the blocker, and eventually triggers `escape_map`.
- Container: closed object changes to `open`; a later `pick_up` or `examine` while open grants an unplaced item and changes the container to `empty`.
- Revealed pickup: keep a placed item `active: false`; a console or container sets it active so it appears on the map.
- Blocker: obstacle starts impassable; using the right item makes it inactive or passable.
- Riddle: clue gives the answer; `talk_to` on a console or NPC checks the phrase and grants progress.
- Red herring: notable object responds with flavor only. Do not use ids or descriptions that say "decoy", "herring", "fake", or otherwise expose that it is nonessential.

## Quality Checklist

- A complete solution exists and has no dead ends.
- At least one behavior can trigger `escape_map`.
- The first useful clue or interactable object is visible or reachable from the start.
- Essential objects are not sealed behind inactive or permanently impassable blockers.
- The JSON validates with the bundled validator script.
- The walkthrough uses exact action names, target ids, item ids, phrases, and coordinates where useful.
