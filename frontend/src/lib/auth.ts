// ---------------------------------------------------------------------------
// 登录 / 注册 / 当前用户
// ---------------------------------------------------------------------------

export type AuthUser = {
  id: number;
  username: string;
  email: string | null;
  display_name: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
};

export type AuthTokenResponse = {
  user: AuthUser;
  token: string;
  expires_at: string;
};

const STORAGE_KEY = "mowen.auth";
const SESSION_KEY = "mowen.auth.session";

type AuthSession = {
  user: AuthUser;
  token: string;
  expires_at: string;
};

export function loadAuthSession(): AuthSession | null {
  // 优先 localStorage（记住我），其次 sessionStorage（仅本次会话）
  const raw =
    window.localStorage.getItem(STORAGE_KEY) ??
    window.sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as AuthSession;
    if (parsed.expires_at && new Date(parsed.expires_at).getTime() < Date.now()) {
      window.localStorage.removeItem(STORAGE_KEY);
      window.sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveAuthSession(
  session: AuthSession,
  options?: { remember?: boolean },
): void {
  const remember = options?.remember !== false;
  const payload = JSON.stringify(session);
  if (remember) {
    window.localStorage.setItem(STORAGE_KEY, payload);
    window.sessionStorage.removeItem(SESSION_KEY);
  } else {
    window.sessionStorage.setItem(SESSION_KEY, payload);
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

export function clearAuthSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
  window.sessionStorage.removeItem(SESSION_KEY);
}

function getApiBase(): string {
  // 同步 src/lib/api.ts 的逻辑
  const envUrl = (import.meta as unknown as { env: Record<string, string | undefined> }).env
    .VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() !== "") return envUrl.trim();
  return "/api/v1";
}

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getApiBase()}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const payload = (await res.json()) as { detail?: string; message?: string };
      detail = payload.detail || payload.message || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const payload = (await res.json()) as { data: T; message?: string };
  return payload.data;
}

export async function loginRequest(username: string, password: string): Promise<AuthTokenResponse> {
  return authFetch<AuthTokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function registerRequest(
  username: string,
  password: string,
  email?: string,
  displayName?: string,
): Promise<AuthTokenResponse> {
  return authFetch<AuthTokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      username,
      password,
      email: email || null,
      display_name: displayName || null,
    }),
  });
}

export async function fetchCurrentUser(token: string): Promise<AuthUser> {
  return authFetch<AuthUser>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}
