export const mapSize = 16;
export const historyLimit = 50;
export const editorValidationDelayMs = 600;

export const actionOptions = ["examine", "take", "open", "close", "push", "pull", "talk_to", "operate", "use_item"];
export const actionLabels = {
  examine: "examine",
  take: "take",
  open: "open",
  close: "close",
  push: "push",
  pull: "pull",
  talk_to: "talk to",
  operate: "operate",
  use_item: "use item",
};

export const effectOptions = [
  "message",
  "add_inventory",
  "remove_inventory",
  "set_entity_state",
  "set_entity_passable",
  "set_entity_active",
  "escape_map",
];
export const effectLabels = {
  message: "Message",
  add_inventory: "Give",
  remove_inventory: "Take",
  set_entity_state: "State",
  set_entity_passable: "Passable",
  set_entity_active: "Active",
  escape_map: "Escape",
};

export const booleanLabels = {
  true: "Yes",
  false: "No",
};

export const maxVisibleIconOptions = 10;
export const defaultIconColor = "#f8ffe8";
export const iconColorOptions = [
  { name: "White", color: "" },
  { name: "Red", color: "#ff6b6b" },
  { name: "Green", color: "#71f7b1" },
  { name: "Blue", color: "#2563eb" },
  { name: "Violet", color: "#a855f7" },
  { name: "Yellow", color: "#ffd447" },
  { name: "Brown", color: "#8b5a2b" },
  { name: "Stone", color: "#8f9aa3" },
];
export const suggestedIconValues = [
  "\u{1F9F1}",
  "\u{1F6AA}",
  "\u{1F511}",
  "\u{1F4DD}",
  "\u{1F9CD}",
  "\u{1F39A}\uFE0F",
  "\u{1F4E6}",
  "\u{1F4A1}",
  "\u{1FA9F}",
  "\u{1F9F0}",
  "\u{1F512}",
  "\u{1FA9C}",
  "\u{1F9EA}",
  "\u{1F4DA}",
  "\u{1F3C1}",
  "\u{1F310}",
  "\u{1F56F}\uFE0F",
  "\u{1F573}\uFE0F",
  "\u{1F5FF}",
  "\u{1FA9E}",
  "\u{1F9E9}",
  "\u{1F50E}",
  "\u{1F9ED}",
  "\u{1F9F2}",
  "\u2699\uFE0F",
  "\u23F3",
  "\u{1F9FF}",
  "\u{1F48E}",
  "\u{1FA99}",
  "\u{1F9F9}",
  "\u{1FAA3}",
  "\u{1FAA4}",
];

export const presets = [
  {
    type: "wall",
    name: "Wall",
    icon: "\u{1F9F1}",
    description: "A solid wall.",
    passable: false,
    notable: false,
  },
  {
    type: "door",
    name: "Door",
    icon: "\u{1F6AA}",
    description: "A closed door.",
    passable: false,
    state: "closed",
  },
  {
    type: "key",
    name: "Key",
    icon: "\u{1F511}",
    description: "A small key.",
    passable: true,
  },
  {
    type: "note",
    name: "Note",
    icon: "\u{1F4DD}",
    description: "A note with useful writing on it.",
    passable: true,
  },
  {
    type: "character",
    name: "Character",
    icon: "\u{1F9CD}",
    description: "Someone waiting in the room.",
    passable: false,
  },
  {
    type: "switch",
    name: "Switch",
    icon: "\u{1F39A}\uFE0F",
    description: "A switch that can trigger something.",
    passable: true,
  },
  {
    type: "item",
    name: "Item",
    icon: "\u{1F4E6}",
    description: "A useful item.",
    passable: true,
  },
  {
    type: "exit",
    name: "Exit",
    icon: "\u{1F3C1}",
    description: "The way out.",
    passable: true,
    behaviors: [
      {
        trigger: { action: "operate" },
        conditions: [],
        effects: [
          { type: "message", text: "You escape the room." },
          { type: "escape_map" },
        ],
      },
    ],
  },
];
