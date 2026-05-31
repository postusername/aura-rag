#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Aura RAG Setup ==="
echo ""

# 1. Check .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "[!] Created .env from .env.example — please fill in your credentials before continuing."
  echo "    Required: KAITEN_TOKEN, KAITEN_DOMAIN"
  echo "    Optional: GOOGLE_API_KEY (for Google embeddings), OLLAMA_MODEL (for local embeddings)"
  echo ""
fi

# 2. Check docker
if ! command -v docker &>/dev/null; then
  echo "[!] Docker not found. Install Docker: https://docs.docker.com/get-docker/"
  exit 1
fi

# 3. Start services
echo "[*] Starting Docker services..."
docker compose up -d
echo "[+] Services started. RAG server available at http://localhost:8080"
echo ""

# 4. Detect and configure AI tools
echo "[*] Detecting installed AI tools..."
echo ""

CONFIGURED=()

# Claude Code
if command -v claude &>/dev/null; then
  echo "[+] Claude Code detected — installing skills..."
  bash "$ROOT/skills/install.sh"
  CONFIGURED+=("Claude Code (skills installed + .mcp.json auto-loaded)")
else
  echo "[ ] Claude Code not found (install from https://claude.ai/code)"
fi

# Cursor
if command -v cursor &>/dev/null || [ -d "$HOME/.cursor" ]; then
  echo "[+] Cursor detected — .cursor/mcp.json is already in the project root (auto-loaded)."
  echo "    Copy cursor rules if needed:"
  echo "    cp -r configs/cursor-rules/* .cursor/rules/"
  CONFIGURED+=("Cursor (.cursor/mcp.json auto-loaded)")
else
  echo "[ ] Cursor not found"
fi

# VS Code
if command -v code &>/dev/null; then
  echo "[+] VS Code detected — .vscode/mcp.json is already in the project root (auto-loaded)."
  CONFIGURED+=("VS Code / GitHub Copilot (.vscode/mcp.json auto-loaded)")
else
  echo "[ ] VS Code not found"
fi

# Codex CLI
if command -v codex &>/dev/null; then
  echo "[*] OpenAI Codex CLI detected — see configs/codex.md for setup instructions."
  CONFIGURED+=("Codex CLI (manual setup required — see configs/codex.md)")
fi

echo ""
echo "=== Setup Complete ==="
echo ""
if [ ${#CONFIGURED[@]} -gt 0 ]; then
  echo "Configured tools:"
  for t in "${CONFIGURED[@]}"; do
    echo "  ✓ $t"
  done
else
  echo "No AI tools auto-detected. See configs/ directory for manual setup."
fi
echo ""
echo "Next steps:"
echo "  1. Edit .env with your credentials (if not done)"
echo "  2. docker compose restart  (if .env was just edited)"
echo "  3. Run /rag-sync in your AI assistant to index the knowledge base"
echo "  4. Run /rag-query to start asking questions"
