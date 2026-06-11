import { customMapOptionFromDocument } from "./custom-maps.js";
import { renderMapInto } from "./map-renderer.js";
import { escapeHtml } from "./shared/html.js";

export function createMapSelector({
  customMapStore,
  dom,
  getSelectedModel,
  maps = [],
  onCustomMapDeleted = () => {},
  onSelected,
  pixelSprite,
  premadeMaps = maps,
}) {
  let selectedMapIndex = 0;
  let currentMaps = [];

  function renderMapOptions() {
    const selectedIdentity = currentMaps[selectedMapIndex] ? mapIdentity(currentMaps[selectedMapIndex]) : null;
    currentMaps = playableMaps();
    if (!currentMaps.length) {
      renderEmptyState();
      return;
    }
    const retainedIndex = selectedIdentity ? currentMaps.findIndex((gameMap) => mapIdentity(gameMap) === selectedIdentity) : -1;
    selectedMapIndex = retainedIndex >= 0 ? retainedIndex : normalizeMapIndex(selectedMapIndex);
    dom.mapOptions.replaceChildren(...mapOptionElements());
    updateMapPreview();
  }

  function moveMapSelection(direction) {
    if (!currentMaps.length) {
      return;
    }
    selectedMapIndex = normalizeMapIndex(selectedMapIndex + direction);
    focusSelectedMapOption();
  }

  function focusSelectedMapOption() {
    if (!currentMaps.length) {
      return;
    }
    selectMapOption(selectedMapIndex);
    selectedMapOptionButton()?.focus({ preventScroll: true });
  }

  function selectMapOption(index) {
    if (!currentMaps.length) {
      return;
    }
    selectedMapIndex = normalizeMapIndex(index);
    dom.mapOptions.querySelectorAll("[data-map-index]").forEach((button) => {
      button.classList.toggle("is-selected", Number(button.dataset.mapIndex) === selectedMapIndex);
    });
    updateMapPreview();
  }

  function chooseSelectedMap() {
    if (!currentMaps.length) {
      return;
    }
    const gameMap = currentMaps[selectedMapIndex];
    dom.gameSelectionLabel.textContent = `${getSelectedModel().display_name} / ${mapDisplayName(gameMap)}`;
    onSelected(gameMap);
  }

  function updateMapPreview() {
    const gameMap = currentMaps[selectedMapIndex];
    if (!gameMap) {
      renderEmptyState();
      return;
    }
    dom.mapPreviewTitle.textContent = mapDisplayName(gameMap);
    dom.mapPreviewDescription.textContent = gameMap.description;
    renderMapInto({
      agentPosition: gameMap.agent_position,
      colorText: gameMap.preview_map_colors,
      container: dom.mapPreview,
      getAgentColor: () => getSelectedModel()?.brand_color,
      mapText: gameMap.preview_map,
      pixelSprite,
    });
  }

  function renderEmptyState() {
    dom.mapOptions.replaceChildren();
    dom.mapPreview.replaceChildren();
    dom.mapPreviewTitle.textContent = "No Maps";
    dom.mapPreviewDescription.textContent = "No maps are available.";
  }

  function handleKeydown(event) {
    if (event.target?.matches("[data-map-delete]") && (event.key === "Enter" || event.key === " ")) {
      return;
    }
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      moveMapSelection(-1);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      moveMapSelection(1);
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      chooseSelectedMap();
    }
  }

  function normalizeMapIndex(index) {
    return (index + currentMaps.length) % currentMaps.length;
  }

  function playableMaps() {
    return [
      ...premadeMaps.map((gameMap) => ({ ...gameMap, source: "premade" })),
      ...customMapStore.list().map(customMapOptionFromDocument),
    ];
  }

  function mapOptionElements() {
    const elements = [];
    let previousSource = null;
    currentMaps.forEach((gameMap, index) => {
      if (gameMap.source !== previousSource) {
        elements.push(mapOptionHeading(gameMap.source));
        previousSource = gameMap.source;
      }
      elements.push(mapOptionRow(gameMap, index));
    });
    return elements;
  }

  function mapOptionHeading(source) {
    const heading = document.createElement("div");
    heading.className = "map-option-heading";
    heading.textContent = source === "custom" ? "Custom Maps" : "Premade Maps";
    return heading;
  }

  function mapOptionRow(gameMap, index) {
    const row = document.createElement("div");
    row.className = `map-option-row is-${gameMap.source}`;
    row.append(mapOptionButton(gameMap, index));
    if (gameMap.source === "custom") {
      row.append(deleteMapButton(gameMap, index));
    }
    return row;
  }

  function mapOptionButton(gameMap, index) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `selection-card map-card is-${gameMap.source}`;
    button.dataset.mapIndex = String(index);
    button.classList.toggle("is-selected", index === selectedMapIndex);
    button.innerHTML = `
      <span class="selection-title">${escapeHtml(gameMap.name)}</span>
      ${gameMap.source === "custom" ? '<span class="map-card-badge">Custom</span>' : ""}
    `;
    button.addEventListener("focus", () => selectMapOption(index));
    button.addEventListener("pointerenter", () => selectMapOption(index));
    button.addEventListener("click", () => {
      selectMapOption(index);
      chooseSelectedMap();
    });
    return button;
  }

  function deleteMapButton(gameMap, index) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mini-button map-delete-button";
    button.dataset.mapDelete = "true";
    button.textContent = "Delete";
    button.setAttribute("aria-label", `Delete custom map ${gameMap.name}`);
    button.addEventListener("focus", () => selectMapOption(index));
    button.addEventListener("pointerenter", () => selectMapOption(index));
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteCustomMap(gameMap);
    });
    return button;
  }

  function deleteCustomMap(gameMap) {
    if (!window.confirm(`Delete custom map "${gameMap.name}"?`)) {
      return;
    }
    customMapStore.remove(gameMap.id);
    onCustomMapDeleted(gameMap);
    renderMapOptions();
  }

  function selectedMapOptionButton() {
    return dom.mapOptions.querySelector(`[data-map-index="${selectedMapIndex}"]`);
  }

  function mapIdentity(gameMap) {
    return `${gameMap.source}:${gameMap.id}`;
  }

  function mapDisplayName(gameMap) {
    return gameMap.source === "custom" ? `${gameMap.name} (Custom)` : gameMap.name;
  }

  return {
    focusSelectedMapOption,
    handleKeydown,
    refresh: updateMapPreview,
    render: renderMapOptions,
  };
}
