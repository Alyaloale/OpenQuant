# OpenQuant Windows 快捷脚本
# 用法: .\scripts\run.ps1 scan | run | status | report | test

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("setup", "scan", "run", "status", "report", "test")]
    [string]$Command,
    [string]$Symbols = "",
    [int]$Interval = 30,
    [string]$Period = "day"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot

switch ($Command) {
    "setup" {
        pip install -r requirements.txt
        New-Item -ItemType Directory -Force -Path data/db, logs, notebooks | Out-Null
        if (!(Test-Path config/.env)) {
            Copy-Item config/.env.example config/.env
            Write-Host "已复制 config/.env.example -> config/.env"
        }
        Write-Host "请编辑 config/.env 配置 API 密钥"
    }
    "scan" {
        if ($Symbols) { python -m src.main scan --symbols $Symbols }
        else { python -m src.main scan }
    }
    "run" {
        python -m src.main run --interval $Interval
    }
    "status" {
        python -m src.main status
    }
    "report" {
        python -m src.main report --period $Period
    }
    "test" {
        python -m pytest tests/ -v
    }
}
