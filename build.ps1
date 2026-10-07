param(
    [switch]$Clean,
    [switch]$Release,
    [string]$OutputDirectory,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$python = Join-Path $projectDirectory '.venv\Scripts\python.exe'
# Only this build process is changed; never modify the user's Windows PATH.
$env:PATH = (($env:PATH -split ';') | Where-Object {
    $_ -notmatch '[\\/]codex-runtimes[\\/].*[\\/]dependencies[\\/]native([\\/]|$)'
}) -join ';'
$appVersion = & $python -c 'import sys; sys.path.insert(0, sys.argv[1]); from app_metadata import VERSION; print(VERSION)' $projectDirectory
if ($LASTEXITCODE -ne 0) { throw 'Could not read application version' }
$buildArguments = @()
if ($Release) {
    $releaseDirectory = Join-Path $projectDirectory ("releases\{0}" -f $appVersion)
} else {
    $releaseDirectory = Join-Path $projectDirectory 'dist'
}
if ($OutputDirectory) {
    $releaseDirectory = [IO.Path]::GetFullPath((Join-Path $projectDirectory $OutputDirectory))
    if (-not $releaseDirectory.StartsWith($projectDirectory + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Build output must be a child directory of the project'
    }
}
$workDirectory = Join-Path $projectDirectory ("build\{0}" -f (Split-Path -Leaf $releaseDirectory))
$buildArguments += @('--distpath', $releaseDirectory, '--workpath', $workDirectory)

if ($Clean) {
    foreach ($generatedDirectory in @('build', 'dist')) {
        $generatedPath = [IO.Path]::GetFullPath((Join-Path $projectDirectory $generatedDirectory))
        if (-not $generatedPath.StartsWith($projectDirectory + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to clean a directory outside the project'
        }
        if (Test-Path -LiteralPath $generatedPath) {
            if ((Get-Item -LiteralPath $generatedPath).LinkType) { throw 'Refusing to clean a linked directory' }
            $resolvedGeneratedPath = (Resolve-Path -LiteralPath $generatedPath).Path
            if ($resolvedGeneratedPath -ne $generatedPath) { throw 'Refusing to clean an unexpected resolved path' }
            Remove-Item -LiteralPath $resolvedGeneratedPath -Recurse -Force
        }
    }
}

& $python (Join-Path $projectDirectory 'tools\prepare_audio_assets.py')
if ($LASTEXITCODE -ne 0) { throw 'Audio asset preparation failed' }
& $python (Join-Path $projectDirectory 'tools\build_app_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
if (-not $SkipTests) {
    & $python -m unittest discover -s (Join-Path $projectDirectory 'tests') -t $projectDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; build cancelled' }
}
& $python -m PyInstaller --noconfirm --clean `
    @buildArguments (Join-Path $projectDirectory 'PS3Presence.spec')
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }

Write-Host "Built: $(Join-Path $releaseDirectory 'PS3Presence\PS3Presence.exe')"
