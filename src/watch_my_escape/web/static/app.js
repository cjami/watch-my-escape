import emojibaseCompactData from "emojibase-data/en/compact.json";

const appData = JSON.parse(document.querySelector("#app-data").textContent);
const screens = new Map([...document.querySelectorAll("[data-screen]")].map((screen) => [screen.dataset.screen, screen]));
const modelOptions = document.querySelector("#model-options");
const previousModelButton = document.querySelector("#previous-model");
const nextModelButton = document.querySelector("#next-model");
const chooseModelButton = document.querySelector("#choose-model");
const modelMenuButton = document.querySelector("#model-menu");
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
const menuOptions = [playGameButton, openEditorButton];
const editorBackButton = document.querySelector("#editor-back");
const importMapButton = document.querySelector("#import-map");
const importMapFile = document.querySelector("#import-map-file");
const exportMapButton = document.querySelector("#export-map");
const undoEditorButton = document.querySelector("#undo-editor");
const redoEditorButton = document.querySelector("#redo-editor");
const editorGrid = document.querySelector("#editor-grid");
const entityPresets = document.querySelector("#entity-presets");
const entityForm = document.querySelector("#entity-form");
const behaviorList = document.querySelector("#behavior-list");
const addBehaviorButton = document.querySelector("#add-behavior");
const editorStatus = document.querySelector("#editor-status");
const editorValidation = document.querySelector("#editor-validation");
const editorMapName = document.querySelector("#editor-map-name");
const editorDescription = document.querySelector("#editor-description");
const editorTabButtons = document.querySelectorAll("[data-editor-tab]");
const entityTabPanel = document.querySelector("#entity-tab-panel");
const behaviorsTabPanel = document.querySelector("#behaviors-tab-panel");

const mapSize = 16;
const historyLimit = 50;
const editorValidationDelayMs = 600;
const escapeCelebrationDelayMs = 2000;
const actionLabelHeight = 0.52;
const actionLabelPadding = 0.06;
const actionLabelFallbackWidth = 0.9;
const actionLabelFallbackOffset = 0.28;
const actionLabelMinWidth = 1.25;
const actionLabelMaxWidth = 3.3;
const actionLabelCharacterWidth = 0.34;
const actionLabelWidthPadding = 0.28;
const spriteCache = new Map();
const actionOptions = ["examine", "pick_up", "open", "close", "push", "pull", "talk_to", "use", "use_item"];
const actionLabels = {
  examine: "examine",
  pick_up: "pick up",
  open: "open",
  close: "close",
  push: "push",
  pull: "pull",
  talk_to: "talk to",
  use: "use",
  use_item: "use item",
};
const effectOptions = [
  "message",
  "add_inventory",
  "remove_inventory",
  "set_entity_state",
  "set_entity_passable",
  "set_entity_active",
  "escape_map",
];
const effectLabels = {
  message: "Message",
  add_inventory: "Give",
  remove_inventory: "Take",
  set_entity_state: "State",
  set_entity_passable: "Passable",
  set_entity_active: "Active",
  escape_map: "Escape",
};
const booleanLabels = {
  true: "Yes",
  false: "No",
};
const maxVisibleIconOptions = 10;
const suggestedIconValues = [
  "🧱",
  "🚪",
  "🔑",
  "📝",
  "🧍",
  "🎚️",
  "📦",
  "💡",
  "🪟",
  "🧰",
  "🔒",
  "🪜",
  "🧪",
  "📚",
  "🏁",
  "🌐",
  "🕯️",
  "🕳️",
  "🗿",
  "🪞",
  "🧩",
  "🔎",
  "🧭",
  "🧲",
  "⚙️",
  "⏳",
  "🧿",
  "💎",
  "🪙",
  "🧹",
  "🪣",
  "🪤",
];
const emojiIconOptions = emojibaseCompactData
  .filter((emoji) => emoji.unicode && emoji.label)
  .map((emoji) => ({
    icon: emoji.unicode,
    name: emoji.label,
    terms: Array.isArray(emoji.tags) ? emoji.tags : [],
    searchText: normalizeIconSearch([emoji.label, emoji.unicode, ...(Array.isArray(emoji.tags) ? emoji.tags : [])].join(" ")),
    searchTokens: normalizedIconTokens([emoji.label, ...(Array.isArray(emoji.tags) ? emoji.tags : [])].join(" ")),
  }));
const emojiIconOptionsByIcon = new Map();
for (const option of emojiIconOptions) {
  emojiIconOptionsByIcon.set(option.icon, option);
  emojiIconOptionsByIcon.set(normalizeEmojiIcon(option.icon), option);
}
const suggestedIconOptions = suggestedIconValues.map((icon) => iconOptionForIcon(icon)).filter(Boolean);
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
let selectedMenuIndex = 0;
let selectedEntityId = null;
let selectedEditorTab = "entity";
let selectedBehaviorIndex = 0;
let iconSearchQuery = "";
let editorState = starterEditorState();
let undoStack = [];
let redoStack = [];
let dragState = null;
let validationTimer = null;
let validationEpoch = 0;
let selectedModelIndex = 0;
let lastMapText = "";
let lastVisibilityText = "";
let lastAgentPosition = "";
let lastActionLabel = "";
let gameIntroTimer = null;
let escapeCelebrationTimer = null;
let runEpoch = 0;

renderModelOptions();
renderMapOptions();
renderPresets();
renderEditor();
refreshSpritesWhenFontsLoad();

screens.get("splash").addEventListener("click", showMainMenu, { once: true });
window.addEventListener("keydown", handleGlobalKeydown);
menuOptions.forEach((button, index) => {
  button.addEventListener("focus", () => selectMenuOption(index));
  button.addEventListener("pointerenter", () => selectMenuOption(index));
});

playGameButton.addEventListener("click", () => {
  selectMenuOption(0);
  renderModelOptions();
  showScreen("models");
  modelOptions.focus();
});
previousModelButton.addEventListener("click", () => changeModel(-1));
nextModelButton.addEventListener("click", () => changeModel(1));
chooseModelButton.addEventListener("click", chooseSelectedModel);
modelMenuButton.addEventListener("click", showMainMenu);
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
openEditorButton.addEventListener("click", () => {
  selectMenuOption(1);
  showScreen("editor");
});
editorBackButton.addEventListener("click", showMainMenu);
importMapButton.addEventListener("click", () => importMapFile.click());
importMapFile.addEventListener("change", importEditorMap);
exportMapButton.addEventListener("click", exportEditorMap);
undoEditorButton.addEventListener("click", undoEditorChange);
redoEditorButton.addEventListener("click", redoEditorChange);
addBehaviorButton.addEventListener("click", () => {
  const entity = selectedEntity();
  if (!entity) {
    setEditorStatus("Select an entity before adding behavior.");
    return;
  }
  recordEditorHistory();
  entity.behaviors.push(defaultBehavior());
  selectedBehaviorIndex = entity.behaviors.length - 1;
  setEditorTab("behaviors");
  renderEditor();
  setEditorStatus("Behavior added.");
});
restartButton.addEventListener("click", () => {
  runEpoch += 1;
  stopStream();
  resetGame();
  showScreen("models");
});
runButton.addEventListener("click", runEscape);
editorMapName.addEventListener("input", () => {
  recordEditorHistory();
  scheduleEditorValidation();
});
editorDescription.addEventListener("input", () => {
  recordEditorHistory();
  scheduleEditorValidation();
});
document.querySelectorAll("[data-editor-tool]").forEach((button) => {
  button.addEventListener("click", () => {
    setEditorTool(button.dataset.editorTool);
    setEditorStatus(editorToolHint(button.dataset.editorTool));
  });
});
editorTabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setEditorTab(button.dataset.editorTab);
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
  const startupDelay = gameStartupDelay();
  void playGameIntro();
  statusOutput.textContent = "The model is trying to escape...";

  const params = new URLSearchParams({
    model_preset: selectedModel.id,
    map_id: selectedMap.id,
    startup_delay_ms: String(startupDelay),
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
    renderMap(frame.map, frame.position, frame.visibility, frame.action_label);
    visibleEntitiesOutput.textContent = frame.visible_entities;
    inventoryOutput.textContent = frame.inventory;
    journalOutput.textContent = frame.journal;
    transcriptOutput.textContent = frame.transcript;
    if (frame.escaped) {
      scheduleEscapeCelebration(currentRunEpoch);
    } else {
      clearEscapeCelebrationTimer();
      escapeBanner.hidden = true;
    }
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
}

function showScreen(name) {
  for (const screen of screens.values()) {
    screen.classList.toggle("is-active", screen.dataset.screen === name);
  }
}

function showMainMenu() {
  showScreen("menu");
  focusSelectedMenuOption();
}

function handleGlobalKeydown(event) {
  if (screens.get("splash").classList.contains("is-active")) {
    event.preventDefault();
    showMainMenu();
    return;
  }
  if (screens.get("menu").classList.contains("is-active")) {
    handleMainMenuKeydown(event);
  }
}

function handleMainMenuKeydown(event) {
  if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
    event.preventDefault();
    moveMenuSelection(-1);
    return;
  }
  if (event.key === "ArrowDown" || event.key === "ArrowRight") {
    event.preventDefault();
    moveMenuSelection(1);
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    menuOptions[selectedMenuIndex].click();
  }
}

function moveMenuSelection(direction) {
  selectedMenuIndex = (selectedMenuIndex + direction + menuOptions.length) % menuOptions.length;
  focusSelectedMenuOption();
}

function focusSelectedMenuOption() {
  selectMenuOption(selectedMenuIndex);
  menuOptions[selectedMenuIndex].focus({ preventScroll: true });
}

function selectMenuOption(index) {
  selectedMenuIndex = index;
  menuOptions.forEach((button, optionIndex) => {
    button.classList.toggle("is-selected", optionIndex === selectedMenuIndex);
  });
}

function gameIntroDuration() {
  if (!gameIntro) {
    return 0;
  }
  return 4300;
}

function gameStartupDelay() {
  if (!gameIntro) {
    return 0;
  }
  return 2000;
}

function playGameIntro(introDuration = gameIntroDuration()) {
  if (!gameIntro) {
    return Promise.resolve();
  }

  window.clearTimeout(gameIntroTimer);
  gameIntro.hidden = false;
  gameIntro.classList.remove("is-playing");
  void gameIntro.offsetWidth;
  gameIntro.classList.add("is-playing");
  return new Promise((resolve) => {
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

function scheduleEscapeCelebration(currentRunEpoch) {
  clearEscapeCelebrationTimer();
  escapeBanner.hidden = true;
  escapeCelebrationTimer = window.setTimeout(() => {
    if (currentRunEpoch !== runEpoch) {
      return;
    }
    renderEscapeCelebration();
    escapeBanner.hidden = false;
    escapeCelebrationTimer = null;
  }, escapeCelebrationDelayMs);
}

function clearEscapeCelebrationTimer() {
  window.clearTimeout(escapeCelebrationTimer);
  escapeCelebrationTimer = null;
}

function resetGame() {
  statusOutput.textContent = "Ready.";
  sanityOutput.textContent = "Sanity: 100";
  positionOutput.textContent = "Position: --";
  visibleEntitiesOutput.textContent = "- None.";
  inventoryOutput.textContent = "- Empty.";
  journalOutput.textContent = "- No notes recorded.";
  transcriptOutput.textContent = "The model has not tried the room yet.";
  clearEscapeCelebrationTimer();
  escapeBanner.hidden = true;
  escapeAgentIcon.replaceChildren();
  renderMap("", "", "", "");
  runButton.disabled = false;
}

function renderMap(mapText, agentPosition, visibilityText = "", actionLabel = "") {
  const previousAgentPosition = lastAgentPosition;
  lastMapText = mapText;
  lastVisibilityText = visibilityText;
  lastAgentPosition = agentPosition;
  lastActionLabel = actionLabel;
  mapOutput.replaceChildren();
  const rows = parseMapRows(mapText);
  if (!rows.length) {
    return;
  }

  const visibilityRows = parseVisibilityRows(visibilityText);
  const hasVisibility = visibilityRows.length === rows.length;
  const agentCoordinate = parsePosition(agentPosition);
  const agentMoved = Boolean(previousAgentPosition && agentPosition && previousAgentPosition !== agentPosition);
  const labelPosition = actionLabel
    ? actionLabelPosition(rows, visibilityRows, hasVisibility, agentCoordinate, actionLabel)
    : null;
  rows.forEach((row, y) => {
    row.forEach((cell, x) => {
      const tile = document.createElement("span");
      tile.className = "map-tile";
      const visibleToAgent = !hasVisibility || visibilityRows[y]?.[x] !== false;
      tile.classList.toggle("visible-tile", visibleToAgent);
      tile.classList.toggle("hidden-tile", !visibleToAgent);
      tile.setAttribute("aria-label", visibleToAgent ? "visible to agent" : "not visible to agent");
      const isAgentTile = agentCoordinate?.x === x && agentCoordinate.y === y;
      if (agentCoordinate?.x === x && agentCoordinate.y === y) {
        tile.classList.add("agent-tile");
        tile.classList.toggle("agent-just-moved", agentMoved);
      }
      if (cell !== ".") {
        const tint = isAgentTile ? selectedModel?.brand_color : null;
        tile.append(pixelSprite(cell, cell, tint));
      }
      mapOutput.append(tile);
    });
  });
  if (labelPosition) {
    mapOutput.append(actionLabelElement(actionLabel, labelPosition));
  }
}

function parseMapRows(mapText) {
  if (!mapText?.trim()) {
    return [];
  }
  return mapText
    .trim()
    .split("\n")
    .map((row) => row.split(" "));
}

function parseVisibilityRows(visibilityText) {
  if (!visibilityText?.trim()) {
    return [];
  }
  return visibilityText
    .trim()
    .split("\n")
    .map((row) => row.split(" ").map((cell) => cell === "1"));
}

function actionLabelPosition(rows, visibilityRows, hasVisibility, agentCoordinate, label) {
  if (!agentCoordinate) {
    return null;
  }

  const width = actionLabelWidth(label);
  const center = { x: agentCoordinate.x + 0.5, y: agentCoordinate.y + 0.5 };
  const candidates = actionLabelCandidates(center, width);
  const candidate =
    candidates.find((placement) =>
      canPlaceActionLabel(rows, visibilityRows, hasVisibility, agentCoordinate, placement.box),
    ) ?? actionLabelFallback(center);
  return {
    direction: candidate.direction,
    left: `${(candidate.x / rows[0].length) * 100}%`,
    top: `${(candidate.y / rows.length) * 100}%`,
  };
}

function actionLabelWidth(label) {
  return Math.min(
    actionLabelMaxWidth,
    Math.max(actionLabelMinWidth, label.length * actionLabelCharacterWidth + actionLabelWidthPadding),
  );
}

function actionLabelCandidates(center, width) {
  const topAnchor = center.y - 0.5 - actionLabelPadding;
  const rightAnchor = center.x + 0.5 + actionLabelPadding;
  const bottomAnchor = center.y + 0.5 + actionLabelPadding;
  const leftAnchor = center.x - 0.5 - actionLabelPadding;
  return [
    {
      direction: "above",
      x: center.x,
      y: topAnchor,
      box: boxAbove(center.x, topAnchor, width),
    },
    {
      direction: "right",
      x: rightAnchor,
      y: center.y,
      box: boxRight(rightAnchor, center.y, width),
    },
    {
      direction: "below",
      x: center.x,
      y: bottomAnchor,
      box: boxBelow(center.x, bottomAnchor, width),
    },
    {
      direction: "left",
      x: leftAnchor,
      y: center.y,
      box: boxLeft(leftAnchor, center.y, width),
    },
  ];
}

function actionLabelFallback(center) {
  const y = Math.max(actionLabelHeight / 2, center.y - actionLabelFallbackOffset);
  return {
    direction: "agent",
    x: center.x,
    y,
    box: boxFromCenter(center.x, y, actionLabelFallbackWidth, actionLabelHeight),
  };
}

function boxAbove(x, bottom, width) {
  return { left: x - width / 2, right: x + width / 2, top: bottom - actionLabelHeight, bottom };
}

function boxRight(left, y, width) {
  return { left, right: left + width, top: y - actionLabelHeight / 2, bottom: y + actionLabelHeight / 2 };
}

function boxBelow(x, top, width) {
  return { left: x - width / 2, right: x + width / 2, top, bottom: top + actionLabelHeight };
}

function boxLeft(right, y, width) {
  return { left: right - width, right, top: y - actionLabelHeight / 2, bottom: y + actionLabelHeight / 2 };
}

function boxFromCenter(x, y, width, height) {
  return {
    left: x - width / 2,
    right: x + width / 2,
    top: y - height / 2,
    bottom: y + height / 2,
  };
}

function canPlaceActionLabel(rows, visibilityRows, hasVisibility, agentCoordinate, box) {
  if (box.left < 0 || box.top < 0 || box.right > rows[0].length || box.bottom > rows.length) {
    return false;
  }

  for (let y = Math.floor(box.top); y < Math.ceil(box.bottom); y += 1) {
    for (let x = Math.floor(box.left); x < Math.ceil(box.right); x += 1) {
      if (x === agentCoordinate.x && y === agentCoordinate.y) {
        continue;
      }
      if (labelOverlapsVisibleEntity(rows, visibilityRows, hasVisibility, box, x, y)) {
        return false;
      }
    }
  }
  return true;
}

function labelOverlapsVisibleEntity(rows, visibilityRows, hasVisibility, box, x, y) {
  const cell = rows[y]?.[x];
  const visibleToAgent = !hasVisibility || visibilityRows[y]?.[x] !== false;
  return Boolean(cell && cell !== "." && visibleToAgent && rectanglesOverlap(box, cellBox(x, y)));
}

function cellBox(x, y) {
  return { left: x, right: x + 1, top: y, bottom: y + 1 };
}

function rectanglesOverlap(first, second) {
  return (
    first.left < second.right &&
    first.right > second.left &&
    first.top < second.bottom &&
    first.bottom > second.top
  );
}

function actionLabelElement(label, position) {
  const element = document.createElement("span");
  element.className = "action-label";
  element.classList.add(`is-${position.direction}`);
  element.style.left = position.left;
  element.style.top = position.top;
  element.textContent = label;
  return element;
}

function renderEscapeCelebration() {
  escapeAgentIcon.replaceChildren(pixelSprite("\u{1F973}", "Escaped agent", selectedModel?.brand_color, 40));
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
      name.className = "preset-name";
      name.textContent = preset.name;
      button.append(icon, name);
      button.classList.toggle("is-selected", preset === selectedPreset);
      button.addEventListener("click", () => {
        selectedPreset = preset;
        setEditorTool("place");
        renderPresets();
        setEditorStatus(`${preset.name} preset selected.`);
      });
      return button;
    }),
  );
}

function renderEditor() {
  renderEditorTabs();
  renderEditorGrid();
  renderEntityForm();
  renderBehaviors();
  updateHistoryButtons();
  scheduleEditorValidation();
}

function renderEditorGrid() {
  editorGrid.replaceChildren();
  for (let y = 0; y < mapSize; y += 1) {
    for (let x = 0; x < mapSize; x += 1) {
      const cell = document.createElement("button");
      const entity = editorState.entities.find((candidate) => candidate.position.x === x && candidate.position.y === y);
      const isAgentStart = editorState.agentStart.x === x && editorState.agentStart.y === y;
      cell.type = "button";
      cell.className = "editor-cell";
      cell.dataset.x = String(x);
      cell.dataset.y = String(y);
      cell.classList.toggle("is-start", isAgentStart);
      cell.classList.toggle("is-selected", entity?.entity.id === selectedEntityId);
      cell.classList.toggle("is-inactive", Boolean(entity && !entity.entity.active));
      applyDragClasses(cell, x, y);
      if (entity) {
        cell.append(pixelSprite(entity.entity.icon, entity.entity.name));
      }
      cell.title = editorCellTitle(entity, isAgentStart, x, y);
      cell.setAttribute("aria-label", cell.title);
      cell.addEventListener("pointerdown", (event) => handleEditorCellPointerDown(event, cell, x, y, entity));
      cell.addEventListener("pointerenter", () => handleEditorCellPointerEnter(cell, x, y));
      cell.addEventListener("pointerup", () => handleEditorCellPointerUp(x, y));
      editorGrid.append(cell);
    }
  }
}

function handleEditorCellPointerDown(event, cell, x, y, placedEntity) {
  if (event.button !== 0) {
    return;
  }
  event.preventDefault();
  clearDropPreview();
  if (selectedTool === "start") {
    beginStartDrag(cell, x, y);
    return;
  }
  if (selectedTool === "select" && !placedEntity && editorState.agentStart.x === x && editorState.agentStart.y === y) {
    beginStartDrag(cell, x, y);
    return;
  }
  if (selectedTool === "select" && !placedEntity) {
    selectedEntityId = null;
    selectedEditorTab = "entity";
    renderEditor();
    return;
  }
  dragState = {
    tool: selectedTool,
    sourceId: placedEntity?.entity.id ?? null,
    sourceX: x,
    sourceY: y,
    targetX: x,
    targetY: y,
    count: 0,
    changed: false,
    visited: new Set(),
  };
  if (selectedTool === "erase") {
    paintErase(x, y);
    return;
  }
  if (selectedTool === "place") {
    paintPlace(x, y);
    return;
  }
  if (selectedTool === "select" && placedEntity) {
    updateDropPreview(cell, x, y);
    setEditorStatus(`Dragging ${placedEntity.entity.name}. Release on an open tile to move it.`);
  }
}

function handleEditorCellPointerEnter(cell, x, y) {
  if (!dragState) {
    return;
  }
  if (dragState.tool === "place") {
    paintPlace(x, y);
    return;
  }
  if (dragState.tool === "erase") {
    paintErase(x, y);
    return;
  }
  if (dragState.tool === "start") {
    updateDropPreview(cell, x, y);
    return;
  }
  if (dragState.tool === "select" && dragState.sourceId) {
    updateDropPreview(cell, x, y);
  }
}

function handleEditorCellPointerUp(x, y) {
  if (!dragState) {
    return;
  }
  if (dragState.tool === "select") {
    finishSelectDrag(x, y);
  }
  if (dragState.tool === "start") {
    finishStartDrag(x, y);
  }
  finishGridDrag();
}

document.addEventListener("pointerup", finishGridDrag);

function beginStartDrag(cell, x, y) {
  dragState = {
    tool: "start",
    sourceId: null,
    sourceX: editorState.agentStart.x,
    sourceY: editorState.agentStart.y,
    targetX: x,
    targetY: y,
    count: 0,
    changed: false,
    visited: new Set(),
  };
  updateDropPreview(cell, x, y);
  setEditorStatus("Dragging agent start. Release on a tile to set the new starting position.");
}

function finishSelectDrag(x, y) {
  if (!dragState?.sourceId) {
    return;
  }
  const source = editorState.entities.find((placed) => placed.entity.id === dragState.sourceId);
  if (!source) {
    return;
  }
  if (source.position.x === x && source.position.y === y) {
    selectedEntityId = source.entity.id;
    selectedEditorTab = "entity";
    renderEditor();
    return;
  }
  const target = entityAt(x, y);
  if (target) {
    selectedEntityId = source.entity.id;
    setEditorStatus(`${target.entity.name} already occupies that tile.`);
    renderEditor();
    return;
  }
  recordEditorHistory();
  source.position = { x, y };
  selectedEntityId = source.entity.id;
  selectedEditorTab = "entity";
  setEditorStatus(`Moved ${source.entity.name} to (${x}, ${y}).`);
  renderEditor();
}

function finishStartDrag(x, y) {
  if (!dragState) {
    return;
  }
  if (editorState.agentStart.x === x && editorState.agentStart.y === y) {
    setEditorStatus(`Agent start remains at (${x}, ${y}).`);
    return;
  }
  recordEditorHistory();
  editorState.agentStart = { x, y };
  setEditorStatus(`Agent start moved to (${x}, ${y}).`);
  renderEditor();
}

function finishGridDrag() {
  if (!dragState) {
    return;
  }
  if (dragState.tool === "place" && dragState.count > 1) {
    setEditorStatus(`Placed ${dragState.count} ${selectedPreset.name.toLowerCase()} entities.`);
  }
  if (dragState.tool === "erase" && dragState.count > 1) {
    setEditorStatus(`Removed ${dragState.count} entities.`);
  }
  dragState = null;
  clearDropPreview();
}

function paintPlace(x, y) {
  if (!dragState || visitDraggedTile(x, y) || entityAt(x, y)) {
    return;
  }
  recordDragHistory();
  const entity = createEntity(selectedPreset, x, y);
  editorState.entities.push(entity);
  selectedEntityId = entity.entity.id;
  dragState.count += 1;
  setEditorStatus(`Placed ${entity.entity.name}.`);
  renderEditor();
}

function paintErase(x, y) {
  const placedEntity = entityAt(x, y);
  if (!dragState || visitDraggedTile(x, y) || !placedEntity) {
    return;
  }
  recordDragHistory();
  editorState.entities = editorState.entities.filter((candidate) => candidate.entity.id !== placedEntity.entity.id);
  if (selectedEntityId === placedEntity.entity.id) {
    selectedEntityId = null;
  }
  dragState.count += 1;
  setEditorStatus(`Removed ${placedEntity.entity.name}.`);
  renderEditor();
}

function visitDraggedTile(x, y) {
  const key = `${x},${y}`;
  if (dragState.visited.has(key)) {
    return true;
  }
  dragState.visited.add(key);
  return false;
}

function recordDragHistory() {
  if (dragState.changed) {
    return;
  }
  recordEditorHistory();
  dragState.changed = true;
}

function clearDropPreview() {
  editorGrid.classList.remove("is-dragging");
  editorGrid.querySelectorAll(".is-drag-source, .is-drop-ok, .is-drop-blocked").forEach((cell) => {
    cell.classList.remove("is-drag-source", "is-drop-ok", "is-drop-blocked");
  });
}

function updateDropPreview(cell, x, y) {
  if (!dragState) {
    return;
  }
  dragState.targetX = x;
  dragState.targetY = y;
  clearDropPreview();
  applyDragClasses(editorGridCell(dragState.sourceX, dragState.sourceY), dragState.sourceX, dragState.sourceY);
  applyDragClasses(cell, x, y);
}

function applyDragClasses(cell, x, y) {
  if (!cell || !dragState) {
    return;
  }
  if (dragState.tool !== "select" && dragState.tool !== "start") {
    return;
  }
  editorGrid.classList.add("is-dragging");
  if (dragState.sourceX === x && dragState.sourceY === y) {
    cell.classList.add("is-drag-source");
  }
  if (dragState.targetX !== x || dragState.targetY !== y) {
    return;
  }
  if (dragState.tool === "start") {
    cell.classList.add("is-drop-ok");
    return;
  }
  if (dragState.tool !== "select" || !dragState.sourceId) {
    return;
  }
  const target = entityAt(x, y);
  cell.classList.add(target && target.entity.id !== dragState.sourceId ? "is-drop-blocked" : "is-drop-ok");
}

function editorGridCell(x, y) {
  return editorGrid.querySelector(`[data-x="${x}"][data-y="${y}"]`);
}

function setEditorTool(tool) {
  selectedTool = tool;
  document.querySelectorAll("[data-editor-tool]").forEach((toolButton) => {
    toolButton.classList.toggle("is-selected", toolButton.dataset.editorTool === tool);
  });
}

function editorToolHint(tool) {
  const hints = {
    select: "Select an entity, drag an entity to move it, or drag the start marker.",
    place: `Drag on open tiles to place ${selectedPreset.name.toLowerCase()} entities.`,
    erase: "Drag across occupied tiles to remove entities.",
    start: "Click a tile or drag the start marker to set the agent start.",
  };
  return hints[tool] ?? "Ready.";
}

function editorCellTitle(entity, isAgentStart, x, y) {
  return [entity?.entity.name, isAgentStart ? "Agent start" : null, `(${x}, ${y})`].filter(Boolean).join(" - ");
}

function setEditorTab(tab) {
  selectedEditorTab = tab;
  renderEditorTabs();
}

function renderEditorTabs() {
  editorTabButtons.forEach((button) => {
    const selected = button.dataset.editorTab === selectedEditorTab;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  entityTabPanel.hidden = selectedEditorTab !== "entity";
  behaviorsTabPanel.hidden = selectedEditorTab !== "behaviors";
}

function renderEntityForm() {
  const placed = selectedPlacedEntity();
  if (!placed) {
    entityForm.innerHTML = `<p class="selection-detail">Select an entity on the grid or place one from a preset.</p>`;
    return;
  }
  const entity = placed.entity;
  entityForm.innerHTML = `
    <label><span>Id</span><input data-entity-field="id" type="text" value="${escapeAttribute(entity.id)}" /></label>
    <label><span>Name</span><input data-entity-field="name" type="text" value="${escapeAttribute(entity.name)}" /></label>
    <div>
      <span class="field-label">Icon</span>
      <label class="icon-search-label">
        <span>Search Icons</span>
        <input data-icon-search type="search" placeholder="door, key, clue..." value="${escapeAttribute(iconSearchQuery)}" />
      </label>
      <div class="icon-picker" aria-label="Entity icon"></div>
    </div>
    <label><span>Description</span><textarea data-entity-field="description" rows="3">${escapeHtml(entity.description)}</textarea></label>
    <label><span>State</span><input data-entity-field="state" type="text" value="${escapeAttribute(entity.state)}" /></label>
    <div class="checkbox-row">
      <label><input data-entity-field="passable" type="checkbox" ${entity.passable ? "checked" : ""} />Passable</label>
      <label><input data-entity-field="active" type="checkbox" ${entity.active ? "checked" : ""} />Active</label>
      <label><input data-entity-field="notable" type="checkbox" ${entity.notable ? "checked" : ""} />Notable</label>
    </div>
  `;
  entityForm.querySelectorAll("[data-entity-field]").forEach((input) => {
    input.addEventListener("input", () => updateEntityField(input, placed));
  });
  const iconPicker = entityForm.querySelector(".icon-picker");
  const iconSearch = entityForm.querySelector("[data-icon-search]");
  renderIconOptions(iconPicker, placed);
  iconSearch.addEventListener("input", () => {
    iconSearchQuery = iconSearch.value;
    renderIconOptions(iconPicker, placed);
  });
}

function renderIconOptions(iconPicker, placed) {
  const entity = placed.entity;
  iconPicker.replaceChildren(
    ...visibleIconOptions(entity.icon).map((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "icon-option";
      button.dataset.icon = option.icon;
      button.classList.toggle("is-selected", entity.icon === option.icon);
      button.title = option.name;
      button.setAttribute("aria-label", `Choose ${option.name} icon`);
      button.append(pixelSprite(option.icon, option.name));
      button.addEventListener("click", () => {
        recordEditorHistory();
        placed.entity.icon = button.dataset.icon;
        renderEditor();
      });
      return button;
    }),
  );
}

function visibleIconOptions(selectedIcon) {
  const query = normalizeIconSearch(iconSearchQuery);
  const queryTerms = query.split(/\s+/).filter(Boolean);
  const matchingOptions = query ? rankedIconOptions(queryTerms) : suggestedIconOptions;
  const visibleOptions = matchingOptions.slice(0, maxVisibleIconOptions);
  if (!selectedIcon || visibleOptions.some((option) => normalizeEmojiIcon(option.icon) === normalizeEmojiIcon(selectedIcon))) {
    return visibleOptions;
  }

  const selectedOption = iconOptionForIcon(selectedIcon);
  return [selectedOption, ...matchingOptions.filter((option) => normalizeEmojiIcon(option.icon) !== normalizeEmojiIcon(selectedIcon))].slice(
    0,
    maxVisibleIconOptions,
  );
}

function rankedIconOptions(queryTerms) {
  return emojiIconOptions
    .map((option, index) => ({
      option,
      rank: iconSearchRank(option, queryTerms),
      index,
    }))
    .filter((result) => result.rank > 0)
    .sort((left, right) => right.rank - left.rank || left.index - right.index)
    .map((result) => result.option);
}

function iconSearchRank(option, queryTerms) {
  return queryTerms.reduce((total, term) => {
    const termRank = iconSearchTermRank(option, term);
    return termRank > 0 && total >= 0 ? total + termRank : -1;
  }, 0);
}

function iconSearchTermRank(option, term) {
  if (normalizeEmojiIcon(option.icon) === normalizeEmojiIcon(term)) {
    return 100;
  }
  if (option.searchTokens.some((token) => token === term)) {
    return 80;
  }
  if (option.searchTokens.some((token) => token.startsWith(term))) {
    return 50;
  }
  return option.searchText.includes(term) ? 10 : 0;
}

function iconOptionForIcon(icon) {
  return (
    emojiIconOptionsByIcon.get(icon) ??
    emojiIconOptionsByIcon.get(normalizeEmojiIcon(icon)) ?? {
      icon,
      name: "Current icon",
      terms: [],
    }
  );
}

function normalizeIconSearch(value) {
  return String(value).trim().toLowerCase();
}

function normalizedIconTokens(value) {
  return normalizeIconSearch(value).split(/[^a-z0-9]+/).filter(Boolean);
}

function normalizeEmojiIcon(value) {
  return String(value).replaceAll("\uFE0E", "").replaceAll("\uFE0F", "");
}

function updateEntityField(input, placed) {
  recordEditorHistory();
  const field = input.dataset.entityField;
  if (field === "id") {
    selectedEntityId = input.value.trim();
  }
  if (input.type === "checkbox") {
    placed.entity[field] = input.checked;
  } else if (field === "id") {
    placed.entity[field] = input.value.trim();
  } else {
    placed.entity[field] = input.value;
  }
  updateEditorAfterEntityFieldChange(field);
}

function updateEditorAfterEntityFieldChange(field) {
  renderEditorGrid();
  if (field === "id" || field === "notable") {
    renderBehaviors();
  }
  updateHistoryButtons();
  scheduleEditorValidation();
}

function renderBehaviors() {
  const placed = selectedPlacedEntity();
  behaviorList.replaceChildren();
  if (!placed) {
    behaviorList.innerHTML = `<p class="selection-detail">No entity selected.</p>`;
    return;
  }
  if (!placed.entity.behaviors.length) {
    behaviorList.innerHTML = `<p class="selection-detail">No behaviors configured.</p>`;
    selectedBehaviorIndex = 0;
    return;
  }
  selectedBehaviorIndex = Math.min(selectedBehaviorIndex, placed.entity.behaviors.length - 1);
  const ruleList = document.createElement("div");
  ruleList.className = "behavior-rule-list";
  placed.entity.behaviors.forEach((behavior, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "behavior-summary";
    button.classList.toggle("is-selected", index === selectedBehaviorIndex);
    button.innerHTML = `
      <span>Rule ${index + 1}</span>
      <strong>${escapeHtml(behaviorSummary(behavior))}</strong>
    `;
    button.addEventListener("click", () => {
      selectedBehaviorIndex = index;
      renderBehaviors();
    });
    ruleList.append(button);
  });
  behaviorList.append(ruleList, behaviorBlock(placed.entity.behaviors[selectedBehaviorIndex], selectedBehaviorIndex));
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
      <label class="block-field">On action ${selectHtml(actionOptions, behavior.trigger.action, `data-trigger-field="action"`, actionLabels)}</label>
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
      recordEditorHistory();
      const value = input.value.trim();
      behavior.trigger[input.dataset.triggerField] = value || undefined;
      normalizeTrigger(behavior.trigger);
      if (input.dataset.triggerField === "action") {
        renderBehaviors();
      } else {
        renderEditor();
      }
    });
  });
  block.querySelector("[data-remove-behavior]").addEventListener("click", () => {
    recordEditorHistory();
    selectedPlacedEntity().entity.behaviors.splice(index, 1);
    selectedBehaviorIndex = Math.max(0, index - 1);
    renderEditor();
  });
  block.querySelector("[data-add-condition]").addEventListener("click", () => {
    recordEditorHistory();
    behavior.conditions.push({ entity_id: "", state: "" });
    renderEditor();
  });
  block.querySelector("[data-add-effect]").addEventListener("click", () => {
    recordEditorHistory();
    behavior.effects.push({ type: "message", text: "Something happens." });
    renderEditor();
  });
  renderConditionList(block.querySelector("[data-condition-list]"), behavior);
  renderEffectList(block.querySelector("[data-effect-list]"), behavior);
  return block;
}

function triggerFieldsHtml(trigger) {
  if (trigger.action === "use_item") {
    return `<label class="block-field">Item ${entitySelectHtml(trigger.item, `data-trigger-field="item"`, { emptyLabel: "Choose item" })}</label>`;
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
        <label class="block-field">Entity ${entitySelectHtml(condition.entity_id, `data-condition-field="entity_id"`, { emptyLabel: "Any entity" })}</label>
        <label class="block-field">State <input data-condition-field="state" type="text" value="${escapeAttribute(condition.state ?? "")}" /></label>
        <button type="button" class="mini-button" data-remove-condition="${index}">Remove</button>
      `;
      row.querySelectorAll("[data-condition-field]").forEach((input) => {
        input.addEventListener("input", () => {
          recordEditorHistory();
          condition[input.dataset.conditionField] = input.value.trim() || null;
          scheduleEditorValidation();
        });
      });
      row.querySelector("[data-remove-condition]").addEventListener("click", () => {
        recordEditorHistory();
        behavior.conditions.splice(index, 1);
        renderEditor();
      });
      return row;
    }),
  );
}

function renderEffectList(container, behavior) {
  container.replaceChildren(
    ...behavior.effects.map((effect, index) => {
      const row = document.createElement("div");
      row.className = "block-grid effect-grid";
      row.innerHTML = `
        <label class="block-field">Effect ${selectHtml(effectOptions, effect.type, `data-effect-field="type"`, effectLabels)}</label>
        ${effectFieldsHtml(effect)}
        <button type="button" class="mini-button block-action" data-remove-effect="${index}">Remove</button>
      `;
      row.querySelectorAll("[data-effect-field]").forEach((input) => {
        input.addEventListener("input", () => {
          recordEditorHistory();
          updateEffectField(effect, input);
          if (input.dataset.effectField === "type") {
            renderEditor();
          } else {
            scheduleEditorValidation();
          }
        });
      });
      row.querySelector("[data-remove-effect]").addEventListener("click", () => {
        recordEditorHistory();
        behavior.effects.splice(index, 1);
        renderEditor();
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
    return `<label class="block-field">Entity ${entitySelectHtml(effect.entity_id, `data-effect-field="entity_id"`, { allowEmpty: false })}</label>`;
  }
  if (effect.type === "set_entity_state") {
    return `
      <label class="block-field">Entity ${entitySelectHtml(effect.entity_id, `data-effect-field="entity_id"`)}</label>
      <label class="block-field">State <input data-effect-field="state" type="text" value="${escapeAttribute(effect.state ?? "")}" /></label>
    `;
  }
  if (effect.type === "set_entity_passable" || effect.type === "set_entity_active") {
    const valueField = effect.type === "set_entity_passable" ? "passable" : "active";
    return `
      <label class="block-field">Entity ${entitySelectHtml(effect.entity_id, `data-effect-field="entity_id"`)}</label>
      <label class="block-field">${effectToggleLabel(effect.type)} ${selectHtml(["true", "false"], String(effect[valueField] ?? true), `data-effect-field="${valueField}"`, booleanLabels)}</label>
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
  effect[field] = input.value.trim() || undefined;
}

async function exportEditorMap() {
  const localIssues = editorValidationIssues();
  if (localIssues.length) {
    const message = localIssues.slice(0, 3).join(" ");
    updateValidationState("invalid", message);
    setEditorStatus(`Validation failed: ${message}`);
    return;
  }
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
  updateValidationState("valid", "Map is valid.");
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
  recordEditorHistory();
  loadEditorDocument(normalized);
  setEditorStatus(`Imported ${normalized.map.name}.`);
}

function loadEditorDocument(document) {
  editorDescription.value = document.description;
  editorMapName.value = document.map.name || document.map.id;
  editorState = {
    agentStart: document.map.agent_start,
    entities: document.map.entities.map((placed) => ({
      position: placed.position,
      entity: normalizeImportedEntity(placed.entity),
    })),
  };
  selectedEntityId = editorState.entities[0]?.entity.id ?? null;
  selectedEditorTab = "entity";
  selectedBehaviorIndex = 0;
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
    behaviors: entity.behaviors ?? [],
  };
}

function buildEditorDocument() {
  return {
    description: editorDescription.value.trim(),
    map: {
      id: slugify(editorMapName.value) || "new-escape-room",
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

function behaviorSummary(behavior) {
  const trigger = behavior.trigger.item
    ? `${optionLabel(actionLabels, behavior.trigger.action)} ${behavior.trigger.item}`
    : behavior.trigger.phrase
      ? `${optionLabel(actionLabels, behavior.trigger.action)} "${behavior.trigger.phrase}"`
      : optionLabel(actionLabels, behavior.trigger.action);
  const effects = behavior.effects.map(effectSummary).filter(Boolean);
  return `${trigger} -> ${effects.length ? effects.join(", ") : "no effects"}`;
}

function effectSummary(effect) {
  if (effect.type === "message") {
    return "Message";
  }
  if (effect.type === "escape_map") {
    return "Escape";
  }
  if (effect.type === "set_entity_state") {
    return `State ${effect.entity_id || "self"}`;
  }
  if (effect.type === "set_entity_active") {
    return `Active ${effect.active ? "yes" : "no"} ${effect.entity_id || "self"}`;
  }
  if (effect.type === "set_entity_passable") {
    return `Passable ${effect.passable ? "yes" : "no"} ${effect.entity_id || "self"}`;
  }
  if (effect.type === "add_inventory") {
    return `Give ${effect.entity_id || "item"}`;
  }
  if (effect.type === "remove_inventory") {
    return `Take ${effect.entity_id || "item"}`;
  }
  return optionLabel(effectLabels, effect.type);
}

function effectToggleLabel(type) {
  if (type === "set_entity_passable") {
    return "Passable";
  }
  if (type === "set_entity_active") {
    return "Active";
  }
  return "Value";
}

function entitySelectHtml(selected, attributes, options = {}) {
  const allowEmpty = options.allowEmpty ?? true;
  const emptyLabel = options.emptyLabel ?? "Current entity";
  const entityOptions = editorState.entities
    .filter((placed) => placed.entity.notable)
    .map((placed) => ({
      value: placed.entity.id,
      label: placed.entity.id,
    }));
  const optionHtml = [
    ...(allowEmpty ? [{ value: "", label: emptyLabel }] : []),
    ...entityOptions,
  ]
    .map(
      (option) =>
        `<option value="${escapeAttribute(option.value)}" ${option.value === (selected ?? "") ? "selected" : ""}>${escapeHtml(option.label)}</option>`,
    )
    .join("");
  return `<select ${attributes}>${optionHtml}</select>`;
}

function recordEditorHistory() {
  undoStack.push(editorSnapshot());
  if (undoStack.length > historyLimit) {
    undoStack = undoStack.slice(-historyLimit);
  }
  redoStack = [];
  updateHistoryButtons();
}

function undoEditorChange() {
  if (!undoStack.length) {
    return;
  }
  redoStack.push(editorSnapshot());
  restoreEditorSnapshot(undoStack.pop());
  setEditorStatus("Undid last editor change.");
}

function redoEditorChange() {
  if (!redoStack.length) {
    return;
  }
  undoStack.push(editorSnapshot());
  restoreEditorSnapshot(redoStack.pop());
  setEditorStatus("Redid editor change.");
}

function editorSnapshot() {
  return {
    state: structuredClone(editorState),
    selectedEntityId,
    selectedTool,
    selectedPresetType: selectedPreset.type,
    selectedEditorTab,
    selectedBehaviorIndex,
    mapName: editorMapName.value,
    description: editorDescription.value,
  };
}

function restoreEditorSnapshot(snapshot) {
  editorState = structuredClone(snapshot.state);
  selectedEntityId = snapshot.selectedEntityId;
  selectedTool = snapshot.selectedTool;
  selectedPreset = presets.find((preset) => preset.type === snapshot.selectedPresetType) ?? selectedPreset;
  selectedEditorTab = snapshot.selectedEditorTab;
  selectedBehaviorIndex = snapshot.selectedBehaviorIndex;
  editorMapName.value = snapshot.mapName;
  editorDescription.value = snapshot.description;
  setEditorTool(selectedTool);
  renderPresets();
  renderEditor();
}

function updateHistoryButtons() {
  undoEditorButton.disabled = !undoStack.length;
  redoEditorButton.disabled = !redoStack.length;
}

function scheduleEditorValidation() {
  window.clearTimeout(validationTimer);
  validationEpoch += 1;
  updateValidationState("pending", "Validation pending.");
  validationTimer = window.setTimeout(() => validateEditorDocument(validationEpoch), editorValidationDelayMs);
}

async function validateEditorDocument(currentEpoch) {
  const localIssues = editorValidationIssues();
  if (localIssues.length) {
    updateValidationState("invalid", localIssues.slice(0, 3).join(" "));
    return;
  }

  try {
    const response = await fetch("/maps/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildEditorDocument()),
    });
    if (currentEpoch !== validationEpoch) {
      return;
    }
    if (!response.ok) {
      const error = await response.json();
      updateValidationState("invalid", `Validation failed: ${formatValidationError(error)}`);
      return;
    }
    updateValidationState("valid", "Map is valid.");
  } catch {
    if (currentEpoch === validationEpoch) {
      updateValidationState("pending", "Validation unavailable while the app is offline.");
    }
  }
}

function editorValidationIssues() {
  const issues = [];
  if (!editorMapName.value.trim()) {
    issues.push("Map name is required.");
  }
  const entityIds = editorState.entities.map((placed) => placed.entity.id.trim()).filter(Boolean);
  const entityIdSet = new Set(entityIds);
  if (entityIds.length !== new Set(entityIds).size) {
    issues.push("Entity ids must be unique.");
  }
  const positions = editorState.entities.map((placed) => `${placed.position.x},${placed.position.y}`);
  if (positions.length !== new Set(positions).size) {
    issues.push("Only one entity may occupy each tile.");
  }
  for (const placed of editorState.entities) {
    for (const behavior of placed.entity.behaviors) {
      if (behavior.trigger.action === "use_item" && !behavior.trigger.item) {
        issues.push(`${placed.entity.id} use item behavior needs an item.`);
      }
      if (behavior.trigger.item && !entityIdSet.has(behavior.trigger.item)) {
        issues.push(`${placed.entity.id} references missing item ${behavior.trigger.item}.`);
      }
      for (const condition of behavior.conditions) {
        if (condition.entity_id && !entityIdSet.has(condition.entity_id)) {
          issues.push(`${placed.entity.id} condition references missing entity ${condition.entity_id}.`);
        }
      }
      for (const effect of behavior.effects) {
        if ((effect.type === "add_inventory" || effect.type === "remove_inventory") && !effect.entity_id) {
          issues.push(`${placed.entity.id} ${optionLabel(effectLabels, effect.type)} effect needs an entity.`);
        }
        if (effect.entity_id && !entityIdSet.has(effect.entity_id)) {
          issues.push(`${placed.entity.id} effect references missing entity ${effect.entity_id}.`);
        }
      }
    }
  }
  return issues;
}

function updateValidationState(state, message) {
  editorValidation.classList.toggle("is-valid", state === "valid");
  editorValidation.classList.toggle("is-invalid", state === "invalid");
  editorValidation.classList.toggle("is-pending", state === "pending");
  editorValidation.textContent = message;
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

function selectHtml(options, selected, attributes, labels = {}) {
  return `<select ${attributes}>${options
    .map(
      (option) =>
        `<option value="${escapeAttribute(option)}" ${option === selected ? "selected" : ""}>${escapeHtml(optionLabel(labels, option))}</option>`,
    )
    .join("")}</select>`;
}

function optionLabel(labels, value) {
  return labels[value] ?? value;
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
      renderMap(lastMapText, lastAgentPosition, lastVisibilityText, lastActionLabel);
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
