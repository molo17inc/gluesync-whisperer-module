declare global {
  interface Window {
    __FRONTEND_BASE_PATH__?: string;
  }
}

const normalizePath = (path?: string | null): string => {
  if (!path) {
    return '';
  }
  const trimmed = path.trim();
  if (!trimmed) {
    return '';
  }
  const withLeading = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  const normalized =
    withLeading.length > 1 && withLeading.endsWith('/') ? withLeading.slice(0, -1) : withLeading;
  return normalized;
};

export const detectBasePath = (): string => {
  if (typeof window !== 'undefined') {
    const runtimeValue = window.__FRONTEND_BASE_PATH__;
    if (runtimeValue) {
      return normalizePath(runtimeValue);
    }
  }

  const envBasePath = import.meta?.env?.VITE_APP_BASE_PATH;
  if (envBasePath) {
    return normalizePath(envBasePath);
  }

  return '';
};

export const getRouterBaseName = (): string | undefined => {
  const basePath = detectBasePath();
  if (!basePath || basePath === '/') {
    return undefined;
  }
  return basePath;
};
