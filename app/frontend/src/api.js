export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

export async function request(path, signal, options = {}) {
  let response;
  try {
    response = await fetch(`${BACKEND_URL.replace(/\/$/, '')}${path}`, { ...options, signal });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Cannot reach the backend. Check that the server is running.');
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error('The server returned an invalid response. Please try again.'); }
  if (!response.ok) {
    const detail = data.detail;
    const message = data.message || (typeof detail === 'string' ? detail : detail?.message) || 'Check your input and try again.';
    const error = new Error(message);
    error.errors = (Array.isArray(data.errors) && data.errors.length > 0)
      ? data.errors
      : (Array.isArray(detail) ? detail.map(item => `${item.loc?.slice(1).join('.') || 'Input'}: ${item.msg}`) : detail?.errors || []);
    throw error;
  }
  return data;
}
