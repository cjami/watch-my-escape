import { appDataFromDocument, getDomRefs } from "./app/dom.js";
import { createEditor } from "./app/editor/controller.js";
import { createGameRunner } from "./app/game-runner.js";
import { createMapRenderer } from "./app/map-renderer.js";
import { createMapSelector } from "./app/maps.js";
import { createModelSelector } from "./app/models.js";
import { createScreenController } from "./app/screens.js";
import { createSpriteRenderer } from "./app/shared/sprites.js";

const appData = appDataFromDocument();
const dom = getDomRefs();
const appState = {
  selectedMap: null,
  selectedModel: null,
};

const sprites = createSpriteRenderer();
const screens = createScreenController({ dom });
const mapRenderer = createMapRenderer({
  dom,
  getSelectedModel: () => appState.selectedModel,
  pixelSprite: sprites.pixelSprite,
});
const mapSelector = createMapSelector({
  dom,
  getSelectedModel: () => appState.selectedModel,
  maps: appData.maps,
  onSelected: (gameMap) => {
    appState.selectedMap = gameMap;
    screens.showScreen("game");
  },
  pixelSprite: sprites.pixelSprite,
});
const modelSelector = createModelSelector({
  dom,
  models: appData.models,
  onSelected: (model) => {
    appState.selectedModel = model;
    screens.showScreen("maps");
    mapSelector.focusSelectedMapOption();
  },
  pixelSprite: sprites.pixelSprite,
});
const gameRunner = createGameRunner({
  dom,
  getSelectedMap: () => appState.selectedMap,
  getSelectedModel: () => appState.selectedModel,
  mapRenderer,
  pixelSprite: sprites.pixelSprite,
  showScreen: screens.showScreen,
});
const editor = createEditor({
  dom,
  onBack: screens.showMainMenu,
  pixelSprite: sprites.pixelSprite,
});

modelSelector.render();
mapSelector.render();
editor.init();
gameRunner.init();
sprites.refreshWhenFontsLoad([editor.refreshSprites, mapSelector.refresh, mapRenderer.refresh]);

dom.screens.get("splash").addEventListener("click", screens.showMainMenu, { once: true });
window.addEventListener("keydown", handleGlobalKeydown);
dom.menuOptions.forEach((button, index) => {
  button.addEventListener("focus", () => screens.selectMenuOption(index));
  button.addEventListener("pointerenter", () => screens.selectMenuOption(index));
});
dom.playGameButton.addEventListener("click", () => {
  screens.selectMenuOption(0);
  modelSelector.render();
  screens.showScreen("models");
  modelSelector.focus();
});
dom.modelMenuButton.addEventListener("click", screens.showMainMenu);
dom.previousModelButton.addEventListener("click", () => modelSelector.change(-1));
dom.nextModelButton.addEventListener("click", () => modelSelector.change(1));
dom.chooseModelButton.addEventListener("click", modelSelector.choose);
dom.modelOptions.addEventListener("keydown", modelSelector.handleKeydown);
dom.mapOptions.addEventListener("keydown", mapSelector.handleKeydown);
dom.openEditorButton.addEventListener("click", () => {
  screens.selectMenuOption(1);
  screens.showScreen("editor");
});

function handleGlobalKeydown(event) {
  if (screens.isScreenActive("splash")) {
    event.preventDefault();
    screens.showMainMenu();
    return;
  }
  if (screens.isScreenActive("menu")) {
    screens.handleMainMenuKeydown(event);
    return;
  }
  if (screens.isScreenActive("models")) {
    if (event.target === dom.modelOptions || dom.modelOptions.contains(event.target)) {
      return;
    }
    modelSelector.handleKeydown(event);
    return;
  }
  if (screens.isScreenActive("maps")) {
    if (event.target === dom.mapOptions || dom.mapOptions.contains(event.target)) {
      return;
    }
    mapSelector.handleKeydown(event);
  }
}
