---
name: rag-manage
description: Manage the RAG knowledge base configuration — add, update, or remove domains, change the embedding model or provider, check system status. Use when the user says "add domain", "добавь область", "remove domain", "update domain", "change embedding", "поменяй модель", "switch to ollama", "check rag status", or asks to configure the knowledge base system.
---

# RAG Manage — Configuration & Administration

## Dispatch by user intent

### Add a new domain
1. Ask the user for: domain ID (lowercase-hyphen), label, description (natural language), and optionally Kaiten space IDs / document group IDs / card board IDs.
2. Call `rag_add_domain(id, label, description, space_ids?, document_group_ids?, card_board_ids?)`.
3. Tell the user to run `/rag-sync` to index the new domain.

### Update a domain
1. Call `rag_update_domain(id, <fields to change>)`.
2. Remind user to re-sync the domain.

### Remove a domain
1. Confirm with the user — this deletes the domain's entire vector index.
2. Call `rag_remove_domain(id)`.

### Change embedding provider / model
1. Show current config with `rag_get_embedding_config()`.
2. Call `rag_set_embedding_provider(provider, model, dimensions?)`.
   - provider: `"google"` or `"ollama"`
   - For Google models: `"gemini-embedding-2"` (best, free), `"text-embedding-004"`
   - For Ollama models: `"nomic-embed-text"`, `"mxbai-embed-large"`, `"bge-m3"`
3. Warn the user that all existing embeddings are now stale — they must run `/rag-sync` with force=true.
4. For Ollama: remind them to set `OLLAMA_MODEL=<model>` in `.env` and restart Docker.

### Check system status
1. Call `rag_embedding_status()` to verify provider connectivity.
2. Call `rag_list_domains()` to show all domains and their sync state.
