import { renderMapInto } from "./map-renderer.js";
import { escapeHtml } from "./shared/html.js";

export function createMapSelector({ dom, getSelectedModel, maps, onSelected, pixelSprite }) {
  let selectedMapIndex = 0;

  function renderMapOptions() {
    if (!maps.length) {
      renderEmptyState();
      return;
    }
    selectedMapIndex = normalizeMapIndex(selectedMapIndex);
    dom.mapOptions.replaceChildren(
      ...maps.map((gameMap, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "selection-card map-card";
        button.classList.toggle("is-selected", index === selectedMapIndex);
        button.innerHTML = `
          <span class="selection-title">${escapeHtml(gameMap.name)}</span>
        `;
        button.addEventListener("focus", () => selectMapOption(index));
        button.addEventListener("pointerenter", () => selectMapOption(index));
        button.addEventListener("click", () => {
          selectMapOption(index);
          chooseSelectedMap();
        });
        return button;
      }),
    );
    updateMapPreview();
  }

  function moveMapSelection(direction) {
    if (!maps.length) {
      return;
    }
    selectedMapIndex = normalizeMapIndex(selectedMapIndex + direction);
    focusSelectedMapOption();
  }

  function focusSelectedMapOption() {
    if (!maps.length) {
      return;
    }
    selectMapOption(selectedMapIndex);
    dom.mapOptions.children[selectedMapIndex]?.focus({ preventScroll: true });
  }

  function selectMapOption(index) {
    if (!maps.length) {
      return;
    }
    selectedMapIndex = normalizeMapIndex(index);
    [...dom.mapOptions.children].forEach((button, optionIndex) => {
      button.classList.toggle("is-selected", optionIndex === selectedMapIndex);
    });
    updateMapPreview();
  }

  function chooseSelectedMap() {
    if (!maps.length) {
      return;
    }
    const gameMap = maps[selectedMapIndex];
    dom.gameSelectionLabel.textContent = `${getSelectedModel().display_name} / ${gameMap.name}`;
    onSelected(gameMap);
  }

  function updateMapPreview() {
    const gameMap = maps[selectedMapIndex];
    if (!gameMap) {
      renderEmptyState();
      return;
    }
    dom.mapPreviewTitle.textContent = gameMap.name;
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
    dom.mapPreviewDescription.textContent = "No premade maps are available.";
  }

  function handleKeydown(event) {
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
    return (index + maps.length) % maps.length;
  }

  return {
    focusSelectedMapOption,
    handleKeydown,
    refresh: updateMapPreview,
    render: renderMapOptions,
  };
}
