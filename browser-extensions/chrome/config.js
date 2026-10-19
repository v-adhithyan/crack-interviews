export const ORIGINS = ['https://www.hackerleap.com', 'https://hackerleap.com', 'http://localhost:8000', 'http://127.0.0.1:8000'];
export const DEFAULT_ORIGIN = ORIGINS[0];
export const BRIDGE = '/app/extension/';
export function allowedOrigin(origin) {
  if (!ORIGINS.includes(origin)) throw new Error('Choose a supported HackerLeap environment.');
  return origin;
}
export function permissionPattern(origin) {
  const url = new URL(allowedOrigin(origin));
  // Chrome host match patterns do not specify ports. Requests still enforce the exact origin.
  return `${url.protocol}//${url.hostname}/*`;
}
