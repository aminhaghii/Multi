@echo off
setlocal
pushd "%~dp0models\llama-b7611"
start "llama-server" cmd /k ".\llama-server.exe --model ..\qwen\Meta-Llama-3-8B-Instruct-Q4_K_M.gguf --port 8080 --ctx-size 8192 --host 127.0.0.1"
if errorlevel 1 (
    echo Error occurred while starting the server.
) else (
    echo Server started successfully.
)
popd
endlocal
