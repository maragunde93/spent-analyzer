param()

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

function ConvertTo-CommandLineArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$composeProject = Get-EnvOrDefault "SPENT_COMPOSE_PROJECT" "spent-analyzer"
$composeFile = Get-EnvOrDefault "SPENT_COMPOSE_FILE" "docker-compose.yml"
$envFile = Get-EnvOrDefault "SPENT_ENV_FILE" ".env"
$dbService = Get-EnvOrDefault "SPENT_DB_SERVICE" "postgres"
$dbName = Get-EnvOrDefault "SPENT_POSTGRES_DB" "spent_analyzer"
$dbUser = Get-EnvOrDefault "SPENT_POSTGRES_USER" "spent"
$backupDir = Get-EnvOrDefault "SPENT_BACKUP_DIR" (Join-Path $repoRoot "backups")
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$backupPath = Join-Path $backupDir "spent_analyzer_$timestamp.dump"
if ([System.IO.Path]::IsPathRooted($envFile)) {
    $envFilePath = $envFile
}
else {
    $envFilePath = Join-Path $repoRoot $envFile
}

Set-Location $repoRoot

if (-not (Test-Path -LiteralPath $envFilePath -PathType Leaf)) {
    Write-Error "Environment file not found: $envFilePath"
    exit 1
}

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "Creating backup: $backupPath"

$dockerArgs = @(
    "compose",
    "-p", $composeProject,
    "-f", $composeFile,
    "--env-file", $envFile,
    "exec",
    "-T",
    $dbService,
    "pg_dump",
    "-U", $dbUser,
    "-d", $dbName,
    "--format=custom"
)

$dockerCommand = "docker " + (($dockerArgs | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join " ")
$stderrPath = [System.IO.Path]::GetTempFileName()

try {
    $cmd = if ($env:ComSpec) { $env:ComSpec } else { "cmd.exe" }
    $cmdCommand = "$dockerCommand 1> $(ConvertTo-CommandLineArgument $backupPath) 2> $(ConvertTo-CommandLineArgument $stderrPath)"
    & $cmd /d /s /c $cmdCommand
    $exitCode = $LASTEXITCODE

    $backupFile = Get-Item -LiteralPath $backupPath
    if ($exitCode -ne 0) {
        $stderr = Get-Content -LiteralPath $stderrPath -Raw
        throw "Backup failed with exit code $exitCode.`n$stderr"
    }

    if ($backupFile.Length -eq 0) {
        $stderr = Get-Content -LiteralPath $stderrPath -Raw
        throw "Backup failed: Docker completed successfully, but the dump file is empty.`n$stderr"
    }
}
catch {
    if (Test-Path -LiteralPath $backupPath) {
        Remove-Item -LiteralPath $backupPath -Force
    }

    throw
}
finally {
    if (Test-Path -LiteralPath $stderrPath) {
        Remove-Item -LiteralPath $stderrPath -Force
    }
}

Write-Host "Backup complete."
