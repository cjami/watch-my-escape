const runButton = document.querySelector("#run-escape");
const statusOutput = document.querySelector("#status");
const sanityOutput = document.querySelector("#sanity");
const positionOutput = document.querySelector("#position");
const mapOutput = document.querySelector("#map-view");
const visibleEntitiesOutput = document.querySelector("#visible-entities");
const inventoryOutput = document.querySelector("#inventory");
const journalOutput = document.querySelector("#journal");
const transcriptOutput = document.querySelector("#transcript");

let activeStream = null;

runButton.addEventListener("click", async () => {
  if (activeStream) {
    activeStream.close();
  }

  runButton.disabled = true;
  statusOutput.textContent = "The model is trying to escape...";
  transcriptOutput.textContent = "Waiting for the first turn...";
  renderMap("");

  activeStream = new EventSource("/escape-stream");
  activeStream.onmessage = (event) => {
    const demo = JSON.parse(event.data);
    statusOutput.textContent = demo.status;
    sanityOutput.textContent = `Sanity: ${demo.sanity}`;
    positionOutput.textContent = demo.position ? `Position: ${demo.position}` : "Position: --";
    renderMap(demo.map);
    visibleEntitiesOutput.textContent = demo.visible_entities;
    inventoryOutput.textContent = demo.inventory;
    journalOutput.textContent = demo.journal;
    transcriptOutput.textContent = demo.transcript;
    if (demo.escaped || demo.sanity === "0" || demo.status === "Model is not configured.") {
      activeStream.close();
      activeStream = null;
      runButton.disabled = false;
    }
  };
  activeStream.onerror = () => {
    statusOutput.textContent = "The room stream closed.";
    activeStream.close();
    activeStream = null;
    runButton.disabled = false;
  };
});

function renderMap(mapText) {
  mapOutput.replaceChildren();
  const rows = mapText.trim() ? mapText.trim().split("\n") : [];
  if (!rows.length) {
    const empty = document.createElement("span");
    empty.className = "map-empty";
    empty.textContent = "No map available.";
    mapOutput.append(empty);
    return;
  }

  for (const row of rows) {
    for (const cell of row.split(" ")) {
      const tile = document.createElement("span");
      tile.className = "map-tile";
      tile.textContent = cell;
      mapOutput.append(tile);
    }
  }
}
