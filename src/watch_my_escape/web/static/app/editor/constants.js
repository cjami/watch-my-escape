export const mapSize = 15;
export const historyLimit = 50;
export const editorValidationDelayMs = 600;

export const actionOptions = ["examine", "pick_up", "open", "close", "push", "pull", "talk_to", "operate", "use_item"];
export const simpleActionOptions = ["examine", "pick_up", "open", "close", "push", "pull", "operate"];
export const actionLabels = {
  examine: "examine",
  pick_up: "pick up",
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
    behaviors: [
      {
        trigger: { action: "examine" },
        conditions: [{ state: "closed" }],
        effects: [{ type: "message", text: "The handle looks usable." }],
      },
      {
        trigger: { action: "open", actions: ["open", "pull", "operate"] },
        conditions: [{ state: "closed" }],
        effects: [
          { type: "message", text: "The door opens." },
          { type: "set_entity_active", active: false },
        ],
      },
      {
        trigger: { action: "close" },
        conditions: [{ state: "closed" }],
        effects: [{ type: "message", text: "The door is already closed." }],
      },
    ],
  },
  {
    type: "exit",
    name: "Exit Door",
    icon: "\u{1F6AA}",
    color: "#ffd447",
    description: "A yellow exit door is closed.",
    passable: false,
    state: "closed",
    behaviors: [
      {
        trigger: { action: "examine" },
        conditions: [],
        effects: [{ type: "message", text: "An exit sign is above the door." }],
      },
      {
        trigger: { action: "open", actions: ["open", "pull", "operate"] },
        conditions: [{ state: "closed" }],
        effects: [
          { type: "message", text: "The exit door opens. You escape." },
          { type: "set_entity_active", active: false },
          { type: "escape_map" },
        ],
      },
    ],
  },
  {
    type: "key",
    name: "Key",
    icon: "\u{1F511}",
    description: "A small key.",
    passable: true,
    behaviors: [
      {
        trigger: { action: "examine" },
        conditions: [],
        effects: [{ type: "message", text: "It is small enough to carry." }],
      },
      {
        trigger: { action: "pick_up", actions: ["pick_up", "pull"] },
        conditions: [],
        effects: [
          { type: "message", text: "You pick up the key." },
          { type: "add_inventory", entity_id: "{self}" },
          { type: "set_entity_active", active: false },
        ],
      },
    ],
  },
  {
    type: "note",
    name: "Note",
    icon: "\u{1F4DD}",
    description: "A readable note.",
    passable: true,
    behaviors: [
      {
        trigger: { action: "examine", actions: ["examine", "operate"] },
        conditions: [],
        effects: [{ type: "message", text: "The note has writing on it." }],
      },
      {
        trigger: { action: "pick_up", actions: ["pick_up", "pull"] },
        conditions: [],
        effects: [
          { type: "message", text: "You pick up the note." },
          { type: "add_inventory", entity_id: "{self}" },
          { type: "set_entity_active", active: false },
        ],
      },
    ],
  },
  {
    type: "character",
    name: "Character",
    icon: "\u{1F9CD}",
    description: "A person is waiting here.",
    passable: false,
    state: "waiting",
    behaviors: [
      {
        trigger: { action: "examine" },
        conditions: [],
        effects: [{ type: "message", text: "They are alert and watching you." }],
      },
      {
        trigger: { action: "talk_to" },
        conditions: [],
        effects: [{ type: "message", text: "They listen but give no clear answer." }],
      },
      {
        trigger: { action: "pick_up", actions: ["pick_up", "open", "close", "push", "pull", "operate"] },
        conditions: [],
        effects: [{ type: "message", text: "That does not help." }],
      },
    ],
  },
  {
    type: "lever",
    name: "Lever",
    icon: "\u{1F579}\uFE0F",
    description: "A lever points up.",
    passable: true,
    state: "up",
    behaviors: [
      {
        trigger: { action: "examine" },
        conditions: [{ state: "up" }],
        effects: [{ type: "message", text: "The lever can be pulled." }],
      },
      {
        trigger: { action: "examine" },
        conditions: [{ state: "down" }],
        effects: [{ type: "message", text: "The lever is down." }],
      },
      {
        trigger: { action: "pull", actions: ["pull", "operate"] },
        conditions: [{ state: "up" }],
        effects: [
          { type: "message", text: "The lever moves down." },
          { type: "set_entity_state", state: "down" },
        ],
      },
      {
        trigger: { action: "pull", actions: ["pull", "operate"] },
        conditions: [{ state: "down" }],
        effects: [{ type: "message", text: "The lever is already down." }],
      },
    ],
  },
  {
    type: "container",
    name: "Container",
    icon: "\u{1F9F0}",
    description: "A container is {state}.",
    passable: true,
    state: "closed",
    behaviors: [
      {
        trigger: { action: "examine" },
        conditions: [{ state: "closed" }],
        effects: [{ type: "message", text: "The lid can be opened." }],
      },
      {
        trigger: { action: "examine" },
        conditions: [{ state: "open" }],
        effects: [{ type: "message", text: "The container is open." }],
      },
      {
        trigger: { action: "open", actions: ["open", "pull", "operate"] },
        conditions: [{ state: "closed" }],
        effects: [
          { type: "message", text: "The container opens." },
          { type: "set_entity_state", state: "open" },
        ],
      },
      {
        trigger: { action: "close" },
        conditions: [{ state: "open" }],
        effects: [
          { type: "message", text: "The container closes." },
          { type: "set_entity_state", state: "closed" },
        ],
      },
    ],
  },
  {
    type: "item",
    name: "Item",
    icon: "\u{1F4E6}",
    description: "A useful item.",
    passable: true,
    behaviors: [
      {
        trigger: { action: "examine" },
        conditions: [],
        effects: [{ type: "message", text: "It is small enough to carry." }],
      },
      {
        trigger: { action: "pick_up", actions: ["pick_up", "pull"] },
        conditions: [],
        effects: [
          { type: "message", text: "You pick up the item." },
          { type: "add_inventory", entity_id: "{self}" },
          { type: "set_entity_active", active: false },
        ],
      },
    ],
  },
  {
    type: "sign",
    name: "Sign",
    icon: "\u{1FAA7}",
    description: "A readable sign is mounted here.",
    passable: true,
    behaviors: [
      {
        trigger: { action: "examine", actions: ["examine", "operate"] },
        conditions: [],
        effects: [{ type: "message", text: "The sign is readable." }],
      },
    ],
  },
];
