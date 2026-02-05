@echo off
setlocal
pushd "%~dp0models"

set "LLAMA_DLL_DIR=%CD%\llama-b7611"
set "PATH=%LLAMA_DLL_DIR%;%PATH%"

start "llama-server" cmd /k "llama-server.exe --model qwen\qwen2.5-7b-instruct-q5_k_m-00001-of-00002.gguf --port 8080 --ctx-size 16000 --host 127.0.0.1"
popd
endlocal
