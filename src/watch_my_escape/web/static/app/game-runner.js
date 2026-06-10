const escapeCelebrationDelayMs = 2000;

export function createGameRunner({ dom, getSelectedMap, getSelectedModel, mapRenderer, showScreen }) {
  let activeStream = null;
  let gameIntroTimer = null;
  let escapeCelebrationTimer = null;
  let runEpoch = 0;

  function init() {
    dom.restartButton.addEventListener("click", restartSetup);
    dom.runButton.addEventListener("click", runEscape);
  }

  async function runEscape() {
    const selectedModel = getSelectedModel();
    const selectedMap = getSelectedMap();
    if (!selectedModel || !selectedMap) {
      showScreen("models");
      return;
    }

    stopStream();
    resetGame();
    const currentRunEpoch = (runEpoch += 1);
    dom.runButton.disabled = true;
    dom.statusOutput.textContent = "The CRT is warming up...";
    dom.transcriptOutput.textContent = "Waiting for the first turn...";
    const startupDelay = gameStartupDelay();
    void playGameIntro();
    dom.statusOutput.textContent = "The model is trying to escape...";

    const params = new URLSearchParams({
      model_preset: selectedModel.id,
      map_id: selectedMap.id,
      startup_delay_ms: String(startupDelay),
    });
    activeStream = new EventSource(`/escape-stream?${params}`);
    activeStream.onmessage = (event) => {
      if (currentRunEpoch !== runEpoch) {
        return;
      }
      const frame = JSON.parse(event.data);
      dom.statusOutput.textContent = frame.status;
      dom.sanityOutput.textContent = `Sanity: ${frame.sanity}`;
      dom.positionOutput.textContent = frame.position ? `Position: ${frame.position}` : "Position: --";
      mapRenderer.renderMap(frame.map, frame.position, frame.visibility, frame.action_label);
      dom.visibleEntitiesOutput.textContent = frame.visible_entities;
      dom.inventoryOutput.textContent = frame.inventory;
      dom.transcriptOutput.textContent = frame.transcript;
      if (frame.escaped) {
        scheduleEscapeCelebration(currentRunEpoch);
      } else {
        clearEscapeCelebrationTimer();
        dom.escapeBanner.hidden = true;
      }
      if (frame.escaped || frame.sanity === "0" || frame.status === "Model is not configured.") {
        stopStream();
        dom.runButton.disabled = false;
      }
    };
    activeStream.onerror = () => {
      if (currentRunEpoch !== runEpoch) {
        return;
      }
      dom.statusOutput.textContent = "The room stream closed.";
      stopStream();
      dom.runButton.disabled = false;
    };
  }

  function restartSetup() {
    runEpoch += 1;
    stopStream();
    resetGame();
    showScreen("models");
  }

  function gameIntroDuration() {
    if (!dom.gameIntro) {
      return 0;
    }
    return 4300;
  }

  function gameStartupDelay() {
    if (!dom.gameIntro) {
      return 0;
    }
    return 2000;
  }

  function playGameIntro(introDuration = gameIntroDuration()) {
    if (!dom.gameIntro) {
      return Promise.resolve();
    }

    window.clearTimeout(gameIntroTimer);
    dom.gameIntro.hidden = false;
    dom.gameIntro.classList.remove("is-playing");
    void dom.gameIntro.offsetWidth;
    dom.gameIntro.classList.add("is-playing");
    return new Promise((resolve) => {
      gameIntroTimer = window.setTimeout(() => {
        dom.gameIntro.hidden = true;
        dom.gameIntro.classList.remove("is-playing");
        resolve();
      }, introDuration);
    });
  }

  function stopStream() {
    if (!activeStream) {
      return;
    }
    activeStream.close();
    activeStream = null;
  }

  function scheduleEscapeCelebration(currentRunEpoch) {
    clearEscapeCelebrationTimer();
    dom.escapeBanner.hidden = true;
    escapeCelebrationTimer = window.setTimeout(() => {
      if (currentRunEpoch !== runEpoch) {
        return;
      }
      mapRenderer.renderEscapeCelebration();
      dom.escapeBanner.hidden = false;
      escapeCelebrationTimer = null;
    }, escapeCelebrationDelayMs);
  }

  function clearEscapeCelebrationTimer() {
    window.clearTimeout(escapeCelebrationTimer);
    escapeCelebrationTimer = null;
  }

  function resetGame() {
    dom.statusOutput.textContent = "Ready.";
    dom.sanityOutput.textContent = "Sanity: 100";
    dom.positionOutput.textContent = "Position: --";
    dom.visibleEntitiesOutput.textContent = "- None.";
    dom.inventoryOutput.textContent = "- Empty.";
    dom.transcriptOutput.textContent = "The model has not tried the room yet.";
    clearEscapeCelebrationTimer();
    dom.escapeBanner.hidden = true;
    dom.escapeAgentIcon.replaceChildren();
    mapRenderer.renderMap("", "", "", "");
    dom.runButton.disabled = false;
  }

  return { init, resetGame, runEscape, stopStream };
}
