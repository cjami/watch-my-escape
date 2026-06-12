import { escapeHtml } from "./shared/html.js";

export function createModelSelector({ dom, models, onSelected, pixelSprite }) {
  let selectedModelIndex = 0;
  let selectedModelSettings = defaultDeliberationSettings(models[0]);

  dom.modelSettingsToggle.addEventListener("click", toggleAdvancedSettings);
  dom.modelThinkingToggle.addEventListener("click", toggleThinking);
  dom.modelTemperatureDown.addEventListener("click", () => adjustTemperature(-temperatureStep));
  dom.modelTemperatureUp.addEventListener("click", () => adjustTemperature(temperatureStep));
  document.addEventListener("click", closeAdvancedSettingsOnOutsideClick);

  function renderModelOptions() {
    if (!models.length) {
      return;
    }
    selectedModelIndex = clampModelIndex(selectedModelIndex);
    const model = models[selectedModelIndex];
    const maxParameters = Math.max(...models.map((candidate) => candidate.parameter_size_b));
    const sizeRatio = Math.sqrt(model.parameter_size_b / maxParameters);
    dom.modelOptions.style.setProperty("--model-color", model.brand_color);
    dom.modelAgentOrbit.style.setProperty("--model-color", model.brand_color);
    dom.modelAgentOrbit.style.setProperty("--model-scale", String(0.62 + sizeRatio * 0.48));
    dom.modelAgentIcon.replaceChildren(pixelSprite(model.agent_icon, model.display_name, model.brand_color, 48));
    dom.modelCompany.textContent = model.company;
    dom.modelName.textContent = model.display_name;
    dom.modelStats.replaceChildren(
      modelStat("Params", formatParameters(model.parameter_size_b)),
      modelStat("Class", modelClass(model.parameter_size_b)),
      modelStat("Active", model.active_parameter_size_b ? formatParameters(model.active_parameter_size_b) : "Dense"),
    );
    dom.modelFile.textContent = model.filename;
    renderDeliberationSettings(model);
    dom.previousModelButton.disabled = selectedModelIndex === 0;
    dom.nextModelButton.disabled = selectedModelIndex === models.length - 1;
    dom.modelLineup.replaceChildren(
      ...models.map((candidate, index) => {
        const button = document.createElement("button");
        const ratio = Math.sqrt(candidate.parameter_size_b / maxParameters);
        button.type = "button";
        button.className = "model-lineup-agent";
        button.classList.toggle("is-selected", index === selectedModelIndex);
        button.style.setProperty("--lineup-color", candidate.brand_color);
        button.style.setProperty("--lineup-size", `${2.2 + ratio * 2.4}rem`);
        button.setAttribute("aria-label", candidate.display_name);
        button.append(pixelSprite(candidate.agent_icon, candidate.display_name, candidate.brand_color, 32));
        button.addEventListener("click", () => {
          selectModel(index);
          renderModelOptions();
        });
        return button;
      }),
    );
  }

  function changeModel(direction) {
    selectModel(selectedModelIndex + direction);
    renderModelOptions();
  }

  function chooseSelectedModel() {
    const model = models[selectedModelIndex];
    dom.selectedModelLabel.textContent = `${model.company} / ${model.display_name}`;
    document.documentElement.style.setProperty("--agent-color", model.brand_color);
    closeAdvancedSettings();
    onSelected({
      ...model,
      deliberation_settings: { ...selectedModelSettings },
    });
  }

  function handleKeydown(event) {
    if (event.key === "Escape" && isAdvancedSettingsOpen()) {
      event.preventDefault();
      closeAdvancedSettings();
      dom.modelSettingsToggle.focus();
      return;
    }
    if (dom.modelAdvancedSettings.contains(event.target)) {
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      changeModel(-1);
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      changeModel(1);
      return;
    }
    if ((event.key === "Enter" || event.key === " ") && event.target === dom.modelOptions) {
      event.preventDefault();
      chooseSelectedModel();
    }
  }

  function focus() {
    dom.modelOptions.focus();
  }

  function clampModelIndex(index) {
    return Math.min(Math.max(index, 0), models.length - 1);
  }

  function selectModel(index) {
    selectedModelIndex = clampModelIndex(index);
    selectedModelSettings = defaultDeliberationSettings(models[selectedModelIndex]);
  }

  function toggleAdvancedSettings(event) {
    event.stopPropagation();
    if (isAdvancedSettingsOpen()) {
      closeAdvancedSettings();
      return;
    }
    openAdvancedSettings();
  }

  function openAdvancedSettings() {
    dom.modelAdvancedSettings.hidden = false;
    dom.modelSettingsToggle.classList.add("is-open");
    dom.modelSettingsToggle.setAttribute("aria-expanded", "true");
  }

  function closeAdvancedSettings() {
    dom.modelAdvancedSettings.hidden = true;
    dom.modelSettingsToggle.classList.remove("is-open");
    dom.modelSettingsToggle.setAttribute("aria-expanded", "false");
  }

  function isAdvancedSettingsOpen() {
    return !dom.modelAdvancedSettings.hidden;
  }

  function closeAdvancedSettingsOnOutsideClick(event) {
    if (!isAdvancedSettingsOpen()) {
      return;
    }
    if (dom.modelAdvancedSettings.contains(event.target) || dom.modelSettingsToggle.contains(event.target)) {
      return;
    }
    closeAdvancedSettings();
  }

  function renderDeliberationSettings(model) {
    const thinkingSupported = model.thinking_supported !== false;
    const thinkingEnabled = thinkingSupported && selectedModelSettings.enable_thinking;
    dom.modelThinkingToggle.disabled = !thinkingSupported;
    dom.modelThinkingToggle.classList.toggle("is-on", thinkingEnabled);
    dom.modelThinkingToggle.setAttribute("aria-pressed", String(thinkingEnabled));
    dom.modelThinkingToggle.textContent = thinkingSupported ? (thinkingEnabled ? "On" : "Off") : "nope";
    dom.modelTemperatureValue.value = formatTemperature(selectedModelSettings.temperature);
    dom.modelTemperatureValue.textContent = formatTemperature(selectedModelSettings.temperature);
    dom.modelTemperatureDown.disabled = selectedModelSettings.temperature <= minTemperature;
    dom.modelTemperatureUp.disabled = selectedModelSettings.temperature >= maxTemperature;
  }

  function toggleThinking() {
    const model = models[selectedModelIndex];
    if (model.thinking_supported === false) {
      return;
    }
    selectedModelSettings = {
      ...selectedModelSettings,
      enable_thinking: !selectedModelSettings.enable_thinking,
    };
    renderDeliberationSettings(model);
  }

  function adjustTemperature(delta) {
    selectedModelSettings = {
      ...selectedModelSettings,
      temperature: clampTemperature(roundTemperature(selectedModelSettings.temperature + delta)),
    };
    renderDeliberationSettings(models[selectedModelIndex]);
  }

  function modelStat(label, value) {
    const stat = document.createElement("span");
    stat.className = "model-stat";
    stat.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>`;
    return stat;
  }

  return {
    change: changeModel,
    choose: chooseSelectedModel,
    focus,
    handleKeydown,
    render: renderModelOptions,
  };
}

const temperatureStep = 0.05;
const minTemperature = 0;
const maxTemperature = 1;

function formatParameters(value) {
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}B`;
}

function defaultDeliberationSettings(model) {
  if (!model) {
    return { enable_thinking: true, temperature: 1 };
  }
  const thinkingSupported = model.thinking_supported !== false;
  return {
    enable_thinking: thinkingSupported && model.thinking_enabled !== false,
    temperature: clampTemperature(Number(model.thinking_temperature ?? 1)),
  };
}

function clampTemperature(value) {
  if (!Number.isFinite(value)) {
    return maxTemperature;
  }
  return Math.min(Math.max(value, minTemperature), maxTemperature);
}

function formatTemperature(value) {
  return value.toFixed(2);
}

function roundTemperature(value) {
  return Math.round(value / temperatureStep) * temperatureStep;
}

function modelClass(parameterSizeB) {
  if (parameterSizeB >= 10) {
    return "Heavy";
  }
  if (parameterSizeB >= 4) {
    return "Medium";
  }
  if (parameterSizeB >= 2) {
    return "Light";
  }
  return "Feather";
}
