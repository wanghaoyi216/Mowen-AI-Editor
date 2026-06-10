import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

// 移除启动闪屏（首屏渲染后淡出）
requestAnimationFrame(() => {
  const splash = document.getElementById("app-splash");
  if (splash) {
    splash.style.opacity = "0";
    setTimeout(() => splash.remove(), 450);
  }
});
