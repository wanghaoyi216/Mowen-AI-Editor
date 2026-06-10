# Novel AI Editor: Windows 一键重建 (PowerShell)
# 重建 frontend + backend 镜像并重启所有服务
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

Write-Host "===== Novel AI Editor: 一键重建 =====" -ForegroundColor Cyan

Write-Host "[1/4] 停止 frontend 和 backend..." -ForegroundColor Yellow
docker compose stop frontend backend

Write-Host "[2/4] 重建镜像（无缓存）..." -ForegroundColor Yellow
docker compose build --no-cache frontend backend

Write-Host "[3/4] 启动所有服务..." -ForegroundColor Yellow
docker compose up -d

Write-Host "[4/4] 等待健康检查..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
docker compose ps

Write-Host "===== 重建完成 =====" -ForegroundColor Green
Write-Host "前端: http://localhost:5173"
Write-Host "后端: http://localhost:8000/api/v1/docs"
