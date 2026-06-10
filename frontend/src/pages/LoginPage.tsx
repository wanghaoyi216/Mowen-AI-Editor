import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./LoginPage.css";

type Mode = "login" | "register";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register, user } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 已经登录直接跳到主系统
  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  // 锁定页面滚动，避免底部 .cc-ink-bg 露出造成视觉割裂
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    const prevHeight = document.body.style.height;
    document.body.style.overflow = "hidden";
    document.body.style.height = "100vh";
    return () => {
      document.body.style.overflow = prevOverflow;
      document.body.style.height = prevHeight;
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(username.trim(), password, remember);
      } else {
        await register(username.trim(), password, email.trim() || undefined, displayName.trim() || undefined, remember);
      }
      navigate("/", { replace: true });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "操作失败";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-page-card">
        <div className="login-brand">
          <div className="login-brand-mark">墨</div>
          <h1 className="login-brand-title">墨问 · Novel AI Editor</h1>
          <p className="login-brand-subtitle">让 AI 落墨成卷，为你写百万字江山</p>
        </div>

        <div className="login-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={`login-tab ${mode === "login" ? "is-active" : ""}`}
            onClick={() => { setMode("login"); setError(null); }}
          >
            登 录
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            className={`login-tab ${mode === "register" ? "is-active" : ""}`}
            onClick={() => { setMode("register"); setError(null); }}
          >
            注 册
          </button>
        </div>

        <form className="login-form" onSubmit={handleSubmit} autoComplete="on">
          <label className="login-field">
            <span className="login-field-label">用户名</span>
            <input
              className="login-field-input"
              type="text"
              required
              minLength={3}
              maxLength={64}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="3-64 字符，字母/数字/中文/下划线"
              autoComplete="username"
              disabled={busy}
            />
          </label>

          <label className="login-field">
            <span className="login-field-label">密码</span>
            <input
              className="login-field-input"
              type="password"
              required
              minLength={6}
              maxLength={64}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="6-64 字符"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              disabled={busy}
            />
          </label>

          {mode === "register" && (
            <>
              <label className="login-field">
                <span className="login-field-label">邮箱（可选）</span>
                <input
                  className="login-field-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@mowen.ai"
                  autoComplete="email"
                  disabled={busy}
                />
              </label>
              <label className="login-field">
                <span className="login-field-label">显示名（可选）</span>
                <input
                  className="login-field-input"
                  type="text"
                  maxLength={120}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="默认与用户名一致"
                  disabled={busy}
                />
              </label>
            </>
          )}

          {error && <div className="login-error" role="alert">⚠ {error}</div>}

          {/* 记住我 / 忘记密码（仅登录模式显示） */}
          {mode === "login" && (
            <div className="login-form-extras">
              <label className="login-remember">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  disabled={busy}
                />
                <span className="login-remember-box" aria-hidden="true">
                  {remember && (
                    <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 8 7 12 13 4" />
                    </svg>
                  )}
                </span>
                <span className="login-remember-text">记住我 7 天免登录</span>
              </label>
              <button
                type="button"
                className="login-forgot"
                onClick={() => {
                  setError("忘记密码？请联系管理员或重新注册账号（演示版未开放邮箱找回）。");
                }}
                tabIndex={-1}
              >
                忘记密码？
              </button>
            </div>
          )}

          <button type="submit" className="login-submit" disabled={busy}>
            {busy ? "请稍候…" : mode === "login" ? "登 录" : "注册并登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
