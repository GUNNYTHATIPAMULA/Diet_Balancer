/** Resize a photo in the browser to at most `max` px and return a JPEG data URL (~50–150 KB). */
export async function resizeImage(file, max = 512, quality = 0.82) {
  if (!file || !/^image\/(jpeg|png|webp|heic|heif)$/i.test(file.type)) {
    throw new Error("Choose a JPEG, PNG or WebP photo.");
  }
  if (file.size > 15 * 1024 * 1024) throw new Error("That photo is too large (max 15 MB).");
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("That photo could not be read."));
      el.src = url;
    });
    const scale = Math.min(1, max / Math.max(img.width, img.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", quality);
  } finally {
    URL.revokeObjectURL(url);
  }
}
