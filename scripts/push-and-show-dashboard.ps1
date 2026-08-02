<#
.SYNOPSIS
Push to GitHub, wait for the CI/CD pipeline, and open the dashboard when all tests pass.

.EXAMPLE
.\scripts\push-and-show-dashboard.ps1
.\scripts\push-and-show-dashboard.ps1 -Branch main
#>
param(
    [string]$Branch = "main",
    [string]$Repo = "shahsadruddin2009-code/Final_Assessment_Devops_Module"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Pushing to origin/$Branch..." -ForegroundColor Cyan
git push origin $Branch
if ($LASTEXITCODE -ne 0) { Write-Error "git push failed"; exit 1 }

Write-Host "Waiting for the workflow run to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 10
$runId = gh run list --repo $Repo --branch $Branch -L 1 --json databaseId -q ".[0].databaseId"
if (-not $runId) { Write-Error "Could not find a workflow run"; exit 1 }
Write-Host "Watching run $runId (this can take a few minutes)..." -ForegroundColor Cyan

gh run watch $runId --repo $Repo --exit-status
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pipeline FAILED - dashboard will not be opened." -ForegroundColor Red
    Write-Host "Inspect the failure with: gh run view $runId --repo $Repo --log-failed"
    exit 1
}

Write-Host "All tests passed. Downloading dashboard artifact..." -ForegroundColor Green
$dest = Join-Path $repoRoot "dashboard-download"
Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
gh run download $runId --repo $Repo --name northwind-dashboard --dir $dest
if ($LASTEXITCODE -ne 0) { Write-Error "Artifact download failed"; exit 1 }

$index = Join-Path $dest "index.html"
Write-Host "Opening dashboard: $index" -ForegroundColor Green
Start-Process $index
