export function createEditorTabs({ context }) {
  function set(tab) {
    context.selectedEditorTab = tab;
    render();
  }

  function render() {
    context.dom.editorTabButtons.forEach((button) => {
      const selected = button.dataset.editorTab === context.selectedEditorTab;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-selected", String(selected));
    });
    context.dom.entityTabPanel.hidden = context.selectedEditorTab !== "entity";
    context.dom.behaviorsTabPanel.hidden = context.selectedEditorTab !== "behaviors";
  }

  return { render, set };
}
