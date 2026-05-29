# Ollama MCP - multi-agent mode (HexStrike + RAG)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = Join-Path $ProjectRoot "hexstrike-with-rag-config.json"
$Model = "qwen3:32b"

Write-Host "Starting Ollama MCP (multi-agent mode)..."
Write-Host "Config: $ConfigFile"
Write-Host "Model:  $Model"
Write-Host ""

Set-Location $ProjectRoot
python -m mcp_client_for_ollama.cli --servers-json $ConfigFile --model $Model
