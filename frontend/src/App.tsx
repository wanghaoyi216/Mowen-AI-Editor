import React from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ProjectProvider } from "./context/ProjectContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { CommandCenter } from "./components/CommandCenter";
import LoginPage from "./pages/LoginPage";
import "./styles.css";
import { EXPORT_MENU_CSS } from "./components/ExportMenu";

// 把 ExportMenu 的样式注入到 <head>。动态插入便于 ExportMenu.tsx 不再
// 依赖全局 CSS 加载顺序；样式内容唯一，不会重复。
if (typeof document !== "undefined" && !document.getElementById("export-menu-styles")) {
  const style = document.createElement("style");
  style.id = "export-menu-styles";
  style.textContent = EXPORT_MENU_CSS;
  document.head.appendChild(style);
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          minHeight: '100vh', gap: 16, background: '#f5f0ff', fontFamily: 'sans-serif',
          color: '#2d1b4a', padding: 32,
        }}>
          <div style={{ fontSize: 48 }}>⚠</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>应用出现异常</div>
          <div style={{ fontSize: 13, color: '#6b3fa0', maxWidth: 480, textAlign: 'center' }}>
            {this.state.error?.message || "未知错误"}
          </div>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '8px 20px', background: '#7c3aed', color: '#fff',
              border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 14,
            }}
          >
            刷新页面
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function RequireAuth({ children }: { children: React.ReactElement }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" />
        <div className="auth-loading-text">唤醒创作引擎中…</div>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

function AppRoutes() {
  const { theme } = useTheme();
  return (
    <div
      className="cc-ink-bg"
      style={{
        // v2 升级：把当前主题的背景图注入为 CSS 变量（与 .cc-ink-bg 的 background-image 配合）
        ["--theme-bg-image" as never]: `url("${theme.imageUrl}") center center / cover no-repeat`,
      }}
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <CommandCenter />
            </RequireAuth>
          }
        />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <ProjectProvider>
            <AppRoutes />
          </ProjectProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
