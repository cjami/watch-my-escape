import { createBehaviorEditor } from "./behavior-form.js";
import { createEditorDocuments } from "./document.js";
import { createEntityForm } from "./entity-form.js";
import { createEditorGrid } from "./grid.js";
import { createEditorHistory } from "./history.js";
import { createIconCatalog } from "./icons.js";
import { createPresetPicker } from "./presets.js";
import { createEditorContext } from "./state.js";
import { createEditorTabs } from "./tabs.js";
import { createEditorValidation } from "./validation.js";

export function createEditor({ customMapStore, dom, onBack, onCustomMapsChanged, pixelSprite }) {
  const context = createEditorContext({ dom, pixelSprite });
  const iconCatalog = createIconCatalog({ context });
  const tabs = createEditorTabs({ context });
  const presetPicker = createPresetPicker({ context });
  const history = createEditorHistory({
    context,
    renderEditor,
    renderPresets: presetPicker.render,
  });
  const documents = createEditorDocuments({
    context,
    customMapStore,
    onCustomMapsChanged,
    recordHistory: history.record,
    renderEditor,
  });
  const validation = createEditorValidation({
    buildEditorDocument: documents.buildEditorDocument,
    context,
  });
  const grid = createEditorGrid({
    context,
    history,
    renderEditor,
  });
  const behaviorEditor = createBehaviorEditor({
    context,
    history,
    renderEditor,
    validation,
  });
  const entityForm = createEntityForm({
    context,
    history,
    iconCatalog,
    renderBehaviors: behaviorEditor.render,
    renderEditor,
    renderGrid: grid.renderGrid,
    renderTray: grid.renderTray,
    validation,
  });
  documents.setValidation(validation);

  function init() {
    presetPicker.render();
    renderEditor();
    documents.renderSavedMapList();
    customMapStore.subscribe(documents.renderSavedMapList);
    wireEvents();
  }

  function refreshSprites() {
    presetPicker.render();
    renderEditor();
  }

  function renderEditor() {
    tabs.render();
    grid.renderGrid();
    grid.renderTray();
    entityForm.render();
    behaviorEditor.render();
    history.updateButtons();
    validation.schedule();
  }

  function wireEvents() {
    dom.editorBackButton.addEventListener("click", onBack);
    dom.loadMapButton.addEventListener("click", openLoadMapPopup);
    dom.loadMapPopup.addEventListener("click", handleLoadMapPopupClick);
    dom.saveMapDialogButton.addEventListener("click", openSaveMapPopup);
    dom.saveMapPopup.addEventListener("click", handleSaveMapPopupClick);
    dom.importMapButton.addEventListener("click", () => dom.importMapFile.click());
    dom.importMapFile.addEventListener("change", async () => {
      if (await documents.importEditorMap()) {
        closeLoadMapPopup();
        dom.loadMapButton.focus();
      }
    });
    dom.exportMapButton.addEventListener("click", async () => {
      if (await documents.exportEditorMap()) {
        closeSaveMapPopup();
        dom.saveMapDialogButton.focus();
      }
    });
    dom.saveMapButton.addEventListener("click", async () => {
      if (await documents.saveEditorMap()) {
        closeSaveMapPopup();
        dom.saveMapDialogButton.focus();
      }
    });
    dom.loadSavedMapButton.addEventListener("click", () => {
      if (documents.loadSavedMap()) {
        closeLoadMapPopup();
        dom.loadMapButton.focus();
      }
    });
    dom.deleteSavedMapButton.addEventListener("click", documents.deleteSavedMap);
    dom.savedMapList.addEventListener("keydown", documents.handleSavedMapListKeydown);
    dom.editorValidationPopup.addEventListener("click", documents.handleValidationPopupClick);
    dom.undoEditorButton.addEventListener("click", history.undo);
    dom.redoEditorButton.addEventListener("click", history.redo);
    dom.addBehaviorButton.addEventListener("click", behaviorEditor.addBehavior);
    dom.editorMapName.addEventListener("input", () => {
      history.record();
      validation.schedule();
    });
    dom.editorDescription.addEventListener("input", () => {
      history.record();
      validation.schedule();
    });
    dom.editorToolButtons.forEach((button) => {
      button.addEventListener("click", () => {
        context.setEditorTool(button.dataset.editorTool);
        context.setStatus(context.editorToolHint(button.dataset.editorTool));
      });
    });
    dom.editorTabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        tabs.set(button.dataset.editorTab);
      });
    });
    document.addEventListener("keydown", documents.handleValidationPopupKeydown);
    document.addEventListener("keydown", handleMapDocumentPopupKeydown);
    document.addEventListener("click", behaviorEditor.handleDocumentClick);
    document.addEventListener("pointermove", grid.handleDragPointerMove);
    document.addEventListener("pointerup", grid.finishGridDrag);
  }

  function openLoadMapPopup() {
    documents.renderSavedMapList();
    dom.loadMapPopup.hidden = false;
    const selectedSavedMap = dom.savedMapList.querySelector('[aria-selected="true"]');
    (selectedSavedMap ?? dom.importMapButton).focus();
  }

  function closeLoadMapPopup() {
    dom.loadMapPopup.hidden = true;
  }

  function handleLoadMapPopupClick(event) {
    if (event.target === dom.loadMapPopup || dom.loadMapPopupClose.contains(event.target)) {
      closeLoadMapPopup();
      dom.loadMapButton.focus();
    }
  }

  function openSaveMapPopup() {
    dom.saveMapPopup.hidden = false;
    dom.saveMapButton.focus();
  }

  function closeSaveMapPopup() {
    dom.saveMapPopup.hidden = true;
  }

  function handleSaveMapPopupClick(event) {
    if (event.target === dom.saveMapPopup || dom.saveMapPopupClose.contains(event.target)) {
      closeSaveMapPopup();
      dom.saveMapDialogButton.focus();
    }
  }

  function handleMapDocumentPopupKeydown(event) {
    if (event.key !== "Escape" || (dom.loadMapPopup.hidden && dom.saveMapPopup.hidden)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    if (!dom.loadMapPopup.hidden) {
      closeLoadMapPopup();
      dom.loadMapButton.focus();
      return;
    }
    closeSaveMapPopup();
    dom.saveMapDialogButton.focus();
  }

  return { init, refreshSprites };
}
