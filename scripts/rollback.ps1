# Novel AI Editor: Windows 一键回滚 (PowerShell)
# 用 git checkout HEAD~1 回滚到上一版本并重建
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

Write-Host "===== Novel AI Editor: 回滚到上一版本 =====" -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
  Write-Error "未检测到 .git 目录"
  exit 1
}

$current = git rev-parse --short HEAD
Write-Host "当前 HEAD: $current"
git checkout HEAD~1
$newHead = git rev-parse --short HEAD
Write-Host "回滚到: $newHead"

docker compose build --no-cache frontend backend
docker compose up -d
Write-Host "===== 回滚完成 =====" -ForegroundColor Green
