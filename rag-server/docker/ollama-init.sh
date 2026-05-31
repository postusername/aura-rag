#!/bin/sh
set -e

if [ -z "$OLLAMA_MODEL" ]; then
  echo "[ollama] OLLAMA_MODEL is not set — local embeddings disabled."
  echo "[ollama] To enable, add OLLAMA_MODEL=<model-name> to your .env file."
  echo "[ollama] Available models: nomic-embed-text, mxbai-embed-large, bge-m3"
  exit 0
fi

echo "[ollama] Starting Ollama server..."
ollama serve &
SERVER_PID=$!

echo "[ollama] Waiting for server to be ready..."
for i in $(seq 1 30); do
  if ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[ollama] Pulling model: $OLLAMA_MODEL"
if ! ollama pull "$OLLAMA_MODEL"; then
  echo "[ollama] ERROR: Failed to pull model '$OLLAMA_MODEL'. Check the model name and internet connection."
  kill $SERVER_PID 2>/dev/null || true
  exit 1
fi

echo "[ollama] Model '$OLLAMA_MODEL' ready. Ollama is running."
wait $SERVER_PID
