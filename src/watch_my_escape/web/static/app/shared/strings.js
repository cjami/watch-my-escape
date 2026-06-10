import { escapeAttribute, escapeHtml } from "./html.js";

export function slugify(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function parsePosition(position) {
  const match = /^\((\d+), (\d+)\)$/.exec(position || "");
  if (!match) {
    return null;
  }
  return { x: Number(match[1]), y: Number(match[2]) };
}

export function optionLabel(labels, value) {
  return labels[value] ?? value;
}

export function selectHtml(options, selected, attributes, labels = {}) {
  return `<select ${attributes}>${options
    .map(
      (option) =>
        `<option value="${escapeAttribute(option)}" ${option === selected ? "selected" : ""}>${escapeHtml(optionLabel(labels, option))}</option>`,
    )
    .join("")}</select>`;
}

export function formatValidationError(error) {
  const detail = error.detail;
  if (!Array.isArray(detail) || !detail.length) {
    return "unknown validation error.";
  }
  const first = detail[0];
  return `${(first.loc ?? []).join(".")}: ${first.msg}`;
}
