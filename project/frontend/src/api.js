export const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
export async function api(path, options = {}) {
  const { ai, ...requestOptions } = options;
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
  if (ai?.enabled) {
    headers['X-User-API-Key'] = ai.apiKey;
    headers['X-User-Agent-ID'] = ai.agentId;
    headers['X-User-Config-ID'] = ai.configId;
    headers['X-User-AI-Consent'] = ai.consent ? 'yes' : 'no';
  }
  const response = await fetch(`${BASE}/api${path}`, { ...requestOptions, headers: { ...headers, ...requestOptions.headers } });
  if (!response.ok) {
    let detail = `요청을 완료하지 못했습니다 (${response.status})`;
    try { const data = await response.json(); detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data); } catch {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}
export const fileURL = (url) => url?.startsWith('/') ? BASE + url : url;
