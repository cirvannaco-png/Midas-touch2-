[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$MetaEditorPath,

    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath (Join-Path $_ "MQL5") -PathType Container })]
    [string]$TerminalDataPath,

    [string]$LogDirectory = (Join-Path $env:TEMP "MidasTouch-MetaEditor-Logs")
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stager = Join-Path $repoRoot "tools/stage_mt5_package.py"
$expertDir = Join-Path $TerminalDataPath "MQL5/Experts/MedisTouch"
$indicatorDir = Join-Path $TerminalDataPath "MQL5/Indicators/MedisTouch"
$expertSource = Join-Path $expertDir "MedisTouch_v2.8.mq5"
$indicatorSource = Join-Path $indicatorDir "MedisTouch_Indicator_v2.8.mq5"

if (-not (Test-Path -LiteralPath $MetaEditorPath -PathType Leaf)) {
    throw "MetaEditor executable not found: $MetaEditorPath"
}
if (-not (Test-Path -LiteralPath $stager -PathType Leaf)) {
    throw "Missing package stager: $stager"
}
if (-not (Test-Path -LiteralPath $TerminalDataPath -PathType Container)) {
    throw "MT5 terminal data folder not found: $TerminalDataPath"
}

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$LogDirectory = (Resolve-Path $LogDirectory).Path

Write-Host "Validating repository MQL5 structure..."
Push-Location $repoRoot
try {
    & python "tools/validate_mql5.py" "EA"
    if ($LASTEXITCODE -ne 0) {
        throw "Repository MQL5 structural validation failed."
    }

    Write-Host "Staging EA and indicator into the selected MT5 data folder..."
    & python $stager --destination $expertDir --indicator-destination $indicatorDir
    if ($LASTEXITCODE -ne 0) {
        throw "MQL5 staging failed."
    }
}
finally {
    Pop-Location
}

function Invoke-MetaEditorCompile {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$LogPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "Compile source missing after staging: $SourcePath"
    }

    $binaryPath = [System.IO.Path]::ChangeExtension($SourcePath, ".ex5")
    $metaLogPath = [System.IO.Path]::ChangeExtension($SourcePath, ".log")
    Remove-Item -LiteralPath $LogPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $metaLogPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $binaryPath -Force -ErrorAction SilentlyContinue

    $compileArg = '/compile:"{0}"' -f $SourcePath
    # MetaEditor documents /log as a switch that writes <source>.log beside the source.
    # Copy that authoritative log to the central log directory only after compilation.
    $includeArg = '/inc:"{0}"' -f (Join-Path $TerminalDataPath "MQL5")
    Write-Host "Compiling: $SourcePath"
    Write-Host "Include root: $(Join-Path $TerminalDataPath 'MQL5')"
    $process = Start-Process -FilePath $MetaEditorPath -ArgumentList @($compileArg, "/log", $includeArg) -Wait -PassThru

    if (-not (Test-Path -LiteralPath $metaLogPath -PathType Leaf)) {
        throw "MetaEditor did not create its documented source-side compile log for $SourcePath (process exit $($process.ExitCode))."
    }
    Copy-Item -LiteralPath $metaLogPath -Destination $LogPath -Force
    if (-not (Test-Path -LiteralPath $LogPath -PathType Leaf)) {
        throw "Could not copy MetaEditor log to $LogPath"
    }

    $logText = Get-Content -LiteralPath $LogPath -Raw
    if ($logText -match '(?im)\b([1-9][0-9]*)\s+errors?\b') {
        throw "MetaEditor reported $($Matches[1]) error(s) compiling $SourcePath. See $LogPath"
    }
    if ($logText -notmatch '(?im)\b0\s+errors?\b') {
        throw "Could not verify a zero-error result from MetaEditor. Inspect $LogPath"
    }
    if ($process.ExitCode -ne 0) {
        throw "MetaEditor exited with code $($process.ExitCode) for $SourcePath. See $LogPath"
    }
    if (-not (Test-Path -LiteralPath $binaryPath -PathType Leaf)) {
        throw "MetaEditor log reported zero errors, but no compiled binary was produced: $binaryPath"
    }

    if ($logText -match '(?im)\b([1-9][0-9]*)\s+warnings?\b') {
        Write-Warning "MetaEditor reported $($Matches[1]) warning(s) for $SourcePath. Review $LogPath before live use."
    }
    Write-Host "PASS: zero compile errors — $SourcePath"
    Write-Host "Log: $LogPath"
    Write-Host "Binary: $binaryPath"
}

Invoke-MetaEditorCompile -SourcePath $expertSource -LogPath (Join-Path $LogDirectory "MedisTouch_v2.8.compile.log")
Invoke-MetaEditorCompile -SourcePath $indicatorSource -LogPath (Join-Path $LogDirectory "MedisTouch_Indicator_v2.8.compile.log")

Write-Host ""
Write-Host "MetaEditor compilation completed with zero errors for both entry points."
Write-Host "This verifies compilation only; run the Strategy Tester and inspect its report before live deployment."
