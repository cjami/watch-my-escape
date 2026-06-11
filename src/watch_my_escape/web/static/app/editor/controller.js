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

export function createEditor({ dom, onBack, pixelSprite }) {
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
    dom.importMapButton.addEventListener("click", () => dom.importMapFile.click());
    dom.importMapFile.addEventListener("change", documents.importEditorMap);
    dom.exportMapButton.addEventListener("click", documents.exportEditorMap);
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
    document.addEventListener("click", behaviorEditor.handleDocumentClick);
    document.addEventListener("pointerup", grid.finishGridDrag);
  }

  return { init, refreshSprites };
}
