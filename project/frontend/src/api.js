export const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
export async function api(path, options = {}) {
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
  const response = await fetch(`${BASE}/api${path}`, { ...options, headers: { ...headers, ...options.headers } });
  if (!response.ok) {
    let detail = `요청을 완료하지 못했습니다 (${response.status})`;
    try { const data = await response.json(); detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data); } catch {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}
export const fileURL = (url) => url?.startsWith('/') ? BASE + url : url;
