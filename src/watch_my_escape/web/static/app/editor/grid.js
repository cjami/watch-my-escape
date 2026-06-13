import { slugify } from "../shared/strings.js";

import { mapSize } from "./constants.js";

const offMapLabelColumnSpan = 2;
const minimumOffMapCellCount = mapSize - offMapLabelColumnSpan;
const entityDragActivationCellRatio = 0.4;
const entityDragActivationMinPx = 12;
const entityDragActivationMaxPx = 28;

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
          cell.append(context.pixelSprite(entity.entity.icon, entity.entity.id, entity.entity.color || null));
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
    const entitiesBySlot = trayEntitiesBySlot(items);
    const cellCount = trayCellCount(entitiesBySlot);
    context.dom.editorTray.style.setProperty("--tray-cell-count", String(cellCount));
    context.dom.editorTray.replaceChildren(
      ...Array.from({ length: cellCount }, (_, index) => {
        const entity = entitiesBySlot.get(index) ?? null;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "editor-cell editor-tray-cell";
        button.dataset.trayIndex = String(index);
        if (entity) {
          button.dataset.entityId = entity.id;
        }
        button.classList.toggle("is-selected", entity?.id === context.selectedEntityId);
        button.classList.toggle("is-inactive", Boolean(entity && !entity.active));
        applyTrayDragClasses(button, index);
        if (entity) {
          button.append(context.pixelSprite(entity.icon, entity.id, entity.color || null));
        }
        button.title = editorTrayCellTitle(entity, index);
        button.setAttribute("aria-label", button.title);
        button.addEventListener("pointerdown", (event) => handleEditorTrayCellPointerDown(event, button, index, entity));
        button.addEventListener("pointerenter", () => handleEditorTrayCellPointerEnter(button, index));
        button.addEventListener("pointerup", () => handleEditorTrayCellPointerUp(index));
        return button;
      }),
    );
  }

  function finishGridDrag(event) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "preset") {
      if (context.dragState.dragActive && event?.clientX !== undefined && event?.clientY !== undefined) {
        finishPresetDragFromPoint(event.clientX, event.clientY);
      }
      schedulePresetClickReset();
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
      dragActive: false,
      pointerStartX: event.clientX,
      pointerStartY: event.clientY,
      activationDistance: entityDragActivationDistance(cell),
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
  }

  function handleEditorTrayCellPointerDown(event, cell, index, entity) {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    clearDropPreview();
    if (context.selectedTool === "place") {
      context.dragState = {
        tool: "place",
        sourceId: null,
        sourceKind: "tray",
        sourceIndex: index,
        targetIndex: index,
        count: 0,
        changed: false,
        visited: new Set(),
      };
      paintTrayPlace(index);
      return;
    }
    if (context.selectedTool === "erase") {
      context.dragState = {
        tool: "erase",
        sourceId: entity?.id ?? null,
        sourceKind: "tray",
        sourceIndex: index,
        targetIndex: index,
        count: 0,
        changed: false,
        visited: new Set(),
      };
      paintTrayErase(index);
      return;
    }
    if (context.selectedTool !== "select") {
      context.setStatus("Off-map cells can hold entities, but the agent start must stay on the room grid.");
      return;
    }
    if (!entity) {
      context.selectedEntityId = null;
      context.selectedEditorTab = "entity";
      renderEditor();
      return;
    }
    context.dragState = {
      tool: "select",
      sourceId: entity.id,
      sourceKind: "tray",
      sourceIndex: index,
      sourceX: null,
      sourceY: null,
      targetIndex: index,
      targetX: null,
      targetY: null,
      count: 0,
      changed: false,
      dragActive: false,
      pointerStartX: event.clientX,
      pointerStartY: event.clientY,
      activationDistance: entityDragActivationDistance(cell),
      visited: new Set(),
    };
  }

  function handleEditorCellPointerEnter(cell, x, y) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "preset" && context.dragState.dragActive) {
      updateDropPreview(cell, x, y);
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
    if (context.dragState.tool === "select" && context.dragState.sourceId && context.dragState.dragActive) {
      updateDropPreview(cell, x, y);
    }
  }

  function handleEditorCellPointerUp(x, y) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "preset") {
      if (context.dragState.dragActive) {
        finishPresetDrag(x, y);
      }
      finishGridDrag();
      return;
    }
    if (context.dragState.tool === "select") {
      if (!context.dragState.dragActive) {
        selectDragSource();
        finishGridDrag();
        return;
      }
      finishSelectDrag(x, y);
    }
    if (context.dragState.tool === "start") {
      finishStartDrag(x, y);
    }
    finishGridDrag();
  }

  function handleEditorTrayCellPointerEnter(cell, index) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "place") {
      paintTrayPlace(index);
      return;
    }
    if (context.dragState.tool === "erase") {
      paintTrayErase(index);
      return;
    }
    if (context.dragState.tool === "select" && context.dragState.sourceId && context.dragState.dragActive) {
      updateTrayCellDropPreview(cell, index);
    }
  }

  function handleEditorTrayCellPointerUp(index) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "select") {
      if (!context.dragState.dragActive) {
        selectDragSource();
        finishGridDrag();
        return;
      }
      finishTraySelectDrag(index);
    }
    finishGridDrag();
  }

  function handleDragPointerMove(event) {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.tool === "preset") {
      handlePresetDragPointerMove(event);
      return;
    }
    if (context.dragState.tool !== "select" || !context.dragState.sourceId) {
      return;
    }
    if (!context.dragState.dragActive) {
      if (!isEntityDragActivationMove(event)) {
        return;
      }
      context.dragState.dragActive = true;
      context.setStatus(entityDragStatusMessage());
    }
    updateSelectDragPreviewFromPoint(event.clientX, event.clientY);
  }

  function beginPresetDrag(event, button, preset) {
    if (event.button !== 0) {
      return;
    }
    clearDropPreview();
    context.dragState = {
      tool: "preset",
      preset,
      sourceId: null,
      sourceKind: "preset",
      sourceElement: button,
      targetX: null,
      targetY: null,
      count: 0,
      changed: false,
      dragActive: false,
      pointerStartX: event.clientX,
      pointerStartY: event.clientY,
      activationDistance: entityDragActivationDistance(button),
      visited: new Set(),
    };
  }

  function handlePresetDragPointerMove(event) {
    if (!context.dragState) {
      return;
    }
    if (!context.dragState.dragActive) {
      if (!isEntityDragActivationMove(event)) {
        return;
      }
      event.preventDefault();
      context.dragState.dragActive = true;
      context.suppressNextPresetClick = true;
      context.dragState.sourceElement?.classList.add("is-drag-source");
      context.setStatus(`Dragging ${context.dragState.preset.name}. Release on an open map tile to place one.`);
    }
    updatePresetDragPreviewFromPoint(event.clientX, event.clientY);
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
      delete source.entity.editorTraySlot;
      context.editorState.entities.push({ position: { x, y }, entity: source.entity });
    }
    context.selectedEntityId = source.entity.id;
    context.selectedEditorTab = "entity";
    context.setStatus(`Moved ${source.entity.id} to (${x}, ${y}).`);
    renderEditor();
  }

  function selectDragSource() {
    const source = context.selectedDragEntity();
    if (!source) {
      return;
    }
    context.selectedEntityId = source.entity.id;
    context.selectedEditorTab = "entity";
    renderEditor();
  }

  function finishTraySelectDrag(index) {
    if (!context.dragState?.sourceId) {
      return;
    }
    const source = context.selectedDragEntity();
    if (!source) {
      return;
    }
    const target = trayEntityAt(index);
    if (target && target.id !== source.entity.id) {
      context.selectedEntityId = source.entity.id;
      context.setStatus(`${target.id} already occupies that off-map cell.`);
      renderEditor();
      return;
    }
    if (!source.position) {
      if (source.entity.editorTraySlot !== index) {
        history.record();
        source.entity.editorTraySlot = index;
        context.setStatus(`Moved ${source.entity.id} to an off-map cell.`);
      }
      context.selectedEntityId = source.entity.id;
      context.selectedEditorTab = "entity";
      renderEditor();
      return;
    }
    history.record();
    context.editorState.entities = context.editorState.entities.filter((placed) => placed.entity.id !== source.entity.id);
    source.entity.editorTraySlot = index;
    context.editorState.unplacedEntities = [...(context.editorState.unplacedEntities ?? []), source.entity];
    context.selectedEntityId = source.entity.id;
    context.selectedEditorTab = "entity";
    context.setStatus(`Moved ${source.entity.id} off-map.`);
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

  function finishPresetDragFromPoint(clientX, clientY) {
    const target = document.elementFromPoint(clientX, clientY);
    const gridCell = target?.closest("[data-x][data-y]");
    if (!gridCell || !context.dom.editorGrid.contains(gridCell)) {
      return;
    }
    finishPresetDrag(Number(gridCell.dataset.x), Number(gridCell.dataset.y));
  }

  function finishPresetDrag(x, y) {
    if (!context.dragState?.preset) {
      return;
    }
    const target = context.entityAt(x, y);
    if (target) {
      context.setStatus(`${target.entity.id} already occupies that tile.`);
      renderEditor();
      return;
    }
    history.record();
    const entity = context.createEntity(context.dragState.preset, x, y);
    context.editorState.entities.push(entity);
    context.selectedEntityId = entity.entity.id;
    context.selectedEditorTab = "entity";
    context.dragState.count = 1;
    context.setStatus(`Placed ${entity.entity.id}.`);
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

  function paintTrayPlace(index) {
    if (!context.dragState || visitDraggedTarget(`tray:${index}`) || trayEntityAt(index)) {
      return;
    }
    recordDragHistory();
    const id = context.uniqueEntityId(slugify(context.selectedPreset.name || context.selectedPreset.type));
    const entity = context.entityFromPreset(context.selectedPreset, id);
    entity.editorTraySlot = index;
    context.editorState.unplacedEntities = [...(context.editorState.unplacedEntities ?? []), entity];
    context.selectedEntityId = entity.id;
    context.dragState.count += 1;
    context.setStatus(`Placed ${entity.id} off-map.`);
    renderEditor();
  }

  function paintTrayErase(index) {
    const entity = trayEntityAt(index);
    if (!context.dragState || visitDraggedTarget(`tray:${index}`) || !entity) {
      return;
    }
    recordDragHistory();
    context.editorState.unplacedEntities = (context.editorState.unplacedEntities ?? []).filter(
      (candidate) => candidate.id !== entity.id,
    );
    if (context.selectedEntityId === entity.id) {
      context.selectedEntityId = null;
    }
    context.dragState.count += 1;
    context.setStatus(`Removed ${entity.id}.`);
    renderEditor();
  }

  function visitDraggedTile(x, y) {
    return visitDraggedTarget(`grid:${x},${y}`);
  }

  function visitDraggedTarget(key) {
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
    context.dom.entityPresets.querySelectorAll(".is-drag-source").forEach((button) => {
      button.classList.remove("is-drag-source");
    });
    context.dom.editorGrid.querySelectorAll(".is-drag-source, .is-drop-ok, .is-drop-blocked").forEach((cell) => {
      cell.classList.remove("is-drag-source", "is-drop-ok", "is-drop-blocked");
    });
    context.dom.editorTray.querySelectorAll(".is-drag-source, .is-drop-ok, .is-drop-blocked").forEach((item) => {
      item.classList.remove("is-drag-source", "is-drop-ok", "is-drop-blocked");
    });
  }

  function updateSelectDragPreviewFromPoint(clientX, clientY) {
    const target = document.elementFromPoint(clientX, clientY);
    const gridCell = target?.closest("[data-x][data-y]");
    if (gridCell && context.dom.editorGrid.contains(gridCell)) {
      updateDropPreview(gridCell, Number(gridCell.dataset.x), Number(gridCell.dataset.y));
      return;
    }
    const trayCell = target?.closest("[data-tray-index]");
    if (trayCell && context.dom.editorTray.contains(trayCell)) {
      updateTrayCellDropPreview(trayCell, Number(trayCell.dataset.trayIndex));
      return;
    }
    clearDropPreview();
    applyDragSourcePreview();
  }

  function updatePresetDragPreviewFromPoint(clientX, clientY) {
    const target = document.elementFromPoint(clientX, clientY);
    const gridCell = target?.closest("[data-x][data-y]");
    if (gridCell && context.dom.editorGrid.contains(gridCell)) {
      updateDropPreview(gridCell, Number(gridCell.dataset.x), Number(gridCell.dataset.y));
      return;
    }
    clearDropPreview();
    context.dragState?.sourceElement?.classList.add("is-drag-source");
  }

  function applyDragSourcePreview() {
    if (!context.dragState) {
      return;
    }
    if (context.dragState.sourceKind === "grid") {
      applyDragClasses(
        editorGridCell(context.dragState.sourceX, context.dragState.sourceY),
        context.dragState.sourceX,
        context.dragState.sourceY,
      );
      return;
    }
    if (context.dragState.sourceKind === "preset") {
      context.dragState.sourceElement?.classList.add("is-drag-source");
      return;
    }
    applyTrayDragClasses(editorTrayCell(context.dragState.sourceIndex), context.dragState.sourceIndex);
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
    } else if (context.dragState.sourceKind === "preset") {
      context.dragState.sourceElement?.classList.add("is-drag-source");
    } else {
      editorTrayItem(context.dragState.sourceId)?.classList.add("is-drag-source");
    }
    applyDragClasses(cell, x, y);
  }

  function updateTrayCellDropPreview(cell, index) {
    if (!context.dragState) {
      return;
    }
    context.dragState.targetIndex = index;
    clearDropPreview();
    if (context.dragState.sourceKind === "grid") {
      applyDragClasses(editorGridCell(context.dragState.sourceX, context.dragState.sourceY), context.dragState.sourceX, context.dragState.sourceY);
    } else {
      editorTrayItem(context.dragState.sourceId)?.classList.add("is-drag-source");
    }
    applyTrayDragClasses(cell, index);
  }

  function applyTrayDragClasses(cell, index) {
    if (!cell || !context.dragState) {
      return;
    }
    if (context.dragState.tool !== "select") {
      return;
    }
    if (!context.dragState.dragActive) {
      return;
    }
    context.dom.editorTray.classList.add("is-dragging");
    if (context.dragState.sourceKind === "tray" && context.dragState.sourceIndex === index) {
      cell.classList.add("is-drag-source");
    }
    if (context.dragState.targetIndex !== index || !context.dragState.sourceId) {
      return;
    }
    const target = trayEntityAt(index);
    cell.classList.add(target && target.id !== context.dragState.sourceId ? "is-drop-blocked" : "is-drop-ok");
  }

  function applyDragClasses(cell, x, y) {
    if (!cell || !context.dragState) {
      return;
    }
    if (context.dragState.tool !== "select" && context.dragState.tool !== "start" && context.dragState.tool !== "preset") {
      return;
    }
    if ((context.dragState.tool === "select" || context.dragState.tool === "preset") && !context.dragState.dragActive) {
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
    if (context.dragState.tool === "preset") {
      cell.classList.add(context.entityAt(x, y) ? "is-drop-blocked" : "is-drop-ok");
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

  function editorTrayCell(index) {
    return context.dom.editorTray.querySelector(`[data-tray-index="${index}"]`);
  }

  function isEntityDragActivationMove(event) {
    const distance = Math.hypot(
      event.clientX - context.dragState.pointerStartX,
      event.clientY - context.dragState.pointerStartY,
    );
    return distance >= context.dragState.activationDistance;
  }

  function entityDragActivationDistance(cell) {
    const rect = cell.getBoundingClientRect();
    const cellSize = Math.min(rect.width, rect.height);
    return Math.min(
      entityDragActivationMaxPx,
      Math.max(entityDragActivationMinPx, cellSize * entityDragActivationCellRatio),
    );
  }

  function entityDragStatusMessage() {
    if (context.dragState.sourceKind === "grid") {
      return `Dragging ${context.dragState.sourceId}. Release on an open tile or the tray.`;
    }
    return `Dragging ${context.dragState.sourceId}. Release on an open tile to place it.`;
  }

  function schedulePresetClickReset() {
    if (!context.suppressNextPresetClick) {
      return;
    }
    window.setTimeout(() => {
      context.suppressNextPresetClick = false;
    }, 0);
  }

  function trayEntityAt(index) {
    return trayEntitiesBySlot(context.editorState.unplacedEntities ?? []).get(index) ?? null;
  }

  function trayEntitiesBySlot(items) {
    const entitiesBySlot = new Map();
    items.forEach((entity, fallbackIndex) => {
      let slot = Number.isInteger(entity.editorTraySlot) && entity.editorTraySlot >= 0 ? entity.editorTraySlot : fallbackIndex;
      while (entitiesBySlot.has(slot)) {
        slot += 1;
      }
      entity.editorTraySlot = slot;
      entitiesBySlot.set(slot, entity);
    });
    return entitiesBySlot;
  }

  function trayCellCount(entitiesBySlot) {
    const maxSlot = Math.max(-1, ...entitiesBySlot.keys());
    return Math.max(minimumOffMapCellCount, maxSlot + 2);
  }

  function editorCellTitle(entity, isAgentStart, x, y) {
    return [entity?.entity.id, isAgentStart ? "Agent start" : null, `(${x}, ${y})`].filter(Boolean).join(" - ");
  }

  function editorTrayCellTitle(entity, index) {
    return [entity?.id, `Off-map ${index + 1}`].filter(Boolean).join(" - ");
  }

  return {
    beginPresetDrag,
    finishGridDrag,
    handleDragPointerMove,
    renderGrid,
    renderTray,
  };
}
