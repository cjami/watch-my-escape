function query(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return element;
}

function queryAll(selector) {
  return [...document.querySelectorAll(selector)];
}

export function appDataFromDocument() {
  return JSON.parse(query("#app-data").textContent);
}

export function getDomRefs() {
  const playGameButton = query("#play-game");
  const openEditorButton = query("#open-editor");

  return {
    screens: new Map(queryAll("[data-screen]").map((screen) => [screen.dataset.screen, screen])),
    modelOptions: query("#model-options"),
    previousModelButton: query("#previous-model"),
    nextModelButton: query("#next-model"),
    chooseModelButton: query("#choose-model"),
    modelMenuButton: query("#model-menu"),
    modelLineup: query("#model-lineup"),
    modelAgentOrbit: query("#model-agent-orbit"),
    modelAgentIcon: query("#model-agent-icon"),
    modelCompany: query("#model-company"),
    modelName: query("#model-name"),
    modelStats: query("#model-stats"),
    modelFile: query("#model-file"),
    mapOptions: query("#map-options"),
    mapPreview: query("#map-preview"),
    mapPreviewTitle: query("#map-preview-title"),
    mapPreviewDescription: query("#map-preview-description"),
    mapBackButton: query("#map-back"),
    selectedModelLabel: query("#selected-model-label"),
    gameSelectionLabel: query("#game-selection-label"),
    runButton: query("#run-escape"),
    restartButton: query("#restart-flow"),
    sanityOutput: query("#sanity"),
    positionOutput: query("#position"),
    mapOutput: query("#map-view"),
    escapeBanner: query("#escape-banner"),
    escapeAgentIcon: query("#escape-agent-icon"),
    visibleEntitiesOutput: query("#visible-entities"),
    inventoryOutput: query("#inventory"),
    transcriptOutput: query("#transcript"),
    gameIntro: query("#game-intro"),
    playGameButton,
    openEditorButton,
    menuOptions: [playGameButton, openEditorButton],
    editorBackButton: query("#editor-back"),
    importMapButton: query("#import-map"),
    importMapFile: query("#import-map-file"),
    exportMapButton: query("#export-map"),
    saveMapButton: query("#save-map"),
    loadMapButton: query("#load-map"),
    loadMapPopup: query("#load-map-popup"),
    loadMapPopupClose: query("#load-map-close"),
    saveMapDialogButton: query("#save-map-dialog"),
    saveMapPopup: query("#save-map-popup"),
    saveMapPopupClose: query("#save-map-close"),
    savedMapList: query("#saved-map-list"),
    savedMapPreview: query("#saved-map-preview"),
    loadSavedMapButton: query("#load-saved-map"),
    deleteSavedMapButton: query("#delete-saved-map"),
    undoEditorButton: query("#undo-editor"),
    redoEditorButton: query("#redo-editor"),
    editorGrid: query("#editor-grid"),
    editorTray: query("#editor-tray"),
    behaviorEditorOverlay: query("#behavior-editor-overlay"),
    behaviorEditorPanel: query("#behavior-editor-panel"),
    entityPresets: query("#entity-presets"),
    entityForm: query("#entity-form"),
    behaviorList: query("#behavior-list"),
    addBehaviorButton: query("#add-behavior"),
    editorStatus: query("#editor-status"),
    editorValidation: query("#editor-validation"),
    editorValidationPopup: query("#editor-validation-popup"),
    editorValidationPopupClose: query("#editor-validation-popup-close"),
    editorValidationPopupList: query("#editor-validation-popup-list"),
    editorMapName: query("#editor-map-name"),
    editorDescription: query("#editor-description"),
    editorToolButtons: queryAll("[data-editor-tool]"),
    editorTabButtons: queryAll("[data-editor-tab]"),
    entityTabPanel: query("#entity-tab-panel"),
    behaviorsTabPanel: query("#behaviors-tab-panel"),
  };
}
