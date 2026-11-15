export const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
export const LIVE_WS = API.replace(/^http/, "ws") + "/api/live";

export async function apiFetch(path, _session, options = {}) {
  const headers = new Headers(options.headers || {});
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {}
    throw new Error(message);
  }
  return response;
}
