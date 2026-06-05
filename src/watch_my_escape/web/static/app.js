import { Client } from "https://cdn.jsdelivr.net/npm/@gradio/client/dist/index.min.js";

const form = document.querySelector("#escape-form");
const actionInput = document.querySelector("#action");
const responseOutput = document.querySelector("#room-response");

const client = await Client.connect(window.location.origin);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  responseOutput.textContent = "The room is thinking...";

  try {
    const result = await client.predict("/attempt_escape", {
      action: actionInput.value,
    });
    responseOutput.textContent = result.data[0];
  } catch (error) {
    responseOutput.textContent = `The room resists the attempt: ${error.message}`;
  }
});
