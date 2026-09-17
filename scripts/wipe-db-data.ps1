[CmdletBinding()]
param(
    [switch]$ConfirmWipe,
    [switch]$ConfirmProductionWipe,
    [string]$ComposeProject,
    [string]$ComposeFile
)

$ErrorActionPreference = "Stop"

function Get-EnvOrDefault {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$DefaultValue
    )

    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $DefaultValue
    }

    return $value
}

if (-not $ConfirmWipe) {
    throw "This deletes all application data. Run again with -ConfirmWipe after checking the selected Compose target."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$projectFromEnvironment = [Environment]::GetEnvironmentVariable("SPENT_COMPOSE_PROJECT")
$fileFromEnvironment = [Environment]::GetEnvironmentVariable("SPENT_COMPOSE_FILE")
$projectWasSpecified = $PSBoundParameters.ContainsKey("ComposeProject") -or -not [string]::IsNullOrWhiteSpace($projectFromEnvironment)
$fileWasSpecified = $PSBoundParameters.ContainsKey("ComposeFile") -or -not [string]::IsNullOrWhiteSpace($fileFromEnvironment)
$selectedComposeProject = if ($PSBoundParameters.ContainsKey("ComposeProject")) {
    $ComposeProject
}
elseif (-not [string]::IsNullOrWhiteSpace($projectFromEnvironment)) {
    $projectFromEnvironment
}
else {
    "spent-analyzer"
}
$selectedComposeFile = if ($PSBoundParameters.ContainsKey("ComposeFile")) {
    $ComposeFile
}
elseif (-not [string]::IsNullOrWhiteSpace($fileFromEnvironment)) {
    $fileFromEnvironment
}
else {
    "docker-compose.yml"
}
$envFile = Get-EnvOrDefault "SPENT_ENV_FILE" ".env"
$dbService = Get-EnvOrDefault "SPENT_DB_SERVICE" "postgres"
$dbName = Get-EnvOrDefault "SPENT_POSTGRES_DB" "spent_analyzer"
$dbUser = Get-EnvOrDefault "SPENT_POSTGRES_USER" "spent"
$environment = Get-EnvOrDefault "SPENT_ENVIRONMENT" "development"
$safetyKeepText = Get-EnvOrDefault "SPENT_BACKUP_SAFETY_KEEP" "20"
$safetyKeep = 0

if (-not [int]::TryParse($safetyKeepText, [ref]$safetyKeep) -or $safetyKeep -lt 1) {
    throw "SPENT_BACKUP_SAFETY_KEEP must be a positive integer."
}

# The demo launcher uses a generated Compose file and a distinct project name.
# Discover it from Docker so the normal local command needs no extra flags.
if (-not $projectWasSpecified -or -not $fileWasSpecified) {
    $composeProjectsJson = & docker compose ls --format json
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect Docker Compose projects."
    }

    $composeProjects = @($composeProjectsJson | ConvertFrom-Json)

    if (-not $projectWasSpecified) {
        $defaultProject = $composeProjects | Where-Object {
            $_.Name -eq "spent-analyzer" -and $_.Status -match "running"
        } | Select-Object -First 1
        $demoProject = $composeProjects | Where-Object {
            $_.Name -eq "spent-analyzer-demo" -and $_.Status -match "running"
        } | Select-Object -First 1

        if ($null -ne $defaultProject) {
            $selectedComposeProject = $defaultProject.Name
        }
        elseif ($null -ne $demoProject) {
            $selectedComposeProject = $demoProject.Name
        }
    }

    if (-not $fileWasSpecified) {
        $selectedProject = $composeProjects | Where-Object {
            $_.Name -eq $selectedComposeProject -and $_.Status -match "running"
        } | Select-Object -First 1

        if ($null -ne $selectedProject -and -not [string]::IsNullOrWhiteSpace($selectedProject.ConfigFiles)) {
            $selectedComposeFile = @($selectedProject.ConfigFiles -split ",")[0]
        }
    }
}

Write-Host "Using Compose project '$selectedComposeProject'."
Write-Host "Using Compose file '$selectedComposeFile'."

$looksLikeProduction = (
    (Split-Path -Leaf $selectedComposeFile) -match "prod" -or
    $dbService -eq "spent-postgres" -or
    $environment -eq "production"
)

if ($looksLikeProduction -and -not $ConfirmProductionWipe) {
    throw "The selected target looks like production. Also pass -ConfirmProductionWipe to wipe it."
}

$defaultAppServices = if ($looksLikeProduction) { "spent-api spent-web" } else { "api web" }
$appServices = (Get-EnvOrDefault "SPENT_APP_SERVICES" $defaultAppServices) -split "\s+"
$envFilePath = if ([System.IO.Path]::IsPathRooted($envFile)) {
    $envFile
}
else {
    Join-Path $repoRoot $envFile
}

if (-not (Test-Path -LiteralPath $envFilePath -PathType Leaf)) {
    throw "Environment file not found: $envFilePath"
}

$composeArgs = @(
    "compose",
    "-p", $selectedComposeProject,
    "-f", $selectedComposeFile,
    "--env-file", $envFile
)

Set-Location $repoRoot

$runningOutput = & docker @composeArgs ps --status running --services
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect the running Compose services."
}

$runningServices = @(
    $runningOutput | Where-Object { $_ -in $appServices }
)

$safetyBackupDir = Join-Path $repoRoot "backups\safety"
$backupEnvironment = @{
    SPENT_COMPOSE_PROJECT = $selectedComposeProject
    SPENT_COMPOSE_FILE = $selectedComposeFile
    SPENT_ENV_FILE = $envFile
    SPENT_DB_SERVICE = $dbService
    SPENT_POSTGRES_DB = $dbName
    SPENT_POSTGRES_USER = $dbUser
    SPENT_BACKUP_DIR = $safetyBackupDir
}
$originalEnvironment = @{}

foreach ($name in $backupEnvironment.Keys) {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name)
}

try {
    if ($runningServices.Count -gt 0) {
        Write-Host "Stopping application services during backup and wipe..."
        & docker @composeArgs stop @runningServices
        if ($LASTEXITCODE -ne 0) {
            throw "Could not stop the application services."
        }
    }

    Write-Host "Creating the mandatory pre-wipe safety backup..."
    foreach ($name in $backupEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $backupEnvironment[$name])
    }
    & (Join-Path $scriptDir "backup-current-db.ps1")

    Get-ChildItem -LiteralPath $safetyBackupDir -Filter "spent_analyzer_*.dump" -File |
        Sort-Object Name -Descending |
        Select-Object -Skip $safetyKeep |
        Remove-Item -Force

    $sql = @'
DO $wipe$
DECLARE
    table_list text;
BEGIN
    SELECT string_agg(format('%I.%I', schemaname, tablename), ', ')
      INTO table_list
      FROM pg_tables
     WHERE schemaname = 'public'
       AND tablename <> 'alembic_version';

    IF table_list IS NOT NULL THEN
        EXECUTE 'TRUNCATE TABLE ' || table_list || ' RESTART IDENTITY CASCADE';
    END IF;
END
$wipe$;
'@

    Write-Host "Truncating application tables in the public schema..."
    & docker @composeArgs exec -T $dbService `
        psql -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -c $sql
    if ($LASTEXITCODE -ne 0) {
        throw "The database wipe failed."
    }

    Write-Host "Database data wipe complete; schema and Alembic migration state were preserved."
}
finally {
    foreach ($name in $originalEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name])
    }

    if ($runningServices.Count -gt 0) {
        Write-Host "Restarting previously running application services..."
        & docker @composeArgs up -d @runningServices
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "The database operation finished, but one or more application services could not be restarted."
        }
    }
}
