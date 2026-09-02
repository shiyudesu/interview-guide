const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

export function authenticatedStreamInit(
  init: RequestInit,
  csrfToken: string | null,
): RequestInit {
  const headers = new Headers(init.headers);
  const method = (init.method ?? 'GET').toUpperCase();
  if (csrfToken && !SAFE_METHODS.has(method)) {
    headers.set('X-CSRF-Token', csrfToken);
  }
  return {
    ...init,
    headers,
    credentials: init.credentials ?? 'include',
  };
}
