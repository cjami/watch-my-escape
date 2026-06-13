export function createScreenController({ dom }) {
  let selectedMenuIndex = 0;

  for (const screen of dom.screens.values()) {
    screen.tabIndex = -1;
  }

  showScreen(activeScreenName() ?? "splash");

  function showScreen(name) {
    const activeScreen = dom.screens.get(name);
    for (const screen of dom.screens.values()) {
      const isActive = screen.dataset.screen === name;
      screen.classList.toggle("is-active", isActive);
      screen.toggleAttribute("aria-hidden", !isActive);
      screen.inert = !isActive;
    }
    return activeScreen;
  }

  function showMainMenu() {
    showScreen("menu");
    focusSelectedMenuOption();
  }

  function focusScreen(name) {
    focusElement(dom.screens.get(name), { silent: true });
  }

  function focusElement(element, { silent = false } = {}) {
    if (!element) {
      return;
    }
    if (silent) {
      element.dataset.silentFocus = "true";
      element.addEventListener("blur", clearSilentFocus, { once: true });
    }
    element.focus({ preventScroll: true });
  }

  function clearSilentFocus(event) {
    delete event.currentTarget.dataset.silentFocus;
  }

  function isScreenActive(name) {
    return dom.screens.get(name).classList.contains("is-active");
  }

  function handleMainMenuKeydown(event) {
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      event.stopPropagation();
      moveMenuSelection(-1);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      event.stopPropagation();
      moveMenuSelection(1);
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

  function activeScreenName() {
    return [...dom.screens.values()].find((screen) => screen.classList.contains("is-active"))?.dataset.screen;
  }

  return {
    focusElement,
    focusScreen,
    handleMainMenuKeydown,
    isScreenActive,
    selectMenuOption,
    showMainMenu,
    showScreen,
  };
}
