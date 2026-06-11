const customMapStorageKey = "watch-my-escape.custom";
const storageVersion = 1;
const mapSize = 15;
const agentPreviewIcon = "\u{1F642}";

export function createCustomMapStore({ storage = browserStorage() } = {}) {
  const listeners = new Set();

  function list() {
    return [...readDocuments()].sort(compareDocuments);
  }

  function get(mapId) {
    return readDocuments().find((document) => document.map.id === mapId) ?? null;
  }

  function save(document) {
    const documents = readDocuments();
    const existingIndex = documents.findIndex((candidate) => candidate.map.id === document.map.id);
    if (existingIndex >= 0) {
      documents[existingIndex] = document;
    } else {
      documents.push(document);
    }
    writeDocuments(documents);
  }

  function remove(mapId) {
    writeDocuments(readDocuments().filter((document) => document.map.id !== mapId));
  }

  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function readDocuments() {
    try {
      const stored = JSON.parse(storage.getItem(customMapStorageKey) ?? "{}");
      const documents = Array.isArray(stored) ? stored : stored.maps;
      return Array.isArray(documents) ? documents.filter(isMapDocument) : [];
    } catch {
      return [];
    }
  }

  function writeDocuments(documents) {
    storage.setItem(customMapStorageKey, JSON.stringify({ version: storageVersion, maps: documents }));
    notify();
  }

  function notify() {
    listeners.forEach((listener) => listener());
  }

  window.addEventListener("storage", (event) => {
    if (event.key === customMapStorageKey) {
      notify();
    }
  });

  return {
    get,
    list,
    remove,
    save,
    subscribe,
  };
}

function browserStorage() {
  try {
    return window.localStorage;
  } catch {
    return unavailableStorage();
  }
}

function unavailableStorage() {
  return {
    getItem: () => null,
    setItem: () => {
      throw new Error("Browser storage is unavailable.");
    },
  };
}

export function customMapOptionFromDocument(document) {
  return {
    id: document.map.id,
    name: document.map.name || document.map.id,
    description: document.description,
    source: "custom",
    document,
    preview_map: formatPreviewMap(document),
    preview_map_colors: formatPreviewColors(document),
    agent_position: formatPosition(document.map.agent_start),
  };
}

function isMapDocument(document) {
  return Boolean(document?.map?.id && document?.map?.agent_start && Array.isArray(document.map.entities));
}

function compareDocuments(first, second) {
  return displayName(first).localeCompare(displayName(second), undefined, { sensitivity: "base" });
}

function displayName(document) {
  return document.map.name || document.map.id;
}

function formatPreviewMap(document) {
  const rows = emptyRows(".");
  for (const placed of activePlacedEntities(document)) {
    rows[placed.position.y][placed.position.x] = placed.entity.icon;
  }
  const start = document.map.agent_start;
  rows[start.y][start.x] = agentPreviewIcon;
  return formatRows(rows);
}

function formatPreviewColors(document) {
  const rows = emptyRows(".");
  for (const placed of activePlacedEntities(document)) {
    rows[placed.position.y][placed.position.x] = placed.entity.color || ".";
  }
  const start = document.map.agent_start;
  rows[start.y][start.x] = ".";
  return formatRows(rows);
}

function activePlacedEntities(document) {
  return document.map.entities.filter(
    (placed) => isCoordinate(placed.position) && placed.entity?.active !== false && placed.entity?.icon,
  );
}

function emptyRows(value) {
  return Array.from({ length: mapSize }, () => Array.from({ length: mapSize }, () => value));
}

function formatRows(rows) {
  return rows.map((row) => row.join(" ")).join("\n");
}

function formatPosition(position) {
  return `(${position.x}, ${position.y})`;
}

function isCoordinate(position) {
  return (
    Number.isInteger(position?.x) &&
    Number.isInteger(position?.y) &&
    position.x >= 0 &&
    position.x < mapSize &&
    position.y >= 0 &&
    position.y < mapSize
  );
}
