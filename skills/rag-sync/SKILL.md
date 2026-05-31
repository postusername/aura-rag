---
name: rag-sync
description: Sync the RAG knowledge base from Kaiten — fetches documents and cards, embeds them, stores vectors in Qdrant. Use when the user says "sync", "обновить базу знаний", "re-index", "update knowledge base", "fetch new docs", or when rag-query returns no results and the index may be stale.
---

# RAG Sync — Knowledge Base Indexer

Fetches content from Kaiten and rebuilds the semantic search index.

## Workflow

1. Ask: sync a specific domain or all? Show the list from `rag_list_domains()`.

2. Call `rag_sync(domain?, force?)`:
   - Omit `domain` to sync everything.
   - Set `force: true` if the user says "force", "full re-index", or the embedding provider was just changed.

3. Report back: how many chunks indexed, which domains updated.

4. If sync fails with an authentication error, verify that `KAITEN_TOKEN` and `KAITEN_DOMAIN` are set in the `.env` file and that Docker services are running (`docker compose up -d`).

## Notes

- First sync may take 1–3 minutes depending on document count.
- Subsequent syncs are incremental by default (existing vectors are kept unless `force=true`).
