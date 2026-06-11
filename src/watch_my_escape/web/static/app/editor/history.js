import { historyLimit, presets } from "./constants.js";

export function createEditorHistory({ context, renderEditor, renderPresets }) {
  let undoStack = [];
  let redoStack = [];

  function record() {
    undoStack.push(editorSnapshot());
    if (undoStack.length > historyLimit) {
      undoStack = undoStack.slice(-historyLimit);
    }
    redoStack = [];
    updateButtons();
  }

  function undo() {
    if (!undoStack.length) {
      return;
    }
    redoStack.push(editorSnapshot());
    restoreEditorSnapshot(undoStack.pop());
    context.setStatus("Undid last editor change.");
  }

  function redo() {
    if (!redoStack.length) {
      return;
    }
    undoStack.push(editorSnapshot());
    restoreEditorSnapshot(redoStack.pop());
    context.setStatus("Redid editor change.");
  }

  function updateButtons() {
    context.dom.undoEditorButton.disabled = !undoStack.length;
    context.dom.redoEditorButton.disabled = !redoStack.length;
  }

  function editorSnapshot() {
    return {
      state: structuredClone(context.editorState),
      selectedEntityId: context.selectedEntityId,
      selectedTool: context.selectedTool,
      selectedPresetType: context.selectedPreset.type,
      selectedEditorTab: context.selectedEditorTab,
      openBehaviorEditor: structuredClone(context.openBehaviorEditor),
      mapName: context.dom.editorMapName.value,
      description: context.dom.editorDescription.value,
    };
  }

  function restoreEditorSnapshot(snapshot) {
    context.editorState = structuredClone(snapshot.state);
    context.selectedEntityId = snapshot.selectedEntityId;
    context.selectedTool = snapshot.selectedTool;
    context.selectedPreset = presets.find((preset) => preset.type === snapshot.selectedPresetType) ?? context.selectedPreset;
    context.selectedEditorTab = snapshot.selectedEditorTab;
    context.openBehaviorEditor = structuredClone(snapshot.openBehaviorEditor ?? null);
    context.dom.editorMapName.value = snapshot.mapName;
    context.dom.editorDescription.value = snapshot.description;
    context.setEditorTool(context.selectedTool);
    renderPresets();
    renderEditor();
  }

  return {
    record,
    redo,
    undo,
    updateButtons,
  };
}
