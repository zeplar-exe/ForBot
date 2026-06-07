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

MODELS_TMP="/workspace/models_tmp"
OLLAMA_PID=""

cleanup() {
    echo "Cleaning up..."
    rm -rf "${MODELS_TMP}"
    [[ -n "${OLLAMA_PID}" ]] && kill "${OLLAMA_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Store Ollama blobs on the large volume, not ~/.ollama on root disk
export OLLAMA_MODELS="/workspace/ollama_models"
mkdir -p "${OLLAMA_MODELS}"

echo "=== ForBot Local LLM Setup ==="

# 1. Download GGUF to a temp dir (deleted after import)
echo "[1/4] Downloading ${MODEL_FILE} from ${MODEL_REPO}..."
mkdir -p "${MODELS_TMP}"
hf download "${MODEL_REPO}" "${MODEL_FILE}" --local-dir "${MODELS_TMP}"

# 2. Start Ollama if not already running
echo "[2/4] Ensuring Ollama is running..."
if ollama list &>/dev/null; then
    echo "      Ollama already running, using existing instance."
else
    ollama serve &>/tmp/ollama.log &
    OLLAMA_PID=$!
    echo "      Waiting for Ollama to be ready..."
    for i in $(seq 1 30); do
        ollama list &>/dev/null && break
        sleep 1
        [[ $i -eq 30 ]] && { echo "ERROR: Ollama failed to start. Check /tmp/ollama.log"; exit 1; }
    done
fi

echo "      Importing model as '${OLLAMA_MODEL_NAME}'..."
cat > /tmp/forbot_modelfile <<EOF
FROM ${MODELS_TMP}/${MODEL_FILE}
EOF
ollama create "${OLLAMA_MODEL_NAME}" -f /tmp/forbot_modelfile
rm /tmp/forbot_modelfile

# 3. Pull embedding model
echo "[3/4] Pulling embedding model '${EMBED_MODEL}'..."
ollama pull "${EMBED_MODEL}"

# 4. Verify
echo "[4/4] Verifying models are available..."
ollama list | grep -E "${OLLAMA_MODEL_NAME}|${EMBED_MODEL}" || true

echo ""
echo "Done. Start Ollama with:"
echo "  OLLAMA_NUM_PARALLEL=4 ollama serve"
