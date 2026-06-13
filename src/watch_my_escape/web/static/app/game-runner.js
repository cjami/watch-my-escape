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
    renderTranscriptMessage(dom.transcriptOutput, "Waiting for the first turn...");
    transcriptScroll.scrollToBottom();
    const startupDelay = gameStartupDelay();

    let params;
    try {
      params = await escapeStreamParams(selectedModel, selectedMap, startupDelay, getSessionId());
    } catch (error) {
      if (currentRunEpoch !== runEpoch) {
        return;
      }
      renderTranscriptMessage(dom.transcriptOutput, error.message);
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
      renderTranscript(dom.transcriptOutput, frame, pixelSprite);
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
      renderTranscriptMessage(dom.transcriptOutput, "The room stream closed.");
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
    renderTranscriptMessage(dom.transcriptOutput, "The model has not tried the room yet.");
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

function renderTranscript(element, frame, pixelSprite) {
  const events = Array.isArray(frame.transcript_events) ? frame.transcript_events : [];
  if (!events.length) {
    renderTranscriptMessage(element, frame.transcript || "Waiting for the first turn.");
    return;
  }

  const signature = JSON.stringify(events);
  if (element.dataset.transcriptSignature === signature) {
    return;
  }

  element.dataset.transcriptSignature = signature;
  element.replaceChildren(...events.map((event) => transcriptCard(event, pixelSprite)));
}

function renderTranscriptMessage(element, message) {
  const signature = JSON.stringify({ message });
  if (element.dataset.transcriptSignature === signature) {
    return;
  }

  element.dataset.transcriptSignature = signature;
  const empty = document.createElement("p");
  empty.className = "transcript-empty";
  empty.textContent = message;
  element.replaceChildren(empty);
}

function transcriptCard(event, pixelSprite) {
  if (event.kind === "turn") {
    return transcriptTurnCard(event, pixelSprite);
  }
  return transcriptIntroCard(event, pixelSprite);
}

function transcriptIntroCard(event, pixelSprite) {
  const card = document.createElement("article");
  card.className = "transcript-card transcript-card-intro";

  const header = document.createElement("div");
  header.className = "transcript-card-header";
  header.append(transcriptKicker("Map"), transcriptTitle("Visible entities"));
  card.append(header);

  if (event.message) {
    const message = document.createElement("p");
    message.className = "transcript-card-copy";
    message.textContent = event.message;
    card.append(message);
  }

  const entities = entityDetails(event.visible_entities, "");
  if (entities.length) {
    const list = document.createElement("div");
    list.className = "transcript-entity-list";
    list.setAttribute("aria-label", "Visible entities at start");
    entities.forEach((entity) => {
      list.append(transcriptEntityChip(entity, pixelSprite));
    });
    card.append(list);
  } else {
    const empty = document.createElement("p");
    empty.className = "transcript-empty";
    empty.textContent = "No visible entities.";
    card.append(empty);
  }

  return card;
}

function transcriptTurnCard(event, pixelSprite) {
  const card = document.createElement("article");
  const actionType = String(event.action_type || "unknown");
  card.className = `transcript-card transcript-card-turn transcript-action-${cssIdentifier(actionType)}`;
  if (actionType === "talk_to") {
    card.classList.add("transcript-card-talk");
  }

  const header = document.createElement("div");
  header.className = "transcript-card-header";
  header.append(transcriptKicker(`Turn ${event.turn_number ?? "?"}`), transcriptSanity(event));
  card.append(header);

  const action = document.createElement("div");
  action.className = "transcript-action-line";
  const icon = document.createElement("span");
  icon.className = "transcript-action-icon";
  icon.append(pixelSprite(event.action_emoji || fallbackActionEmoji(actionType), actionType, null, 20));
  const actionText = document.createElement("strong");
  actionText.className = "transcript-action-text";
  actionText.textContent = event.action_text || "Unknown action";
  action.append(icon, actionText);
  card.append(action);

  if (actionType === "talk_to" && event.spoken_text) {
    const speech = document.createElement("p");
    speech.className = "transcript-speech";
    speech.textContent = `"${event.spoken_text}"`;
    card.append(speech);
  }

  if (event.result) {
    const result = document.createElement("p");
    result.className = "transcript-result";
    result.textContent = event.result;
    card.append(result);
  }

  const effects = Array.isArray(event.effects) ? event.effects.filter((effect) => effect.text) : [];
  if (effects.length) {
    card.append(transcriptEffects(effects));
  }

  if (event.deliberation) {
    card.append(transcriptDeliberation(event.deliberation));
  }

  return card;
}

function transcriptKicker(text) {
  const element = document.createElement("span");
  element.className = "transcript-kicker";
  element.textContent = text;
  return element;
}

function transcriptTitle(text) {
  const element = document.createElement("strong");
  element.className = "transcript-title";
  element.textContent = text;
  return element;
}

function transcriptSanity(event) {
  const element = document.createElement("span");
  element.className = "transcript-sanity";
  element.textContent = `Sanity ${event.sanity_before ?? "?"} → ${event.sanity_after ?? "?"}`;
  return element;
}

function transcriptEffects(effects) {
  const list = document.createElement("div");
  list.className = "transcript-effects";
  list.setAttribute("aria-label", "Action effects");
  effects.forEach((effect) => {
    list.append(transcriptEffectChip(effect));
  });
  return list;
}

function transcriptEffectChip(effect) {
  const chip = document.createElement("span");
  chip.className = `transcript-effect transcript-effect-${cssIdentifier(effect.kind || "effect")}`;
  chip.textContent = effect.text;
  return chip;
}

function transcriptEntityChip(item, pixelSprite) {
  const chip = document.createElement("span");
  chip.className = "transcript-entity-chip";
  chip.title = entityLabel(item);

  const icon = document.createElement("span");
  icon.className = "transcript-entity-icon";
  icon.append(pixelSprite(item.icon || "?", item.id, item.color || null, 18));

  const label = document.createElement("span");
  label.className = "transcript-entity-name";
  label.textContent = item.id;

  chip.append(icon, label);
  if (item.description) {
    const description = document.createElement("span");
    description.className = "transcript-entity-description";
    description.textContent = item.description;
    chip.append(description);
  }
  return chip;
}

function transcriptDeliberation(text) {
  const details = document.createElement("details");
  details.className = "transcript-deliberation";

  const summary = document.createElement("summary");
  summary.textContent = "Deliberation";

  const copy = document.createElement("p");
  copy.textContent = text;

  details.append(summary, copy);
  return details;
}

function fallbackActionEmoji(actionType) {
  const emojis = {
    close: "\u{21A9}\u{FE0F}",
    examine: "\u{1F50D}",
    invalid: "\u{26A0}\u{FE0F}",
    none: "\u{00B7}",
    open: "\u{1F6AA}",
    operate: "\u{2699}\u{FE0F}",
    pick_up: "\u{1F590}\u{FE0F}",
    pull: "\u{2B07}\u{FE0F}",
    push: "\u{2B06}\u{FE0F}",
    talk_to: "\u{1F4AC}",
    use_item: "\u{1F9F0}",
  };
  return emojis[actionType] || emojis.invalid;
}

function cssIdentifier(value) {
  return String(value).replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
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
