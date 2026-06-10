export function createSpriteRenderer() {
  const spriteCache = new Map();

  function pixelSprite(value, label, tint = null, size = 24) {
    const textIcon = toTextEmoji(value);
    const source = spriteSource(textIcon, tint, size);
    if (!source) {
      const fallback = document.createElement("span");
      fallback.className = "pixel-sprite-fallback";
      fallback.textContent = textIcon;
      return fallback;
    }

    const image = new Image();
    image.className = "pixel-sprite";
    image.alt = label;
    image.draggable = false;
    image.src = source;
    return image;
  }

  function spriteSource(icon, tint = null, size = 24) {
    const cacheKey = tint ? `${icon}:${tint}:${size}` : `${icon}:${size}`;
    if (spriteCache.has(cacheKey)) {
      return spriteCache.get(cacheKey);
    }

    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    if (!context) {
      spriteCache.set(cacheKey, null);
      return null;
    }

    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, size, size);
    context.font = `${Math.round(size * 0.8)}px "Noto Emoji Local", "Noto Emoji", "Segoe UI Symbol", sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = "#f8ffe8";
    context.fillText(icon, size / 2, size / 2 + size * 0.04);
    if (tint) {
      context.globalCompositeOperation = "source-in";
      context.fillStyle = tint;
      context.fillRect(0, 0, size, size);
      context.globalCompositeOperation = "source-over";
    }

    const source = canvas.toDataURL("image/png");
    spriteCache.set(cacheKey, source);
    return source;
  }

  function refreshWhenFontsLoad(callbacks) {
    if (!document.fonts) {
      return;
    }

    Promise.all([document.fonts.load('19px "Noto Emoji Local"', "\u{1F9F1}"), document.fonts.ready])
      .then(() => {
        spriteCache.clear();
        callbacks.forEach((callback) => callback());
      })
      .catch(() => undefined);
  }

  return { pixelSprite, refreshWhenFontsLoad };
}

function toTextEmoji(value) {
  return value.replaceAll("\uFE0F", "").replace(/(\p{Emoji_Presentation}|\p{Extended_Pictographic})/gu, "$1\uFE0E");
}
