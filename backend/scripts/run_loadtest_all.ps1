# 分阶段 k6 压测（Windows）
param(
    [string]$BaseUrl = "http://127.0.0.1:8000/api/v2"
)
$ErrorActionPreference = "Stop"
$Lt = Join-Path $PSScriptRoot "loadtest"

function Run-Phase($Name, $Script, [string[]]$ExtraEnv = @()) {
    Write-Host "==== k6 $Name ===="
    $env:BASE_URL = $BaseUrl
    foreach ($e in $ExtraEnv) {
        if ($e -match "^([^=]+)=(.*)$") {
            Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
        }
    }
    k6 run $Script
    if ($LASTEXITCODE -ne 0) { throw "k6 $Name 失败" }
}

Run-Phase "phase1_auth" (Join-Path $Lt "phase1_auth.js")
if (-not $env:TOKEN) {
    Write-Host "提示：设置 `$env:TOKEN、`$env:TOKEN_A、`$env:TOKEN_B、`$env:BOOK_ID 后可跑 phase2-5"
    exit 0
}
Run-Phase "phase2_pair" (Join-Path $Lt "phase2_pair.js")
Run-Phase "phase3_reading" (Join-Path $Lt "phase3_reading.js")
Run-Phase "phase4_store" (Join-Path $Lt "phase4_store.js")
Run-Phase "phase5_settings" (Join-Path $Lt "phase5_settings.js")
Write-Host "全部 k6 阶段完成"
