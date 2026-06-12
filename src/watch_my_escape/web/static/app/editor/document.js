import { downloadJson } from "../shared/downloads.js";
import { formatValidationError, slugify } from "../shared/strings.js";
import { customMapOptionFromDocument } from "../custom-maps.js";
import { renderMapInto } from "../map-renderer.js";

import { mapSize, simpleActionOptions } from "./constants.js";

export function createEditorDocuments({ context, customMapStore, onCustomMapsChanged = () => {}, recordHistory, renderEditor }) {
  let validation = null;
  let selectedSavedMapId = null;

  function setValidation(validationApi) {
    validation = validationApi;
  }

  async function exportEditorMap() {
    const normalized = await validateCurrentEditorDocument();
    if (!normalized) {
      return false;
    }
    downloadJson(`${normalized.map.id}.json`, normalized);
    validation.updateState("valid", "Map is valid.");
    context.setStatus("Map validated and exported.");
    return true;
  }

  async function saveEditorMap() {
    const normalized = await validateCurrentEditorDocument();
    if (!normalized) {
      return false;
    }

    const existing = customMapStore.get(normalized.map.id);
    if (existing && !window.confirm(`Replace saved map "${existing.map.name || existing.map.id}"?`)) {
      context.setStatus("Save canceled.");
      return false;
    }

    try {
      customMapStore.save(normalized);
    } catch {
      const message = "Save failed: browser storage is unavailable.";
      context.setStatus(message);
      showValidationErrorPopup([message]);
      return false;
    }

    selectedSavedMapId = normalized.map.id;
    renderSavedMapList();
    validation.updateState("valid", "Map is valid.");
    context.setStatus(`Saved ${normalized.map.name}.`);
    onCustomMapsChanged();
    return true;
  }

  function loadSavedMap() {
    const document = selectedSavedMapDocument();
    if (!document) {
      context.setStatus("No saved map selected.");
      return false;
    }
    recordHistory();
    loadEditorDocument(document);
    context.setStatus(`Loaded ${document.map.name}.`);
    return true;
  }

  function deleteSavedMap() {
    const document = selectedSavedMapDocument();
    if (!document) {
      context.setStatus("No saved map selected.");
      return;
    }
    if (!window.confirm(`Delete saved map "${document.map.name || document.map.id}"?`)) {
      context.setStatus("Delete canceled.");
      return;
    }
    try {
      customMapStore.remove(document.map.id);
    } catch {
      context.setStatus("Delete failed: browser storage is unavailable.");
      return;
    }
    selectedSavedMapId = null;
    renderSavedMapList();
    context.setStatus(`Deleted ${document.map.name}.`);
    onCustomMapsChanged();
  }

  async function validateCurrentEditorDocument() {
    const localIssues = validation.issues();
    if (localIssues.length) {
      const message = localIssues.slice(0, 3).join(" ");
      validation.updateState("invalid", message);
      context.setStatus(`Validation failed: ${message}`);
      showValidationErrorPopup(localIssues);
      return;
    }
    const payload = buildEditorDocument();
    let response;
    try {
      response = await fetch("/maps/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch {
      const message = "Validation unavailable while the app is offline.";
      validation.updateState("pending", message);
      context.setStatus(message);
      showValidationErrorPopup([message]);
      return;
    }
    if (!response.ok) {
      const error = await response.json();
      const message = formatValidationError(error);
      validation.updateState("invalid", message);
      context.setStatus(`Validation failed: ${message}`);
      showValidationErrorPopup([message]);
      return;
    }
    return response.json();
  }

  async function importEditorMap() {
    const [file] = context.dom.importMapFile.files;
    context.dom.importMapFile.value = "";
    if (!file) {
      return false;
    }
    let payload;
    try {
      payload = JSON.parse(await file.text());
    } catch {
      context.setStatus("Import failed: JSON could not be parsed.");
      return false;
    }

    const response = await fetch("/maps/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const error = await response.json();
      context.setStatus(`Import failed: ${formatValidationError(error)}`);
      return false;
    }

    const normalized = await response.json();
    recordHistory();
    loadEditorDocument(normalized);
    context.setStatus(`Imported ${normalized.map.name}.`);
    return true;
  }

  function loadEditorDocument(document) {
    context.dom.editorDescription.value = document.description;
    context.dom.editorMapName.value = document.map.name || document.map.id;
    context.editorState = {
      agentStart: document.map.agent_start,
      entities: document.map.entities.map((placed) => ({
        position: placed.position,
        entity: normalizeImportedEntity(placed.entity),
      })),
      unplacedEntities: (document.map.unplaced_entities ?? []).map(normalizeImportedEntity),
    };
    context.selectedEntityId = context.editorState.entities[0]?.entity.id ?? context.editorState.unplacedEntities[0]?.id ?? null;
    context.selectedEditorTab = "entity";
    context.openBehaviorEditor = null;
    renderEditor();
  }

  function renderSavedMapList() {
    const savedMaps = customMapStore.list();
    if (!savedMaps.some((savedDocument) => savedDocument.map.id === selectedSavedMapId)) {
      selectedSavedMapId = savedMaps[0]?.map.id ?? null;
    }

    context.dom.savedMapList.replaceChildren(
      ...(savedMaps.length ? savedMaps.map(savedMapListItem) : [savedMapEmptyState()]),
    );

    const hasSelection = Boolean(selectedSavedMapId);
    context.dom.loadSavedMapButton.disabled = !hasSelection;
    context.dom.deleteSavedMapButton.disabled = !hasSelection;
    renderSavedMapPreview();
  }

  function savedMapListItem(savedDocument) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "saved-map-list-item";
    button.dataset.mapId = savedDocument.map.id;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", String(savedDocument.map.id === selectedSavedMapId));
    button.innerHTML = `
      <span class="saved-map-list-name"></span>
      <span class="saved-map-list-description"></span>
    `;
    button.querySelector(".saved-map-list-name").textContent = savedDocument.map.name || savedDocument.map.id;
    button.querySelector(".saved-map-list-description").textContent = savedDocument.description;
    button.addEventListener("click", () => selectSavedMap(savedDocument.map.id));
    return button;
  }

  function savedMapEmptyState() {
    const empty = document.createElement("div");
    empty.className = "saved-map-list-empty";
    empty.textContent = "No saved maps.";
    return empty;
  }

  function selectSavedMap(mapId) {
    selectedSavedMapId = mapId;
    renderSavedMapList();
  }

  function renderSavedMapPreview() {
    const savedDocument = selectedSavedMapDocument();
    context.dom.savedMapPreview.replaceChildren();
    if (!savedDocument) {
      return;
    }

    const option = customMapOptionFromDocument(savedDocument);
    renderMapInto({
      agentPosition: option.agent_position,
      colorText: option.preview_map_colors,
      container: context.dom.savedMapPreview,
      mapText: option.preview_map,
      pixelSprite: context.pixelSprite,
    });
  }

  function handleSavedMapListKeydown(event) {
    const savedMaps = customMapStore.list();
    if (!savedMaps.length) {
      return;
    }
    const currentIndex = Math.max(
      0,
      savedMaps.findIndex((savedDocument) => savedDocument.map.id === selectedSavedMapId),
    );
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      selectSavedMap(savedMaps[Math.max(0, currentIndex - 1)].map.id);
      focusSelectedSavedMap();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      selectSavedMap(savedMaps[Math.min(savedMaps.length - 1, currentIndex + 1)].map.id);
      focusSelectedSavedMap();
    }
  }

  function focusSelectedSavedMap() {
    [...context.dom.savedMapList.querySelectorAll("[data-map-id]")]
      .find((button) => button.dataset.mapId === selectedSavedMapId)
      ?.focus({ preventScroll: true });
  }

  function selectedSavedMapDocument() {
    return selectedSavedMapId ? customMapStore.get(selectedSavedMapId) : null;
  }

  function buildEditorDocument() {
    return {
      description: context.dom.editorDescription.value.trim(),
      map: {
        id: slugify(context.dom.editorMapName.value) || "new-escape-room",
        name: context.dom.editorMapName.value.trim(),
        agent_start: context.editorState.agentStart,
        width: mapSize,
        height: mapSize,
        entities: context.editorState.entities.map((placed) => ({
          position: placed.position,
          entity: normalizeEntity(placed.entity),
        })),
        unplaced_entities: (context.editorState.unplacedEntities ?? []).map(normalizeEntity),
      },
    };
  }

  function showValidationErrorPopup(issues) {
    context.dom.editorValidationPopupList.replaceChildren(
      ...issues.map((issue) => {
        const item = document.createElement("li");
        item.textContent = issue;
        return item;
      }),
    );
    context.dom.editorValidationPopup.hidden = false;
    context.dom.editorValidationPopupClose.focus();
  }

  function hideValidationErrorPopup() {
    context.dom.editorValidationPopup.hidden = true;
  }

  function handleValidationPopupClick(event) {
    if (
      event.target === context.dom.editorValidationPopup ||
      context.dom.editorValidationPopupClose.contains(event.target)
    ) {
      hideValidationErrorPopup();
    }
  }

  function handleValidationPopupKeydown(event) {
    if (context.dom.editorValidationPopup.hidden || event.key !== "Escape") {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    hideValidationErrorPopup();
  }

  return {
    buildEditorDocument,
    exportEditorMap,
    deleteSavedMap,
    handleValidationPopupClick,
    handleValidationPopupKeydown,
    importEditorMap,
    handleSavedMapListKeydown,
    loadEditorDocument,
    loadSavedMap,
    renderSavedMapList,
    saveEditorMap,
    setValidation,
  };
}

function normalizeImportedEntity(entity) {
  return {
    id: entity.id,
    icon: entity.icon,
    color: normalizeColor(entity.color) ?? "",
    description: entity.description,
    passable: entity.passable,
    active: entity.active,
    notable: entity.notable,
    state: entity.state,
    behaviors: (entity.behaviors ?? []).map(normalizeImportedBehavior),
  };
}

function normalizeEntity(entity) {
  const entityId = entity.id.trim();
  return compactObject({
    id: entityId,
    icon: entity.icon.trim(),
    color: normalizeColor(entity.color),
    description: entity.description.trim(),
    passable: entity.passable,
    active: entity.active,
    notable: entity.notable,
    state: entity.state.trim() || "default",
    behaviors: entity.behaviors.map((behavior) => normalizeBehavior(behavior, entityId)),
  });
}

function normalizeBehavior(behavior, entityId) {
  return {
    trigger: normalizeBehaviorTrigger(behavior.trigger),
    conditions: (behavior.conditions ?? []).map(compactObject),
    effects: (behavior.effects ?? []).map((effect) => normalizeEffect(effect, entityId)).map(compactObject),
  };
}

function normalizeEffect(effect, entityId) {
  if (effect.type === "add_inventory" && !effect.entity_id) {
    return { ...effect, entity_id: entityId };
  }
  return effect;
}

function normalizeImportedBehavior(behavior) {
  return {
    trigger: normalizeImportedTrigger(behavior.trigger ?? {}),
    conditions: behavior.conditions ?? [],
    effects: behavior.effects ?? [],
  };
}

function normalizeImportedTrigger(trigger) {
  const action = trigger.action ?? "examine";
  const actions = simpleTriggerActions({ ...trigger, action });
  return compactObject({
    ...trigger,
    action,
    actions: actions.length > 1 ? actions : undefined,
  });
}

function normalizeBehaviorTrigger(trigger) {
  if (!isSimpleAction(trigger.action)) {
    return compactObject({
      action: trigger.action,
      item: trigger.action === "use_item" ? trigger.item : undefined,
      phrase: trigger.action === "talk_to" ? trigger.phrase : undefined,
    });
  }
  const actions = simpleTriggerActions(trigger);
  return compactObject({
    action: actions[0] ?? trigger.action,
    actions: actions.length > 1 ? actions : undefined,
  });
}

function simpleTriggerActions(trigger) {
  const actions = Array.isArray(trigger.actions) && trigger.actions.length ? trigger.actions : [trigger.action];
  const selected = new Set(actions.filter(isSimpleAction));
  if (isSimpleAction(trigger.action)) {
    selected.add(trigger.action);
  }
  return simpleActionOptions.filter((action) => selected.has(action));
}

function isSimpleAction(action) {
  return simpleActionOptions.includes(action);
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined && entry !== null && entry !== ""),
  );
}

function normalizeColor(value) {
  const color = String(value ?? "").trim();
  return /^#[0-9a-f]{6}$/iu.test(color) ? color : undefined;
}
