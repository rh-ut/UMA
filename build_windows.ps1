# Build the standalone UMA Windows executable.
#
# Run in Windows PowerShell from the project folder:
#     powershell -ExecutionPolicy Bypass -File build_windows.ps1
#
# Produces dist\uma.exe — a single self-contained file (no Python needed to run).
# Requires Python 3.10+ for Windows on PATH (the `py` launcher).

$ErrorActionPreference = "Stop"

# 1. isolated build environment
if (-not (Test-Path ".venv")) {
    py -m venv .venv
}
$py = ".\.venv\Scripts\python.exe"

# 2. dependencies (+ pyinstaller). On Windows, sounddevice bundles PortAudio,
#    so live playback works with no extra system install.
& $py -m pip install --upgrade pip
& $py -m pip install numpy soundfile sounddevice lameenc PySide6 pytest pyinstaller

# 3. verify before packaging
& $py -m pytest tests -q

# 4. one-file, windowed (no console) build
& $py -m PyInstaller --noconfirm --clean --name uma --onefile --windowed `
    --paths . `
    --collect-binaries sounddevice --collect-binaries soundfile --collect-binaries _soundfile_data `
    --collect-submodules PySide6 `
    run_uma.py

Write-Output ""
Write-Output "Done. Executable: dist\uma.exe"
