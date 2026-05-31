# Aura RAG

A RAG (Retrieval-Augmented Generation) system that connects your AI assistant to the Kaiten knowledge base. Supports Claude Code, Cursor, VS Code / GitHub Copilot, JetBrains, and more.

## How it works

1. Documents and cards from Kaiten are fetched and embedded using Google AI or a local Ollama model
2. Embeddings are stored in Qdrant (vector database)
3. When you ask a question, it's classified by domain, embedded, and matched against the stored vectors
4. The AI assistant answers using the retrieved context

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/postusername/aura-rag.git
cd aura-rag
git submodule update --init

# 2. Configure credentials
cp .env.example .env
# Edit .env with your KAITEN_TOKEN, KAITEN_DOMAIN, and GOOGLE_API_KEY

# 3. Run setup (starts Docker, installs skills, detects your AI tools)
bash scripts/setup.sh

# 4. Sync the knowledge base (in your AI assistant)
# /rag-sync

# 5. Start asking questions
# /rag-query
```

## Requirements

- Docker + Docker Compose
- A Kaiten account with API token
- One of: Google AI Studio API key (free) **or** Ollama running locally

## Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `KAITEN_TOKEN` | Yes | Kaiten API token |
| `KAITEN_DOMAIN` | Yes | Kaiten workspace subdomain (e.g. `mycompany`) |
| `GOOGLE_API_KEY` | For Google | Free key from [Google AI Studio](https://aistudio.google.com/apikey) |
| `OLLAMA_MODEL` | For local | Model name (e.g. `nomic-embed-text`). If not set, Ollama container exits automatically |

## AI Tool Setup

### Claude Code (auto)
The `.mcp.json` in the project root is auto-loaded. Run:
```bash
bash scripts/setup.sh  # installs skills to ~/.claude/skills/
```
Skills available: `/rag-query`, `/rag-sync`, `/rag-manage`

### Cursor (auto)
The `.cursor/mcp.json` in the project root is auto-loaded when you open the project.

To add skill-like rules:
```bash
cp configs/cursor-rules/* .cursor/rules/
```

### VS Code / GitHub Copilot (auto)
The `.vscode/mcp.json` is auto-loaded at workspace open. All RAG tools appear in the Copilot tool picker.

To add copilot instructions:
```bash
cat configs/copilot-instructions.md >> .github/copilot-instructions.md
```

### Qwen Coder
Uses VS Code's MCP — see [configs/qwen.md](configs/qwen.md).

### OpenAI Codex CLI
See [configs/codex.md](configs/codex.md) for options.

### JetBrains IDEs
See [configs/jetbrains.md](configs/jetbrains.md) for manual setup instructions.

## Managing Knowledge Domains

Domains define what gets indexed and how queries are classified. Use the `rag-manage` skill or call MCP tools directly:

```
# In any AI assistant (Claude Code, Cursor, etc.):
rag_list_domains()
rag_add_domain("legal", "Legal", "Contracts, compliance, NDAs, GDPR", space_ids=[42])
rag_sync(domain="legal")
rag_query("What is our data retention policy?")
```

### Starter domain examples

| Domain | Description |
|--------|-------------|
| `business-analysis` | Business requirements, strategy, KPIs, roadmaps |
| `programming` | Code, APIs, architecture, bugs, software development |
| `hr` | Hiring, onboarding, performance, team culture |

`rag-server/config/settings.json` generates automatically on first start.

For cloud/non-interactive startup, initialize domains via `RAG_INIT_DOMAINS`.
Examples:
- `RAG_INIT_DOMAINS=engineering,product,hr`
- `RAG_INIT_DOMAINS=engineering:Engineering,hr:HR & People`

If `RAG_INIT_DOMAINS` is empty and startup is interactive, server asks for domains in console.
If startup is non-interactive and variable is empty, config is created with an empty `domains` list.

## Embedding Providers

| Provider | Model | Notes |
|----------|-------|-------|
| `google` | `gemini-embedding-2` | Default. Free, best quality, multilingual + code |
| `google` | `text-embedding-004` | Free alternative, 768 dims |
| `ollama` | `nomic-embed-text` | Fully local, good general purpose |
| `ollama` | `bge-m3` | Fully local, best multilingual + code |

Switch provider via `rag_set_embedding_provider` tool, then re-sync.

### Using Ollama (local embeddings)

```bash
# In .env:
OLLAMA_MODEL=nomic-embed-text

# Restart services:
docker compose restart

# Re-sync with new embeddings:
# rag_sync(force=true)
```

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `rag-server` | 8080 | Python MCP server (SSE at `/sse`) |
| `qdrant` | 6333 | Vector database |
| `ollama` | 11434 | Local embedding model (exits if `OLLAMA_MODEL` unset) |

```bash
docker compose up -d      # start all services
docker compose logs -f    # view logs
docker compose down       # stop all services
```

## Architecture

```
kaiten-mcp/           Git submodule — Kaiten API MCP server (Node.js, 61 tools)
rag-server/           Python RAG MCP server
  src/
    main.py           MCP server with SSE transport (port 8080)
    embedder.py       Google AI + Ollama embedding clients
    vector_store.py   Qdrant client wrapper
    indexer.py        Kaiten document/card fetcher + text chunker
    classifier.py     Domain classifier (cosine similarity)
    config_manager.py Domain + embedding config CRUD
  config/
    settings.json     Auto-generated on first start (gitignored)
skills/               Claude Code skill files
configs/              Setup guides for other AI tools
```

## MCP Tools Reference

| Tool | Description |
|------|-------------|
| `rag_query(query, domain?, max_results?)` | Search knowledge base |
| `rag_sync(domain?, force?)` | Fetch from Kaiten + re-embed |
| `rag_list_domains()` | List domains with stats |
| `rag_add_domain(id, label, description, ...)` | Add domain |
| `rag_update_domain(id, ...)` | Update domain |
| `rag_remove_domain(id)` | Remove domain + delete vectors |
| `rag_get_embedding_config()` | Show embedding settings |
| `rag_set_embedding_provider(provider, model)` | Switch provider |
| `rag_embedding_status()` | Test embedding connectivity |
