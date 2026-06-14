export async function downloadJson(filename, payload) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  if (window.showSaveFilePicker) {
    const handle = await fileSaveHandle(filename);
    if (!handle) {
      return false;
    }
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
    return true;
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  return true;
}

async function fileSaveHandle(filename) {
  try {
    return await window.showSaveFilePicker({
      suggestedName: filename,
      types: [
        {
          description: "JSON files",
          accept: { "application/json": [".json"] },
        },
      ],
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      return null;
    }
    throw error;
  }
}
