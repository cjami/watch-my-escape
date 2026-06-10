export function createScreenController({ dom }) {
  let selectedMenuIndex = 0;

  function showScreen(name) {
    for (const screen of dom.screens.values()) {
      screen.classList.toggle("is-active", screen.dataset.screen === name);
    }
  }

  function showMainMenu() {
    showScreen("menu");
    focusSelectedMenuOption();
  }

  function isScreenActive(name) {
    return dom.screens.get(name).classList.contains("is-active");
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
      dom.menuOptions[selectedMenuIndex].click();
    }
  }

  function moveMenuSelection(direction) {
    selectedMenuIndex = (selectedMenuIndex + direction + dom.menuOptions.length) % dom.menuOptions.length;
    focusSelectedMenuOption();
  }

  function focusSelectedMenuOption() {
    selectMenuOption(selectedMenuIndex);
    dom.menuOptions[selectedMenuIndex].focus({ preventScroll: true });
  }

  function selectMenuOption(index) {
    selectedMenuIndex = index;
    dom.menuOptions.forEach((button, optionIndex) => {
      button.classList.toggle("is-selected", optionIndex === selectedMenuIndex);
    });
  }

  return {
    handleMainMenuKeydown,
    isScreenActive,
    selectMenuOption,
    showMainMenu,
    showScreen,
  };
}
