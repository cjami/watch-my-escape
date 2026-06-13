import { presets } from "./constants.js";

export function createPresetPicker({ beginPresetDrag, context }) {
  function render() {
    context.dom.entityPresets.replaceChildren(
      ...presets.map((preset) => {
        const button = document.createElement("button");
        const icon = document.createElement("span");
        const name = document.createElement("span");

        button.type = "button";
        button.className = "preset-button";
        icon.className = "preset-icon";
        icon.append(context.pixelSprite(preset.icon, preset.name, preset.color ?? null));
        name.className = "preset-name";
        name.textContent = preset.name;
        button.append(icon, name);
        button.title = "Click to select, or drag onto the map to place once.";
        button.classList.toggle("is-selected", preset === context.selectedPreset);
        button.addEventListener("pointerdown", (event) => beginPresetDrag(event, button, preset));
        button.addEventListener("click", () => {
          if (context.suppressNextPresetClick) {
            context.suppressNextPresetClick = false;
            return;
          }
          context.selectedPreset = preset;
          context.setEditorTool("place");
          render();
          context.setStatus(`${preset.name} preset selected.`);
        });
        return button;
      }),
    );
  }

  return { render };
}
