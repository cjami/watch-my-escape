import { escapeAttribute, escapeHtml } from "../shared/html.js";
import { optionLabel, selectHtml } from "../shared/strings.js";

import { actionLabels, actionOptions, booleanLabels, effectLabels, effectOptions } from "./constants.js";
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
    context.selectedBehaviorIndex = entity.behaviors.length - 1;
    context.selectedEditorTab = "behaviors";
    renderEditor();
    context.setStatus("Behavior added.");
  }

  function render() {
    const placed = context.selectedPlacedEntity();
    context.dom.behaviorList.replaceChildren();
    if (!placed) {
      context.dom.behaviorList.innerHTML = `<p class="selection-detail">No entity selected.</p>`;
      return;
    }
    if (!placed.entity.behaviors.length) {
      context.dom.behaviorList.innerHTML = `<p class="selection-detail">No behaviors configured.</p>`;
      context.selectedBehaviorIndex = 0;
      return;
    }
    context.selectedBehaviorIndex = Math.min(context.selectedBehaviorIndex, placed.entity.behaviors.length - 1);
    const ruleList = document.createElement("div");
    ruleList.className = "behavior-rule-list";
    placed.entity.behaviors.forEach((behavior, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "behavior-summary";
      button.classList.toggle("is-selected", index === context.selectedBehaviorIndex);
      button.innerHTML = `
        <span>Rule ${index + 1}</span>
        <strong>${escapeHtml(behaviorSummary(behavior))}</strong>
      `;
      button.addEventListener("click", () => {
        context.selectedBehaviorIndex = index;
        render();
      });
      ruleList.append(button);
    });
    context.dom.behaviorList.append(
      ruleList,
      behaviorBlock(placed.entity.behaviors[context.selectedBehaviorIndex], context.selectedBehaviorIndex),
    );
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
        normalizeTrigger(behavior.trigger);
        if (input.dataset.triggerField === "action") {
          render();
        } else {
          renderEditor();
        }
      });
    });
    block.querySelector("[data-remove-behavior]").addEventListener("click", () => {
      history.record();
      context.selectedPlacedEntity().entity.behaviors.splice(index, 1);
      context.selectedBehaviorIndex = Math.max(0, index - 1);
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
    return "";
  }

  function normalizeTrigger(trigger) {
    if (trigger.action !== "use_item") {
      delete trigger.item;
    }
    if (trigger.action !== "talk_to") {
      delete trigger.phrase;
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
    if (effect.type === "add_inventory" || effect.type === "remove_inventory") {
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
    const trigger = behavior.trigger.item
      ? `${optionLabel(actionLabels, behavior.trigger.action)} ${behavior.trigger.item}`
      : behavior.trigger.phrase
        ? `${optionLabel(actionLabels, behavior.trigger.action)} "${behavior.trigger.phrase}"`
        : optionLabel(actionLabels, behavior.trigger.action);
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
      return `Give ${effect.entity_id || "item"}`;
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
    const entityOptions = context.allEditorEntities().map((entity) => ({
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

  return { addBehavior, render };
}
