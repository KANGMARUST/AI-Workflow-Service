const rawPrefix = (import.meta.env.VITE_API_PREFIX || '/api').replace(/\/$/, '');
const prefix = rawPrefix.startsWith('/') ? rawPrefix : `/${rawPrefix}`;
const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const token = import.meta.env.VITE_API_TOKEN || '';

export async function requestQuote(path, { download = false, ...options } = {}) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${base}${prefix}${path}`, { ...options, headers });
  if (response.ok && download) return response.blob();
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : Array.isArray(payload.detail)
      ? payload.detail.map((item) => `${item.loc?.slice(1).join('.') || ''}: ${item.msg}`).join(', ')
      : '요청을 처리하지 못했습니다.';
    throw new Error(`${response.status}: ${detail}`);
  }
  return payload;
}
