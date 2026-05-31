# Qwen Coder — Aura RAG Setup

Qwen Coder (VS Code extension) uses VS Code's MCP system. The `.vscode/mcp.json` in this
repo auto-registers the RAG server when you open this project in VS Code.

## Setup

1. Install the Qwen Coder VS Code extension.
2. Make sure the RAG Docker services are running:
   ```bash
   docker compose up -d
   ```
3. Open this project folder in VS Code — `.vscode/mcp.json` is auto-loaded.
4. In the Qwen Coder chat, the RAG tools (`rag_query`, `rag_sync`, etc.) will appear
   in the tool picker.

## Usage

Ask Qwen Coder questions about internal company knowledge:
- "What is our API authentication standard?"
- "How do we handle onboarding new employees?"
- "What architecture decisions were made for the payment system?"

Qwen will call `rag_query` automatically and answer using retrieved context.

## Configuring domains

Use the `rag_manage` tools directly in Qwen Coder chat:
- "Add a domain for Legal documentation covering contracts and compliance"
- "Show me the current embedding configuration"
- "Switch to Ollama with the bge-m3 model"
