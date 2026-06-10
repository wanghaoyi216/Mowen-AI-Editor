# 完整截图脚本：使用 Edge headless 拍摄项目关键页面
# 1. 登录页
# 2. 注册页（用临时注入的 JS 切换 tab）
# 3. API 文档
# 4. 6 张主题缩略图（直接复制）
# 5. Neo4j Browser
$ErrorActionPreference = "Stop"
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$outDir = "D:\Study\novel_ai_editer\docs\screenshots"

if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
Get-ChildItem $outDir -Filter "*.png" -ErrorAction SilentlyContinue | Remove-Item -Force

function Capture-Page {
    param(
        [string]$Url,
        [string]$OutFile,
        [int]$WaitMs = 8000,
        [int]$Width = 1920,
        [int]$Height = 1080,
        [string]$ExtraArgs = ""
    )
    $full = Join-Path $outDir $OutFile
    Write-Host "[*] $OutFile <- $Url" -ForegroundColor Cyan
    $argList = @(
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--window-size=$Width,$Height",
        "--screenshot=`"$full`"",
        "--virtual-time-budget=$WaitMs"
    )
    if ($ExtraArgs) { $argList += $ExtraArgs }
    $argList += "`"$Url`""
    $proc = Start-Process -FilePath $edge -ArgumentList $argList -NoNewWindow -PassThru -Wait -RedirectStandardError "$env:TEMP\edge_err.log"
    Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    if (Test-Path $full) {
        $len = (Get-Item $full).Length
        Write-Host "    OK ($len bytes)" -ForegroundColor Green
    } else {
        Write-Host "    FAILED" -ForegroundColor Red
    }
}

# 1. 登录页
Capture-Page -Url "http://localhost:8080/login" -OutFile "01-login.png" -WaitMs 8000

# 2. 注册 tab（用 hash 触发 React state 不行；改用 about:blank + window.location + setTimeout 跳转登录并切 tab，
#    这里用 file:// + 简单 HTML 注入；最简单做法是再拍一张登录页 + 用户手动截注册 tab 即可）
#    拍一张"主题切换面板展开"通过 URL 参数 hack - LoginPage 暂不支持，我们改拍主页项目列表（需要登录态）

# 3. API 文档
Capture-Page -Url "http://localhost:8080/api/v1/docs" -OutFile "03-api-docs.png" -WaitMs 12000

# 4. Neo4j Browser
Capture-Page -Url "http://localhost:7474" -OutFile "04-neo4j.png" -WaitMs 10000

# 5. 6 张主题缩略图（直接复制）
$themeDir = "D:\Study\novel_ai_editer\frontend\public\themes"
$sourceFiles = @(
    "theme-mowen-default.png",
    "theme-mowen-login.png",
    "theme-cyan-jade.png",
    "theme-moonlit-bamboo.png",
    "theme-dreamy-ink.png",
    "theme-vermilion-maple.png"
)
$i = 0
foreach ($f in $sourceFiles) {
    $src = Join-Path $themeDir $f
    $name = $f -replace "^theme-", "" -replace "\.png$", ""
    $dst = Join-Path $outDir ("theme-" + (++$i).ToString("00") + "-" + $name + ".png")
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "[*] Theme copy: $dst" -ForegroundColor DarkCyan
    }
}

Write-Host ""
Write-Host "===== Done =====" -ForegroundColor Green
Get-ChildItem $outDir | ForEach-Object { Write-Output ("  " + $_.Name + " - " + $_.Length + " bytes") }
