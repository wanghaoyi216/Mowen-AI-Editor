import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearAuthSession,
  fetchCurrentUser,
  loadAuthSession,
  loginRequest,
  registerRequest,
  saveAuthSession,
  type AuthUser,
} from "../lib/auth";

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string, remember?: boolean) => Promise<void>;
  register: (username: string, password: string, email?: string, displayName?: string, remember?: boolean) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const initial = loadAuthSession();
  const [user, setUser] = useState<AuthUser | null>(initial?.user ?? null);
  const [token, setToken] = useState<string | null>(initial?.token ?? null);
  const [loading, setLoading] = useState<boolean>(!!initial);

  // 静默校验 token
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchCurrentUser(token)
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) {
          clearAuthSession();
          setUser(null);
          setToken(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = useCallback(async (username: string, password: string, remember: boolean = true) => {
    const result = await loginRequest(username, password);
    saveAuthSession(result, { remember });
    setUser(result.user);
    setToken(result.token);
  }, []);

  const register = useCallback(
    async (username: string, password: string, email?: string, displayName?: string, remember: boolean = true) => {
      const result = await registerRequest(username, password, email, displayName);
      saveAuthSession(result, { remember });
      setUser(result.user);
      setToken(result.token);
    },
    [],
  );

  const logout = useCallback(() => {
    clearAuthSession();
    setUser(null);
    setToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, loading, login, register, logout }),
    [user, token, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
