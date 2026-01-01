param(
  [string]$RepoRoot = (Get-Location).Path,
  [string]$PythonVersion = "3.8.17"
)

function Abort($msg){ Write-Error $msg; exit 1 }

Write-Host "Repo root: $RepoRoot"

# warn if not elevated
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
  Write-Warning "Not running as Administrator. Some install steps may fail. Re-run PowerShell as Administrator if installer fails."
}

# 1) Check for python
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
  Write-Host "Python not found. Attempting install..."
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if ($winget) {
    Write-Host "Trying winget install..."
    try {
      Start-Process -FilePath "winget" -ArgumentList "install --silent --accept-package-agreements --accept-source-agreements --id Python.Python.3" -NoNewWindow -Wait -ErrorAction Stop
    } catch {
      Write-Warning "winget install failed or unavailable. Will try direct download."
    }
  }

  # check again
  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if (-not $pyCmd) {
    $installer = Join-Path $env:TEMP "python-$PythonVersion-amd64.exe"
    $url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
    Write-Host "Downloading Python installer $url ..."
    try {
      Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing -ErrorAction Stop
      Write-Host "Running installer (quiet, add to PATH)..."
      Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait -NoNewWindow -ErrorAction Stop
      Remove-Item $installer -ErrorAction SilentlyContinue
    } catch {
      Abort "Failed to download/install Python: $_"
    }
  }
}

# refresh PATH for current session (may require reopening shell)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { Abort "python not found after install. Reopen shell and retry." }

Write-Host "Python found: $(python --version)"

# 2) ensure pip and upgrade packaging tools
try {
  python -m ensurepip --upgrade | Out-Null
} catch { Write-Verbose "ensurepip not needed or failed; continuing." }
python -m pip install --upgrade pip setuptools wheel

# 3) create and activate venv
Push-Location $RepoRoot
if (-not (Test-Path ".\venv")) {
  Write-Host "Creating virtualenv..."
  python -m venv venv
}

# adjust ExecutionPolicy for this session then activate
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\venv\Scripts\Activate.ps1

# 4) install requirements
if (-not (Test-Path ".\requirements.txt")) { Abort "requirements.txt not found at $RepoRoot" }

Write-Host "Installing requirements (may fail for dlib/face_recognition on Windows)..."
try {
  pip install --upgrade pip
  pip install -r requirements.txt
  Write-Host "Requirements installed."
} catch {
  Write-Warning "pip install -r requirements.txt failed. Attempting best-effort workarounds..."
  try { pip install --upgrade setuptools wheel cmake } catch {}
  try { pip install --only-binary=:all: dlib } catch { Write-Warning "dlib wheel install failed." }
  try { pip install --only-binary=:all: face_recognition } catch { Write-Warning "face_recognition wheel install failed." }
  Write-Warning "If heavy packages still fail, use WSL2 or Docker (recommended)."
}

Write-Host ""
Write-Host "Setup finished. To run locally:"
Write-Host "  . .\venv\Scripts\Activate.ps1"
Write-Host "  set DB env vars (PowerShell):"
Write-Host "    $env:DB_HOST='127.0.0.1'"
Write-Host "    $env:DB_USER='hrmsuser'"
Write-Host "    $env:DB_PASSWORD='secret'"
Write-Host "    $env:DB_NAME='hrms'"
Write-Host "  Run app (example): python src/app.py  or use flask run if configured"
Write-Host ""
Write-Host "Notes: dlib/face_recognition frequently fail to build on Windows. Recommended alternatives:"
Write-Host " - Use WSL2 (Ubuntu) and run this repo setup inside WSL."
Write-Host " - Or use Docker with docker-compose (faster and reproducible)."
Pop-Location