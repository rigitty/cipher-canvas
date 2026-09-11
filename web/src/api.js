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

export async function encodeImage({ carrier, message, passphrase, messageFile, bitDepth = 1 }) {
  const form = new FormData();
  form.append("carrier", carrier);
  form.append("passphrase", passphrase);
  form.append("bit_depth", String(bitDepth));
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
    bitDepth: Number(res.headers.get("X-Bit-Depth")) || bitDepth,
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
