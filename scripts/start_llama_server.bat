<<<<<<< C:/Users/aminh/OneDrive/Desktop/Multi_agent/scripts/start_llama_server.bat
"C:\Users\aminh\OneDrive\Desktop\Multi_agent\models\llama-server.exe" --model "C:\Users\aminh\OneDrive\Desktop\Multi_agent\models\deepseek\DeepSeek-R1-Distill-Qwen-14B-IQ4_XS.gguf" --port 8080 --host 127.0.0.1 -ngl 40 --no-mmap --main-gpu 0 -c 2048 -b 512 -ub 256 -t 6 -ctk q8_0 -ctv q8_0
=======
@echo off
setlocal enabledelayedexpansion

REM Determine repository root (script directory is scripts\)
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "MODELS_DIR=%REPO_ROOT%\models"
set "SERVER=%MODELS_DIR%\llama-server.exe"
set "MODEL=%MODELS_DIR%\deepseek\DeepSeek-R1-Distill-Qwen-14B-IQ4_XS.gguf"

if not exist "%SERVER%" (
    echo [ERROR] Could not find llama-server.exe under "%MODELS_DIR%".
    echo         Make sure the binaries are downloaded to the models folder.
    goto :EOF
)

if not exist "%MODEL%" (
    echo [ERROR] Could not find the DeepSeek GGUF model at:
    echo         %MODEL%
    echo         Please copy the file there or update start_llama_server.bat.
    goto :EOF
)

echo Starting llama-server...
echo Model: %MODEL%
start "llama-server" cmd /k ""%SERVER%" --model "%MODEL%" --port 8080 --host 127.0.0.1 -ngl 40 --no-mmap --main-gpu 0 -c 2048 -b 512 -ub 256 -t 6 -ctk q8_0 -ctv q8_0"

endlocal

>>>>>>> C:/Users/aminh/.windsurf/worktrees/Multi_agent/Multi_agent-b3f5a2b7/scripts/start_llama_server.bat
