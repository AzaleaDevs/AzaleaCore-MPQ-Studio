param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    $pythonCommand = $pythonLauncher.Source
    $pythonPrefix = @("-3")
} else {
    $pythonLauncher = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonLauncher) {
        throw "Instala Python 3.11 o posterior en este equipo de compilación."
    }
    $pythonCommand = $pythonLauncher.Source
    $pythonPrefix = @()
}

$buildVenv = Join-Path $projectRoot ".venv"
$buildPython = Join-Path $buildVenv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $buildPython)) {
    & $pythonCommand @pythonPrefix -m venv $buildVenv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno de compilación." }
}

& $buildPython -m pip install -e ".[build]"
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias de compilación." }

$version = (& $buildPython -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])").Trim()
$appName = "AzaleaCore MPQ Studio"
$stageName = "portable-$version"
$stagePath = Join-Path $projectRoot "dist\$stageName"
$bundlePath = Join-Path $stagePath $appName
$zipPath = Join-Path $projectRoot "dist\$appName $version portable.zip"
$iconPath = Join-Path $projectRoot "assets\azaleacore-mpq-studio.ico"
$entryPoint = Join-Path $projectRoot "tools\portable_entry.py"
$sourcePath = Join-Path $projectRoot "src"
$buildPath = Join-Path $projectRoot "build\pyinstaller-$version"

if (Test-Path -LiteralPath $stagePath) {
    throw "Ya existe la salida '$stagePath'. Muévela o renómbrala antes de compilar otra vez."
}
if (Test-Path -LiteralPath $zipPath) {
    throw "Ya existe el ZIP '$zipPath'. Muévelo o renómbralo antes de compilar otra vez."
}

& $buildPython -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name $appName `
    --icon $iconPath `
    --add-data "$iconPath;assets" `
    --paths $sourcePath `
    --distpath $stagePath `
    --workpath $buildPath `
    --specpath $buildPath `
    $entryPoint
if ($LASTEXITCODE -ne 0) { throw "PyInstaller no pudo generar la versión portable." }

Copy-Item -LiteralPath (Join-Path $projectRoot "docs\README-portable.txt") -Destination $bundlePath
Copy-Item -LiteralPath (Join-Path $projectRoot "CHANGELOG.md") -Destination $bundlePath
Compress-Archive -LiteralPath $bundlePath -DestinationPath $zipPath -CompressionLevel Optimal

Write-Output "Versión portable generada:"
Write-Output $bundlePath
Write-Output $zipPath
