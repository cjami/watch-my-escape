import { slugify } from "../shared/strings.js";

import { mapSize, presets } from "./constants.js";

export function createEditorContext({ dom, pixelSprite }) {
  const context = {
    dom,
    pixelSprite,
    selectedTool: "select",
    selectedPreset: presets[0],
    selectedEntityId: null,
    selectedEditorTab: "entity",
    openBehaviorEditor: null,
    iconSearchQuery: "",
    editorState: starterEditorState(),
    dragState: null,
  };

  context.setStatus = (message) => {
    dom.editorStatus.textContent = message;
  };
  context.setEditorTool = (tool) => {
    context.selectedTool = tool;
    dom.editorToolButtons.forEach((toolButton) => {
      toolButton.classList.toggle("is-selected", toolButton.dataset.editorTool === tool);
    });
  };
  context.editorToolHint = (tool) => {
    const hints = {
      select: "Select an entity, drag an entity to move it, or drag the start marker.",
      place: `Drag on open tiles to place ${context.selectedPreset.name.toLowerCase()} entities.`,
      erase: "Drag across occupied tiles to remove entities.",
      start: "Click a tile or drag the start marker to set the agent start.",
    };
    return hints[tool] ?? "Ready.";
  };
  context.createEntity = (preset, x, y) => createEntity(context, preset, x, y);
  context.entityFromPreset = (preset, id) => entityFromPreset(preset, id);
  context.selectedPlacedEntity = () => selectedPlacedEntity(context);
  context.selectedEntity = () => context.selectedPlacedEntity()?.entity ?? null;
  context.selectedUnplacedEntityRecord = () => selectedUnplacedEntityRecord(context);
  context.selectedDragEntity = () => selectedDragEntity(context);
  context.allEditorEntities = () => allEditorEntities(context);
  context.entityAt = (x, y) => entityAt(context, x, y);
  context.uniqueEntityId = (base) => uniqueEntityId(context, base);

  return context;
}

export function defaultBehavior() {
  return {
    trigger: { action: "examine" },
    conditions: [],
    effects: [{ type: "message", text: "You notice nothing unusual." }],
  };
}

export function defaultEffect(type) {
  if (type === "message") {
    return { type, text: "Something happens." };
  }
  if (type === "add_inventory" || type === "remove_inventory") {
    return { type, entity_id: "" };
  }
  if (type === "set_entity_state") {
    return { type, entity_id: "", state: "open" };
  }
  if (type === "set_entity_passable") {
    return { type, entity_id: "", passable: true };
  }
  if (type === "set_entity_active") {
    return { type, entity_id: "", active: true };
  }
  return { type: "escape_map" };
}

export function starterEditorState() {
  const entities = [];
  const center = Math.floor(mapSize / 2);
  for (let y = 0; y < mapSize; y += 1) {
    for (let x = 0; x < mapSize; x += 1) {
      if (x !== 0 && x !== mapSize - 1 && y !== 0 && y !== mapSize - 1) {
        continue;
      }
      if (x === mapSize - 1 && y === center) {
        continue;
      }
      entities.push(placedEntityFromDefinition(wallDefinition(x, y), x, y));
    }
  }
  entities.push(
    placedEntityFromDefinition(
      {
        id: "brass-key",
        icon: "\u{1F511}",
        description: "A tarnished brass key.",
        passable: true,
        active: true,
        notable: true,
        state: "default",
        behaviors: [
          {
            trigger: { action: "pick_up" },
            conditions: [],
            effects: [
              { type: "message", text: "You pick up the brass key." },
              { type: "add_inventory", entity_id: "brass-key" },
              { type: "set_entity_active", active: false },
            ],
          },
        ],
      },
      8,
      center,
    ),
    placedEntityFromDefinition(
      {
        id: "locked-door",
        icon: "\u{1F6AA}",
        description: "A locked door bars the exit.",
        passable: false,
        active: true,
        notable: true,
        state: "locked",
        behaviors: [
          {
            trigger: { action: "use_item", item: "brass-key" },
            conditions: [],
            effects: [
              { type: "message", text: "The brass key turns, and the door opens. You escape." },
              { type: "set_entity_state", state: "open" },
              { type: "set_entity_passable", passable: true },
              { type: "escape_map" },
            ],
          },
        ],
      },
      mapSize - 1,
      center,
    ),
  );
  return {
    agentStart: { x: center, y: center },
    entities,
    unplacedEntities: [],
  };
}

function wallDefinition(x, y) {
  return {
    id: `wall-${x}-${y}`,
    icon: "\u{1F9F1}",
    description: "A solid wall.",
    passable: false,
    active: true,
    notable: false,
    state: "default",
    behaviors: [],
  };
}

function placedEntityFromDefinition(entity, x, y) {
  return {
    position: { x, y },
    entity: structuredClone(entity),
  };
}

function createEntity(context, preset, x, y) {
  const id = context.uniqueEntityId(slugify(preset.name || preset.type));
  return {
    position: { x, y },
    entity: entityFromPreset(preset, id),
  };
}

function entityFromPreset(preset, id) {
  return {
    id,
    icon: preset.icon,
    color: preset.color ?? "",
    description: preset.description,
    passable: preset.passable,
    active: preset.active ?? true,
    notable: preset.notable ?? true,
    state: preset.state ?? "default",
    behaviors: structuredClone(preset.behaviors ?? []),
  };
}

function selectedPlacedEntity(context) {
  return (
    context.editorState.entities.find((placed) => placed.entity.id === context.selectedEntityId) ??
    selectedUnplacedEntityRecord(context) ??
    null
  );
}

function selectedUnplacedEntityRecord(context) {
  const entity = (context.editorState.unplacedEntities ?? []).find(
    (candidate) => candidate.id === context.selectedEntityId,
  );
  return entity ? { entity, position: null } : null;
}

function selectedDragEntity(context) {
  const placed = context.editorState.entities.find((candidate) => candidate.entity.id === context.dragState.sourceId);
  if (placed) {
    return placed;
  }
  const entity = (context.editorState.unplacedEntities ?? []).find(
    (candidate) => candidate.id === context.dragState.sourceId,
  );
  return entity ? { entity, position: null } : null;
}

function allEditorEntities(context) {
  return [...context.editorState.entities.map((placed) => placed.entity), ...(context.editorState.unplacedEntities ?? [])];
}

function entityAt(context, x, y) {
  return (
    context.editorState.entities.find((candidate) => candidate.position.x === x && candidate.position.y === y) ?? null
  );
}

function uniqueEntityId(context, base) {
  let candidate = base || "entity";
  let suffix = 2;
  const existing = new Set(context.allEditorEntities().map((entity) => entity.id));
  while (existing.has(candidate)) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  return candidate;
}
