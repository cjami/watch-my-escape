import { escapeAttribute, escapeHtml } from "../shared/html.js";
import { optionLabel, selectHtml } from "../shared/strings.js";

import {
  actionLabels,
  actionOptions,
  booleanLabels,
  effectLabels,
  effectOptions,
  simpleActionOptions,
} from "./constants.js";
import { defaultBehavior, defaultEffect } from "./state.js";

export function createBehaviorEditor({ context, history, renderEditor, validation }) {
  function addBehavior() {
    const entity = context.selectedEntity();
    if (!entity) {
      context.setStatus("Select an entity before adding behavior.");
      return;
    }
    history.record();
    entity.behaviors.push(defaultBehavior());
    context.openBehaviorEditor = { entityId: entity.id, index: entity.behaviors.length - 1 };
    context.selectedEditorTab = "behaviors";
    renderEditor();
    context.setStatus("Behavior added.");
  }

  function render() {
    const placed = context.selectedPlacedEntity();
    context.dom.behaviorList.replaceChildren();
    const openRule = openBehaviorRule();
    if (!placed) {
      context.dom.behaviorList.innerHTML = `<p class="selection-detail">No entity selected.</p>`;
      renderBehaviorOverlay(openRule);
      return;
    }
    if (!placed.entity.behaviors.length) {
      context.dom.behaviorList.innerHTML = `<p class="selection-detail">No behaviors configured.</p>`;
      renderBehaviorOverlay(openRule);
      return;
    }
    const ruleList = document.createElement("div");
    ruleList.className = "behavior-rule-list";
    placed.entity.behaviors.forEach((behavior, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "behavior-summary";
      button.classList.toggle("is-selected", openRule?.entity.id === placed.entity.id && openRule.index === index);
      button.setAttribute("aria-expanded", String(openRule?.entity.id === placed.entity.id && openRule.index === index));
      button.innerHTML = `
        <span>Rule ${index + 1}</span>
        <strong>${escapeHtml(behaviorSummary(behavior))}</strong>
      `;
      button.addEventListener("click", () => {
        toggleBehaviorEditor(placed.entity.id, index);
        render();
      });
      ruleList.append(button);
    });
    context.dom.behaviorList.append(ruleList);
    renderBehaviorOverlay(openRule);
  }

  function handleDocumentClick(event) {
    if (!context.openBehaviorEditor) {
      return;
    }
    if (eventStartedInside(event, context.dom.behaviorEditorPanel, context.dom.behaviorList, context.dom.addBehaviorButton)) {
      return;
    }
    closeBehaviorEditor();
  }

  function eventStartedInside(event, ...elements) {
    const path = event.composedPath();
    return elements.some((element) => path.includes(element) || element.contains(event.target));
  }

  function toggleBehaviorEditor(entityId, index) {
    if (isBehaviorEditorOpenFor(entityId, index)) {
      context.openBehaviorEditor = null;
      return;
    }
    context.openBehaviorEditor = { entityId, index };
  }

  function closeBehaviorEditor() {
    context.openBehaviorEditor = null;
    render();
  }

  function openBehaviorRule() {
    const { openBehaviorEditor } = context;
    const placed = context.selectedPlacedEntity();
    if (
      !openBehaviorEditor ||
      !placed ||
      placed.entity.id !== openBehaviorEditor.entityId ||
      context.selectedEditorTab !== "behaviors"
    ) {
      context.openBehaviorEditor = null;
      return null;
    }
    const behavior = placed.entity.behaviors[openBehaviorEditor.index];
    if (!behavior) {
      context.openBehaviorEditor = null;
      return null;
    }
    return {
      behavior,
      entity: placed.entity,
      index: openBehaviorEditor.index,
    };
  }

  function isBehaviorEditorOpenFor(entityId, index) {
    return context.openBehaviorEditor?.entityId === entityId && context.openBehaviorEditor.index === index;
  }

  function renderBehaviorOverlay(openRule) {
    context.dom.behaviorEditorPanel.replaceChildren();
    if (!openRule) {
      context.dom.behaviorEditorOverlay.hidden = true;
      return;
    }
    context.dom.behaviorEditorOverlay.hidden = false;
    context.dom.behaviorEditorPanel.append(behaviorBlock(openRule.behavior, openRule.index));
  }

  function behaviorBlock(behavior, index) {
    const block = document.createElement("article");
    block.className = "behavior-block";
    block.innerHTML = `
      <div class="panel-heading">
        <h2>Rule ${index + 1}</h2>
        <button type="button" class="mini-button" data-remove-behavior="${index}">Remove</button>
      </div>
      <div class="block-grid">
        <label class="block-field">On action ${selectHtml(actionOptions, behavior.trigger.action, `data-trigger-field="action"`, actionLabels)}</label>
        ${triggerFieldsHtml(behavior.trigger)}
      </div>
      <div>
        <span class="field-label">Conditions</span>
        <div class="block-list" data-condition-list></div>
        <button type="button" class="mini-button" data-add-condition>Add Condition</button>
      </div>
      <div>
        <span class="field-label">Effects</span>
        <div class="block-list" data-effect-list></div>
        <button type="button" class="mini-button" data-add-effect>Add Effect</button>
      </div>
    `;
    block.querySelectorAll("[data-trigger-field]").forEach((input) => {
      input.addEventListener("input", () => {
        history.record();
        const value = input.value.trim();
        behavior.trigger[input.dataset.triggerField] = value || undefined;
        if (input.dataset.triggerField === "action") {
          resetTriggerForAction(behavior.trigger);
          render();
        } else {
          normalizeTrigger(behavior.trigger);
          renderEditor();
        }
      });
    });
    block.querySelectorAll("[data-trigger-action-option]").forEach((input) => {
      input.addEventListener("input", () => {
        history.record();
        updateTriggerActions(behavior.trigger, input.value, input.checked);
        render();
      });
    });
    block.querySelector("[data-remove-behavior]").addEventListener("click", () => {
      history.record();
      context.selectedPlacedEntity().entity.behaviors.splice(index, 1);
      context.openBehaviorEditor = null;
      renderEditor();
    });
    block.querySelector("[data-add-condition]").addEventListener("click", () => {
      history.record();
      behavior.conditions.push({ entity_id: "", state: "" });
      renderEditor();
    });
    block.querySelector("[data-add-effect]").addEventListener("click", () => {
      history.record();
      behavior.effects.push({ type: "message", text: "Something happens." });
      renderEditor();
      scrollBehaviorEditorToBottom();
    });
    renderConditionList(block.querySelector("[data-condition-list]"), behavior);
    renderEffectList(block.querySelector("[data-effect-list]"), behavior);
    return block;
  }

  function triggerFieldsHtml(trigger) {
    if (trigger.action === "use_item") {
      return `<label class="block-field">Item ${entitySelectHtml(trigger.item, `data-trigger-field="item"`, { emptyLabel: "Choose item" })}</label>`;
    }
    if (trigger.action === "talk_to") {
      return `<label class="block-field block-wide">Phrase <input data-trigger-field="phrase" type="text" value="${escapeAttribute(trigger.phrase ?? "")}" /></label>`;
    }
    return simpleActionCheckboxesHtml(trigger);
  }

  function simpleActionCheckboxesHtml(trigger) {
    const selected = new Set(simpleTriggerActions(trigger));
    return `
      <fieldset class="block-field block-wide action-checkboxes">
        <legend>Alternative actions</legend>
        ${simpleActionOptions
          .filter((action) => action !== trigger.action)
          .map(
            (action) => `
              <label>
                <input type="checkbox" data-trigger-action-option value="${escapeAttribute(action)}" ${selected.has(action) ? "checked" : ""} />
                ${escapeHtml(optionLabel(actionLabels, action))}
              </label>
            `,
          )
          .join("")}
      </fieldset>
    `;
  }

  function resetTriggerForAction(trigger) {
    delete trigger.item;
    delete trigger.phrase;
    delete trigger.actions;
    if (trigger.action === "use_item") {
      trigger.item = "";
    }
    if (trigger.action === "talk_to") {
      trigger.phrase = "";
    }
  }

  function updateTriggerActions(trigger, action, checked) {
    const selected = new Set(simpleTriggerActions(trigger));
    if (checked) {
      selected.add(action);
    } else {
      selected.delete(action);
    }
    if (!selected.size) {
      selected.add(trigger.action);
    }
    const actions = simpleActionOptions.filter((option) => selected.has(option));
    trigger.action = actions[0];
    if (actions.length > 1) {
      trigger.actions = actions;
    } else {
      delete trigger.actions;
    }
    normalizeTrigger(trigger);
  }

  function simpleTriggerActions(trigger) {
    const actions = Array.isArray(trigger.actions) && trigger.actions.length ? trigger.actions : [trigger.action];
    const selected = actions.filter((action) => simpleActionOptions.includes(action));
    return selected.length ? selected : [simpleActionOptions[0]];
  }

  function isSimpleAction(action) {
    return simpleActionOptions.includes(action);
  }

  function normalizedSimpleActions(trigger) {
    const selected = new Set(simpleTriggerActions(trigger));
    selected.add(trigger.action);
    return simpleActionOptions.filter((action) => selected.has(action));
  }

  function normalizeTrigger(trigger) {
    if (trigger.action !== "use_item") {
      delete trigger.item;
    }
    if (trigger.action !== "talk_to") {
      delete trigger.phrase;
    }
    if (!isSimpleAction(trigger.action)) {
      delete trigger.actions;
      return;
    }
    const actions = normalizedSimpleActions(trigger);
    if (actions.length > 1) {
      trigger.actions = actions;
    } else {
      delete trigger.actions;
    }
  }

  function renderConditionList(container, behavior) {
    container.replaceChildren(
      ...behavior.conditions.map((condition, index) => {
        const row = document.createElement("div");
        row.className = "block-grid";
        row.innerHTML = `
          <label class="block-field">Entity ${entitySelectHtml(condition.entity_id, `data-condition-field="entity_id"`, { emptyLabel: "Any entity" })}</label>
          <label class="block-field">State <input data-condition-field="state" type="text" value="${escapeAttribute(condition.state ?? "")}" /></label>
          <button type="button" class="mini-button" data-remove-condition="${index}">Remove</button>
        `;
        row.querySelectorAll("[data-condition-field]").forEach((input) => {
          input.addEventListener("input", () => {
            history.record();
            condition[input.dataset.conditionField] = input.value.trim() || null;
            validation.schedule();
          });
        });
        row.querySelector("[data-remove-condition]").addEventListener("click", () => {
          history.record();
          behavior.conditions.splice(index, 1);
          renderEditor();
        });
        return row;
      }),
    );
  }

  function renderEffectList(container, behavior) {
    container.replaceChildren(
      ...behavior.effects.map((effect, index) => {
        const row = document.createElement("div");
        row.className = "block-grid effect-grid";
        row.innerHTML = `
          <label class="block-field">Effect ${selectHtml(effectOptions, effect.type, `data-effect-field="type"`, effectLabels)}</label>
          ${effectFieldsHtml(effect)}
          <button type="button" class="mini-button block-action" data-remove-effect="${index}">Remove</button>
        `;
        row.querySelectorAll("[data-effect-field]").forEach((input) => {
          input.addEventListener("input", () => {
            history.record();
            updateEffectField(effect, input);
            if (input.dataset.effectField === "type") {
              renderEditor();
            } else {
              validation.schedule();
            }
          });
        });
        row.querySelector("[data-remove-effect]").addEventListener("click", () => {
          history.record();
          behavior.effects.splice(index, 1);
          renderEditor();
        });
        return row;
      }),
    );
  }

  function effectFieldsHtml(effect) {
    if (effect.type === "message") {
      return `<label class="block-field block-wide">Text <input data-effect-field="text" type="text" value="${escapeAttribute(effect.text ?? "")}" /></label>`;
    }
    if (effect.type === "add_inventory") {
      return `<label class="block-field">Entity ${entitySelectHtml(effect.entity_id, `data-effect-field="entity_id"`, { emptyLabel: "Current entity" })}</label>`;
    }
    if (effect.type === "remove_inventory") {
      return `<label class="block-field">Entity ${entitySelectHtml(effect.entity_id, `data-effect-field="entity_id"`, { allowEmpty: false })}</label>`;
    }
    if (effect.type === "set_entity_state") {
      return `
        <label class="block-field">Entity ${entitySelectHtml(effect.entity_id, `data-effect-field="entity_id"`)}</label>
        <label class="block-field">State <input data-effect-field="state" type="text" value="${escapeAttribute(effect.state ?? "")}" /></label>
      `;
    }
    if (effect.type === "set_entity_passable" || effect.type === "set_entity_active") {
      const valueField = effect.type === "set_entity_passable" ? "passable" : "active";
      return `
        <label class="block-field">Entity ${entitySelectHtml(effect.entity_id, `data-effect-field="entity_id"`)}</label>
        <label class="block-field">${effectToggleLabel(effect.type)} ${selectHtml(["true", "false"], String(effect[valueField] ?? true), `data-effect-field="${valueField}"`, booleanLabels)}</label>
      `;
    }
    return "";
  }

  function updateEffectField(effect, input) {
    const field = input.dataset.effectField;
    if (field === "type") {
      for (const key of Object.keys(effect)) {
        delete effect[key];
      }
      Object.assign(effect, defaultEffect(input.value));
      return;
    }
    if (field === "passable" || field === "active") {
      effect[field] = input.value === "true";
      return;
    }
    effect[field] = input.value.trim() || undefined;
  }

  function behaviorSummary(behavior) {
    let trigger;
    if (behavior.trigger.action === "use_item") {
      trigger = behavior.trigger.item
        ? `${optionLabel(actionLabels, behavior.trigger.action)} ${behavior.trigger.item}`
        : optionLabel(actionLabels, behavior.trigger.action);
    } else if (behavior.trigger.action === "talk_to") {
      trigger = behavior.trigger.phrase
        ? `${optionLabel(actionLabels, behavior.trigger.action)} "${behavior.trigger.phrase}"`
        : optionLabel(actionLabels, behavior.trigger.action);
    } else {
      trigger = simpleTriggerActions(behavior.trigger)
        .map((action) => optionLabel(actionLabels, action))
        .join(" or ");
    }
    const effects = behavior.effects.map(effectSummary).filter(Boolean);
    return `${trigger} -> ${effects.length ? effects.join(", ") : "no effects"}`;
  }

  function effectSummary(effect) {
    if (effect.type === "message") {
      return "Message";
    }
    if (effect.type === "escape_map") {
      return "Escape";
    }
    if (effect.type === "set_entity_state") {
      return `State ${effect.entity_id || "self"}`;
    }
    if (effect.type === "set_entity_active") {
      return `Active ${effect.active ? "yes" : "no"} ${effect.entity_id || "self"}`;
    }
    if (effect.type === "set_entity_passable") {
      return `Passable ${effect.passable ? "yes" : "no"} ${effect.entity_id || "self"}`;
    }
    if (effect.type === "add_inventory") {
      return `Give ${effect.entity_id || "self"}`;
    }
    if (effect.type === "remove_inventory") {
      return `Take ${effect.entity_id || "item"}`;
    }
    return optionLabel(effectLabels, effect.type);
  }

  function effectToggleLabel(type) {
    if (type === "set_entity_passable") {
      return "Passable";
    }
    if (type === "set_entity_active") {
      return "Active";
    }
    return "Value";
  }

  function entitySelectHtml(selected, attributes, options = {}) {
    const allowEmpty = options.allowEmpty ?? true;
    const emptyLabel = options.emptyLabel ?? "Current entity";
    const entityOptions = context
      .allEditorEntities()
      .filter((entity) => entity.notable)
      .map((entity) => ({
        value: entity.id,
        label: entity.id,
      }));
    const optionHtml = [
      ...(allowEmpty ? [{ value: "", label: emptyLabel }] : []),
      ...entityOptions,
    ]
      .map(
        (option) =>
          `<option value="${escapeAttribute(option.value)}" ${option.value === (selected ?? "") ? "selected" : ""}>${escapeHtml(option.label)}</option>`,
      )
      .join("");
    return `<select ${attributes}>${optionHtml}</select>`;
  }

  function scrollBehaviorEditorToBottom() {
    if (context.dom.behaviorEditorOverlay.hidden) {
      return;
    }
    requestAnimationFrame(() => {
      context.dom.behaviorEditorPanel.scrollTop = context.dom.behaviorEditorPanel.scrollHeight;
    });
  }

  return { addBehavior, handleDocumentClick, render };
}
