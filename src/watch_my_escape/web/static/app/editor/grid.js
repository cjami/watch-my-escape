import { slugify } from "../shared/strings.js";

import { mapSize } from "./constants.js";

export function createEditorGrid({ context, history, renderEditor }) {
  function renderGrid() {
    context.dom.editorGrid.replaceChildren();
    for (let y = 0; y < mapSize; y += 1) {
      for (let x = 0; x < mapSize; x += 1) {
        const cell = document.createElement("button");
        const entity = context.editorState.entities.find((candidate) => candidate.position.x === x && candidate.position.y === y);
        const isAgentStart = context.editorState.agentStart.x === x && context.editorState.agentStart.y === y;
        cell.type = "button";
        cell.className = "editor-cell";
        cell.dataset.x = String(x);
        cell.dataset.y = String(y);
        cell.classList.toggle("is-start", isAgentStart);
        cell.classList.toggle("is-selected", entity?.entity.id === context.selectedEntityId);
        cell.classList.toggle("is-inactive", Boolean(entity && !entity.entity.active));
        applyDragClasses(cell, x, y);
        if (entity) {
          cell.append(context.pixelSprite(entity.entity.icon, entity.entity.id));
        }
        cell.title = editorCellTitle(entity, isAgentStart, x, y);
        cell.setAttribute("aria-label", cell.title);
        cell.addEventListener("pointerdown", (event) => handleEditorCellPointerDown(event, cell, x, y, entity));
        cell.addEventListener("pointerenter", () => handleEditorCellPointerEnter(cell, x, y));
        cell.addEventListener("pointerup", () => handleEditorCellPointerUp(x, y));
        context.dom.editorGrid.append(cell);
      }
    }
  }

  function renderTray() {
    const items = context.editorState.unplacedEntities ?? [];
    if (!items.length) {
      context.dom.editorTray.innerHTML = `<p class="selection-detail">No off-map entities.</p>`;
      return;
    }
    context.dom.editorTray.replaceChildren(
      ...items.map((entity) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "tray-entity";
        button.dataset.entityId = entity.id;
        button.classList.toggle("is-selected", entity.id === context.selectedEntityId);
        button.classList.toggle("is-inactive", !entity.active);
        button.title = `${entity.id} - off-map`;
        button.setAttribute("aria-label", button.title);
        button.append(context.pixelSprite(entity.icon, entity.id));
        button.addEventListener("pointerdown", (event) => handleEditorTrayPointerDown(event, entity));
        return button;
      }),
    );
  }

  function addSelectedPresetToTray() {
    history.record();
    const id = context.uniqueEntityId(slugify(context.selectedPreset.name || context.selectedPreset.type));
    const entity = context.entityFromPreset(context.selectedPreset, id);
    context.editorState.unplacedEntities = [...(context.editorState.unplacedEntities ?? []), entity];
    context.selectedEntityId = entity.id;
    context.selectedEditorTab = "entity";
    context.setEditorTool("select");
    context.setStatus(`Added ${entity.id} to the tray.`);
    renderEditor();
  }

  function finishGridDrag() {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "place" && context.dragState.count > 1) {
      context.setStatus(`Placed ${context.dragState.count} ${context.selectedPreset.name.toLowerCase()} entities.`);
    }
    if (context.dragState.tool === "erase" && context.dragState.count > 1) {
      context.setStatus(`Removed ${context.dragState.count} entities.`);
    }
    context.dragState = null;
    clearDropPreview();
  }

  function handleEditorCellPointerDown(event, cell, x, y, placedEntity) {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    clearDropPreview();
    if (context.selectedTool === "start") {
      beginStartDrag(cell, x, y);
      return;
    }
    if (
      context.selectedTool === "select" &&
      !placedEntity &&
      context.editorState.agentStart.x === x &&
      context.editorState.agentStart.y === y
    ) {
      beginStartDrag(cell, x, y);
      return;
    }
    if (context.selectedTool === "select" && !placedEntity) {
      context.selectedEntityId = null;
      context.selectedEditorTab = "entity";
      renderEditor();
      return;
    }
    context.dragState = {
      tool: context.selectedTool,
      sourceId: placedEntity?.entity.id ?? null,
      sourceKind: "grid",
      sourceX: x,
      sourceY: y,
      targetX: x,
      targetY: y,
      count: 0,
      changed: false,
      visited: new Set(),
    };
    if (context.selectedTool === "erase") {
      paintErase(x, y);
      return;
    }
    if (context.selectedTool === "place") {
      paintPlace(x, y);
      return;
    }
    if (context.selectedTool === "select" && placedEntity) {
      updateDropPreview(cell, x, y);
      context.setStatus(`Dragging ${placedEntity.entity.id}. Release on an open tile or the tray.`);
    }
  }

  function handleEditorTrayPointerDown(event, entity) {
    if (event.button !== 0 || context.selectedTool !== "select") {
      return;
    }
    event.preventDefault();
    clearDropPreview();
    context.dragState = {
      tool: "select",
      sourceId: entity.id,
      sourceKind: "tray",
      sourceX: null,
      sourceY: null,
      targetX: null,
      targetY: null,
      count: 0,
      changed: false,
      visited: new Set(),
    };
    editorTrayItem(entity.id)?.classList.add("is-drag-source");
    context.dom.editorTray.classList.add("is-dragging");
    context.setStatus(`Dragging ${entity.id}. Release on an open tile to place it.`);
  }

  function handleEditorCellPointerEnter(cell, x, y) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "place") {
      paintPlace(x, y);
      return;
    }
    if (context.dragState.tool === "erase") {
      paintErase(x, y);
      return;
    }
    if (context.dragState.tool === "start") {
      updateDropPreview(cell, x, y);
      return;
    }
    if (context.dragState.tool === "select" && context.dragState.sourceId) {
      updateDropPreview(cell, x, y);
    }
  }

  function handleEditorCellPointerUp(x, y) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "select") {
      finishSelectDrag(x, y);
    }
    if (context.dragState.tool === "start") {
      finishStartDrag(x, y);
    }
    finishGridDrag();
  }

  function beginStartDrag(cell, x, y) {
    context.dragState = {
      tool: "start",
      sourceId: null,
      sourceKind: "grid",
      sourceX: context.editorState.agentStart.x,
      sourceY: context.editorState.agentStart.y,
      targetX: x,
      targetY: y,
      count: 0,
      changed: false,
      visited: new Set(),
    };
    updateDropPreview(cell, x, y);
    context.setStatus("Dragging agent start. Release on a tile to set the new starting position.");
  }

  function finishSelectDrag(x, y) {
    if (!context.dragState?.sourceId) {
      return;
    }
    const source = context.selectedDragEntity();
    if (!source) {
      return;
    }
    if (source.position && source.position.x === x && source.position.y === y) {
      context.selectedEntityId = source.entity.id;
      context.selectedEditorTab = "entity";
      renderEditor();
      return;
    }
    const target = context.entityAt(x, y);
    if (target) {
      context.selectedEntityId = source.entity.id;
      context.setStatus(`${target.entity.id} already occupies that tile.`);
      renderEditor();
      return;
    }
    history.record();
    if (source.position) {
      source.position = { x, y };
    } else {
      context.editorState.unplacedEntities = (context.editorState.unplacedEntities ?? []).filter(
        (entity) => entity.id !== source.entity.id,
      );
      context.editorState.entities.push({ position: { x, y }, entity: source.entity });
    }
    context.selectedEntityId = source.entity.id;
    context.selectedEditorTab = "entity";
    context.setStatus(`Moved ${source.entity.id} to (${x}, ${y}).`);
    renderEditor();
  }

  function handleTrayPointerEnter() {
    if (context.dragState?.tool === "select" && context.dragState.sourceId) {
      updateTrayDropPreview();
    }
  }

  function handleTrayPointerUp() {
    if (context.dragState?.tool !== "select" || !context.dragState.sourceId) {
      return;
    }
    finishTrayDrop();
    finishGridDrag();
  }

  function finishTrayDrop() {
    const source = context.selectedDragEntity();
    if (!source) {
      return;
    }
    if (!source.position) {
      context.selectedEntityId = source.entity.id;
      context.selectedEditorTab = "entity";
      renderEditor();
      return;
    }
    history.record();
    context.editorState.entities = context.editorState.entities.filter((placed) => placed.entity.id !== source.entity.id);
    context.editorState.unplacedEntities = [...(context.editorState.unplacedEntities ?? []), source.entity];
    context.selectedEntityId = source.entity.id;
    context.selectedEditorTab = "entity";
    context.setStatus(`Moved ${source.entity.id} to the tray.`);
    renderEditor();
  }

  function finishStartDrag(x, y) {
    if (!context.dragState) {
      return;
    }
    if (context.editorState.agentStart.x === x && context.editorState.agentStart.y === y) {
      context.setStatus(`Agent start remains at (${x}, ${y}).`);
      return;
    }
    history.record();
    context.editorState.agentStart = { x, y };
    context.setStatus(`Agent start moved to (${x}, ${y}).`);
    renderEditor();
  }

  function paintPlace(x, y) {
    if (!context.dragState || visitDraggedTile(x, y) || context.entityAt(x, y)) {
      return;
    }
    recordDragHistory();
    const entity = context.createEntity(context.selectedPreset, x, y);
    context.editorState.entities.push(entity);
    context.selectedEntityId = entity.entity.id;
    context.dragState.count += 1;
    context.setStatus(`Placed ${entity.entity.id}.`);
    renderEditor();
  }

  function paintErase(x, y) {
    const placedEntity = context.entityAt(x, y);
    if (!context.dragState || visitDraggedTile(x, y) || !placedEntity) {
      return;
    }
    recordDragHistory();
    context.editorState.entities = context.editorState.entities.filter(
      (candidate) => candidate.entity.id !== placedEntity.entity.id,
    );
    if (context.selectedEntityId === placedEntity.entity.id) {
      context.selectedEntityId = null;
    }
    context.dragState.count += 1;
    context.setStatus(`Removed ${placedEntity.entity.id}.`);
    renderEditor();
  }

  function visitDraggedTile(x, y) {
    const key = `${x},${y}`;
    if (context.dragState.visited.has(key)) {
      return true;
    }
    context.dragState.visited.add(key);
    return false;
  }

  function recordDragHistory() {
    if (context.dragState.changed) {
      return;
    }
    history.record();
    context.dragState.changed = true;
  }

  function clearDropPreview() {
    context.dom.editorGrid.classList.remove("is-dragging");
    context.dom.editorTray.classList.remove("is-dragging", "is-drop-ok");
    context.dom.editorGrid.querySelectorAll(".is-drag-source, .is-drop-ok, .is-drop-blocked").forEach((cell) => {
      cell.classList.remove("is-drag-source", "is-drop-ok", "is-drop-blocked");
    });
    context.dom.editorTray.querySelectorAll(".is-drag-source").forEach((item) => {
      item.classList.remove("is-drag-source");
    });
  }

  function updateDropPreview(cell, x, y) {
    if (!context.dragState) {
      return;
    }
    context.dragState.targetX = x;
    context.dragState.targetY = y;
    clearDropPreview();
    if (context.dragState.sourceKind === "grid") {
      applyDragClasses(editorGridCell(context.dragState.sourceX, context.dragState.sourceY), context.dragState.sourceX, context.dragState.sourceY);
    } else {
      editorTrayItem(context.dragState.sourceId)?.classList.add("is-drag-source");
    }
    applyDragClasses(cell, x, y);
  }

  function updateTrayDropPreview() {
    if (!context.dragState) {
      return;
    }
    clearDropPreview();
    context.dom.editorGrid.classList.add("is-dragging");
    context.dom.editorTray.classList.add("is-dragging", "is-drop-ok");
    if (context.dragState.sourceKind === "grid") {
      applyDragClasses(editorGridCell(context.dragState.sourceX, context.dragState.sourceY), context.dragState.sourceX, context.dragState.sourceY);
    } else {
      editorTrayItem(context.dragState.sourceId)?.classList.add("is-drag-source");
    }
  }

  function applyDragClasses(cell, x, y) {
    if (!cell || !context.dragState) {
      return;
    }
    if (context.dragState.tool !== "select" && context.dragState.tool !== "start") {
      return;
    }
    context.dom.editorGrid.classList.add("is-dragging");
    if (context.dragState.sourceX === x && context.dragState.sourceY === y) {
      cell.classList.add("is-drag-source");
    }
    if (context.dragState.targetX !== x || context.dragState.targetY !== y) {
      return;
    }
    if (context.dragState.tool === "start") {
      cell.classList.add("is-drop-ok");
      return;
    }
    if (context.dragState.tool !== "select" || !context.dragState.sourceId) {
      return;
    }
    const target = context.entityAt(x, y);
    cell.classList.add(target && target.entity.id !== context.dragState.sourceId ? "is-drop-blocked" : "is-drop-ok");
  }

  function editorGridCell(x, y) {
    return context.dom.editorGrid.querySelector(`[data-x="${x}"][data-y="${y}"]`);
  }

  function editorTrayItem(entityId) {
    return (
      [...context.dom.editorTray.querySelectorAll("[data-entity-id]")].find((item) => item.dataset.entityId === entityId) ??
      null
    );
  }

  function editorCellTitle(entity, isAgentStart, x, y) {
    return [entity?.entity.id, isAgentStart ? "Agent start" : null, `(${x}, ${y})`].filter(Boolean).join(" - ");
  }

  return {
    addSelectedPresetToTray,
    finishGridDrag,
    handleTrayPointerEnter,
    handleTrayPointerUp,
    renderGrid,
    renderTray,
  };
}
