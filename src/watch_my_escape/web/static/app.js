const appData = JSON.parse(document.querySelector("#app-data").textContent);
const screens = new Map([...document.querySelectorAll("[data-screen]")].map((screen) => [screen.dataset.screen, screen]));
const modelOptions = document.querySelector("#model-options");
const previousModelButton = document.querySelector("#previous-model");
const nextModelButton = document.querySelector("#next-model");
const chooseModelButton = document.querySelector("#choose-model");
const modelLineup = document.querySelector("#model-lineup");
const modelAgentOrbit = document.querySelector("#model-agent-orbit");
const modelAgentIcon = document.querySelector("#model-agent-icon");
const modelCompany = document.querySelector("#model-company");
const modelName = document.querySelector("#model-name");
const modelStats = document.querySelector("#model-stats");
const modelFile = document.querySelector("#model-file");
const mapOptions = document.querySelector("#map-options");
const selectedModelLabel = document.querySelector("#selected-model-label");
const gameSelectionLabel = document.querySelector("#game-selection-label");
const runButton = document.querySelector("#run-escape");
const restartButton = document.querySelector("#restart-flow");
const statusOutput = document.querySelector("#status");
const sanityOutput = document.querySelector("#sanity");
const positionOutput = document.querySelector("#position");
const mapOutput = document.querySelector("#map-view");
const escapeBanner = document.querySelector("#escape-banner");
const escapeAgentIcon = document.querySelector("#escape-agent-icon");
const visibleEntitiesOutput = document.querySelector("#visible-entities");
const inventoryOutput = document.querySelector("#inventory");
const journalOutput = document.querySelector("#journal");
const transcriptOutput = document.querySelector("#transcript");
const gameIntro = document.querySelector("#game-intro");
const playGameButton = document.querySelector("#play-game");
const openEditorButton = document.querySelector("#open-editor");
const editorBackButton = document.querySelector("#editor-back");
const importMapButton = document.querySelector("#import-map");
const importMapFile = document.querySelector("#import-map-file");
const exportMapButton = document.querySelector("#export-map");
const editorGrid = document.querySelector("#editor-grid");
const entityPresets = document.querySelector("#entity-presets");
const entityForm = document.querySelector("#entity-form");
const behaviorList = document.querySelector("#behavior-list");
const addEntityButton = document.querySelector("#add-entity");
const addBehaviorButton = document.querySelector("#add-behavior");
const editorStatus = document.querySelector("#editor-status");
const editorMapName = document.querySelector("#editor-map-name");
const editorMapId = document.querySelector("#editor-map-id");
const editorDescription = document.querySelector("#editor-description");

const mapSize = 16;
const spriteCache = new Map();
const actionOptions = ["examine", "pick_up", "open", "close", "push", "pull", "talk_to", "use", "use_item"];
const effectOptions = [
  "message",
  "add_inventory",
  "remove_inventory",
  "set_entity_state",
  "set_entity_property",
  "set_entity_passable",
  "set_entity_active",
  "escape_map",
];
const emojiOptions = ["🧱", "🚪", "🔑", "📝", "🧍", "🎚️", "📦", "💡", "🪟", "🧰", "🔒", "🪜", "🧪", "📚", "🏁"];
const presets = [
  {
    type: "wall",
    name: "Wall",
    icon: "🧱",
    description: "A solid wall.",
    passable: false,
    notable: false,
  },
  {
    type: "door",
    name: "Door",
    icon: "🚪",
    description: "A closed door.",
    passable: false,
    state: "closed",
  },
  {
    type: "key",
    name: "Key",
    icon: "🔑",
    description: "A small key.",
    passable: true,
  },
  {
    type: "note",
    name: "Note",
    icon: "📝",
    description: "A note with useful writing on it.",
    passable: true,
  },
  {
    type: "character",
    name: "Character",
    icon: "🧍",
    description: "Someone waiting in the room.",
    passable: false,
  },
  {
    type: "switch",
    name: "Switch",
    icon: "🎚️",
    description: "A switch that can trigger something.",
    passable: true,
  },
  {
    type: "item",
    name: "Item",
    icon: "📦",
    description: "A useful item.",
    passable: true,
  },
  {
    type: "exit",
    name: "Exit",
    icon: "🏁",
    description: "The way out.",
    passable: true,
    behaviors: [
      {
        trigger: { action: "use" },
        conditions: [],
        effects: [
          { type: "message", text: "You escape the room." },
          { type: "escape_map" },
        ],
      },
    ],
  },
];

let activeStream = null;
let selectedModel = null;
let selectedMap = null;
let selectedTool = "select";
let selectedPreset = presets[0];
let selectedEntityId = null;
let editorState = starterEditorState();
let selectedModelIndex = 0;
let lastMapText = "";
let lastAgentPosition = "";
let gameIntroTimer = null;
let runEpoch = 0;

renderModelOptions();
renderMapOptions();
renderPresets();
renderEditor();
refreshSpritesWhenFontsLoad();

screens.get("splash").addEventListener("click", () => showScreen("menu"), { once: true });
window.addEventListener(
  "keydown",
  () => {
    if (screens.get("splash").classList.contains("is-active")) {
      showScreen("menu");
    }
  },
  { once: true },
);

playGameButton.addEventListener("click", () => {
  renderModelOptions();
  showScreen("models");
  modelOptions.focus();
});
previousModelButton.addEventListener("click", () => changeModel(-1));
nextModelButton.addEventListener("click", () => changeModel(1));
chooseModelButton.addEventListener("click", chooseSelectedModel);
modelOptions.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    changeModel(-1);
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    changeModel(1);
  }
  if ((event.key === "Enter" || event.key === " ") && event.target === modelOptions) {
    event.preventDefault();
    chooseSelectedModel();
  }
});
openEditorButton.addEventListener("click", () => showScreen("editor"));
editorBackButton.addEventListener("click", () => showScreen("menu"));
importMapButton.addEventListener("click", () => importMapFile.click());
importMapFile.addEventListener("change", importEditorMap);
exportMapButton.addEventListener("click", exportEditorMap);
addEntityButton.addEventListener("click", () => {
  const position = firstOpenPosition() ?? editorState.agentStart;
  if (entityAt(position.x, position.y)) {
    setEditorStatus("No open tile is available for a new entity.");
    return;
  }
  const placedEntity = createEntity(selectedPreset, position.x, position.y);
  editorState.entities.push(placedEntity);
  selectedEntityId = placedEntity.entity.id;
  renderEditor();
});
addBehaviorButton.addEventListener("click", () => {
  const entity = selectedEntity();
  if (!entity) {
    setEditorStatus("Select an entity before adding behavior.");
    return;
  }
  entity.behaviors.push(defaultBehavior());
  renderEditor();
});
restartButton.addEventListener("click", () => {
  runEpoch += 1;
  stopStream();
  resetGame();
  showScreen("models");
});
runButton.addEventListener("click", runEscape);
editorMapName.addEventListener("input", () => {
  if (!editorMapId.dataset.touched) {
    editorMapId.value = slugify(editorMapName.value) || "new-escape-room";
  }
});
editorMapId.addEventListener("input", () => {
  editorMapId.dataset.touched = "true";
});
document.querySelectorAll("[data-editor-tool]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedTool = button.dataset.editorTool;
    document.querySelectorAll("[data-editor-tool]").forEach((toolButton) => {
      toolButton.classList.toggle("is-selected", toolButton === button);
    });
  });
});

function renderModelOptions() {
  if (!appData.models.length) {
    return;
  }
  selectedModelIndex = normalizeModelIndex(selectedModelIndex);
  const model = appData.models[selectedModelIndex];
  const maxParameters = Math.max(...appData.models.map((candidate) => candidate.parameter_size_b));
  const sizeRatio = Math.sqrt(model.parameter_size_b / maxParameters);
  modelOptions.style.setProperty("--model-color", model.brand_color);
  modelAgentOrbit.style.setProperty("--model-color", model.brand_color);
  modelAgentOrbit.style.setProperty("--model-scale", String(0.62 + sizeRatio * 0.48));
  modelAgentIcon.replaceChildren(pixelSprite(model.agent_icon, model.display_name, model.brand_color, 48));
  modelCompany.textContent = model.company;
  modelName.textContent = model.display_name;
  modelStats.replaceChildren(
    modelStat("Params", formatParameters(model.parameter_size_b)),
    modelStat("Class", modelClass(model.parameter_size_b)),
    modelStat("Active", model.active_parameter_size_b ? formatParameters(model.active_parameter_size_b) : "Dense"),
  );
  modelFile.textContent = model.filename;
  modelLineup.replaceChildren(
    ...appData.models.map((candidate, index) => {
      const button = document.createElement("button");
      const ratio = Math.sqrt(candidate.parameter_size_b / maxParameters);
      button.type = "button";
      button.className = "model-lineup-agent";
      button.classList.toggle("is-selected", index === selectedModelIndex);
      button.style.setProperty("--lineup-color", candidate.brand_color);
      button.style.setProperty("--lineup-size", `${2.2 + ratio * 2.4}rem`);
      button.setAttribute("aria-label", candidate.display_name);
      button.append(pixelSprite(candidate.agent_icon, candidate.display_name, candidate.brand_color, 32));
      button.addEventListener("click", () => {
        selectedModelIndex = index;
        renderModelOptions();
      });
      return button;
    }),
  );
}

function changeModel(direction) {
  selectedModelIndex = normalizeModelIndex(selectedModelIndex + direction);
  renderModelOptions();
}

function chooseSelectedModel() {
  const model = appData.models[selectedModelIndex];
  selectedModel = model;
  selectedModelLabel.textContent = `${model.company} / ${model.display_name}`;
  document.documentElement.style.setProperty("--agent-color", model.brand_color);
  showScreen("maps");
}

function normalizeModelIndex(index) {
  return (index + appData.models.length) % appData.models.length;
}

function modelStat(label, value) {
  const stat = document.createElement("span");
  stat.className = "model-stat";
  stat.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>`;
  return stat;
}

function formatParameters(value) {
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}B`;
}

function modelClass(parameterSizeB) {
  if (parameterSizeB >= 10) {
    return "Heavy";
  }
  if (parameterSizeB >= 4) {
    return "Medium";
  }
  if (parameterSizeB >= 2) {
    return "Light";
  }
  return "Feather";
}

function renderMapOptions() {
  mapOptions.replaceChildren(
    ...appData.maps.map((gameMap) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "selection-card map-card";
      button.innerHTML = `
        <span class="selection-title">${escapeHtml(gameMap.name)}</span>
        <span class="selection-detail">${escapeHtml(gameMap.description)}</span>
      `;
      button.addEventListener("click", () => {
        selectedMap = gameMap;
        gameSelectionLabel.textContent = `${selectedModel.display_name} / ${gameMap.name}`;
        showScreen("game");
      });
      return button;
    }),
  );
}

async function runEscape() {
  if (!selectedModel || !selectedMap) {
    showScreen("models");
    return;
  }

  stopStream();
  resetGame();
  const currentRunEpoch = (runEpoch += 1);
  runButton.disabled = true;
  statusOutput.textContent = "The CRT is warming up...";
  transcriptOutput.textContent = "Waiting for the first turn...";
  const introComplete = playGameIntro();
  statusOutput.textContent = "The model is trying to escape...";

  const params = new URLSearchParams({
    model_preset: selectedModel.id,
    map_id: selectedMap.id,
  });
  activeStream = new EventSource(`/escape-stream?${params}`);
  activeStream.onmessage = (event) => {
    if (currentRunEpoch !== runEpoch) {
      return;
    }
    const frame = JSON.parse(event.data);
    statusOutput.textContent = frame.status;
    sanityOutput.textContent = `Sanity: ${frame.sanity}`;
    positionOutput.textContent = frame.position ? `Position: ${frame.position}` : "Position: --";
    renderMap(frame.map, frame.position);
    visibleEntitiesOutput.textContent = frame.visible_entities;
    inventoryOutput.textContent = frame.inventory;
    journalOutput.textContent = frame.journal;
    transcriptOutput.textContent = frame.transcript;
    if (frame.escaped) {
      renderEscapeCelebration();
    }
    escapeBanner.hidden = !frame.escaped;
    if (frame.escaped || frame.sanity === "0" || frame.status === "Model is not configured.") {
      stopStream();
      runButton.disabled = false;
    }
  };
  activeStream.onerror = () => {
    if (currentRunEpoch !== runEpoch) {
      return;
    }
    statusOutput.textContent = "The room stream closed.";
    stopStream();
    runButton.disabled = false;
  };
  await introComplete;
}

function showScreen(name) {
  for (const screen of screens.values()) {
    screen.classList.toggle("is-active", screen.dataset.screen === name);
  }
}

function playGameIntro() {
  if (!gameIntro) {
    return Promise.resolve();
  }

  window.clearTimeout(gameIntroTimer);
  gameIntro.hidden = false;
  gameIntro.classList.remove("is-playing");
  void gameIntro.offsetWidth;
  gameIntro.classList.add("is-playing");
  return new Promise((resolve) => {
    const introDuration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 900 : 4300;
    gameIntroTimer = window.setTimeout(() => {
      gameIntro.hidden = true;
      gameIntro.classList.remove("is-playing");
      resolve();
    }, introDuration);
  });
}

function stopStream() {
  if (!activeStream) {
    return;
  }
  activeStream.close();
  activeStream = null;
}

function resetGame() {
  statusOutput.textContent = "Ready.";
  sanityOutput.textContent = "Sanity: 100";
  positionOutput.textContent = "Position: --";
  visibleEntitiesOutput.textContent = "- None.";
  inventoryOutput.textContent = "- Empty.";
  journalOutput.textContent = "- No notes recorded.";
  transcriptOutput.textContent = "The model has not tried the room yet.";
  escapeBanner.hidden = true;
  escapeAgentIcon.replaceChildren();
  renderMap("", "");
  runButton.disabled = false;
}

function renderMap(mapText, agentPosition) {
  const previousAgentPosition = lastAgentPosition;
  lastMapText = mapText;
  lastAgentPosition = agentPosition;
  mapOutput.replaceChildren();
  const rows = mapText.trim() ? mapText.trim().split("\n") : [];
  if (!rows.length) {
    const empty = document.createElement("span");
    empty.className = "map-empty";
    empty.textContent = ".";
    mapOutput.append(empty);
    return;
  }

  const agentCoordinate = parsePosition(agentPosition);
  const agentMoved = Boolean(previousAgentPosition && agentPosition && previousAgentPosition !== agentPosition);
  rows.forEach((row, y) => {
    row.split(" ").forEach((cell, x) => {
      const tile = document.createElement("span");
      tile.className = "map-tile";
      if (agentCoordinate?.x === x && agentCoordinate.y === y) {
        tile.classList.add("agent-tile");
        tile.classList.toggle("agent-just-moved", agentMoved);
      }
      if (cell !== ".") {
        const tint = agentCoordinate?.x === x && agentCoordinate.y === y ? selectedModel?.brand_color : null;
        tile.append(pixelSprite(cell, cell, tint));
      }
      mapOutput.append(tile);
    });
  });
}

function renderEscapeCelebration() {
  escapeAgentIcon.replaceChildren(pixelSprite("\u{1F973}", "Escaped agent", selectedModel?.brand_color, 96));
}

function renderPresets() {
  entityPresets.replaceChildren(
    ...presets.map((preset) => {
      const button = document.createElement("button");
      const icon = document.createElement("span");
      const name = document.createElement("span");

      button.type = "button";
      button.className = "preset-button";
      icon.className = "preset-icon";
      icon.append(pixelSprite(preset.icon, preset.name));
      name.textContent = preset.name;
      button.append(icon, name);
      button.classList.toggle("is-selected", preset === selectedPreset);
      button.addEventListener("click", () => {
        selectedPreset = preset;
        renderPresets();
      });
      return button;
    }),
  );
}

function renderEditor() {
  renderEditorGrid();
  renderEntityForm();
  renderBehaviors();
}

function renderEditorGrid() {
  editorGrid.replaceChildren();
  for (let y = 0; y < mapSize; y += 1) {
    for (let x = 0; x < mapSize; x += 1) {
      const cell = document.createElement("button");
      const entity = editorState.entities.find((candidate) => candidate.position.x === x && candidate.position.y === y);
      cell.type = "button";
      cell.className = "editor-cell";
      cell.classList.toggle("is-start", editorState.agentStart.x === x && editorState.agentStart.y === y);
      cell.classList.toggle("is-selected", entity?.entity.id === selectedEntityId);
      if (entity) {
        cell.append(pixelSprite(entity.entity.icon, entity.entity.name));
      }
      cell.title = entity ? entity.entity.name : `(${x}, ${y})`;
      cell.addEventListener("click", () => handleEditorCellClick(x, y, entity));
      editorGrid.append(cell);
    }
  }
}

function handleEditorCellClick(x, y, placedEntity) {
  if (selectedTool === "start") {
    editorState.agentStart = { x, y };
    setEditorStatus(`Agent start set to (${x}, ${y}).`);
    renderEditor();
    return;
  }
  if (selectedTool === "erase") {
    if (placedEntity) {
      editorState.entities = editorState.entities.filter((candidate) => candidate.entity.id !== placedEntity.entity.id);
      if (selectedEntityId === placedEntity.entity.id) {
        selectedEntityId = null;
      }
      setEditorStatus(`Removed ${placedEntity.entity.name}.`);
    }
    renderEditor();
    return;
  }
  if (selectedTool === "place") {
    if (placedEntity) {
      selectedEntityId = placedEntity.entity.id;
      setEditorStatus(`${placedEntity.entity.name} is already on this tile.`);
      renderEditor();
      return;
    }
    const entity = createEntity(selectedPreset, x, y);
    editorState.entities.push(entity);
    selectedEntityId = entity.entity.id;
    setEditorStatus(`Placed ${entity.entity.name}.`);
    renderEditor();
    return;
  }
  selectedEntityId = placedEntity?.entity.id ?? null;
  renderEditor();
}

function renderEntityForm() {
  const placed = selectedPlacedEntity();
  if (!placed) {
    entityForm.innerHTML = `<p class="selection-detail">Select an entity on the grid or create one.</p>`;
    return;
  }
  const entity = placed.entity;
  entityForm.innerHTML = `
    <label><span>Id</span><input data-entity-field="id" type="text" value="${escapeAttribute(entity.id)}" /></label>
    <label><span>Name</span><input data-entity-field="name" type="text" value="${escapeAttribute(entity.name)}" /></label>
    <div>
      <span class="field-label">Icon</span>
      <div class="icon-picker" aria-label="Entity icon">
        ${emojiOptions
          .map(
            (emoji) => `
              <button type="button" class="icon-option ${entity.icon === emoji ? "is-selected" : ""}" data-icon="${escapeAttribute(emoji)}">
                ${escapeHtml(toTextEmoji(emoji))}
              </button>
            `,
          )
          .join("")}
      </div>
    </div>
    <label><span>Description</span><textarea data-entity-field="description" rows="3">${escapeHtml(entity.description)}</textarea></label>
    <label><span>State</span><input data-entity-field="state" type="text" value="${escapeAttribute(entity.state)}" /></label>
    <div class="checkbox-row">
      <label><input data-entity-field="passable" type="checkbox" ${entity.passable ? "checked" : ""} />Passable</label>
      <label><input data-entity-field="active" type="checkbox" ${entity.active ? "checked" : ""} />Active</label>
      <label><input data-entity-field="notable" type="checkbox" ${entity.notable ? "checked" : ""} />Notable</label>
    </div>
    <label><span>Properties JSON</span><textarea data-entity-field="properties" rows="3">${escapeHtml(JSON.stringify(entity.properties, null, 2))}</textarea></label>
  `;
  entityForm.querySelectorAll("[data-entity-field]").forEach((input) => {
    input.addEventListener("input", () => updateEntityField(input, placed));
  });
  entityForm.querySelectorAll("[data-icon]").forEach((button) => {
    button.replaceChildren(pixelSprite(button.dataset.icon, "Icon option"));
    button.setAttribute("aria-label", `Choose ${button.dataset.icon}`);
    button.addEventListener("click", () => {
      placed.entity.icon = button.dataset.icon;
      renderEditor();
    });
  });
}

function updateEntityField(input, placed) {
  const field = input.dataset.entityField;
  if (field === "id") {
    selectedEntityId = input.value.trim();
  }
  if (field === "properties") {
    try {
      placed.entity.properties = JSON.parse(input.value || "{}");
      setEditorStatus("Properties updated.");
    } catch {
      setEditorStatus("Properties must be valid JSON.");
      return;
    }
  } else if (input.type === "checkbox") {
    placed.entity[field] = input.checked;
  } else {
    placed.entity[field] = input.value;
  }
  renderEditorGrid();
}

function renderBehaviors() {
  const placed = selectedPlacedEntity();
  behaviorList.replaceChildren();
  if (!placed) {
    behaviorList.innerHTML = `<p class="selection-detail">No entity selected.</p>`;
    return;
  }
  placed.entity.behaviors.forEach((behavior, index) => {
    behaviorList.append(behaviorBlock(behavior, index));
  });
  if (!placed.entity.behaviors.length) {
    behaviorList.innerHTML = `<p class="selection-detail">No behaviors configured.</p>`;
  }
}

function behaviorBlock(behavior, index) {
  const block = document.createElement("article");
  block.className = "behavior-block";
  block.innerHTML = `
    <div class="panel-heading">
      <h2>Rule ${index + 1}</h2>
      <button type="button" class="mini-button" data-remove-behavior="${index}">Remove</button>
    </div>
    <div class="block-grid">
      <label class="block-field">Action ${selectHtml(actionOptions, behavior.trigger.action, `data-trigger-field="action"`)}</label>
      ${triggerFieldsHtml(behavior.trigger)}
    </div>
    <div>
      <span class="field-label">Conditions</span>
      <div class="block-list" data-condition-list></div>
      <button type="button" class="mini-button" data-add-condition>Add Condition</button>
    </div>
    <div>
      <span class="field-label">Effects</span>
      <div class="block-list" data-effect-list></div>
      <button type="button" class="mini-button" data-add-effect>Add Effect</button>
    </div>
  `;
  block.querySelectorAll("[data-trigger-field]").forEach((input) => {
    input.addEventListener("input", () => {
      const value = input.value.trim();
      behavior.trigger[input.dataset.triggerField] = value || undefined;
      normalizeTrigger(behavior.trigger);
      if (input.dataset.triggerField === "action") {
        renderBehaviors();
      }
    });
  });
  block.querySelector("[data-remove-behavior]").addEventListener("click", () => {
    selectedPlacedEntity().entity.behaviors.splice(index, 1);
    renderBehaviors();
  });
  block.querySelector("[data-add-condition]").addEventListener("click", () => {
    behavior.conditions.push({ entity_id: "", state: "", property: "", equals: null });
    renderBehaviors();
  });
  block.querySelector("[data-add-effect]").addEventListener("click", () => {
    behavior.effects.push({ type: "message", text: "Something happens." });
    renderBehaviors();
  });
  renderConditionList(block.querySelector("[data-condition-list]"), behavior);
  renderEffectList(block.querySelector("[data-effect-list]"), behavior);
  return block;
}

function triggerFieldsHtml(trigger) {
  if (trigger.action === "use_item") {
    return `<label class="block-field">Item Id <input data-trigger-field="item" type="text" value="${escapeAttribute(trigger.item ?? "")}" /></label>`;
  }
  if (trigger.action === "talk_to") {
    return `<label class="block-field block-wide">Phrase <input data-trigger-field="phrase" type="text" value="${escapeAttribute(trigger.phrase ?? "")}" /></label>`;
  }
  return "";
}

function normalizeTrigger(trigger) {
  if (trigger.action !== "use_item") {
    delete trigger.item;
  }
  if (trigger.action !== "talk_to") {
    delete trigger.phrase;
  }
}

function renderConditionList(container, behavior) {
  container.replaceChildren(
    ...behavior.conditions.map((condition, index) => {
      const row = document.createElement("div");
      row.className = "block-grid";
      row.innerHTML = `
        <label class="block-field">Entity Id <input data-condition-field="entity_id" type="text" value="${escapeAttribute(condition.entity_id ?? "")}" /></label>
        <label class="block-field">State <input data-condition-field="state" type="text" value="${escapeAttribute(condition.state ?? "")}" /></label>
        <label class="block-field">Property <input data-condition-field="property" type="text" value="${escapeAttribute(condition.property ?? "")}" /></label>
        <label class="block-field">Equals <input data-condition-field="equals" type="text" value="${escapeAttribute(condition.equals ?? "")}" /></label>
        <button type="button" class="mini-button" data-remove-condition="${index}">Remove</button>
      `;
      row.querySelectorAll("[data-condition-field]").forEach((input) => {
        input.addEventListener("input", () => {
          condition[input.dataset.conditionField] = input.value.trim() || null;
        });
      });
      row.querySelector("[data-remove-condition]").addEventListener("click", () => {
        behavior.conditions.splice(index, 1);
        renderBehaviors();
      });
      return row;
    }),
  );
}

function renderEffectList(container, behavior) {
  container.replaceChildren(
    ...behavior.effects.map((effect, index) => {
      const row = document.createElement("div");
      row.className = "block-grid";
      row.innerHTML = `
        <label class="block-field">Type ${selectHtml(effectOptions, effect.type, `data-effect-field="type"`)}</label>
        ${effectFieldsHtml(effect)}
        <button type="button" class="mini-button" data-remove-effect="${index}">Remove</button>
      `;
      row.querySelectorAll("[data-effect-field]").forEach((input) => {
        input.addEventListener("input", () => {
          updateEffectField(effect, input);
          if (input.dataset.effectField === "type") {
            renderBehaviors();
          }
        });
      });
      row.querySelector("[data-remove-effect]").addEventListener("click", () => {
        behavior.effects.splice(index, 1);
        renderBehaviors();
      });
      return row;
    }),
  );
}

function effectFieldsHtml(effect) {
  if (effect.type === "message") {
    return `<label class="block-field block-wide">Text <input data-effect-field="text" type="text" value="${escapeAttribute(effect.text ?? "")}" /></label>`;
  }
  if (effect.type === "add_inventory" || effect.type === "remove_inventory") {
    return `<label class="block-field">Entity Id <input data-effect-field="entity_id" type="text" value="${escapeAttribute(effect.entity_id ?? "")}" /></label>`;
  }
  if (effect.type === "set_entity_state") {
    return `
      <label class="block-field">Entity Id <input data-effect-field="entity_id" type="text" value="${escapeAttribute(effect.entity_id ?? "")}" /></label>
      <label class="block-field">State <input data-effect-field="state" type="text" value="${escapeAttribute(effect.state ?? "")}" /></label>
    `;
  }
  if (effect.type === "set_entity_property") {
    return `
      <label class="block-field">Entity Id <input data-effect-field="entity_id" type="text" value="${escapeAttribute(effect.entity_id ?? "")}" /></label>
      <label class="block-field">Property <input data-effect-field="property" type="text" value="${escapeAttribute(effect.property ?? "")}" /></label>
      <label class="block-field">Value <input data-effect-field="value" type="text" value="${escapeAttribute(effect.value ?? "")}" /></label>
    `;
  }
  if (effect.type === "set_entity_passable" || effect.type === "set_entity_active") {
    const valueField = effect.type === "set_entity_passable" ? "passable" : "active";
    return `
      <label class="block-field">Entity Id <input data-effect-field="entity_id" type="text" value="${escapeAttribute(effect.entity_id ?? "")}" /></label>
      <label class="block-field">${valueField} ${selectHtml(["true", "false"], String(effect[valueField] ?? true), `data-effect-field="${valueField}"`)}</label>
    `;
  }
  return "";
}

function updateEffectField(effect, input) {
  const field = input.dataset.effectField;
  if (field === "type") {
    for (const key of Object.keys(effect)) {
      delete effect[key];
    }
    Object.assign(effect, defaultEffect(input.value));
    return;
  }
  if (field === "passable" || field === "active") {
    effect[field] = input.value === "true";
    return;
  }
  if (field === "value") {
    effect[field] = parseScalar(input.value);
    return;
  }
  effect[field] = input.value.trim() || undefined;
}

async function exportEditorMap() {
  const payload = buildEditorDocument();
  const response = await fetch("/maps/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json();
    setEditorStatus(`Validation failed: ${formatValidationError(error)}`);
    return;
  }
  const normalized = await response.json();
  downloadJson(`${normalized.map.id}.json`, normalized);
  setEditorStatus("Map validated and exported.");
}

async function importEditorMap() {
  const [file] = importMapFile.files;
  importMapFile.value = "";
  if (!file) {
    return;
  }
  let payload;
  try {
    payload = JSON.parse(await file.text());
  } catch {
    setEditorStatus("Import failed: JSON could not be parsed.");
    return;
  }

  const response = await fetch("/maps/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json();
    setEditorStatus(`Import failed: ${formatValidationError(error)}`);
    return;
  }

  const normalized = await response.json();
  loadEditorDocument(normalized);
  setEditorStatus(`Imported ${normalized.map.name}.`);
}

function loadEditorDocument(document) {
  editorDescription.value = document.description;
  editorMapName.value = document.map.name;
  editorMapId.value = document.map.id;
  editorMapId.dataset.touched = "true";
  editorState = {
    agentStart: document.map.agent_start,
    entities: document.map.entities.map((placed) => ({
      position: placed.position,
      entity: normalizeImportedEntity(placed.entity),
    })),
  };
  selectedEntityId = editorState.entities[0]?.entity.id ?? null;
  renderEditor();
}

function normalizeImportedEntity(entity) {
  return {
    id: entity.id,
    name: entity.name,
    icon: entity.icon,
    description: entity.description,
    passable: entity.passable,
    active: entity.active,
    notable: entity.notable,
    state: entity.state,
    properties: entity.properties,
    behaviors: entity.behaviors,
  };
}

function buildEditorDocument() {
  return {
    description: editorDescription.value.trim(),
    map: {
      id: editorMapId.value.trim(),
      name: editorMapName.value.trim(),
      agent_start: editorState.agentStart,
      width: mapSize,
      height: mapSize,
      entities: editorState.entities.map((placed) => ({
        position: placed.position,
        entity: normalizeEntity(placed.entity),
      })),
    },
  };
}

function normalizeEntity(entity) {
  return {
    id: entity.id.trim(),
    name: entity.name.trim(),
    icon: entity.icon.trim(),
    description: entity.description.trim(),
    passable: entity.passable,
    active: entity.active,
    notable: entity.notable,
    state: entity.state.trim() || "default",
    properties: entity.properties,
    behaviors: entity.behaviors.map(normalizeBehavior),
  };
}

function normalizeBehavior(behavior) {
  return {
    trigger: compactObject(behavior.trigger),
    conditions: behavior.conditions.map(compactObject),
    effects: behavior.effects.map(compactObject),
  };
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined && entry !== null && entry !== ""),
  );
}

function starterEditorState() {
  const entities = [];
  for (let y = 0; y < mapSize; y += 1) {
    for (let x = 0; x < mapSize; x += 1) {
      if (x !== 0 && x !== mapSize - 1 && y !== 0 && y !== mapSize - 1) {
        continue;
      }
      if (x === 15 && y === 8) {
        continue;
      }
      entities.push(placedEntityFromDefinition(wallDefinition(x, y), x, y));
    }
  }
  entities.push(
    placedEntityFromDefinition(
      {
        id: "brass-key",
        name: "Brass key",
        icon: "🔑",
        description: "A tarnished brass key.",
        passable: true,
        active: true,
        notable: true,
        state: "default",
        properties: {},
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
      8,
    ),
    placedEntityFromDefinition(
      {
        id: "locked-door",
        name: "Locked door",
        icon: "🚪",
        description: "A locked door bars the exit.",
        passable: false,
        active: true,
        notable: true,
        state: "locked",
        properties: {},
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
      15,
      8,
    ),
  );
  return {
    agentStart: { x: 7, y: 8 },
    entities,
  };
}

function wallDefinition(x, y) {
  return {
    id: `wall-${x}-${y}`,
    name: "Wall",
    icon: "🧱",
    description: "A solid wall.",
    passable: false,
    active: true,
    notable: false,
    state: "default",
    properties: {},
    behaviors: [],
  };
}

function placedEntityFromDefinition(entity, x, y) {
  return {
    position: { x, y },
    entity: structuredClone(entity),
  };
}

function createEntity(preset, x, y) {
  const id = uniqueEntityId(slugify(preset.name || preset.type));
  return {
    position: { x, y },
    entity: {
      id,
      name: preset.name,
      icon: preset.icon,
      description: preset.description,
      passable: preset.passable,
      active: preset.active ?? true,
      notable: preset.notable ?? true,
      state: preset.state ?? "default",
      properties: {},
      behaviors: structuredClone(preset.behaviors ?? []),
    },
  };
}

function defaultBehavior() {
  return {
    trigger: { action: "examine" },
    conditions: [],
    effects: [{ type: "message", text: "You notice nothing unusual." }],
  };
}

function defaultEffect(type) {
  if (type === "message") {
    return { type, text: "Something happens." };
  }
  if (type === "add_inventory" || type === "remove_inventory") {
    return { type, entity_id: "" };
  }
  if (type === "set_entity_state") {
    return { type, entity_id: "", state: "open" };
  }
  if (type === "set_entity_property") {
    return { type, entity_id: "", property: "used", value: true };
  }
  if (type === "set_entity_passable") {
    return { type, entity_id: "", passable: true };
  }
  if (type === "set_entity_active") {
    return { type, entity_id: "", active: true };
  }
  return { type: "escape_map" };
}

function selectedPlacedEntity() {
  return editorState.entities.find((placed) => placed.entity.id === selectedEntityId) ?? null;
}

function selectedEntity() {
  return selectedPlacedEntity()?.entity ?? null;
}

function entityAt(x, y) {
  return editorState.entities.find((candidate) => candidate.position.x === x && candidate.position.y === y) ?? null;
}

function firstOpenPosition() {
  for (let y = 1; y < mapSize - 1; y += 1) {
    for (let x = 1; x < mapSize - 1; x += 1) {
      if (!entityAt(x, y)) {
        return { x, y };
      }
    }
  }
  return null;
}

function uniqueEntityId(base) {
  let candidate = base || "entity";
  let suffix = 2;
  const existing = new Set(editorState.entities.map((placed) => placed.entity.id));
  while (existing.has(candidate)) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  return candidate;
}

function selectHtml(options, selected, attributes) {
  return `<select ${attributes}>${options
    .map((option) => `<option value="${escapeAttribute(option)}" ${option === selected ? "selected" : ""}>${escapeHtml(option)}</option>`)
    .join("")}</select>`;
}

function parseScalar(value) {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  if (value === "null") {
    return null;
  }
  if (value.trim() !== "" && !Number.isNaN(Number(value))) {
    return Number(value);
  }
  return value;
}

function setEditorStatus(message) {
  editorStatus.textContent = message;
}

function downloadJson(filename, payload) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function formatValidationError(error) {
  const detail = error.detail;
  if (!Array.isArray(detail) || !detail.length) {
    return "unknown validation error.";
  }
  const first = detail[0];
  return `${(first.loc ?? []).join(".")}: ${first.msg}`;
}

function parsePosition(position) {
  const match = /^\((\d+), (\d+)\)$/.exec(position || "");
  if (!match) {
    return null;
  }
  return { x: Number(match[1]), y: Number(match[2]) };
}

function slugify(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

function refreshSpritesWhenFontsLoad() {
  if (!document.fonts) {
    return;
  }

  Promise.all([document.fonts.load('19px "Noto Emoji Local"', "\u{1F9F1}"), document.fonts.ready])
    .then(() => {
      spriteCache.clear();
      renderPresets();
      renderEditor();
      renderMap(lastMapText, lastAgentPosition);
    })
    .catch(() => undefined);
}

function pixelSprite(value, label, tint = null, size = 24) {
  const textIcon = toTextEmoji(value);
  const source = spriteSource(textIcon, tint, size);
  if (!source) {
    const fallback = document.createElement("span");
    fallback.className = "pixel-sprite-fallback";
    fallback.textContent = textIcon;
    return fallback;
  }

  const image = new Image();
  image.className = "pixel-sprite";
  image.alt = label;
  image.draggable = false;
  image.src = source;
  return image;
}

function spriteSource(icon, tint = null, size = 24) {
  const cacheKey = tint ? `${icon}:${tint}:${size}` : `${icon}:${size}`;
  if (spriteCache.has(cacheKey)) {
    return spriteCache.get(cacheKey);
  }

  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) {
    spriteCache.set(cacheKey, null);
    return null;
  }

  context.imageSmoothingEnabled = false;
  context.clearRect(0, 0, size, size);
  context.font = `${Math.round(size * 0.8)}px "Noto Emoji Local", "Noto Emoji", "Segoe UI Symbol", sans-serif`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillStyle = "#f8ffe8";
  context.fillText(icon, size / 2, size / 2 + size * 0.04);
  if (tint) {
    context.globalCompositeOperation = "source-in";
    context.fillStyle = tint;
    context.fillRect(0, 0, size, size);
    context.globalCompositeOperation = "source-over";
  }

  const source = canvas.toDataURL("image/png");
  spriteCache.set(cacheKey, source);
  return source;
}

function toTextEmoji(value) {
  return value.replaceAll("\uFE0F", "").replace(/(\p{Emoji_Presentation}|\p{Extended_Pictographic})/gu, "$1\uFE0E");
}
