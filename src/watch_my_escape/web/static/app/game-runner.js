import { formatValidationError } from "./shared/strings.js";

const escapeResultDelayMs = 2000;
const escapeResults = {
  victory: {
    ariaLabel: "I did it",
    icon: "\u{1F973}",
    iconLabel: "Escaped agent",
    words: ["I", "DID", "IT!"],
  },
  loss: {
    ariaLabel: "I give up",
    icon: "\u{1F62D}",
    iconLabel: "Overwhelmed agent",
    words: ["I", "GIVE", "UP"],
  },
};

export function createGameRunner({
  dom,
  getSelectedMap,
  getSelectedModel,
  getSessionId,
  mapRenderer,
  pixelSprite,
  showScreen,
  showSetupScreen = () => showScreen("models"),
}) {
  let activeStream = null;
  let gameIntroTimer = null;
  let escapeResultTimer = null;
  let runEpoch = 0;
  const transcriptScroll = createTranscriptScrollController(dom.transcriptOutput);

  function init() {
    transcriptScroll.init();
    dom.restartButton.addEventListener("click", restartSetup);
    dom.runButton.addEventListener("click", runEscape);
  }

  async function runEscape() {
    const selectedModel = getSelectedModel();
    const selectedMap = getSelectedMap();
    if (!selectedModel || !selectedMap) {
      showSetupScreen();
      return;
    }

    stopStream();
    resetGame();
    const currentRunEpoch = (runEpoch += 1);
    dom.runButton.disabled = true;
    dom.transcriptOutput.textContent = "Waiting for the first turn...";
    transcriptScroll.scrollToBottom();
    const startupDelay = gameStartupDelay();

    let params;
    try {
      params = await escapeStreamParams(selectedModel, selectedMap, startupDelay, getSessionId());
    } catch (error) {
      if (currentRunEpoch !== runEpoch) {
        return;
      }
      dom.transcriptOutput.textContent = error.message;
      transcriptScroll.scrollToBottom();
      dom.runButton.disabled = false;
      return;
    }

    if (currentRunEpoch !== runEpoch) {
      return;
    }
    void playGameIntro();
    activeStream = new EventSource(`/escape-stream?${params}`);
    activeStream.onmessage = (event) => {
      if (currentRunEpoch !== runEpoch) {
        return;
      }
      const frame = JSON.parse(event.data);
      dom.sanityOutput.textContent = `Sanity: ${frame.sanity}`;
      dom.positionOutput.textContent = frame.position ? `Position: ${frame.position}` : "Position: --";
      mapRenderer.renderMap(frame.map, frame.position, frame.visibility, frame.action_label, frame.map_colors);
      renderEntityStrip(dom.visibleEntitiesOutput, frame.visible_entity_details, "None.", frame.visible_entities);
      renderEntityStrip(dom.inventoryOutput, frame.inventory_details, "Empty.", frame.inventory);
      const shouldFollowTranscript = transcriptScroll.shouldFollowOutput();
      dom.transcriptOutput.textContent = frame.transcript;
      transcriptScroll.scrollToBottomIfFollowing(shouldFollowTranscript);
      if (frame.escaped) {
        scheduleEscapeResult(currentRunEpoch, "victory");
      } else if (frame.sanity === "0") {
        scheduleEscapeResult(currentRunEpoch, "loss");
      } else {
        hideEscapeResult();
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
      const shouldFollowTranscript = transcriptScroll.shouldFollowOutput();
      dom.transcriptOutput.textContent = "The room stream closed.";
      transcriptScroll.scrollToBottomIfFollowing(shouldFollowTranscript);
      stopStream();
      dom.runButton.disabled = false;
    };
  }

  function restartSetup() {
    runEpoch += 1;
    stopStream();
    resetGame();
    showSetupScreen();
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

  function scheduleEscapeResult(currentRunEpoch, resultName) {
    clearEscapeResultTimer();
    dom.escapeBanner.hidden = true;
    escapeResultTimer = window.setTimeout(() => {
      if (currentRunEpoch !== runEpoch) {
        return;
      }
      renderEscapeResult(resultName);
      dom.escapeBanner.hidden = false;
      escapeResultTimer = null;
    }, escapeResultDelayMs);
  }

  function renderEscapeResult(resultName) {
    const result = escapeResults[resultName];
    dom.escapeBanner.dataset.result = resultName;
    dom.escapeResultIcon.replaceChildren(
      pixelSprite(result.icon, result.iconLabel, getSelectedModel()?.brand_color, 40),
    );
    dom.escapeResultMessage.setAttribute("aria-label", result.ariaLabel);
    dom.escapeResultMessage.replaceChildren(...result.words.map(escapeWord));
  }

  function escapeWord(text) {
    const word = document.createElement("span");
    word.className = "escape-word";
    word.textContent = text;
    return word;
  }

  function hideEscapeResult() {
    clearEscapeResultTimer();
    dom.escapeBanner.hidden = true;
  }

  function clearEscapeResultTimer() {
    window.clearTimeout(escapeResultTimer);
    escapeResultTimer = null;
  }

  function resetGame() {
    dom.sanityOutput.textContent = "Sanity: 100";
    dom.positionOutput.textContent = "Position: --";
    renderEntityStrip(dom.visibleEntitiesOutput, [], "None.");
    renderEntityStrip(dom.inventoryOutput, [], "Empty.");
    dom.transcriptOutput.textContent = "The model has not tried the room yet.";
    transcriptScroll.scrollToBottom();
    clearEscapeResultTimer();
    dom.escapeBanner.hidden = true;
    dom.escapeBanner.dataset.result = "victory";
    dom.escapeResultIcon.replaceChildren();
    mapRenderer.renderMap("", "", "", "");
    dom.runButton.disabled = false;
  }

  function renderEntityStrip(element, details, emptyText, fallbackText = "") {
    const items = entityDetails(details, fallbackText);
    const signature = entityStripSignature(items, emptyText);
    if (element.dataset.entitySignature === signature) {
      return;
    }

    element.dataset.entitySignature = signature;
    element.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("span");
      empty.className = "entity-strip-empty";
      empty.textContent = emptyText;
      element.append(empty);
      return;
    }

    items.forEach((item) => {
      element.append(entityToken(item));
    });
  }

  function entityToken(item) {
    const token = document.createElement("span");
    token.className = "entity-token";
    token.role = "listitem";
    token.tabIndex = 0;
    token.setAttribute("aria-label", entityLabel(item));
    token.append(pixelSprite(item.icon || "?", item.id, item.color || null, 28));

    const tooltip = document.createElement("span");
    tooltip.className = "entity-tooltip";
    tooltip.role = "tooltip";

    const id = document.createElement("span");
    id.className = "entity-tooltip-id";
    id.textContent = item.id;
    tooltip.append(id);

    if (item.description) {
      const description = document.createElement("span");
      description.className = "entity-tooltip-description";
      description.textContent = item.description;
      tooltip.append(description);
    }

    token.append(tooltip);
    return token;
  }

  return { init, resetGame, restartSetup, runEscape, stopStream };
}

async function escapeStreamParams(selectedModel, selectedMap, startupDelay, sessionId) {
  const params = new URLSearchParams({
    model_preset: selectedModel.id,
    session_id: sessionId,
    startup_delay_ms: String(startupDelay),
  });
  if (selectedModel.deliberation_settings) {
    params.set("deliberation_enable_thinking", String(selectedModel.deliberation_settings.enable_thinking));
    params.set("deliberation_temperature", String(selectedModel.deliberation_settings.temperature));
  }
  if (selectedMap.source === "custom") {
    params.set("custom_map_token", await customMapToken(selectedMap));
    return params;
  }
  params.set("map_id", selectedMap.id);
  return params;
}

async function customMapToken(selectedMap) {
  if (!selectedMap.document) {
    throw new Error("Custom map could not be loaded.");
  }

  let response;
  try {
    response = await fetch("/maps/custom-run-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(selectedMap.document),
    });
  } catch {
    throw new Error("Custom map could not be sent to the room.");
  }

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`Custom map rejected: ${formatValidationError(error)}`);
  }

  const payload = await response.json();
  if (!payload.token) {
    throw new Error("Custom map token was not returned.");
  }
  return payload.token;
}

function entityDetails(details, fallbackText) {
  if (Array.isArray(details) && details.length) {
    return details.map((item) => ({
      id: String(item.id ?? ""),
      icon: String(item.icon ?? ""),
      color: String(item.color ?? ""),
      description: String(item.description ?? ""),
    }));
  }
  return legacyEntityDetails(fallbackText);
}

function legacyEntityDetails(text) {
  if (!text || text === "- None." || text === "- Empty.") {
    return [];
  }
  return text
    .split("\n")
    .map((line) => line.replace(/^- /, "").trim())
    .filter(Boolean)
    .map((line) => {
      const [id, ...descriptionParts] = line.split(": ");
      return {
        id,
        icon: "?",
        color: "",
        description: descriptionParts.join(": "),
      };
    });
}

function entityLabel(item) {
  return [item.id, item.description].filter(Boolean).join(": ");
}

function entityStripSignature(items, emptyText) {
  return JSON.stringify({ emptyText, items });
}

function createTranscriptScrollController(element) {
  const bottomThresholdPx = 8;
  let followsOutput = true;
  let pointerHeld = false;

  function init() {
    element.addEventListener("pointerdown", () => {
      pointerHeld = true;
    });
    element.addEventListener("scroll", updateFollowState);
    window.addEventListener("pointerup", releasePointer);
    window.addEventListener("pointercancel", releasePointer);
    window.addEventListener("blur", releasePointer);
  }

  function shouldFollowOutput() {
    return followsOutput && !pointerHeld;
  }

  function scrollToBottomIfFollowing(shouldFollow) {
    if (shouldFollow) {
      scrollToBottom();
    }
  }

  function scrollToBottom() {
    followsOutput = true;
    requestAnimationFrame(() => {
      element.scrollTop = element.scrollHeight;
      followsOutput = true;
    });
  }

  function releasePointer() {
    pointerHeld = false;
    updateFollowState();
  }

  function updateFollowState() {
    followsOutput = isAtBottom();
  }

  function isAtBottom() {
    return element.scrollHeight - element.scrollTop - element.clientHeight <= bottomThresholdPx;
  }

  return { init, scrollToBottom, scrollToBottomIfFollowing, shouldFollowOutput };
}
