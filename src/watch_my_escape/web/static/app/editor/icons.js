import emojibaseCompactData from "emojibase-data/en/compact.json";

import { maxVisibleIconOptions, suggestedIconValues } from "./constants.js";

const emojiIconOptions = emojibaseCompactData
  .filter((emoji) => emoji.unicode && emoji.label)
  .map((emoji) => ({
    icon: emoji.unicode,
    name: emoji.label,
    terms: Array.isArray(emoji.tags) ? emoji.tags : [],
    searchText: normalizeIconSearch([emoji.label, emoji.unicode, ...(Array.isArray(emoji.tags) ? emoji.tags : [])].join(" ")),
    searchTokens: normalizedIconTokens([emoji.label, ...(Array.isArray(emoji.tags) ? emoji.tags : [])].join(" ")),
  }));
const emojiIconOptionsByIcon = new Map();
for (const option of emojiIconOptions) {
  emojiIconOptionsByIcon.set(option.icon, option);
  emojiIconOptionsByIcon.set(normalizeEmojiIcon(option.icon), option);
}
const suggestedIconOptions = suggestedIconValues.map((icon) => iconOptionForIcon(icon)).filter(Boolean);

export function createIconCatalog({ context }) {
  function visibleIconOptions(selectedIcon) {
    const query = normalizeIconSearch(context.iconSearchQuery);
    const queryTerms = query.split(/\s+/).filter(Boolean);
    const matchingOptions = query ? rankedIconOptions(queryTerms) : suggestedIconOptions;
    const visibleOptions = matchingOptions.slice(0, maxVisibleIconOptions);
    if (!selectedIcon || visibleOptions.some((option) => normalizeEmojiIcon(option.icon) === normalizeEmojiIcon(selectedIcon))) {
      return visibleOptions;
    }

    const selectedOption = iconOptionForIcon(selectedIcon);
    return [
      selectedOption,
      ...matchingOptions.filter((option) => normalizeEmojiIcon(option.icon) !== normalizeEmojiIcon(selectedIcon)),
    ].slice(0, maxVisibleIconOptions);
  }

  return { visibleIconOptions };
}

function rankedIconOptions(queryTerms) {
  return emojiIconOptions
    .map((option, index) => ({
      option,
      rank: iconSearchRank(option, queryTerms),
      index,
    }))
    .filter((result) => result.rank > 0)
    .sort((left, right) => right.rank - left.rank || left.index - right.index)
    .map((result) => result.option);
}

function iconSearchRank(option, queryTerms) {
  return queryTerms.reduce((total, term) => {
    const termRank = iconSearchTermRank(option, term);
    return termRank > 0 && total >= 0 ? total + termRank : -1;
  }, 0);
}

function iconSearchTermRank(option, term) {
  if (normalizeEmojiIcon(option.icon) === normalizeEmojiIcon(term)) {
    return 100;
  }
  if (option.searchTokens.some((token) => token === term)) {
    return 80;
  }
  if (option.searchTokens.some((token) => token.startsWith(term))) {
    return 50;
  }
  return option.searchText.includes(term) ? 10 : 0;
}

function iconOptionForIcon(icon) {
  return (
    emojiIconOptionsByIcon.get(icon) ??
    emojiIconOptionsByIcon.get(normalizeEmojiIcon(icon)) ?? {
      icon,
      name: "Current icon",
      terms: [],
    }
  );
}

function normalizeIconSearch(value) {
  return String(value).trim().toLowerCase();
}

function normalizedIconTokens(value) {
  return normalizeIconSearch(value).split(/[^a-z0-9]+/).filter(Boolean);
}

function normalizeEmojiIcon(value) {
  return String(value).replaceAll("\uFE0E", "").replaceAll("\uFE0F", "");
}
