import { escapeHtml } from "./shared/html.js";

export function createModelSelector({ dom, models, onSelected, pixelSprite }) {
  let selectedModelIndex = 0;

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
          selectedModelIndex = index;
          renderModelOptions();
        });
        return button;
      }),
    );
  }

  function changeModel(direction) {
    selectedModelIndex = clampModelIndex(selectedModelIndex + direction);
    renderModelOptions();
  }

  function chooseSelectedModel() {
    const model = models[selectedModelIndex];
    dom.selectedModelLabel.textContent = `${model.company} / ${model.display_name}`;
    document.documentElement.style.setProperty("--agent-color", model.brand_color);
    onSelected(model);
  }

  function handleKeydown(event) {
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

function formatParameters(value) {
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}B`;
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
