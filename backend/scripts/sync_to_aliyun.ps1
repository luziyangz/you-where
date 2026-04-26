param(
  [string]$Server = "47.99.240.126",
  [string]$User = "root",
  [int]$Port = 22,
  [string]$KeyPath = "",
  [string]$RemoteDir = "/opt/you-where-backend",
  [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"

if ($RemoteDir -notmatch "^/[A-Za-z0-9._/-]+$") {
  throw "RemoteDir must be an absolute Linux path and may only contain letters, numbers, '.', '_', '-' and '/'."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Resolve-Path (Join-Path $scriptDir "..")
$deployDir = Join-Path $backendDir ".deploy"
$packagePath = Join-Path $deployDir "you-where-backend.tar.gz"
$target = "${User}@${Server}"

New-Item -ItemType Directory -Force $deployDir | Out-Null
if (Test-Path -LiteralPath $packagePath) {
  Remove-Item -LiteralPath $packagePath -Force
}

Write-Host "[sync] Packaging backend from $backendDir"
$tarArgs = @(
  "-czf", $packagePath,
  "--exclude=.env",
  "--exclude=.env.local",
  "--exclude=.env.*.local",
  "--exclude=.env.dev",
  "--exclude=.env.development",
  "--exclude=.env.prod",
  "--exclude=.env.production",
  "--exclude=.env.staging",
  "--exclude=.env.test",
  "--exclude=.env.testing",
  "--exclude=.deploy",
  "--exclude=__pycache__",
  "--exclude=.pytest_cache",
  "--exclude=data",
  "--exclude=nginx/logs",
  "-C", $backendDir,
  "."
)
& tar @tarArgs

$scpArgs = @("-P", $Port.ToString())
$sshArgs = @("-p", $Port.ToString())
if ($KeyPath.Trim().Length -gt 0) {
  $scpArgs += @("-i", $KeyPath)
  $sshArgs += @("-i", $KeyPath)
}

Write-Host "[sync] Uploading package to ${target}:/tmp/you-where-backend.tar.gz"
& scp @scpArgs $packagePath "${target}:/tmp/you-where-backend.tar.gz"

$remoteCommand = "set -eu; sudo mkdir -p '$RemoteDir'; sudo tar -xzf /tmp/you-where-backend.tar.gz -C '$RemoteDir'; cd '$RemoteDir'"
if (-not $SkipDeploy) {
  $remoteCommand += "; sudo sh scripts/cloud_deploy.sh"
}

Write-Host "[sync] Running remote deploy command"
& ssh @sshArgs $target $remoteCommand

Write-Host "[sync] Finished. Health URL: http://${Server}:18080/health"
