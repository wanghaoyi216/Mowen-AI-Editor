# ─────────────────────────────────────────────────────────────────────────────
# 阶段 1：构建 Vite 生产资源
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# 先只拷贝依赖定义，利用 Docker layer 缓存加速
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund --loglevel=error

# 拷贝源码并构建（Vite + TS）
COPY . .
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# 阶段 2：Nginx 托管静态资源，并把 /api 反向代理到后端
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# 把 build 产物放进 Nginx 根目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 用自定义 nginx.conf：启用 gzip、SPA fallback、/api 反代
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
