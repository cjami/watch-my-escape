const progressTickMs = 360;
const progressFloor = 7;
const progressCeiling = 92;

export function createModelWarmup({ dom, focusScreen = () => {}, getSelectedModel, getSessionId, showScreen }) {
  let warmupEpoch = 0;
  let progressTimer = null;
  let abortController = null;

  async function runBeforeGame(onComplete) {
    const model = getSelectedModel();
    if (!model) {
      onComplete();
      return;
    }

    const currentEpoch = (warmupEpoch += 1);
    abortActiveRequest();
    abortController = new AbortController();
    showScreen("warmup");
    focusScreen("warmup");
    startProgress(model);

    try {
      await requestWarmup(getSessionId(), model.id, abortController.signal);
      if (currentEpoch !== warmupEpoch) {
        return;
      }
      completeProgress("SYSTEM READY");
    } catch (error) {
      if (currentEpoch !== warmupEpoch || error.name === "AbortError") {
        return;
      }
      completeProgress(error.errorCode === "zerogpu_quota_exhausted" ? "ZEROGPU TIME EXHAUSTED" : "WARMUP SKIPPED");
    }

    window.setTimeout(() => {
      if (currentEpoch === warmupEpoch) {
        onComplete();
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

async function requestWarmup(sessionId, modelPreset, signal) {
  const response = await fetch("/models/warmup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, model_preset: modelPreset }),
    signal,
  });
  if (!response.ok) {
    const detail = await warmupErrorDetail(response);
    if (detail?.error_code === "zerogpu_quota_exhausted") {
      const error = new Error(detail.message || "ZeroGPU time is exhausted.");
      error.errorCode = detail.error_code;
      throw error;
    }
    throw new Error("Model warmup failed.");
  }
}

async function warmupErrorDetail(response) {
  try {
    const payload = await response.json();
    return payload.detail;
  } catch {
    return null;
  }
}
