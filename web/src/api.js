export const API_URL = "http://127.0.0.1:8000";

export const HEADER_BYTES = 8;
export const AES_OVERHEAD = 44;

export function capacityBytes(width, height) {
  const payloadBytes = Math.floor((width * height * 3) / 8);
  return Math.max(0, payloadBytes - HEADER_BYTES - AES_OVERHEAD);
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

export async function encodeImage({ carrier, message, passphrase, messageFile }) {
  const form = new FormData();
  form.append("carrier", carrier);
  form.append("passphrase", passphrase);
  if (messageFile) {
    form.append("message_file", messageFile);
  } else {
    form.append("message", message);
  }

  const res = await fetch(`${API_URL}/api/encode`, { method: "POST", body: form });
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
  };
}

export async function decodeImage({ carrier, passphrase }) {
  const form = new FormData();
  form.append("carrier", carrier);
  form.append("passphrase", passphrase);

  const res = await fetch(`${API_URL}/api/decode`, { method: "POST", body: form });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorDetail(res, body));
  return body.message;
}
