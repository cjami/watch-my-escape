const progressTickMs = 360;
const progressFloor = 7;
const progressCeiling = 92;

export function createModelWarmup({ dom, getSelectedModel, showScreen }) {
  let warmupEpoch = 0;
  let progressTimer = null;
  let abortController = null;

  async function runBeforeGame(onComplete) {
    const model = getSelectedModel();
    if (!model) {
      onComplete(null);
      return;
    }

    const currentEpoch = (warmupEpoch += 1);
    abortActiveRequest();
    abortController = new AbortController();
    showScreen("warmup");
    startProgress(model);

    let warmupToken = null;
    try {
      warmupToken = await requestWarmup(model.id, abortController.signal);
      if (currentEpoch !== warmupEpoch) {
        return;
      }
      completeProgress("SYSTEM READY");
    } catch (error) {
      if (currentEpoch !== warmupEpoch || error.name === "AbortError") {
        return;
      }
      completeProgress("WARMUP SKIPPED");
    }

    window.setTimeout(() => {
      if (currentEpoch === warmupEpoch) {
        onComplete(warmupToken);
      }
    }, 450);
  }

  function cancel() {
    warmupEpoch += 1;
    abortActiveRequest();
    stopProgress();
  }

  function startProgress(model) {
    stopProgress();
    setProgress(progressFloor);
    dom.warmupModel.textContent = `${model.company} / ${model.display_name}`;
    dom.warmupStatus.textContent = "BOOTING MODEL";

    let progress = progressFloor;
    progressTimer = window.setInterval(() => {
      progress += Math.max(0.55, (progressCeiling - progress) * 0.045);
      setProgress(Math.min(progress, progressCeiling));
    }, progressTickMs);
  }

  function completeProgress(status) {
    stopProgress();
    dom.warmupStatus.textContent = status;
    setProgress(100);
  }

  function stopProgress() {
    window.clearInterval(progressTimer);
    progressTimer = null;
  }

  function setProgress(percent) {
    dom.warmupProgress.style.width = `${percent}%`;
  }

  function abortActiveRequest() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  }

  return { cancel, runBeforeGame };
}

async function requestWarmup(modelPreset, signal) {
  const response = await fetch("/models/warmup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_preset: modelPreset }),
    signal,
  });
  if (!response.ok) {
    throw new Error("Model warmup failed.");
  }
  const payload = await response.json();
  return payload.warmup_token ? String(payload.warmup_token) : null;
}
