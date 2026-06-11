import { downloadJson } from "../shared/downloads.js";
import { formatValidationError, slugify } from "../shared/strings.js";

import { mapSize, simpleActionOptions } from "./constants.js";

export function createEditorDocuments({ context, recordHistory, renderEditor }) {
  let validation = null;

  function setValidation(validationApi) {
    validation = validationApi;
  }

  async function exportEditorMap() {
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
    const normalized = await response.json();
    downloadJson(`${normalized.map.id}.json`, normalized);
    validation.updateState("valid", "Map is valid.");
    context.setStatus("Map validated and exported.");
  }

  async function importEditorMap() {
    const [file] = context.dom.importMapFile.files;
    context.dom.importMapFile.value = "";
    if (!file) {
      return;
    }
    let payload;
    try {
      payload = JSON.parse(await file.text());
    } catch {
      context.setStatus("Import failed: JSON could not be parsed.");
      return;
    }

    const response = await fetch("/maps/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const error = await response.json();
      context.setStatus(`Import failed: ${formatValidationError(error)}`);
      return;
    }

    const normalized = await response.json();
    recordHistory();
    loadEditorDocument(normalized);
    context.setStatus(`Imported ${normalized.map.name}.`);
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
    hideValidationErrorPopup();
  }

  return {
    buildEditorDocument,
    exportEditorMap,
    handleValidationPopupClick,
    handleValidationPopupKeydown,
    importEditorMap,
    loadEditorDocument,
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
  return compactObject({
    id: entity.id.trim(),
    icon: entity.icon.trim(),
    color: normalizeColor(entity.color),
    description: entity.description.trim(),
    passable: entity.passable,
    active: entity.active,
    notable: entity.notable,
    state: entity.state.trim() || "default",
    behaviors: entity.behaviors.map(normalizeBehavior),
  });
}

function normalizeBehavior(behavior) {
  return {
    trigger: normalizeBehaviorTrigger(behavior.trigger),
    conditions: (behavior.conditions ?? []).map(compactObject),
    effects: (behavior.effects ?? []).map(compactObject),
  };
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
