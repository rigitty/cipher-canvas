export const API_URL = "http://127.0.0.1:8000";

export const HEADER_SLOTS = 72;
export const AES_OVERHEAD = 44;

export const isTauri = () => "__TAURI_INTERNALS__" in window;

export function capacityBytes(width, height, filenameLength = 0, bitDepth = 1) {
  const b = Math.max(1, Math.min(4, Number(bitDepth) || 1));
  const totalSlots = width * height * 3;
  const availableSlots = Math.max(0, totalSlots - HEADER_SLOTS);
  const payloadBytes = Math.floor((availableSlots * b) / 8);
  const envelope = filenameLength + 1;
  return Math.max(0, payloadBytes - AES_OVERHEAD - envelope);
}

export function capacityRobustBytes(width, height) {
  let w = width;
  let h = height;
  if (Math.max(w, h) > 1280) {
    const scale = 1280 / Math.max(w, h);
    w = Math.max(8, Math.floor(Math.floor(w * scale) / 8) * 8);
    h = Math.max(8, Math.floor(Math.floor(h * scale) / 8) * 8);
  } else {
    w = Math.floor(w / 8) * 8;
    h = Math.floor(h / 8) * 8;
  }
  const totalBlocks = Math.floor(w / 8) * Math.floor(h / 8);
  const avail = totalBlocks - 112;
  if (avail <= 0) return 0;
  const maxEccBytes = Math.floor(avail / 8);

  let low = 0;
  let high = maxEccBytes;
  let ans = 0;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const rawLen = mid + 52;
    const chunks = rawLen > 0 ? Math.ceil(rawLen / 223) : 1;
    const eccLen = rawLen + chunks * 32;
    if (eccLen * 8 <= avail) {
      ans = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return ans;
}

export async function healthCheck() {
  const res = await fetch(`${API_URL}/api/health`, { signal: AbortSignal.timeout(3000) });
  if (!res.ok) throw new Error(`engine health check failed (${res.status})`);
  return res.json();
}

function errorDetail(res, body) {
  const detail = body && body.detail;
  if (typeof detail === "string") return detail;
  return `request failed (${res.status})`;
}

async function postForm(url, form) {
  let res;
  try {
    res = await fetch(url, { method: "POST", body: form });
  } catch {
    throw new Error(
      "cannot reach the engine server — make sure the backend is running"
    );
  }
  return res;
}

export async function encodeImage({ carrier, message, passphrase, messageFile, bitDepth = 1, mode = "stealth" }) {
  const form = new FormData();
  form.append("carrier", carrier);
  form.append("passphrase", passphrase);
  form.append("bit_depth", String(bitDepth));
  form.append("mode", mode);
  if (messageFile) {
    form.append("message_file", messageFile);
  } else {
    form.append("message", message);
  }

  const res = await postForm(`${API_URL}/api/encode`, form);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(errorDetail(res, body));
  }
  const blob = await res.blob();
  return {
    blob,
    url: URL.createObjectURL(blob),
    capacity: Number(res.headers.get("X-Capacity-Bytes")),
    bits: Number(res.headers.get("X-Bits-Written")),
    bitDepth: res.headers.get("X-Bit-Depth") || bitDepth,
    mode: res.headers.get("X-Mode") || mode,
  };
}

export async function decodeImage({ carrier, passphrase }) {
  const form = new FormData();
  form.append("carrier", carrier);
  form.append("passphrase", passphrase);

  const res = await postForm(`${API_URL}/api/decode`, form);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(errorDetail(res, body));
  }
  const blob = await res.blob();
  const rawName = res.headers.get("X-Filename");
  const filename = rawName ? decodeURIComponent(rawName) : "extracted.bin";
  let text = null;
  const isText = blob.type.startsWith("text/") || /\.(txt|md|log|json|csv|py|js|ts|html?)$/i.test(filename);
  if (isText) {
    text = await blob.text();
  }
  return {
    blob,
    url: URL.createObjectURL(blob),
    filename,
    type: blob.type,
    size: blob.size,
    text,
  };
}

export async function inspectImage(file) {
  const form = new FormData();
  form.append("image", file);

  const res = await postForm(`${API_URL}/api/inspect`, form);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(errorDetail(res, body));
  }
  return res.json();
}

export async function readNativeFile(filePath) {
  const { invoke } = await import("@tauri-apps/api/core");
  const bytes = await invoke("read_file_binary", { path: filePath });
  const uint8 = new Uint8Array(bytes);
  const baseName = filePath.split(/[/\\]/).pop() || "image.png";
  const ext = baseName.split(".").pop().toLowerCase();
  const mimeMap = {
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    webp: "image/webp",
    bmp: "image/bmp",
    gif: "image/gif",
  };
  const mimeType = mimeMap[ext] || "image/png";
  return new File([uint8], baseName, { type: mimeType });
}

export async function saveFileNative(fileName, blob, filterName, filterExtensions) {
  const { invoke } = await import("@tauri-apps/api/core");
  const bytes = new Uint8Array(await blob.arrayBuffer());
  return invoke("save_file", {
    fileName,
    data: Array.from(bytes),
    filterName,
    filterExtensions,
  });
}
