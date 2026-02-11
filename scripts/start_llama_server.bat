@echo off
setlocal enabledelayedexpansion

REM Determine repository root (script directory is scripts\)
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "MODELS_DIR=%REPO_ROOT%\models"
set "SERVER=%MODELS_DIR%\llama-server.exe"

REM Try Q4_K_M first, then IQ4_XS as fallback
set "MODEL=%MODELS_DIR%\deepseek\DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf"
if not exist "%MODEL%" (
    set "MODEL=%MODELS_DIR%\deepseek\DeepSeek-R1-Distill-Qwen-14B-IQ4_XS.gguf"
)

if not exist "%SERVER%" (
    echo [ERROR] Could not find llama-server.exe under "%MODELS_DIR%".
    echo         Make sure the binaries are downloaded to the models folder.
    pause
    goto :EOF
)

if not exist "%MODEL%" (
    echo [ERROR] Could not find the DeepSeek GGUF model at:
    echo         %MODEL%
    echo         Please copy the file there or update start_llama_server.bat.
    pause
    goto :EOF
)

REM Flash attention via env var (this llama-server version does NOT support --flash-attn CLI flag)
set "LLAMA_ARG_FLASH_ATTN=on"

echo Starting llama-server...
echo Model: %MODEL%
echo Flash Attn: %LLAMA_ARG_FLASH_ATTN%
start "llama-server" cmd /k ""%SERVER%" --model "%MODEL%" --port 8080 --host 127.0.0.1 -ngl 40 --no-mmap --main-gpu 0 -c 2048 -b 512 -ub 256 -t 6 -ctk q8_0 -ctv q8_0"

endlocal
