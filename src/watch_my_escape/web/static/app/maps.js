import { escapeHtml } from "./shared/html.js";

export function createMapSelector({ dom, getSelectedModel, maps, onSelected }) {
  let selectedMapIndex = 0;

  function renderMapOptions() {
    if (!maps.length) {
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
          <span class="selection-detail">${escapeHtml(gameMap.description)}</span>
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
  }

  function chooseSelectedMap() {
    if (!maps.length) {
      return;
    }
    const gameMap = maps[selectedMapIndex];
    dom.gameSelectionLabel.textContent = `${getSelectedModel().display_name} / ${gameMap.name}`;
    onSelected(gameMap);
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
    render: renderMapOptions,
  };
}
