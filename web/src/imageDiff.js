function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("failed to load image for comparison"));
    img.src = url;
  });
}

export async function objectUrlFor(file) {
  return URL.createObjectURL(file);
}

export async function buildDiffCanvas(originalUrl, encodedUrl) {
  const [original, encoded] = await Promise.all([
    loadImage(originalUrl),
    loadImage(encodedUrl),
  ]);
  const width = encoded.naturalWidth;
  const height = encoded.naturalHeight;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  ctx.drawImage(encoded, 0, 0);
  const encodedData = ctx.getImageData(0, 0, width, height).data;

  ctx.drawImage(original, 0, 0);
  const originalData = ctx.getImageData(0, 0, width, height).data;

  ctx.drawImage(encoded, 0, 0);
  ctx.fillStyle = "rgba(229, 9, 20, 0.9)";
  let changed = 0;
  for (let i = 0; i < originalData.length; i += 4) {
    if (
      originalData[i] !== encodedData[i] ||
      originalData[i + 1] !== encodedData[i + 1] ||
      originalData[i + 2] !== encodedData[i + 2]
    ) {
      const x = (i / 4) % width;
      const y = Math.floor(i / 4 / width);
      ctx.fillRect(x, y, 1, 1);
      changed += 1;
    }
  }
  return { canvas, changed };
}