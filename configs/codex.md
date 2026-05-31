# OpenAI Codex CLI — Aura RAG Setup

The OpenAI Codex CLI does not currently support MCP servers natively. However, you can provide the RAG context through the system prompt.

## Option 1: Direct HTTP API (recommended)

The RAG server exposes its tools via the MCP SSE endpoint at `http://localhost:8080/sse`.
You can query it directly using the MCP protocol, or integrate it into your Codex workflow
by querying the RAG API from a script.

## Option 2: Manual context via system prompt

Add to your Codex system prompt or `~/.codex/config.toml`:

```toml
[agent]
model = "codex-mini-latest"

[system]
instructions = """
This project has an internal knowledge base accessible via a RAG service at http://localhost:8080.
When the user asks about internal processes, documentation, or company-specific information,
fetch context from the RAG service before answering.

RAG service tools (available via MCP at http://localhost:8080/sse):
- rag_query: search the knowledge base
- rag_list_domains: list available domains
- rag_sync: refresh the index
"""
```

## Option 3: Use VS Code + GitHub Copilot

The `.vscode/mcp.json` in this repo auto-registers the RAG MCP server in VS Code.
Open this project in VS Code and use GitHub Copilot Chat — it will have access to all RAG tools.
