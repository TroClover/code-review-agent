Write-Host "=== BRT Code Review Agent Setup ===" -ForegroundColor Cyan

# Try conda first
$condaPath = Get-Command conda -ErrorAction SilentlyContinue
if ($condaPath) {
    Write-Host "Found conda, creating conda environment 'breview'..." -ForegroundColor Green
    conda create -n breview python=3.9 -y
    conda activate breview
    pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
    Write-Host ""
    Write-Host "Done! To use later: conda activate breview" -ForegroundColor Green
    exit 0
}

# Fallback to venv
Write-Host "Conda not found, creating venv..." -ForegroundColor Yellow
python -m venv .venv
.venv\Scripts\activate
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
Write-Host ""
Write-Host "Done! To use later: .venv\Scripts\activate" -ForegroundColor Green
