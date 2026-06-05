# 🏃 Watch my Escape! — Revised Project Blueprint

## 1. Project Overview & Architecture
'Watch my Escape!' is an interactive 2D grid-based escape room simulation. The architecture uses a decoupled pattern via **`gradio.Server`**. A lightweight, custom HTML/JS frontend handles rendering and animations, served directly by the backend. The Python backend utilizes Gradio's API engine to manage queuing for a local `llama.cpp` instance running `gemma-4-e4b`. The LLM must manually navigate the map using cardinal directions to find clues, items, and the exit.

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend/UI** | Custom HTML5, CSS3, Vanilla JS | Renders the 2D grid, animations, and the log. Maps text-based emotion strings to visual emojis. Communicates via the `@gradio/client` JS library. |
| **Font Asset** | Google Noto Emoji Font | Hardcoded into the CSS to guarantee identical, crisp emoji rendering across all OS platforms. |
| **Backend/API** | `gradio.Server` | Extends FastAPI. Serves the HTML frontend on `@app.get("/")` and manages LLM inference queuing via `@app.api()` endpoints. |
| **LLM Backend** | `llama.cpp` (Python) | Runs `gemma-4-e4b` locally. Manages inference, context tracking, and native tool calling. |
| **Game Engine** | Python (Custom) | Validates grid coordinates, tracks character collision, manages item inventories, and stores maps. |

---

## 2. Agent Architecture & Spatial Awareness

Because the agent must manually navigate tile-by-tile, the **State-Injected, Lean-History Architecture** requires strict coordination tracking.

### A. Turn-Based Spatial State Injection
At the end of every turn, the Python engine compiles the current layout relative to the agent's absolute position. Instead of seeing the whole room globally, the agent is provided its current coordinates and its immediate local neighborhood to help it make micro-navigation choices.

### B. The "Piggyback" Emotion System
Every tool schema contains a mandatory `emotion` string parameter. As the agent navigates, the frontend JS receives this string and maps it to a visual asset to update the agent's face smoothly in real time. 
* **Allowed Strings:** `"neutral"`, `"pondering"`, `"realization"`, `"frustrated"`, `"escaped"`.

### C. The "Sliding Window" Context (Stripping Monologues)
Manual navigation means the agent takes multiple steps just to cross a room. To prevent massive context bloat:
* The Python backend **wipes the `<|think|>` tags from all past steps**, keeping only the single most recent thought block.
* The permanent chat history retains only explicit tool calls (`move_north`, `examine`) and tool results (`"Wall to the north"`). Long-term clues remain intact, but redundant movement thoughts are discarded.

### D. Stateless Error Handling
If the LLM attempts to walk into a wall (`🟫`), the engine intercepts the call, returns a localized failure, and appends a `[SYSTEM ERROR]` to the current prompt to force a correction. This failed step is never committed to the permanent log.

---

## 3. The Prompt Payload Structure (Manual Navigation Example)

This example shows Turn 4, where the agent is stepping away from an inspected object toward the door.

<|im_start|>system
You are the main character trapped in a 2D grid room. Your objective is to reach the 🚪 Door and escape.
You must navigate tile-by-tile using cardinal movement tools. You cannot pass through walls (🟫).
You must include an "emotion" parameter (string) in every single tool call to represent your current state. Allowed values: "neutral", "pondering", "realization", "frustrated", "escaped".
<|im_end|>

<|im_start|>assistant
{"name": "examine", "arguments": {"target_object": "Bed", "emotion": "pondering"}}
<|im_end|>

<|im_start|>tool
Result: You look under the dusty 🛏️ Bed. You found a 'Gold Key'.
<|im_end|>

<|im_start|>assistant
{"name": "move_north", "arguments": {"emotion": "realization"}}
<|im_end|>

<|im_start|>tool
Result: Successfully moved North.
<|im_end|>

<|im_start|>assistant
<|think|>I have the Gold Key now. The door is to the North-West. I need to move West to line up with it.<|think|>
{"name": "move_west", "arguments": {"emotion": "neutral"}}
<|im_end|>

<|im_start|>tool
Result: Successfully moved West.
<|im_end|>

<|im_start|>user
=== LATEST STATE ===
Current Coordinates: (X: 2, Y: 4)
Inventory: [Gold Key]
Immediate Surroundings:
- North: ⬛ Floor
- South: ⬛ Floor
- East: ⬛ Floor
- West: 🚪 Door
====================
Action Required: Reason your next move and execute a tool call.
<|im_end|>

---

## 4. Core Tool Schema (Revised)

The LLM will choose from the following strict tool list on every step:

1. **`move_north(emotion)`** / **`move_south(emotion)`** / **`move_east(emotion)`** / **`move_west(emotion)`**: Moves the agent 1 tile in the specified direction if the target tile is passable (`⬛`).
2. **`examine(target_object, emotion)`**: Inspects an adjacent object or tile closely to reveal items or read clues.
3. **`interact_with_object(object_name, emotion)`**: Triggers physics or a mechanic on an adjacent object (e.g., unlocking a door).
4. **`talk_to_character(character_name, message, emotion)`**: Initiates dialogue with an adjacent NPC.

---

## 5. Backend Implementation (`gradio.Server`)

The backend script structure handles both serving the frontend and exposing the LLM logic to Gradio's queuing engine:

```python
import os
from gradio import Server
from fastapi.responses import HTMLResponse

app = Server()

@app.api(name="agent_turn")
def execute_agent_turn(current_state_data):
    # 1. Append state data to prompt
    # 2. Call gemma-4-e4b via llama.cpp
    # 3. Parse tool call (e.g., move_north)
    # 4. Update Game Engine Grid
    # 5. Return new state and emotion string to frontend
    pass

@app.api(name="generate_emoji")
def generate_custom_emoji(object_name, description):
    # Calls smaller e2b model for Room Builder UI
    pass

@app.get("/", response_class=HTMLResponse)
async def homepage():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

app.launch()