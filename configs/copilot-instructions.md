# GitHub Copilot — Aura RAG Instructions

Add the following content to your `.github/copilot-instructions.md` file:

---

## Knowledge Base Access (Aura RAG)

This project has a RAG (Retrieval-Augmented Generation) system connected to Kaiten. Use the MCP tools below when answering questions about internal processes, architecture decisions, or company policies.

### When to use RAG tools

- User asks about internal company processes or documentation
- User asks "what do our docs say about X"
- User asks about team standards, policies, or conventions
- User mentions "knowledge base", "Kaiten", "internal docs"

### Available MCP tools

- `rag_query(query, domain?, max_results?)` — search the knowledge base
- `rag_sync(domain?, force?)` — refresh the index from Kaiten
- `rag_list_domains()` — list available knowledge domains
- `rag_add_domain(id, label, description, ...)` — add a new domain
- `rag_update_domain(id, ...)` — update a domain
- `rag_remove_domain(id)` — remove a domain
- `rag_get_embedding_config()` — show current embedding settings
- `rag_set_embedding_provider(provider, model)` — change embedding model
- `rag_embedding_status()` — check system health

### Usage pattern

When answering from the knowledge base:
1. Call `rag_query` with the user's question
2. Use the `context` field to answer
3. Cite sources by title with their relevance score
