# Сборка портативной версии плеера в dist\Player
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[1/4] PyInstaller (onedir)..." -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
python -m PyInstaller player.spec --noconfirm

$out = "dist\Player"

Write-Host "[2/4] Копирую ресурсы рядом с .exe..." -ForegroundColor Cyan
foreach ($d in @("vlc_engine", "assets", "storage")) {
    Copy-Item -Recurse -Force $d "$out\$d"
}
foreach ($f in @("config.txt", "ui_config.txt")) { Copy-Item -Force $f "$out\$f" }
New-Item -ItemType Directory -Force -Path "$out\music" | Out-Null

Write-Host "[3/4] Кладу клиент Flet (чтобы он не качался при первом запуске)..." -ForegroundColor Cyan
$ver = (python -c "import flet_desktop.version as v; print(v.version)").Trim()
$src = Join-Path $HOME ".flet\client\flet-desktop-full-$ver\flet"
if (Test-Path $src) {
    Copy-Item -Recurse -Force $src "$out\flet_client"
} else {
    Write-Warning "Клиент Flet не найден в $src - запусти приложение один раз из исходников, потом пересобери."
}

Write-Host "[4/4] Архив..." -ForegroundColor Cyan
Remove-Item -Force "Player-windows.zip" -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory((Resolve-Path $out), (Join-Path $PSScriptRoot "Player-windows.zip"))

$mb = [math]::Round((Get-Item "Player-windows.zip").Length / 1MB, 1)
Write-Host "Готово: Player-windows.zip ($mb MB), папка: $out" -ForegroundColor Green
