import { escapeAttribute, escapeHtml } from "../shared/html.js";

export function createEntityForm({
  context,
  history,
  iconCatalog,
  renderBehaviors,
  renderEditor,
  renderGrid,
  renderTray,
  validation,
}) {
  function render() {
    const placed = context.selectedPlacedEntity();
    if (!placed) {
      context.dom.entityForm.innerHTML = `<p class="selection-detail">Select an entity on the grid or place one from a preset.</p>`;
      return;
    }
    const entity = placed.entity;
    context.dom.entityForm.innerHTML = `
      <label><span>Id</span><input data-entity-field="id" type="text" value="${escapeAttribute(entity.id)}" /></label>
      <div>
        <span class="field-label">Icon</span>
        <label class="icon-search-label">
          <span>Search Icons</span>
          <input data-icon-search type="search" placeholder="door, key, clue..." value="${escapeAttribute(context.iconSearchQuery)}" />
        </label>
        <div class="icon-picker" aria-label="Entity icon"></div>
      </div>
      <label><span>Description</span><textarea data-entity-field="description" rows="3">${escapeHtml(entity.description)}</textarea></label>
      <label><span>State</span><input data-entity-field="state" type="text" value="${escapeAttribute(entity.state)}" /></label>
      <div class="checkbox-row">
        <label><input data-entity-field="passable" type="checkbox" ${entity.passable ? "checked" : ""} />Passable</label>
        <label><input data-entity-field="active" type="checkbox" ${entity.active ? "checked" : ""} />Active</label>
        <label><input data-entity-field="notable" type="checkbox" ${entity.notable ? "checked" : ""} />Notable</label>
      </div>
    `;
    context.dom.entityForm.querySelectorAll("[data-entity-field]").forEach((input) => {
      input.addEventListener("input", () => updateEntityField(input, placed));
    });
    const iconPicker = context.dom.entityForm.querySelector(".icon-picker");
    const iconSearch = context.dom.entityForm.querySelector("[data-icon-search]");
    renderIconOptions(iconPicker, placed);
    iconSearch.addEventListener("input", () => {
      context.iconSearchQuery = iconSearch.value;
      renderIconOptions(iconPicker, placed);
    });
  }

  function renderIconOptions(iconPicker, placed) {
    const entity = placed.entity;
    iconPicker.replaceChildren(
      ...iconCatalog.visibleIconOptions(entity.icon).map((option) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "icon-option";
        button.dataset.icon = option.icon;
        button.classList.toggle("is-selected", entity.icon === option.icon);
        button.title = option.name;
        button.setAttribute("aria-label", `Choose ${option.name} icon`);
        button.append(context.pixelSprite(option.icon, option.name));
        button.addEventListener("click", () => {
          history.record();
          placed.entity.icon = button.dataset.icon;
          renderEditor();
        });
        return button;
      }),
    );
  }

  function updateEntityField(input, placed) {
    history.record();
    const field = input.dataset.entityField;
    if (field === "id") {
      context.selectedEntityId = input.value.trim();
    }
    if (input.type === "checkbox") {
      placed.entity[field] = input.checked;
    } else if (field === "id") {
      placed.entity[field] = input.value.trim();
    } else {
      placed.entity[field] = input.value;
    }
    updateEditorAfterEntityFieldChange(field);
  }

  function updateEditorAfterEntityFieldChange(field) {
    renderGrid();
    renderTray();
    if (field === "id" || field === "notable") {
      renderBehaviors();
    }
    history.updateButtons();
    validation.schedule();
  }

  return { render };
}
