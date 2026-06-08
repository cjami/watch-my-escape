const appData = JSON.parse(document.querySelector("#app-data").textContent);
const screens = new Map([...document.querySelectorAll("[data-screen]")].map((screen) => [screen.dataset.screen, screen]));
const modelOptions = document.querySelector("#model-options");
const mapOptions = document.querySelector("#map-options");
const selectedModelLabel = document.querySelector("#selected-model-label");
const gameSelectionLabel = document.querySelector("#game-selection-label");
const runButton = document.querySelector("#run-escape");
const restartButton = document.querySelector("#restart-flow");
const statusOutput = document.querySelector("#status");
const sanityOutput = document.querySelector("#sanity");
const positionOutput = document.querySelector("#position");
const mapOutput = document.querySelector("#map-view");
const visibleEntitiesOutput = document.querySelector("#visible-entities");
const inventoryOutput = document.querySelector("#inventory");
const journalOutput = document.querySelector("#journal");
const transcriptOutput = document.querySelector("#transcript");

let activeStream = null;
let selectedModel = null;
let selectedMap = null;

renderModelOptions();
renderMapOptions();

screens.get("splash").addEventListener("click", () => showScreen("models"), { once: true });
window.addEventListener(
  "keydown",
  () => {
    if (screens.get("splash").classList.contains("is-active")) {
      showScreen("models");
    }
  },
  { once: true },
);

runButton.addEventListener("click", runEscape);
restartButton.addEventListener("click", () => {
  stopStream();
  resetGame();
  showScreen("models");
});

function renderModelOptions() {
  modelOptions.replaceChildren(
    ...appData.models.map((model) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "selection-card";
      button.style.setProperty("--accent", model.brand_color);
      button.innerHTML = `
        <span class="selection-chip"></span>
        <span class="selection-title">${escapeHtml(model.display_name)}</span>
        <span class="selection-meta">${escapeHtml(model.company)}</span>
        <span class="selection-detail">${escapeHtml(model.filename)}</span>
      `;
      button.addEventListener("click", () => {
        selectedModel = model;
        selectedModelLabel.textContent = `${model.company} / ${model.display_name}`;
        document.documentElement.style.setProperty("--agent-color", model.brand_color);
        showScreen("maps");
      });
      return button;
    }),
  );
}

function renderMapOptions() {
  mapOptions.replaceChildren(
    ...appData.maps.map((gameMap) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "selection-card map-card";
      button.innerHTML = `
        <span class="selection-title">${escapeHtml(gameMap.name)}</span>
        <span class="selection-meta">${escapeHtml(gameMap.objective)}</span>
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
  runButton.disabled = true;
  statusOutput.textContent = "The model is trying to escape...";
  transcriptOutput.textContent = "Waiting for the first turn...";

  const params = new URLSearchParams({
    model_preset: selectedModel.id,
    map_id: selectedMap.id,
  });
  activeStream = new EventSource(`/escape-stream?${params}`);
  activeStream.onmessage = (event) => {
    const frame = JSON.parse(event.data);
    statusOutput.textContent = frame.status;
    sanityOutput.textContent = `Sanity: ${frame.sanity}`;
    positionOutput.textContent = frame.position ? `Position: ${frame.position}` : "Position: --";
    renderMap(frame.map, frame.position);
    visibleEntitiesOutput.textContent = frame.visible_entities;
    inventoryOutput.textContent = frame.inventory;
    journalOutput.textContent = frame.journal;
    transcriptOutput.textContent = frame.transcript;
    if (frame.escaped || frame.sanity === "0" || frame.status === "Model is not configured.") {
      stopStream();
      runButton.disabled = false;
    }
  };
  activeStream.onerror = () => {
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
  renderMap("", "");
  runButton.disabled = false;
}

function renderMap(mapText, agentPosition) {
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
  rows.forEach((row, y) => {
    row.split(" ").forEach((cell, x) => {
      const tile = document.createElement("span");
      tile.className = "map-tile";
      if (agentCoordinate?.x === x && agentCoordinate.y === y) {
        tile.classList.add("agent-tile");
      }
      tile.textContent = cell === "." ? "" : toTextEmoji(cell);
      mapOutput.append(tile);
    });
  });
}

function parsePosition(position) {
  const match = /^\((\d+), (\d+)\)$/.exec(position || "");
  if (!match) {
    return null;
  }
  return { x: Number(match[1]), y: Number(match[2]) };
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

function toTextEmoji(value) {
  return value.replaceAll("\uFE0F", "").replace(/(\p{Emoji_Presentation}|\p{Extended_Pictographic})/gu, "$1\uFE0E");
}
