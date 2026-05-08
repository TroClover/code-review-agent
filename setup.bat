@echo off
echo === BRT Code Review Agent Setup ===

REM Option 1: Conda (recommended if you have Anaconda)
where conda >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found conda, creating conda environment...
    conda create -n breview python=3.9 -y
    call conda activate breview
    pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
    echo Done! To use later: conda activate breview
    pause
    exit /b 0
)

REM Option 2: venv (fallback if no conda)
echo Conda not found, creating venv...
python -m venv .venv
call .venv\Scripts\activate
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.
echo Done! To use later: .venv\Scripts\activate
pause
