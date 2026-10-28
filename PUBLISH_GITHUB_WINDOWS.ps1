# Run explicitly to publish source to a private GitHub repo after gh auth login.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Repo = if ($env:DHANFLIP_GITHUB_REPO) {$env:DHANFLIP_GITHUB_REPO} else {'GadatheGod/DhanFlip-MCP'}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {throw 'Install Git for Windows'}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {throw 'Install GitHub CLI (gh) and sign in with gh auth login'}
if (-not (Test-Path .git)) {git init -b main}
git add .github README.md LICENSE.txt .gitignore .env.example requirements.txt pytest.ini dhanflip config/settings.yaml config/tunnel.example.yaml docs tests original_strategy START_WINDOWS.bat INSTALL_WINDOWS.cmd INSTALL_WINDOWS.ps1 INSTALL_LINUX.sh START_LINUX.sh RUN_TESTS.bat RUN_TESTS_LINUX.sh PUBLISH_GITHUB.sh PUBLISH_GITHUB_WINDOWS.ps1
$Changed = git diff --cached --name-only
if ($Changed) {git commit -m 'DhanFlip V3: unified read-only options terminal'}
& gh repo view $Repo *> $null
if ($LASTEXITCODE -ne 0) {gh repo create $Repo --private --description 'DhanFlip V3: NIFTY/SENSEX 3-minute options trading signals (read-only)'}
& git remote get-url origin *> $null
if ($LASTEXITCODE -ne 0) {git remote add origin "https://github.com/$Repo.git"}
git push -u origin main
Write-Host "Published to https://github.com/$Repo"
