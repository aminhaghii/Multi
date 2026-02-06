@echo off
setlocal

REM Start llama-server from the actual binaries folder (models\)
pushd "%~dp0..\models"
start "llama-server" cmd /k ".\llama-server.exe --model .\deepseek\DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf --port 8080 --ctx-size 8000 --host 127.0.0.1"
popd

endlocal

