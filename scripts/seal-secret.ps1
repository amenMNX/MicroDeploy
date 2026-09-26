# -----------------------------------------------------------------------------
# Week 1 Step 2 -- Seal the microdeploy-secret (PowerShell / Windows version)
# Reads DB_PASSWORD from your .env file and produces a SealedSecret YAML
# that is safe to commit to Git.
#
# Run from the root of your MicroDeploy repo:
#   .\scripts\seal-secret.ps1
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$EnvFile = ".env"
$OutFile = "k8s\sealed-secret.yaml"

if (-not (Test-Path $EnvFile)) {
    Write-Host "[ERROR] .env file not found. Copy .env.example to .env and fill in DB_PASSWORD." -ForegroundColor Red
    exit 1
}

# Parse .env manually (PowerShell has no native `source`)
$envVars = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)\s*$') {
        $envVars[$matches[1]] = $matches[2]
    }
}

$DbPassword = $envVars["DB_PASSWORD"]

if ([string]::IsNullOrEmpty($DbPassword) -or $DbPassword -eq "change-me") {
    Write-Host "[ERROR] DB_PASSWORD is not set (or still the placeholder) in .env" -ForegroundColor Red
    exit 1
}

Write-Host "-> Creating SealedSecret for namespace: microdeploy"
Write-Host "   Secret name: microdeploy-secret"
Write-Host "   Key: DB_PASSWORD"

# Pipe kubectl's dry-run secret YAML into kubeseal, just like the bash version
kubectl create secret generic microdeploy-secret `
  --namespace microdeploy `
  --from-literal=DB_PASSWORD="$DbPassword" `
  --dry-run=client `
  --output=yaml | kubeseal `
    --controller-name=sealed-secrets-controller `
    --controller-namespace=kube-system `
    --format=yaml `
    > $OutFile

Write-Host ""
Write-Host "[OK] Written to $OutFile" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. git add $OutFile"
Write-Host "  2. git commit -m 'feat: add sealed secret for DB_PASSWORD'"
Write-Host "  3. kubectl apply -f k8s/namespace.yaml"
Write-Host "  4. kubectl apply -f $OutFile"
Write-Host "  5. Verify: kubectl get sealedsecret microdeploy-secret -n microdeploy"
Write-Host ""
Write-Host "[WARNING] Delete k8s/secret.yaml if it still exists -- never commit plain secrets." -ForegroundColor Yellow