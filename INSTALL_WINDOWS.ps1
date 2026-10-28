# One-time current-user Windows install: no administrator rights required.
$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Project
Write-Host "DhanFlip V3 Windows installation" -ForegroundColor Cyan
$PyCmd = $null
$PyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PyCmd='py'; $PyArgs=@('-3')
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -eq 0) {$PyArgs=@('-3.12')} else {
        & py -3.11 --version *> $null
        if ($LASTEXITCODE -eq 0) {$PyArgs=@('-3.11')}
    }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PyCmd='python'; $PyArgs=@()
} else {throw 'Install Python 3.11 or 3.12 (64-bit) from python.org and run installer again.'}
$Python = Join-Path $Project '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    & $PyCmd @PyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) {throw 'Could not create virtual environment'}
}
& $Python -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) {throw 'Dependency installation failed'}
& $Python -c 'import tkinter;import dhanflip'
if ($LASTEXITCODE -ne 0) {throw 'Python Tkinter missing or application could not import'}
$Shell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath('Desktop')
$Menu = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'
foreach ($Dir in @($Desktop,$Menu)) {
    if (-not (Test-Path $Dir)) {New-Item -ItemType Directory -Force -Path $Dir | Out-Null}
    $Shortcut = $Shell.CreateShortcut((Join-Path $Dir 'DhanFlip V3.lnk'))
    $Shortcut.TargetPath = "$env:ComSpec"
    $Shortcut.Arguments = '/c ""' + (Join-Path $Project 'START_WINDOWS.bat') + '""'
    $Shortcut.WorkingDirectory = $Project
    $Shortcut.Description = 'DhanFlip V3 - read-only NIFTY/SENSEX 3-minute options signals'
    $Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,44"
    $Shortcut.Save()
}
Write-Host "Installed. Double-click DhanFlip V3 on Desktop or Start Menu." -ForegroundColor Green
Write-Host 'Trading is manual. No Dhan order submission is implemented.'
