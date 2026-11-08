# diagram_mcp 安装：Node 依赖、Playwright Chromium、固定版本 PlantUML jar。
# 用法: powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Need($Name, $Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "缺少 $Name。$Hint"
    }
}

Need "node" "请安装 Node.js 20+。"
Need "java" "请安装 JRE 17+。"
Need "npm" "请安装 npm。"

Write-Host "[1/3] 安装 mermaid、playwright、roughjs、jsdom"
npm install --no-audit --no-fund

Write-Host "[2/3] 安装 Playwright Chromium"
npx playwright install chromium

$JarVersion = "1.2026.9"
$JarUrl = "https://github.com/plantuml/plantuml/releases/download/v$JarVersion/plantuml-$JarVersion.jar"
$JarPath = Join-Path $Root "vendor\plantuml.jar"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "vendor") | Out-Null
if (-not (Test-Path $JarPath)) {
    Write-Host "[3/3] 下载 PlantUML $JarVersion"
    Invoke-WebRequest -Uri $JarUrl -OutFile $JarPath
} else {
    Write-Host "[3/3] PlantUML jar 已存在"
}

Write-Host "安装完成。在本目录启动: python -m diagram_mcp"
