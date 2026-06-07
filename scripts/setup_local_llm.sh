#!/usr/bin/env bash
# Generated with Claude Code.
# Assumes: pip, hf (huggingface CLI), ollama are already installed.
set -euo pipefail

# Use mradermacher's imatrix quants (better quality than static Q4 at same size).
# Static quant alternative: mradermacher/Qwen2.5-72B-Instruct-abliterated-GGUF
MODEL_REPO="mradermacher/Qwen2.5-72B-Instruct-abliterated-i1-GGUF"
MODEL_FILE="Qwen2.5-72B-Instruct-abliterated.i1-Q4_K_M.gguf"
EMBED_MODEL="nomic-embed-text"
OLLAMA_MODEL_NAME="qwen2.5-abliterated-q4"

echo "=== ForBot Local LLM Setup ==="

# 1. Download GGUF
echo "[1/4] Downloading ${MODEL_FILE} from ${MODEL_REPO}..."
hf download "${MODEL_REPO}" "${MODEL_FILE}" --local-dir ./models

# 2. Create and import Ollama Modelfile
echo "[2/4] Starting Ollama server in background..."
ollama serve &>/tmp/ollama.log &
OLLAMA_PID=$!
sleep 3  # give it a moment to be ready

echo "      Importing model as '${OLLAMA_MODEL_NAME}'..."
cat > /tmp/forbot_modelfile <<EOF
FROM ./models/${MODEL_FILE}
EOF
ollama create "${OLLAMA_MODEL_NAME}" -f /tmp/forbot_modelfile
rm /tmp/forbot_modelfile

# 3. Pull embedding model
echo "[3/4] Pulling embedding model '${EMBED_MODEL}'..."
ollama pull "${EMBED_MODEL}"

# 4. Verify
echo "[4/4] Verifying models are available..."
echo "Installed Ollama models:"
ollama list | grep -E "${OLLAMA_MODEL_NAME}|${EMBED_MODEL}" || true

kill $OLLAMA_PID 2>/dev/null || true

echo "Done. Start Ollama with:"
echo "  OLLAMA_NUM_PARALLEL=4 ollama serve"
