import { formatValidationError, optionLabel } from "../shared/strings.js";

import { editorValidationDelayMs, effectLabels, simpleActionOptions } from "./constants.js";

export function createEditorValidation({ buildEditorDocument, context }) {
  let validationTimer = null;
  let validationEpoch = 0;

  function schedule() {
    window.clearTimeout(validationTimer);
    validationEpoch += 1;
    updateState("pending", "Validation pending.");
    validationTimer = window.setTimeout(() => validateEditorDocument(validationEpoch), editorValidationDelayMs);
  }

  async function validateEditorDocument(currentEpoch) {
    const localIssues = editorValidationIssues();
    if (localIssues.length) {
      updateState("invalid", localIssues.slice(0, 3).join(" "));
      return;
    }

    try {
      const response = await fetch("/maps/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildEditorDocument()),
      });
      if (currentEpoch !== validationEpoch) {
        return;
      }
      if (!response.ok) {
        const error = await response.json();
        updateState("invalid", `Validation failed: ${formatValidationError(error)}`);
        return;
      }
      updateState("valid", "Map is valid.");
    } catch {
      if (currentEpoch === validationEpoch) {
        updateState("pending", "Validation unavailable while the app is offline.");
      }
    }
  }

  function editorValidationIssues() {
    const issues = [];
    if (!context.dom.editorMapName.value.trim()) {
      issues.push("Map name is required.");
    }
    const entityIds = context.allEditorEntities().map((entity) => entity.id.trim()).filter(Boolean);
    const entityIdSet = new Set(entityIds);
    if (entityIds.length !== new Set(entityIds).size) {
      issues.push("Entity ids must be unique.");
    }
    const positions = context.editorState.entities.map((placed) => `${placed.position.x},${placed.position.y}`);
    if (positions.length !== new Set(positions).size) {
      issues.push("Only one entity may occupy each tile.");
    }
    for (const entity of context.allEditorEntities()) {
      for (const behavior of entity.behaviors) {
        if (behavior.trigger.actions?.length) {
          if (!simpleActionOptions.includes(behavior.trigger.action)) {
            issues.push(`${entity.id} alternative actions must use a simple action.`);
          }
          if (!behavior.trigger.actions.includes(behavior.trigger.action)) {
            issues.push(`${entity.id} alternative actions must include the primary action.`);
          }
          if (behavior.trigger.actions.some((action) => !simpleActionOptions.includes(action))) {
            issues.push(`${entity.id} alternative actions can only use simple actions.`);
          }
          if (behavior.trigger.actions.length !== new Set(behavior.trigger.actions).size) {
            issues.push(`${entity.id} alternative actions cannot repeat actions.`);
          }
        }
        if (behavior.trigger.action === "use_item" && !behavior.trigger.item) {
          issues.push(`${entity.id} use item behavior needs an item.`);
        }
        if (behavior.trigger.item && !entityIdSet.has(behavior.trigger.item)) {
          issues.push(`${entity.id} references missing item ${behavior.trigger.item}.`);
        }
        for (const condition of behavior.conditions) {
          if (condition.entity_id && !entityIdSet.has(condition.entity_id)) {
            issues.push(`${entity.id} condition references missing entity ${condition.entity_id}.`);
          }
        }
        for (const effect of behavior.effects) {
          if (effect.type === "remove_inventory" && !effect.entity_id) {
            issues.push(`${entity.id} ${optionLabel(effectLabels, effect.type)} effect needs an entity.`);
          }
          if (effect.entity_id && !entityIdSet.has(effect.entity_id)) {
            issues.push(`${entity.id} effect references missing entity ${effect.entity_id}.`);
          }
        }
      }
    }
    return issues;
  }

  function updateState(state, message) {
    context.dom.editorValidation.classList.toggle("is-valid", state === "valid");
    context.dom.editorValidation.classList.toggle("is-invalid", state === "invalid");
    context.dom.editorValidation.classList.toggle("is-pending", state === "pending");
    context.dom.editorValidation.textContent = message;
  }

  return {
    issues: editorValidationIssues,
    schedule,
    updateState,
  };
}
