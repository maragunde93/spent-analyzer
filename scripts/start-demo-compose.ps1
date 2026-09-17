param(
    [string]$ProjectName = "spent-analyzer-demo",
    [int]$WebPort = 8081,
    [int]$ApiPort = 8001,
    [int]$PostgresPort = 5433,
    [switch]$Detached,
    [switch]$ResetData,
    [switch]$Down,
    [switch]$NoMercadoPagoHttpDebug
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$safeProjectName = $ProjectName -replace '[^A-Za-z0-9_.-]', '-'
$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "spent-analyzer-$safeProjectName"
$composePath = Join-Path $tmpDir "docker-compose.demo.generated.yml"
$backendContext = ((Resolve-Path (Join-Path $repoRoot "backend")).Path -replace "\\", "/")
$frontendContext = ((Resolve-Path (Join-Path $repoRoot "frontend")).Path -replace "\\", "/")
$mercadoPagoDebugHttpEnabled = if ($NoMercadoPagoHttpDebug) { "false" } else { "true" }

New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

$composeTemplate = @'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: spent_analyzer
      POSTGRES_USER: spent
      POSTGRES_PASSWORD: spent_dev_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "__POSTGRES_PORT__:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U spent -d spent_analyzer"]
      interval: 5s
      timeout: 5s
      retries: 12
      start_period: 5s

  api:
    build:
      context: "__BACKEND_CONTEXT__"
    environment:
      SPENT_ENVIRONMENT: development
      SPENT_DATABASE_URL: postgresql+psycopg://spent:spent_dev_password@postgres:5432/spent_analyzer
      SPENT_CORS_ORIGINS: '["http://localhost:5173","http://127.0.0.1:5173","http://localhost:__WEB_PORT__","http://127.0.0.1:__WEB_PORT__"]'
      SPENT_TEST_AUTH_ENABLED: "false"
      SPENT_PUBLIC_BASE_URL: http://localhost:__WEB_PORT__/finance
      SPENT_PUBLIC_API_BASE_URL: http://localhost:__WEB_PORT__/finance/api
      SPENT_LOCAL_USERS: '[{"username":"mauro","email":"mauro@example.test","display_name":"Mauro","password_hash":"pbkdf2_sha256$$260000$$2pVSTv4HbgAOKvbaAGMnGQ==$$feqKyBaYhvwm-SEKvl5n88HuYFZ9HgZcecC0BANnIzM="},{"username":"mica","email":"mica@example.test","display_name":"Mica","password_hash":"pbkdf2_sha256$$260000$$scS_1EEtDmi2D5srrRN2xg==$$igV54oG2AUzEbDoB7YpFlEQL8bYGChimSB5FG9unoK8="}]'
      SPENT_SESSION_SECRET: local-demo-session-secret-change-for-shared-hosts
      SPENT_SESSION_COOKIE_PATH: /finance
      SPENT_SESSION_COOKIE_SECURE: "false"
      SPENT_SESSION_COOKIE_SAMESITE: lax
      SPENT_SEED_DEMO_DATA: "true"
      SPENT_FX_AUTO_UPDATE_ENABLED: "false"
      SPENT_MERCADOPAGO_DEBUG_HTTP_ENABLED: "__MERCADOPAGO_DEBUG_HTTP_ENABLED__"
      SPENT_MERCADOPAGO_DEBUG_HTTP_MAX_CHARS: "12000"
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "__API_PORT__:8000"

  web:
    build:
      context: "__FRONTEND_CONTEXT__"
      args:
        VITE_APP_BASE: /finance/
        VITE_API_BASE: /finance/api
        VITE_ENABLE_API_FALLBACKS: "false"
    depends_on:
      - api
    ports:
      - "__WEB_PORT__:80"

volumes:
  postgres_data:
'@

$composeContent = $composeTemplate.
    Replace("__WEB_PORT__", [string]$WebPort).
    Replace("__API_PORT__", [string]$ApiPort).
    Replace("__POSTGRES_PORT__", [string]$PostgresPort).
    Replace("__BACKEND_CONTEXT__", $backendContext).
    Replace("__FRONTEND_CONTEXT__", $frontendContext).
    Replace("__MERCADOPAGO_DEBUG_HTTP_ENABLED__", $mercadoPagoDebugHttpEnabled)

Set-Content -LiteralPath $composePath -Value $composeContent -Encoding utf8

Set-Location $repoRoot

if ($Down) {
    $downArgs = @("compose", "-p", $ProjectName, "-f", $composePath, "down", "--remove-orphans")
    if ($ResetData) {
        $downArgs += "--volumes"
    }

    Write-Host "Stopping demo stack for project '$ProjectName'..."
    docker @downArgs
    exit $LASTEXITCODE
}

if ($ResetData) {
    Write-Host "Resetting demo containers and volumes for project '$ProjectName'..."
    docker compose -p $ProjectName -f $composePath down --volumes --remove-orphans
}

$upArgs = @("compose", "-p", $ProjectName, "-f", $composePath, "up", "--build")
if ($Detached) {
    $upArgs += "-d"
}

Write-Host "Starting demo stack with seeded fake data..."
Write-Host "UI:  http://localhost:$WebPort/finance/"
Write-Host "API: http://localhost:$ApiPort"
Write-Host "Login: mauro / local-password-123"
Write-Host "Mercado Pago HTTP debug: $mercadoPagoDebugHttpEnabled"
Write-Host ""

docker @upArgs
