import { parsePosition } from "./shared/strings.js";

const actionLabelHeight = 0.52;
const actionLabelPadding = 0.06;
const actionLabelFallbackWidth = 0.9;
const actionLabelFallbackOffset = 0.28;
const actionLabelMinWidth = 1.25;
const actionLabelMaxWidth = 3.3;
const actionLabelCharacterWidth = 0.34;
const actionLabelWidthPadding = 0.28;

export function createMapRenderer({ dom, getSelectedModel, pixelSprite }) {
  let lastMapText = "";
  let lastVisibilityText = "";
  let lastAgentPosition = "";
  let lastActionLabel = "";
  let lastColorText = "";

  function renderMap(mapText, agentPosition, visibilityText = "", actionLabel = "", colorText = "") {
    const previousAgentPosition = lastAgentPosition;
    lastMapText = mapText;
    lastVisibilityText = visibilityText;
    lastAgentPosition = agentPosition;
    lastActionLabel = actionLabel;
    lastColorText = colorText;
    renderMapInto({
      actionLabel,
      agentPosition,
      colorText,
      container: dom.mapOutput,
      getAgentColor: () => getSelectedModel()?.brand_color,
      mapText,
      pixelSprite,
      previousAgentPosition,
      visibilityText,
    });
  }

  function refresh() {
    renderMap(lastMapText, lastAgentPosition, lastVisibilityText, lastActionLabel, lastColorText);
  }

  return { refresh, renderMap };
}

export function renderMapInto({
  actionLabel = "",
  agentPosition,
  colorText = "",
  container,
  getAgentColor = () => null,
  mapText,
  pixelSprite,
  previousAgentPosition = "",
  visibilityText = "",
}) {
  container.replaceChildren();
  const rows = parseMapRows(mapText);
  if (!rows.length) {
    return;
  }

  const visibilityRows = parseVisibilityRows(visibilityText);
  const colorRows = parseColorRows(colorText);
  const hasVisibility = visibilityRows.length === rows.length;
  const agentCoordinate = parsePosition(agentPosition);
  const agentMoved = Boolean(previousAgentPosition && agentPosition && previousAgentPosition !== agentPosition);
  const labelPosition = actionLabel
    ? actionLabelPosition(rows, visibilityRows, hasVisibility, agentCoordinate, actionLabel)
    : null;
  rows.forEach((row, y) => {
    row.forEach((cell, x) => {
      const tile = document.createElement("span");
      tile.className = "map-tile";
      const visibleToAgent = !hasVisibility || visibilityRows[y]?.[x] !== false;
      tile.classList.toggle("visible-tile", visibleToAgent);
      tile.classList.toggle("hidden-tile", !visibleToAgent);
      tile.setAttribute("aria-label", visibleToAgent ? "visible to agent" : "not visible to agent");
      const isAgentTile = agentCoordinate?.x === x && agentCoordinate.y === y;
      if (isAgentTile) {
        tile.classList.add("agent-tile");
        tile.classList.toggle("agent-just-moved", agentMoved);
      }
      if (cell !== ".") {
        const tint = isAgentTile ? getAgentColor() : entityColorAt(colorRows, x, y);
        tile.append(pixelSprite(cell, cell, tint));
      }
      container.append(tile);
    });
  });
  if (labelPosition) {
    container.append(actionLabelElement(actionLabel, labelPosition));
  }
}

function parseMapRows(mapText) {
  if (!mapText?.trim()) {
    return [];
  }
  return mapText
    .trim()
    .split("\n")
    .map((row) => row.split(" "));
}

function parseVisibilityRows(visibilityText) {
  if (!visibilityText?.trim()) {
    return [];
  }
  return visibilityText
    .trim()
    .split("\n")
    .map((row) => row.split(" ").map((cell) => cell === "1"));
}

function parseColorRows(colorText) {
  if (!colorText?.trim()) {
    return [];
  }
  return colorText
    .trim()
    .split("\n")
    .map((row) => row.split(" "));
}

function entityColorAt(colorRows, x, y) {
  const color = colorRows[y]?.[x];
  return color && color !== "." ? color : null;
}

function actionLabelPosition(rows, visibilityRows, hasVisibility, agentCoordinate, label) {
  if (!agentCoordinate) {
    return null;
  }

  const width = actionLabelWidth(label);
  const center = { x: agentCoordinate.x + 0.5, y: agentCoordinate.y + 0.5 };
  const candidates = actionLabelCandidates(center, width);
  const candidate =
    candidates.find((placement) =>
      canPlaceActionLabel(rows, visibilityRows, hasVisibility, agentCoordinate, placement.box),
    ) ?? actionLabelFallback(center);
  return {
    direction: candidate.direction,
    left: `${(candidate.x / rows[0].length) * 100}%`,
    top: `${(candidate.y / rows.length) * 100}%`,
  };
}

function actionLabelWidth(label) {
  return Math.min(
    actionLabelMaxWidth,
    Math.max(actionLabelMinWidth, label.length * actionLabelCharacterWidth + actionLabelWidthPadding),
  );
}

function actionLabelCandidates(center, width) {
  const topAnchor = center.y - 0.5 - actionLabelPadding;
  const rightAnchor = center.x + 0.5 + actionLabelPadding;
  const bottomAnchor = center.y + 0.5 + actionLabelPadding;
  const leftAnchor = center.x - 0.5 - actionLabelPadding;
  return [
    {
      direction: "above",
      x: center.x,
      y: topAnchor,
      box: boxAbove(center.x, topAnchor, width),
    },
    {
      direction: "right",
      x: rightAnchor,
      y: center.y,
      box: boxRight(rightAnchor, center.y, width),
    },
    {
      direction: "below",
      x: center.x,
      y: bottomAnchor,
      box: boxBelow(center.x, bottomAnchor, width),
    },
    {
      direction: "left",
      x: leftAnchor,
      y: center.y,
      box: boxLeft(leftAnchor, center.y, width),
    },
  ];
}

function actionLabelFallback(center) {
  const y = Math.max(actionLabelHeight / 2, center.y - actionLabelFallbackOffset);
  return {
    direction: "agent",
    x: center.x,
    y,
    box: boxFromCenter(center.x, y, actionLabelFallbackWidth, actionLabelHeight),
  };
}

function boxAbove(x, bottom, width) {
  return { left: x - width / 2, right: x + width / 2, top: bottom - actionLabelHeight, bottom };
}

function boxRight(left, y, width) {
  return { left, right: left + width, top: y - actionLabelHeight / 2, bottom: y + actionLabelHeight / 2 };
}

function boxBelow(x, top, width) {
  return { left: x - width / 2, right: x + width / 2, top, bottom: top + actionLabelHeight };
}

function boxLeft(right, y, width) {
  return { left: right - width, right, top: y - actionLabelHeight / 2, bottom: y + actionLabelHeight / 2 };
}

function boxFromCenter(x, y, width, height) {
  return {
    left: x - width / 2,
    right: x + width / 2,
    top: y - height / 2,
    bottom: y + height / 2,
  };
}

function canPlaceActionLabel(rows, visibilityRows, hasVisibility, agentCoordinate, box) {
  if (box.left < 0 || box.top < 0 || box.right > rows[0].length || box.bottom > rows.length) {
    return false;
  }

  for (let y = Math.floor(box.top); y < Math.ceil(box.bottom); y += 1) {
    for (let x = Math.floor(box.left); x < Math.ceil(box.right); x += 1) {
      if (x === agentCoordinate.x && y === agentCoordinate.y) {
        continue;
      }
      if (labelOverlapsVisibleEntity(rows, visibilityRows, hasVisibility, box, x, y)) {
        return false;
      }
    }
  }
  return true;
}

function labelOverlapsVisibleEntity(rows, visibilityRows, hasVisibility, box, x, y) {
  const cell = rows[y]?.[x];
  const visibleToAgent = !hasVisibility || visibilityRows[y]?.[x] !== false;
  return Boolean(cell && cell !== "." && visibleToAgent && rectanglesOverlap(box, cellBox(x, y)));
}

function cellBox(x, y) {
  return { left: x, right: x + 1, top: y, bottom: y + 1 };
}

function rectanglesOverlap(first, second) {
  return (
    first.left < second.right &&
    first.right > second.left &&
    first.top < second.bottom &&
    first.bottom > second.top
  );
}

function actionLabelElement(label, position) {
  const element = document.createElement("span");
  element.className = "action-label";
  element.classList.add(`is-${position.direction}`);
  element.style.left = position.left;
  element.style.top = position.top;
  element.textContent = label;
  return element;
}
